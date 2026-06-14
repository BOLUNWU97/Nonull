"""
LLM Client — Async + Sync wrappers over OpenAI-compatible Chat Completions API.

Supports any provider that exposes the OpenAI Chat Completions API:
- OpenAI (api.openai.com)
- Anthropic via OpenAI-compatible proxy
- DeepSeek (api.deepseek.com)
- MiniMax / Kimi (custom OpenAI-compatible)
- Ollama (local, http://localhost:11434/v1)
- vLLM (local)
- Any other OpenAI-compatible endpoint

Features (v2):
- Tool/function calling for agent skill dispatch
- Streaming (SSE) support for real-time output
- Context window tracking for token management
- Multiple provider support with auto-routing

Features (v3 — hardening):
- Classified errors (auth / rate-limit / server / request) for precise handling
- 429 rate-limit handling that honors the Retry-After header
- Model fallback chain: auto-switch to backup models on recoverable failures
- Streaming + tool calls in one call via chat_stream_full()
- Structured logging on retries and fallbacks
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import (
    Any, AsyncIterator, Callable, Dict, List, Optional, Union,
)

import httpx

logger = logging.getLogger("Nonull.llm")


# ---------------------------------------------------------------------------
# Exceptions (classified by HTTP status for retry/fallback decisions)
# ---------------------------------------------------------------------------

class LLMError(RuntimeError):
    """Base error for the LLM client.

    LLM 客户端基础异常 / Base exception for LLM client failures.
    """


class LLMAuthError(LLMError):
    """401/403 — authentication failed. Not retryable, not recoverable via fallback.

    认证失败（401/403）/ Auth failure — no retry, no model fallback.
    """


class LLMRateLimitError(LLMError):
    """429 — rate limited. Retryable, honors Retry-After header.

    限流（429）/ Rate limited — retryable with Retry-After.
    """

    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class LLMServerError(LLMError):
    """5xx — server error. Retryable.

    服务端错误（5xx）/ Server error — retryable.
    """


class LLMRequestError(LLMError):
    """4xx (non-429) — bad request. Not retryable on same model, but may fall back.

    请求错误（4xx，非429）/ Bad request — try fallback model, no same-model retry.
    """


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    """Configuration for the LLM client.

    Attributes:
        api_key:        API key for the provider
        base_url:       API base URL
        model:          Model name to use
        provider:       Provider identifier (openai, anthropic, deepseek, ollama, custom)
        timeout:        Request timeout in seconds
        max_retries:    Number of retries on server errors
        max_tokens:     Max output tokens
        temperature:    Sampling temperature (0.0–2.0)
        top_p:          Top-p sampling
    """
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    provider: str = "openai"
    timeout: float = 30.0
    max_retries: int = 2
    max_tokens: int = 4096
    temperature: float = 0.2
    top_p: float = 0.9

    # Context window in tokens (approximate, used for budget tracking)
    context_window: int = 128_000

    # Fallback model chain: tried in order when the primary model fails with a
    # retryable/recoverable error (rate limit, server error, bad request).
    # 备用模型链：主模型遇到可恢复错误时按顺序尝试。
    fallback_models: List[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load from NONULL_LLM_* environment variables.

        Auto-loads .env file from project root if present.
        """
        # Auto-load .env if present
        _dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(_dotenv_path):
            # 强制 UTF-8 编码: Windows 默认 cp936/GBK 无法解码中文注释
            # Force UTF-8 — Windows default cp936/GBK can't decode CJK chars
            with open(_dotenv_path, encoding="utf-8") as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line and not _line.startswith("#") and "=" in _line:
                        _k, _v = _line.split("=", 1)
                        os.environ.setdefault(_k.strip(), _v.strip())

        api_key = os.environ.get("NONULL_LLM_API_KEY", "")
        provider = os.environ.get("NONULL_LLM_PROVIDER", "openai")
        model = os.environ.get("NONULL_LLM_MODEL", "gpt-4o")
        base_url = os.environ.get("NONULL_LLM_API_BASE", "")

        provider_defaults = {
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "ollama": "http://localhost:11434/v1",
        }

        if not base_url:
            base_url = provider_defaults.get(provider, "https://api.openai.com/v1")

        # Comma-separated fallback chain, e.g. "gpt-4o-mini,deepseek-chat"
        _fallback_raw = os.environ.get("NONULL_LLM_FALLBACK_MODELS", "")
        fallback_models = [m.strip() for m in _fallback_raw.split(",") if m.strip()]

        return cls(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            model=model,
            provider=provider,
            max_tokens=int(os.environ.get("NONULL_LLM_MAX_TOKENS", "4096")),
            temperature=float(os.environ.get("NONULL_LLM_TEMPERATURE", "0.2")),
            fallback_models=fallback_models,
        )


# ---------------------------------------------------------------------------
# Message Types
# ---------------------------------------------------------------------------

@dataclass
class LLMMessage:
    """A single chat message.

    Attributes:
        role:       'system' | 'user' | 'assistant' | 'tool'
        content:    Text content
        name:       Optional name (for tool messages)
        tool_calls: Optional tool call specifications (for assistant messages)
        tool_result: Optional tool result (for tool messages)
    """
    role: str = "user"
    content: str = ""
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.tool_result is not None:
            result["tool_call_id"] = self.tool_result.get("tool_call_id", "")
            result["content"] = self.tool_result.get("content", "")
        return result

    @classmethod
    def system(cls, content: str) -> "LLMMessage":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "LLMMessage":
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str = "", tool_calls: Optional[List[Dict]] = None) -> "LLMMessage":
        return cls(role="assistant", content=content, tool_calls=tool_calls)

    @classmethod
    def tool(cls, content: str, tool_call_id: str, name: Optional[str] = None) -> "LLMMessage":
        return cls(
            role="tool",
            content=content,
            name=name,
            tool_result={"tool_call_id": tool_call_id, "content": content},
        )


@dataclass
class LLMResponse:
    """Parsed LLM response.

    Attributes:
        content:        Assistant text response
        model:          Model name
        usage:          Token usage {prompt_tokens, completion_tokens, total_tokens}
        raw:            Full API response dict
        finish_reason:  Why the model stopped (stop, length, tool_calls, content_filter)
        tool_calls:     Tool call specifications (if any)
    """
    content: str = ""
    model: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)
    finish_reason: str = "stop"
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def prompt_tokens(self) -> int:
        return self.usage.get("prompt_tokens", 0)

    @property
    def completion_tokens(self) -> int:
        return self.usage.get("completion_tokens", 0)

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def is_finished(self) -> bool:
        return self.finish_reason in ("stop", "tool_calls", "length")


# ---------------------------------------------------------------------------
# Tool Definitions (for function calling)
# ---------------------------------------------------------------------------

@dataclass
class ToolDefinition:
    """A tool that the LLM can call.

    Attributes:
        name:        Tool name (used in function calling)
        description: Tool description
        parameters:  JSON Schema for parameters
    """
    name: str
    description: str
    parameters: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

class LLMClient:
    """Async + sync LLM client over OpenAI-compatible Chat Completions API.

    Features:
    - Connection pooling via httpx.Client
    - Retry on server errors
    - Tool/function calling support
    - Streaming (SSE) support
    - Context window tracking
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client: Optional[httpx.Client] = None
        self._prompt_tokens_used: int = 0

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # -- helpers ----------------------------------------------------------------

    def _build_request(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        model: Optional[str] = None,
        json_mode: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model or self.config.model,
            "messages": [m.to_dict() for m in messages],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            **kwargs,
        }
        # JSON 强约束模式 (OpenAI 兼容端点支持 response_format)。
        # 强制模型输出合法 JSON, 根治 _parse_llm_json 解析报错。
        # 不支持该参数的端点 (如旧版 Ollama) 调用时应不传 json_mode。
        # Force valid JSON output via response_format — cures parse errors.
        # Endpoints without this param must call without json_mode.
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if tools:
            payload["tools"] = [t.to_dict() for t in tools]
            payload["tool_choice"] = "auto"
        return payload

    @staticmethod
    def _parse_retry_after(resp: "httpx.Response", attempt: int) -> float:
        """Compute backoff delay, honoring the Retry-After header if present.

        遵守 Retry-After 头计算退避时间 / Honor Retry-After header for backoff.
        """
        retry_after = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 60.0)
            except (ValueError, TypeError):
                pass
        # Exponential backoff fallback
        return min(2 ** attempt, 30)

    @staticmethod
    def _classify_status(resp: "httpx.Response") -> Optional[LLMError]:
        """Map an HTTP status to a classified LLMError (or None if OK).

        将 HTTP 状态码映射为分类异常 / Classify HTTP status into a typed error.
        """
        code = resp.status_code
        if code < 400:
            return None
        # Try to surface the provider's error message
        try:
            body = resp.json()
            detail = body.get("error", {})
            msg = detail.get("message") if isinstance(detail, dict) else str(detail)
        except Exception:
            msg = resp.text[:200] if resp.text else ""
        msg = msg or f"HTTP {code}"

        if code in (401, 403):
            return LLMAuthError(f"Auth failed ({code}): {msg}")
        if code == 429:
            ra = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
            retry_after: Optional[float] = None
            if ra:
                try:
                    retry_after = float(ra)
                except (ValueError, TypeError):
                    retry_after = None
            return LLMRateLimitError(f"Rate limited (429): {msg}", retry_after=retry_after)
        if code >= 500:
            return LLMServerError(f"Server error ({code}): {msg}")
        return LLMRequestError(f"Request error ({code}): {msg}")

    # -- sync API ---------------------------------------------------------------

    def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs,
    ) -> LLMResponse:
        """Synchronous chat completion with retry + model fallback.

        Tries the primary model with retries (429/5xx/network). If the primary
        model is exhausted with a recoverable error, falls back through
        config.fallback_models in order.

        同步对话补全，含重试与模型回退。
        """
        model_chain = [self.config.model] + list(self.config.fallback_models)
        last_err: Optional[Exception] = None

        for model_idx, model in enumerate(model_chain):
            is_fallback = model_idx > 0
            if is_fallback:
                logger.warning("Falling back to model '%s' after primary failed", model)
            try:
                return self._chat_once(messages, tools, model, **kwargs)
            except LLMAuthError:
                # Auth failures won't be fixed by switching models — fail fast
                raise
            except (LLMRateLimitError, LLMServerError, LLMRequestError) as e:
                last_err = e
                continue
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ConnectTimeout, ConnectionError) as e:
                last_err = e
                continue

        raise LLMError(f"LLM call failed across {len(model_chain)} model(s): {last_err}")

    def _chat_once(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]],
        model: str,
        **kwargs,
    ) -> LLMResponse:
        """Single-model chat with retry on 429/5xx/network errors."""
        url = f"{self.config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_request(messages, tools=tools, model=model, **kwargs)

        if self._client is None:
            self._client = httpx.Client(timeout=self.config.timeout)

        last_err: Optional[Exception] = None
        for attempt in range(self.config.max_retries + 1):
            try:
                resp = self._client.post(url, json=payload, headers=headers)
                err = self._classify_status(resp)
                if err is not None:
                    # Retryable: 429 and 5xx
                    if isinstance(err, (LLMRateLimitError, LLMServerError)) and attempt < self.config.max_retries:
                        delay = self._parse_retry_after(resp, attempt)
                        logger.info("Retry %d/%d for model '%s' after %.1fs (%s)",
                                    attempt + 1, self.config.max_retries, model, delay, type(err).__name__)
                        last_err = err
                        time.sleep(delay)
                        continue
                    raise err
                data = resp.json()
                result = self._parse(data)
                self._prompt_tokens_used += result.prompt_tokens
                return result
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ConnectTimeout, ConnectionError) as e:
                last_err = e
                if attempt < self.config.max_retries:
                    time.sleep(min(2 ** attempt, 30))
                    continue
                raise
        # Exhausted retries on a retryable classified error
        if last_err is not None:
            raise last_err
        raise LLMError(f"LLM call failed for model '{model}'")

    def simple_chat(
        self,
        user_message: str,
        system_message: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs,
    ) -> str:
        """Convenience: one user message → assistant text.

        Args:
            user_message:  User prompt
            system_message: System prompt (optional)
            max_tokens:    Override max output tokens
            temperature:   Override temperature

        Returns:
            Assistant response text
        """
        messages = []
        if system_message:
            messages.append(LLMMessage(role="system", content=system_message))
        messages.append(LLMMessage(role="user", content=user_message))
        extra = {}
        if max_tokens:
            extra["max_tokens"] = max_tokens
        if temperature is not None:
            extra["temperature"] = temperature
        return self.chat(messages, **extra).content

    # -- tool-use API -----------------------------------------------------------

    def chat_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[ToolDefinition],
        tool_handler: Callable[[Dict[str, Any]], str],
        max_tool_rounds: int = 5,
        **kwargs,
    ) -> LLMResponse:
        """Chat with tool calling, automatically handling tool results.

        This implements the tool-use loop:
        1. Send messages + tools to LLM
        2. If LLM returns tool_calls, execute them via tool_handler
        3. Append tool results to messages and repeat
        4. Return final response after max_tool_rounds or no more tool calls

        Args:
            messages:      Initial messages
            tools:         Available tools
            tool_handler:  Callable(tool_call_dict) -> str  (execute tool, return result text)
            max_tool_rounds: Maximum tool call rounds
            **kwargs:      Extra API parameters

        Returns:
            Final LLMResponse
        """
        current_messages = list(messages)
        final_response: LLMResponse = LLMResponse(content="")

        for _round in range(max_tool_rounds):
            response = self.chat(current_messages, tools=tools, **kwargs)
            final_response = response

            if not response.has_tool_calls:
                break

            # Single assistant message with all tool_calls
            current_messages.append(
                LLMMessage(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                )
            )

            # Execute each tool call and append results
            for tc in response.tool_calls:
                function_name = tc.get("function", {}).get("name", "")
                function_args = tc.get("function", {}).get("arguments", "{}")

                # Parse arguments
                try:
                    parsed_args = json.loads(function_args) if isinstance(function_args, str) else function_args
                except json.JSONDecodeError:
                    parsed_args = {"_raw": function_args}

                # Execute via handler
                result_text = tool_handler({
                    "name": function_name,
                    "arguments": parsed_args,
                })

                current_messages.append(
                    LLMMessage.tool(
                        content=str(result_text),
                        tool_call_id=tc.get("id", f"call_{_round}"),
                        name=function_name,
                    )
                )

        return final_response

    # -- streaming --------------------------------------------------------------

    async def chat_stream(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Streaming chat completion (SSE).

        Yields text chunks as they arrive.

        Args:
            messages: Chat messages
            tools:    Optional tools
            on_chunk: Optional callback for each text chunk
            **kwargs: Extra API parameters
        """
        url = f"{self.config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload = self._build_request(messages, tools=tools, stream=True, **kwargs)

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code >= 400:
                    await resp.aread()
                    err = self._classify_status(resp)
                    if err is not None:
                        raise err
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        return
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            if on_chunk:
                                on_chunk(content)
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def chat_stream_full(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> LLMResponse:
        """Streaming chat that also accumulates tool_call deltas into a full response.

        Unlike chat_stream (which only yields text), this consumes the whole
        stream and returns a complete LLMResponse with assembled tool_calls —
        enabling streaming + tool use in one call.

        流式对话，同时累积 tool_call 增量，返回完整响应（支持流式 + 工具调用）。
        """
        url = f"{self.config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload = self._build_request(messages, tools=tools, stream=True, **kwargs)

        content_parts: List[str] = []
        # tool_calls assembled by index: {idx: {"id", "type", "function": {"name", "arguments"}}}
        tool_acc: Dict[int, Dict[str, Any]] = {}
        finish_reason = "stop"
        model_name = self.config.model

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code >= 400:
                    await resp.aread()
                    err = self._classify_status(resp)
                    if err is not None:
                        raise err
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    model_name = data.get("model", model_name)
                    try:
                        choice = data["choices"][0]
                    except (KeyError, IndexError):
                        continue
                    if choice.get("finish_reason"):
                        finish_reason = choice["finish_reason"]
                    delta = choice.get("delta", {})

                    text = delta.get("content")
                    if text:
                        content_parts.append(text)
                        if on_chunk:
                            on_chunk(text)

                    for tc in delta.get("tool_calls", []) or []:
                        idx = tc.get("index", 0)
                        slot = tool_acc.setdefault(
                            idx, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                        )
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            slot["function"]["name"] = fn["name"]
                        if fn.get("arguments"):
                            slot["function"]["arguments"] += fn["arguments"]

        tool_calls = [tool_acc[i] for i in sorted(tool_acc)]
        return LLMResponse(
            content="".join(content_parts),
            model=model_name,
            usage={},
            raw={},
            finish_reason=finish_reason,
            tool_calls=tool_calls,
        )

    # -- async API --------------------------------------------------------------

    async def achat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs,
    ) -> LLMResponse:
        """Async chat completion with retry + model fallback.

        异步对话补全，含重试与模型回退。
        """
        model_chain = [self.config.model] + list(self.config.fallback_models)
        last_err: Optional[Exception] = None

        for model_idx, model in enumerate(model_chain):
            if model_idx > 0:
                logger.warning("Falling back to model '%s' after primary failed", model)
            try:
                return await self._achat_once(messages, tools, model, **kwargs)
            except LLMAuthError:
                raise
            except (LLMRateLimitError, LLMServerError, LLMRequestError) as e:
                last_err = e
                continue
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ConnectTimeout, ConnectionError) as e:
                last_err = e
                continue

        raise LLMError(f"LLM call failed across {len(model_chain)} model(s): {last_err}")

    async def _achat_once(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]],
        model: str,
        **kwargs,
    ) -> LLMResponse:
        """Single-model async chat with retry on 429/5xx/network errors."""
        url = f"{self.config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_request(messages, tools=tools, model=model, **kwargs)

        last_err: Optional[Exception] = None
        for attempt in range(self.config.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    err = self._classify_status(resp)
                    if err is not None:
                        if isinstance(err, (LLMRateLimitError, LLMServerError)) and attempt < self.config.max_retries:
                            delay = self._parse_retry_after(resp, attempt)
                            logger.info("Retry %d/%d for model '%s' after %.1fs (%s)",
                                        attempt + 1, self.config.max_retries, model, delay, type(err).__name__)
                            last_err = err
                            await asyncio.sleep(delay)
                            continue
                        raise err
                    data = resp.json()
                result = self._parse(data)
                self._prompt_tokens_used += result.prompt_tokens
                return result
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ConnectTimeout, ConnectionError) as e:
                last_err = e
                if attempt < self.config.max_retries:
                    await asyncio.sleep(min(2 ** attempt, 30))
                    continue
                raise
        if last_err is not None:
            raise last_err
        raise LLMError(f"LLM call failed for model '{model}'")

    async def achat_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[ToolDefinition],
        tool_handler: Callable[[Dict[str, Any]], Union[str, asyncio.Future]],
        max_tool_rounds: int = 5,
        **kwargs,
    ) -> LLMResponse:
        """Async tool-use loop."""
        current_messages = list(messages)
        final_response = LLMResponse(content="")

        for _round in range(max_tool_rounds):
            response = await self.achat(current_messages, tools=tools, **kwargs)
            final_response = response

            if not response.has_tool_calls:
                break

            # Single assistant message with all tool_calls
            current_messages.append(
                LLMMessage(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                )
            )

            for tc in response.tool_calls:
                function_name = tc.get("function", {}).get("name", "")
                function_args = tc.get("function", {}).get("arguments", "{}")
                try:
                    parsed_args = json.loads(function_args) if isinstance(function_args, str) else function_args
                except json.JSONDecodeError:
                    parsed_args = {"_raw": function_args}

                result = tool_handler({"name": function_name, "arguments": parsed_args})
                if inspect.isawaitable(result):
                    result_text = await result
                else:
                    result_text = str(result)

                current_messages.append(
                    LLMMessage.tool(
                        content=str(result_text),
                        tool_call_id=tc.get("id", f"call_{_round}"),
                        name=function_name,
                    )
                )

        return final_response

    # -- internal ---------------------------------------------------------------

    def _parse(self, data: Dict[str, Any]) -> LLMResponse:
        """Parse OpenAI-format response."""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])
        return LLMResponse(
            content=content,
            model=data.get("model", self.config.model),
            usage=data.get("usage", {}),
            raw=data,
            finish_reason=choice.get("finish_reason", "stop"),
            tool_calls=tool_calls,
        )

    def context_budget(self) -> float:
        """Return remaining context window budget as a fraction."""
        window = self.config.context_window
        used = self._prompt_tokens_used
        return max(0.0, 1.0 - (used / window))

    @property
    def total_tokens_used(self) -> int:
        return self._prompt_tokens_used


# -- Singleton helper ---------------------------------------------------------

_default_client: Optional[LLMClient] = None

def get_default_client() -> LLMClient:
    global _default_client
    if _default_client is None:
        _default_client = LLMClient(LLMConfig.from_env())
    return _default_client
