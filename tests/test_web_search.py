"""
网页搜索后端测试 / Tests for the web search backend.

不依赖真实网络 (CI 友好): 测解析逻辑 (用 mock HTML/JSON) + 后端选择逻辑 +
错误处理。真实网络调用放在 @pytest.mark.network 的可选测试 (默认不跑)。
"""
import os

import pytest

from skills.core.web_search_backend import (
    web_search, search_duckduckgo, SearchResult, SearchResponse,
    _strip_tags, _ddg_unwrap, _is_ad_or_internal,
)


# ── 辅助函数 ─────────────────────────────────────────────────────

class TestHelpers:
    def test_strip_tags(self):
        assert _strip_tags("<b>hello</b> &amp; world") == "hello & world"

    def test_ddg_unwrap_redirect(self):
        """DDG 跳转包装 /l/?uddg= → 解出真实 URL。"""
        wrapped = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage"
        assert _ddg_unwrap(wrapped) == "https://example.com/page"

    def test_ddg_unwrap_direct(self):
        """直接 URL 不变。"""
        assert _ddg_unwrap("https://example.com") == "https://example.com"

    def test_ad_filter(self):
        """广告/内部链接被识别。"""
        assert _is_ad_or_internal("https://duckduckgo.com/y.js?ad_domain=x.com")
        assert _is_ad_or_internal("https://example.com/?ad_domain=foo")
        assert _is_ad_or_internal("https://duckduckgo.com/duckduckgo-help-pages/x")
        assert not _is_ad_or_internal("https://www.python.org/")
        assert not _is_ad_or_internal("https://en.wikipedia.org/wiki/Python")


# ── 后端选择逻辑 ─────────────────────────────────────────────────

class TestBackendSelection:
    def test_default_is_duckduckgo(self, monkeypatch):
        monkeypatch.delenv("NONULL_SEARCH_ENGINE", raising=False)
        monkeypatch.delenv("NONULL_SEARCH_API_KEY", raising=False)
        # 用 mock 拦截真实网络
        called = {}
        import skills.core.web_search_backend as be
        monkeypatch.setattr(be, "search_duckduckgo",
                            lambda q, m, t: SearchResponse(query=q, backend="duckduckgo"))
        resp = web_search("test query")
        assert resp.backend == "duckduckgo"

    def test_brave_without_key_falls_back(self, monkeypatch):
        """指定 brave 但无 key → 回退 duckduckgo。"""
        monkeypatch.setenv("NONULL_SEARCH_ENGINE", "brave")
        monkeypatch.delenv("NONULL_SEARCH_API_KEY", raising=False)
        import skills.core.web_search_backend as be
        monkeypatch.setattr(be, "search_duckduckgo",
                            lambda q, m, t: SearchResponse(query=q, backend="duckduckgo"))
        resp = web_search("test")
        assert resp.backend == "duckduckgo"  # 回退

    def test_brave_with_key_uses_brave(self, monkeypatch):
        monkeypatch.setenv("NONULL_SEARCH_ENGINE", "brave")
        monkeypatch.setenv("NONULL_SEARCH_API_KEY", "fake-key")
        import skills.core.web_search_backend as be
        monkeypatch.setattr(be, "search_brave",
                            lambda q, m, t, k: SearchResponse(query=q, backend="brave"))
        resp = web_search("test")
        assert resp.backend == "brave"

    def test_explicit_backend_param_wins(self, monkeypatch):
        monkeypatch.setenv("NONULL_SEARCH_ENGINE", "brave")
        import skills.core.web_search_backend as be
        monkeypatch.setattr(be, "search_duckduckgo",
                            lambda q, m, t: SearchResponse(query=q, backend="duckduckgo"))
        resp = web_search("test", backend="duckduckgo")
        assert resp.backend == "duckduckgo"


# ── DDG HTML 解析 (mock 网络) ────────────────────────────────────

_MOCK_DDG_HTML = """
<html><body>
<div class="result">
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fpython.org">Python.org</a>
  <a class="result__snippet">The official home of Python programming.</a>
</div>
<div class="result">
  <a class="result__a" href="https://docs.python.org">Python Docs</a>
  <a class="result__snippet">Documentation for Python.</a>
</div>
</body></html>
"""


class TestDDGParsing:
    def test_parse_results(self, monkeypatch):
        """用 mock HTML 测解析: 提取 title/url/snippet, 解包跳转链接。"""
        import skills.core.web_search_backend as be

        class _MockResp:
            text = _MOCK_DDG_HTML
            def raise_for_status(self): pass

        class _MockClient:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def post(self, url, data=None): return _MockResp()

        monkeypatch.setattr(be.httpx, "Client", _MockClient)
        resp = search_duckduckgo("python", max_results=8, timeout=10.0)
        assert resp.error is None
        assert len(resp.results) == 2
        assert resp.results[0].title == "Python.org"
        assert resp.results[0].url == "https://python.org"  # 解包了
        assert "official home" in resp.results[0].snippet
        assert resp.results[1].url == "https://docs.python.org"

    def test_max_results_limit(self, monkeypatch):
        import skills.core.web_search_backend as be

        class _MockResp:
            text = _MOCK_DDG_HTML
            def raise_for_status(self): pass

        class _MockClient:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def post(self, url, data=None): return _MockResp()

        monkeypatch.setattr(be.httpx, "Client", _MockClient)
        resp = search_duckduckgo("python", max_results=1, timeout=10.0)
        assert len(resp.results) == 1

    def test_network_error_structured(self, monkeypatch):
        """网络错误 → 结构化 error, 不抛异常, 不返回假数据。"""
        import skills.core.web_search_backend as be

        class _MockClient:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def post(self, url, data=None): raise be.httpx.ConnectError("no network")

        monkeypatch.setattr(be.httpx, "Client", _MockClient)
        resp = search_duckduckgo("python", max_results=8, timeout=10.0)
        assert resp.error is not None
        assert "ConnectError" in resp.error
        assert resp.results == []


# ── Skill 集成 ───────────────────────────────────────────────────

class TestWebSearchSkill:
    def test_skill_no_longer_demo(self):
        from skills.core.web_skills import WebSearchSkill
        meta = WebSearchSkill().metadata
        assert "DEMO" not in meta.description
        assert "PLACEHOLDER" not in meta.description
        assert meta.version == "0.2.0"

    def test_skill_execute_with_mock(self, monkeypatch):
        from skills.core.web_skills import WebSearchSkill
        import skills.core.web_search_backend as be
        monkeypatch.setattr(be, "search_duckduckgo",
                            lambda q, m, t: SearchResponse(
                                query=q, backend="duckduckgo",
                                results=[SearchResult("T", "https://x.com", "snip")]))
        monkeypatch.delenv("NONULL_SEARCH_ENGINE", raising=False)
        skill = WebSearchSkill()
        skill.activate()
        result = skill.execute({"query": "test"})
        assert result.success
        assert result.data["result_count"] == 1
        assert result.data["results"][0]["url"] == "https://x.com"


# ── 真实网络 (可选, 默认不跑) ────────────────────────────────────

@pytest.mark.skipif(
    os.environ.get("NONULL_RUN_NETWORK_TESTS") != "1",
    reason="set NONULL_RUN_NETWORK_TESTS=1 to run real network search",
)
class TestRealNetwork:
    def test_real_duckduckgo_search(self):
        resp = web_search("python programming language", max_results=5)
        assert resp.error is None
        assert len(resp.results) > 0
        assert all(r.url.startswith("http") for r in resp.results)
