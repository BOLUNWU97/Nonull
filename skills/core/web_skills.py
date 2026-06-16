"""
Web / Network skills / 网络相关技能
"""
from __future__ import annotations
import re
from typing import Any, Dict, List
import httpx
from skills.base import BaseSkill, SkillMetadata, SkillResult, SkillCategory


class WebFetchSkill(BaseSkill):
    """Fetch a URL and return its text content."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="web_fetch",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Fetch a URL and return the text content. Strips HTML tags.",
            tags=["web", "http", "url", "fetch"],
            author="Nonull Team",
            safety_level=2,
        )

    def _validate_input(self, context: Dict[str, Any]) -> None:
        url = context.get("url", "")
        if not url or not isinstance(url, str):
            raise ValueError("'url' must be a non-empty string")
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"'url' must start with http:// or https://, got: {url!r}")

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        url = context["url"]
        timeout = context.get("timeout", 30.0)
        max_size = context.get("max_size_mb", 5) * 1024 * 1024

        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content = resp.text

        if len(content) > max_size:
            content = content[:max_size] + "\n\n... [truncated]"

        # Naive HTML strip
        text = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()

        return {
            "url": url,
            "status_code": resp.status_code,
            "content_type": resp.headers.get("content-type", ""),
            "raw_size_bytes": len(content),
            "text": text,
            "text_length": len(text),
        }


class WebSearchSkill(BaseSkill):
    """Search the web. Real implementation with multiple backends.

    Backends (auto-selected):
      - duckduckgo (default, no API key — parses the DDG HTML endpoint)
      - brave (set NONULL_SEARCH_ENGINE=brave + NONULL_SEARCH_API_KEY)
      - serpapi (set NONULL_SEARCH_ENGINE=serpapi + NONULL_SEARCH_API_KEY)
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="web_search",
            version="0.2.0",
            category=SkillCategory.GENERAL,
            description="Search the web (DuckDuckGo by default, no key needed; "
                        "Brave/SerpAPI with a key). Returns title/url/snippet results.",
            tags=["web", "search"],
            author="Nonull Team",
            safety_level=2,
        )

    def _validate_input(self, context: Dict[str, Any]) -> None:
        query = context.get("query", "")
        if not query:
            raise ValueError("'query' must be a non-empty string")

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        from skills.core.web_search_backend import web_search
        query = context["query"]
        max_results = int(context.get("max_results", 8))
        timeout = float(context.get("timeout", 15.0))
        backend = context.get("backend")  # 可选: 显式指定后端
        resp = web_search(query, max_results=max_results, timeout=timeout, backend=backend)
        return resp.to_dict()


class LinkExtractorSkill(BaseSkill):
    """Extract all links from HTML or text content."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="link_extractor",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Extract all links (href) from HTML or Markdown text.",
            tags=["web", "html", "links"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context: Dict[str, Any]) -> None:
        if not context.get("content"):
            raise ValueError("'content' must be a non-empty string")

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        content = context["content"]
        # Match href="..." or <a href="...">
        pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
        links = pattern.findall(content)
        # Dedupe while preserving order
        seen = set()
        unique = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique.append(link)
        return {
            "link_count": len(unique),
            "links": unique,
        }
