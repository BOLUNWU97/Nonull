"""
多后端网页搜索引擎 / Multi-backend web search engine.

真实可运行的网页搜索, 非占位。支持三种后端, 按可用性自动选择:

  1. **duckduckgo** (默认, 免 key): 解析 DuckDuckGo HTML 端点
     (https://html.duckduckgo.com/html/), 无需 API key, 开箱即用。
  2. **brave** (需 key): Brave Search API, 设 NONULL_SEARCH_API_KEY +
     NONULL_SEARCH_ENGINE=brave。质量更高、有配额。
  3. **serpapi** (需 key): SerpAPI (Google 结果), 设 NONULL_SEARCH_API_KEY +
     NONULL_SEARCH_ENGINE=serpapi。

返回统一的 SearchResult 列表 (title / url / snippet)。所有网络调用真实发出,
失败时返回结构化错误 (不抛异常, 不返回假数据)。

@module: skills.core.web_search_backend
"""
from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

import httpx

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}


@dataclass
class SearchResponse:
    query: str
    backend: str
    results: List[SearchResult] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "backend": self.backend,
            "result_count": len(self.results),
            "results": [r.to_dict() for r in self.results],
            "error": self.error,
        }


# ── DuckDuckGo HTML 后端 (免 key) ────────────────────────────────

_DDG_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_DDG_SNIPPET_RE = re.compile(
    r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)


def _strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _ddg_unwrap(href: str) -> str:
    """DDG 的链接常是跳转包装 /l/?uddg=<encoded> —— 解出真实 URL。"""
    if href.startswith("//"):
        href = "https:" + href
    try:
        parsed = urlparse(href)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            q = parse_qs(parsed.query)
            if "uddg" in q:
                return unquote(q["uddg"][0])
    except Exception:
        pass
    return href


def search_duckduckgo(query: str, max_results: int, timeout: float) -> SearchResponse:
    """DuckDuckGo 搜索 (免 key)。先试 lite 端点 (更稳, 少反爬), 再退 html 端点。

    DDG 的 html.duckduckgo.com 近期改为返回 202 token-challenge 页 (vqd token),
    单次 POST 拿不到结果。lite.duckduckgo.com/lite/ 是更轻量、对脚本更友好的端点,
    优先用它; 失败再退回 html 端点解析。
    """
    resp = SearchResponse(query=query, backend="duckduckgo")
    headers = {"User-Agent": _UA, "Accept": "text/html",
               "Content-Type": "application/x-www-form-urlencoded"}
    last_err = None
    for url in ("https://lite.duckduckgo.com/lite/", "https://html.duckduckgo.com/html/"):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
                r = client.post(url, data={"q": query})
                r.raise_for_status()
                body = r.text
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            continue

        if "lite" in url:
            results = _parse_ddg_lite(body, max_results)
        else:
            results = _parse_ddg_html(body, max_results)
        if results:
            resp.results = results
            return resp
        last_err = "no results parsed"

    resp.error = last_err or "no results"
    return resp


def _parse_ddg_html(body: str, max_results: int) -> List[SearchResult]:
    """解析 html.duckduckgo.com 的结果。"""
    out: List[SearchResult] = []
    links = _DDG_RESULT_RE.findall(body)
    snippets = _DDG_SNIPPET_RE.findall(body)
    for i, (href, title_html) in enumerate(links[:max_results]):
        snippet = _strip_tags(snippets[i]) if i < len(snippets) else ""
        out.append(SearchResult(title=_strip_tags(title_html),
                                url=_ddg_unwrap(href), snippet=snippet))
    return out


# lite 端点: 结果是 <a rel="nofollow" href="..." class='result-link'>标题</a>
# 紧跟一个 class='result-snippet' 的 td。
# 注意: lite 端点用单引号包裹 class 属性 (class='result-link'), 且 href 在 class 之前,
# 所以正则需对引号风格 (单/双) 与属性顺序都宽容。
_DDG_LITE_LINK_RE = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*class=["\']result-link["\'][^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_DDG_LITE_SNIPPET_RE = re.compile(
    r'<td[^>]*class=["\']result-snippet["\'][^>]*>(.*?)</td>',
    re.DOTALL | re.IGNORECASE,
)


def _is_ad_or_internal(url: str) -> bool:
    """判断是否为 DDG 广告/内部链接 (应过滤)。"""
    low = url.lower()
    return (
        "duckduckgo.com/y.js" in low          # 赞助广告跳转
        or "ad_domain=" in low                 # 广告域参数
        or "/duckduckgo-help-pages/" in low    # DDG 帮助页
        or low.startswith("https://duckduckgo.com/?")  # 内部搜索页
    )


def _parse_ddg_lite(body: str, max_results: int) -> List[SearchResult]:
    """解析 lite.duckduckgo.com 的结果 (过滤广告/内部链接)。"""
    out: List[SearchResult] = []
    links = _DDG_LITE_LINK_RE.findall(body)
    snippets = _DDG_LITE_SNIPPET_RE.findall(body)
    for i, (href, title_html) in enumerate(links):
        real_url = _ddg_unwrap(href)
        if _is_ad_or_internal(real_url):
            continue  # 跳过广告, 不占 max_results 名额
        snippet = _strip_tags(snippets[i]) if i < len(snippets) else ""
        out.append(SearchResult(title=_strip_tags(title_html),
                                url=real_url, snippet=snippet))
        if len(out) >= max_results:
            break
    return out


# ── Brave Search API 后端 (需 key) ───────────────────────────────

def search_brave(query: str, max_results: int, timeout: float, api_key: str) -> SearchResponse:
    resp = SearchResponse(query=query, backend="brave")
    url = "https://api.search.brave.com/res/v1/web/search"
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(url, params={"q": query, "count": max_results},
                           headers={"X-Subscription-Token": api_key,
                                    "Accept": "application/json"})
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        resp.error = f"{type(e).__name__}: {e}"
        return resp
    for item in (data.get("web", {}).get("results", []) or [])[:max_results]:
        resp.results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=_strip_tags(item.get("description", "")),
        ))
    return resp


# ── SerpAPI 后端 (需 key) ────────────────────────────────────────

def search_serpapi(query: str, max_results: int, timeout: float, api_key: str) -> SearchResponse:
    resp = SearchResponse(query=query, backend="serpapi")
    url = "https://serpapi.com/search"
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(url, params={"q": query, "api_key": api_key,
                                        "num": max_results, "engine": "google"})
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        resp.error = f"{type(e).__name__}: {e}"
        return resp
    for item in (data.get("organic_results", []) or [])[:max_results]:
        resp.results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("link", ""),
            snippet=_strip_tags(item.get("snippet", "")),
        ))
    return resp


# ── 统一入口 ─────────────────────────────────────────────────────

def web_search(query: str, max_results: int = 8, timeout: float = 15.0,
               backend: Optional[str] = None) -> SearchResponse:
    """执行网页搜索, 自动选后端 / Run a web search, auto-selecting the backend.

    后端选择优先级:
      - 显式 backend 参数 > NONULL_SEARCH_ENGINE 环境变量 > 默认 duckduckgo
      - brave/serpapi 需 NONULL_SEARCH_API_KEY; 缺 key 时自动回退 duckduckgo
    """
    engine = (backend or os.environ.get("NONULL_SEARCH_ENGINE", "duckduckgo")).lower()
    api_key = os.environ.get("NONULL_SEARCH_API_KEY", "")

    if engine == "brave":
        if api_key:
            return search_brave(query, max_results, timeout, api_key)
        engine = "duckduckgo"  # 缺 key 回退
    elif engine == "serpapi":
        if api_key:
            return search_serpapi(query, max_results, timeout, api_key)
        engine = "duckduckgo"

    return search_duckduckgo(query, max_results, timeout)
