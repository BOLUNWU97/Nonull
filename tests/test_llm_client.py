"""Tests for core.llm_client (P15: LLM client integration)."""
import os
import pytest
from unittest.mock import MagicMock, patch

from core.llm_client import (
    LLMClient, LLMConfig, LLMMessage, LLMResponse, get_default_client,
)


def test_llm_config_from_env_defaults():
    with patch.dict(os.environ, {}, clear=True), patch("os.path.exists", return_value=False):
        cfg = LLMConfig.from_env()
        # No api_key set
        assert cfg.api_key == ""
        assert cfg.provider == "openai"
        assert cfg.base_url == "https://api.openai.com/v1"
        assert cfg.model == "gpt-4o"


def test_llm_config_provider_defaults():
    with patch.dict(os.environ, {
        "NONULL_LLM_API_KEY": "test-key",
        "NONULL_LLM_PROVIDER": "deepseek",
    }, clear=True), patch("os.path.exists", return_value=False):
        cfg = LLMConfig.from_env()
        assert cfg.provider == "deepseek"
        assert cfg.base_url == "https://api.deepseek.com/v1"


def test_llm_config_custom_base_url():
    with patch.dict(os.environ, {
        "NONULL_LLM_API_KEY": "test-key",
        "NONULL_LLM_PROVIDER": "custom",
        "NONULL_LLM_API_BASE": "https://my.api.com/v1",
    }, clear=False):
        cfg = LLMConfig.from_env()
        assert cfg.base_url == "https://my.api.com/v1"


def test_llm_message_to_dict():
    m = LLMMessage(role="user", content="hello")
    assert m.to_dict() == {"role": "user", "content": "hello"}


def test_llm_response_token_counts():
    r = LLMResponse(
        content="hi",
        model="gpt-4o",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        raw={},
    )
    assert r.prompt_tokens == 10
    assert r.completion_tokens == 5
    assert r.total_tokens == 15


def test_llm_client_chat_success():
    """Mock httpx and verify the client parses a successful response."""
    fake_response = {
        "id": "chatcmpl-xxx",
        "model": "gpt-4o",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": "Hello!"},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }
    mock_response = MagicMock()
    mock_response.json.return_value = fake_response
    mock_response.raise_for_status.return_value = None

    cfg = LLMConfig(api_key="test-key", model="gpt-4o")
    client = LLMClient(cfg)

    # Mock the persistent client rather than the context manager pattern
    fake_http = MagicMock()
    fake_http.post.return_value = mock_response
    client._client = fake_http
    resp = client.simple_chat("Hi")

    assert resp == "Hello!"


def test_llm_client_chat_retry_on_5xx():
    """5xx errors should trigger retry; ultimate success returns the result."""
    fake_response = {
        "model": "gpt-4o",
        "choices": [{"message": {"role": "assistant", "content": "OK"}}],
        "usage": {},
    }
    mock_response = MagicMock()
    mock_response.json.return_value = fake_response
    mock_response.raise_for_status.return_value = None

    cfg = LLMConfig(api_key="test-key", max_retries=2)
    client = LLMClient(cfg)

    call_count = [0]
    def fake_post(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception("500 server error")
        return mock_response

    fake_http = MagicMock()
    fake_http.post.side_effect = fake_post
    client._client = fake_http
    resp = client.simple_chat("Hi")

    assert resp == "OK"
    assert call_count[0] == 2  # retried once


def test_get_default_client_singleton():
    """get_default_client should return the same instance on repeated calls."""
    c1 = get_default_client()
    c2 = get_default_client()
    assert c1 is c2


@pytest.mark.skipif(
    not os.environ.get("NONULL_LLM_API_KEY"),
    reason="NONULL_LLM_API_KEY not set; skipping real LLM integration test"
)
def test_real_llm_call():
    """If NONULL_LLM_API_KEY is set, make a real call and verify the response shape."""
    from core.llm_client import LLMClient, LLMConfig, LLMMessage
    cfg = LLMConfig.from_env()
    client = LLMClient(cfg)
    resp = client.simple_chat("Say 'hello' in one word.", max_tokens=10)
    assert len(resp) > 0
    assert "hello" in resp.lower() or "hi" in resp.lower()
