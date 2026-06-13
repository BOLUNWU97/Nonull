"""Tests for LLM client hardening: error classification, rate-limit handling,
model fallback, and streaming-with-tools.

LLM 客户端加固测试：错误分类、限流处理、模型回退、流式工具调用。
"""
import pytest
from unittest.mock import MagicMock, patch

from core.llm_client import (
    LLMClient, LLMConfig, LLMMessage,
    LLMError, LLMAuthError, LLMRateLimitError, LLMServerError, LLMRequestError,
)


def _mock_resp(status_code, body=None, headers=None, text=""):
    r = MagicMock()
    r.status_code = status_code
    r.headers = headers or {}
    r.json.return_value = body if body is not None else {}
    r.text = text
    return r


# -- Error classification ----------------------------------------------------

class TestStatusClassification:
    def test_2xx_returns_none(self):
        assert LLMClient._classify_status(_mock_resp(200)) is None

    def test_401_is_auth_error(self):
        err = LLMClient._classify_status(_mock_resp(401, {"error": {"message": "bad key"}}))
        assert isinstance(err, LLMAuthError)
        assert "bad key" in str(err)

    def test_403_is_auth_error(self):
        assert isinstance(LLMClient._classify_status(_mock_resp(403)), LLMAuthError)

    def test_429_is_rate_limit(self):
        err = LLMClient._classify_status(_mock_resp(429, headers={"retry-after": "5"}))
        assert isinstance(err, LLMRateLimitError)
        assert err.retry_after == 5.0

    def test_429_without_retry_after(self):
        err = LLMClient._classify_status(_mock_resp(429))
        assert isinstance(err, LLMRateLimitError)
        assert err.retry_after is None

    def test_500_is_server_error(self):
        assert isinstance(LLMClient._classify_status(_mock_resp(503)), LLMServerError)

    def test_400_is_request_error(self):
        assert isinstance(LLMClient._classify_status(_mock_resp(400)), LLMRequestError)

    def test_404_is_request_error(self):
        assert isinstance(LLMClient._classify_status(_mock_resp(404)), LLMRequestError)


# -- Retry-After parsing -----------------------------------------------------

class TestRetryAfter:
    def test_honors_retry_after_header(self):
        delay = LLMClient._parse_retry_after(_mock_resp(429, headers={"retry-after": "12"}), attempt=0)
        assert delay == 12.0

    def test_caps_retry_after_at_60(self):
        delay = LLMClient._parse_retry_after(_mock_resp(429, headers={"retry-after": "999"}), attempt=0)
        assert delay == 60.0

    def test_falls_back_to_exponential(self):
        # No retry-after header → exponential backoff 2**attempt
        delay = LLMClient._parse_retry_after(_mock_resp(429), attempt=3)
        assert delay == 8  # 2**3

    def test_invalid_retry_after_uses_exponential(self):
        delay = LLMClient._parse_retry_after(_mock_resp(429, headers={"retry-after": "soon"}), attempt=1)
        assert delay == 2  # 2**1


# -- Auth errors fail fast (no retry, no fallback) ---------------------------

class TestAuthFailFast:
    def test_auth_error_not_retried(self):
        cfg = LLMConfig(api_key="bad", max_retries=3, fallback_models=["backup"])
        client = LLMClient(cfg)
        fake_http = MagicMock()
        fake_http.post.return_value = _mock_resp(401, {"error": {"message": "invalid key"}})
        client._client = fake_http

        with pytest.raises(LLMAuthError):
            client.chat([LLMMessage.user("hi")])
        # Only one call: no retry, no fallback
        assert fake_http.post.call_count == 1


# -- Rate limit retry --------------------------------------------------------

class TestRateLimitRetry:
    def test_429_then_success(self):
        ok = _mock_resp(200, {
            "model": "m", "choices": [{"message": {"content": "done"}}], "usage": {},
        })
        cfg = LLMConfig(api_key="k", max_retries=2)
        client = LLMClient(cfg)

        calls = [0]
        def post(*a, **k):
            calls[0] += 1
            return _mock_resp(429, headers={"retry-after": "1"}) if calls[0] == 1 else ok
        fake_http = MagicMock()
        fake_http.post.side_effect = post
        client._client = fake_http

        with patch("time.sleep"):
            resp = client.chat([LLMMessage.user("hi")])
        assert resp.content == "done"
        assert calls[0] == 2


# -- Model fallback ----------------------------------------------------------

class TestModelFallback:
    def test_falls_back_to_second_model(self):
        ok = _mock_resp(200, {
            "model": "backup", "choices": [{"message": {"content": "fallback worked"}}], "usage": {},
        })
        # Primary always 500 (exhausts retries), fallback returns 200
        cfg = LLMConfig(api_key="k", model="primary", max_retries=1, fallback_models=["backup"])
        client = LLMClient(cfg)

        seen_models = []
        def post(url, json=None, headers=None):
            seen_models.append(json["model"])
            return ok if json["model"] == "backup" else _mock_resp(503)
        fake_http = MagicMock()
        fake_http.post.side_effect = post
        client._client = fake_http

        with patch("time.sleep"):
            resp = client.chat([LLMMessage.user("hi")])
        assert resp.content == "fallback worked"
        assert "primary" in seen_models
        assert "backup" in seen_models

    def test_all_models_fail_raises_llm_error(self):
        cfg = LLMConfig(api_key="k", model="primary", max_retries=0, fallback_models=["backup"])
        client = LLMClient(cfg)
        fake_http = MagicMock()
        fake_http.post.return_value = _mock_resp(503)
        client._client = fake_http

        with patch("time.sleep"):
            with pytest.raises(LLMError):
                client.chat([LLMMessage.user("hi")])

    def test_request_error_triggers_fallback(self):
        # 400 on primary should still try fallback (different model may accept)
        ok = _mock_resp(200, {
            "model": "backup", "choices": [{"message": {"content": "ok"}}], "usage": {},
        })
        cfg = LLMConfig(api_key="k", model="primary", max_retries=0, fallback_models=["backup"])
        client = LLMClient(cfg)

        def post(url, json=None, headers=None):
            return ok if json["model"] == "backup" else _mock_resp(400)
        fake_http = MagicMock()
        fake_http.post.side_effect = post
        client._client = fake_http

        resp = client.chat([LLMMessage.user("hi")])
        assert resp.content == "ok"


# -- Config: fallback models from env ----------------------------------------

class TestFallbackConfig:
    def test_fallback_models_parsed_from_env(self):
        import os
        with patch.dict(os.environ, {
            "NONULL_LLM_API_KEY": "k",
            "NONULL_LLM_FALLBACK_MODELS": "gpt-4o-mini, deepseek-chat ,",
        }, clear=True), patch("os.path.exists", return_value=False):
            cfg = LLMConfig.from_env()
            assert cfg.fallback_models == ["gpt-4o-mini", "deepseek-chat"]

    def test_no_fallback_models_default_empty(self):
        import os
        with patch.dict(os.environ, {"NONULL_LLM_API_KEY": "k"}, clear=True), \
             patch("os.path.exists", return_value=False):
            cfg = LLMConfig.from_env()
            assert cfg.fallback_models == []


# -- Streaming tool-call accumulation ----------------------------------------

class TestStreamingTools:
    @pytest.mark.asyncio
    async def test_chat_stream_full_assembles_tool_calls(self):
        # Simulate SSE chunks: text + split tool_call arguments
        sse_lines = [
            'data: {"model":"m","choices":[{"delta":{"content":"Let me "}}]}',
            'data: {"model":"m","choices":[{"delta":{"content":"check."}}]}',
            'data: {"model":"m","choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"search","arguments":"{\\"q\\":"}}]}}]}',
            'data: {"model":"m","choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"cat\\"}"}}]}}]}',
            'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
            'data: [DONE]',
        ]

        class FakeStream:
            status_code = 200
            async def aiter_lines(self):
                for ln in sse_lines:
                    yield ln
            async def aread(self):
                return b""

        class FakeStreamCtx:
            async def __aenter__(self): return FakeStream()
            async def __aexit__(self, *a): return False

        class FakeClient:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            def stream(self, *a, **k): return FakeStreamCtx()

        cfg = LLMConfig(api_key="k")
        client = LLMClient(cfg)

        chunks = []
        with patch("httpx.AsyncClient", FakeClient):
            resp = await client.chat_stream_full(
                [LLMMessage.user("find cats")],
                on_chunk=chunks.append,
            )

        assert resp.content == "Let me check."
        assert chunks == ["Let me ", "check."]
        assert resp.finish_reason == "tool_calls"
        assert len(resp.tool_calls) == 1
        tc = resp.tool_calls[0]
        assert tc["id"] == "call_1"
        assert tc["function"]["name"] == "search"
        assert tc["function"]["arguments"] == '{"q":"cat"}'
