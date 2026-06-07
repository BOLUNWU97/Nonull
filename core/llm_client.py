"""
LLM Client — async + sync wrappers over the OpenAI-compatible Chat Completions API.

Supports any provider that exposes the OpenAI Chat Completions API:
- OpenAI (api.openai.com)
- Anthropic via OpenAI-compatible proxy
- DeepSeek (api.deepseek.com)
- MiniMax / Kimi (custom OpenAI-compatible)
- Ollama (local, http://localhost:11434/v1)
- vLLM (local)
- Any other OpenAI-compatible endpoint

Default protocol: OpenAI Chat Completions.
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import httpx


@dataclass
class LLMConfig:
    """Configuration for the LLM client."""
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    provider: str = "openai"
    timeout: float = 15.0  # 15s is plenty for most LLMs
    max_retries: int = 1   # one retry, not two

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load from NONULL_LLM_* environment variables (auto-loads .env)."""
        # Auto-load .env if present
        _dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(_dotenv_path):
            with open(_dotenv_path) as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line and not _line.startswith("#") and "=" in _line:
                        _k, _v = _line.split("=", 1)
                        os.environ.setdefault(_k.strip(), _v.strip())
        api_key = os.environ.get("NONULL_LLM_API_KEY", "")
        provider = os.environ.get("NONULL_LLM_PROVIDER", "openai")
        model = os.environ.get("NONULL_LLM_MODEL", "gpt-4o")
        base_url = os.environ.get("NONULL_LLM_API_BASE", "")

        # Provider defaults for base_url
        if not base_url:
            defaults = {
                "openai": "https://api.openai.com/v1",
                "anthropic": "https://api.anthropic.com/v1",
                "deepseek": "https://api.deepseek.com/v1",
                "ollama": "http://localhost:11434/v1",
            }
            base_url = defaults.get(provider, "https://api.openai.com/v1")

        return cls(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            model=model,
            provider=provider,
        )


@dataclass
class LLMMessage:
    role: str  # 'system' | 'user' | 'assistant'
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    """Parsed LLM response."""
    content: str
    model: str
    usage: Dict[str, int]
    raw: Dict[str, Any]

    @property
    def prompt_tokens(self) -> int:
        return self.usage.get("prompt_tokens", 0)

    @property
    def completion_tokens(self) -> int:
        return self.usage.get("completion_tokens", 0)

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


class LLMClient:
    """Synchronous + async LLM client over OpenAI-compatible Chat Completions API.

    Reuses httpx Client for connection pooling (faster on repeated calls).
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client: httpx.Client | None = None

    def _build_request(self, messages: List[LLMMessage], **kwargs) -> Dict[str, Any]:
        return {
            "model": self.config.model,
            "messages": [m.to_dict() for m in messages],
            **kwargs,
        }

    def chat(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        """Synchronous chat completion (reuses httpx Client for connection pooling)."""
        url = f"{self.config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_request(messages, **kwargs)

        if self._client is None:
            self._client = httpx.Client(timeout=self.config.timeout)

        last_err = None
        for attempt in range(self.config.max_retries + 1):
            try:
                resp = self._client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return self._parse(data)
            except (httpx.HTTPError, httpx.RequestError, json.JSONDecodeError, Exception) as e:
                # NOTE: we intentionally also catch generic Exception so
                # misbehaving providers that surface transport-layer
                # problems as plain Exceptions (e.g. a 5xx raised before
                # httpx can classify it) still trigger the retry loop.
                # ADVISORY: not a certified error-handling policy.
                last_err = e
                if attempt < self.config.max_retries:
                    continue
                break
        raise RuntimeError(f"LLM call failed after {self.config.max_retries + 1} attempts: {last_err}")

    async def achat(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        """Async chat completion."""
        url = f"{self.config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_request(messages, **kwargs)

        last_err = None
        for attempt in range(self.config.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                return self._parse(data)
            except (httpx.HTTPError, httpx.RequestError, json.JSONDecodeError) as e:
                last_err = e
                if attempt < self.config.max_retries:
                    continue
                break
        raise RuntimeError(f"LLM call failed after {self.config.max_retries + 1} attempts: {last_err}")

    def _parse(self, data: Dict[str, Any]) -> LLMResponse:
        """Parse OpenAI-format response."""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        return LLMResponse(
            content=content,
            model=data.get("model", self.config.model),
            usage=data.get("usage", {}),
            raw=data,
        )

    def simple_chat(self, user_message: str, system_message: Optional[str] = None, **kwargs) -> str:
        """Convenience: one user message → assistant text."""
        messages = []
        if system_message:
            messages.append(LLMMessage(role="system", content=system_message))
        messages.append(LLMMessage(role="user", content=user_message))
        return self.chat(messages, **kwargs).content


# Singleton-style helper for one-off usage
_default_client: Optional[LLMClient] = None

def get_default_client() -> LLMClient:
    global _default_client
    if _default_client is None:
        _default_client = LLMClient(LLMConfig.from_env())
    return _default_client
