"""
Structured Output with Retry — 结构化输出与重试

Wraps LLM calls with response validation and auto-retry. When validation
fails, the error message is fed back to the LLM for self-correction.

Inspired by:
- Instructor (instructor-ai): Pydantic-based structured outputs
- PydanticAI: ModelRetry exception with error feedback

@module: core.structured_output
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

logger = logging.getLogger("Nonull.structured_output")

T = TypeVar("T")


class RetryExhausted(Exception):
    """All retry attempts failed. / 所有重试次数已耗尽。"""
    def __init__(self, attempts: List["AttemptRecord"], last_error: str):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Structured output failed after {len(attempts)} attempts: {last_error}")


@dataclass
class AttemptRecord:
    """Record of a single parsing attempt. / 单次解析尝试记录。"""
    attempt: int
    raw_output: str
    parsed: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt": self.attempt,
            "raw_output": self.raw_output[:500],
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class StructuredResult:
    """
    Result of a structured output call.
    结构化输出调用结果。
    """
    value: Any
    raw_output: str
    attempts: int
    total_duration_ms: float
    history: List[AttemptRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "attempts": self.attempts,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "history": [a.to_dict() for a in self.history],
        }


class ResponseSchema:
    """
    Defines expected response structure with validation.
    定义预期的响应结构及验证规则。

    Usage:
        schema = ResponseSchema(
            required_keys={"action": str, "confidence": (int, float)},
            validators=[lambda v: v.get("confidence", 0) <= 1.0],
        )
    """

    def __init__(
        self,
        required_keys: Optional[Dict[str, Union[type, tuple]]] = None,
        optional_keys: Optional[Dict[str, Union[type, tuple]]] = None,
        validators: Optional[List[Callable[[Dict], bool]]] = None,
        description: str = "",
    ):
        self.required_keys = required_keys or {}
        self.optional_keys = optional_keys or {}
        self.validators = validators or []
        self.description = description

    def validate(self, value: Any) -> Optional[str]:
        """
        Validate a parsed value. Returns error message or None if valid.
        验证解析值。返回错误消息或 None（如果有效）。
        """
        if not isinstance(value, dict):
            return f"Expected a JSON object (dict), got {type(value).__name__}"

        # Check required keys
        for key, expected_type in self.required_keys.items():
            if key not in value:
                return f"Missing required key: '{key}'"
            if not isinstance(value[key], expected_type):
                type_name = expected_type.__name__ if isinstance(expected_type, type) else str(expected_type)
                return f"Key '{key}' has wrong type: expected {type_name}, got {type(value[key]).__name__}"

        # Check optional key types
        for key, expected_type in self.optional_keys.items():
            if key in value and not isinstance(value[key], expected_type):
                type_name = expected_type.__name__ if isinstance(expected_type, type) else str(expected_type)
                return f"Optional key '{key}' has wrong type: expected {type_name}, got {type(value[key]).__name__}"

        # Run custom validators
        for i, validator_fn in enumerate(self.validators):
            try:
                if not validator_fn(value):
                    return f"Custom validator #{i+1} failed"
            except Exception as e:
                return f"Custom validator #{i+1} raised: {e}"

        return None

    def to_prompt_hint(self) -> str:
        """
        Generate a prompt hint describing the expected format.
        生成描述预期格式的提示。
        """
        lines = ["Return a JSON object with these fields:"]
        for key, expected_type in self.required_keys.items():
            type_name = expected_type.__name__ if isinstance(expected_type, type) else str(expected_type)
            lines.append(f'  - "{key}" ({type_name}, required)')
        for key, expected_type in self.optional_keys.items():
            type_name = expected_type.__name__ if isinstance(expected_type, type) else str(expected_type)
            lines.append(f'  - "{key}" ({type_name}, optional)')
        if self.description:
            lines.append(f"\n{self.description}")
        return "\n".join(lines)


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from LLM output that may contain markdown code blocks or extra text.
    从可能包含 markdown 代码块或额外文本的 LLM 输出中提取 JSON。
    """
    if not text:
        return None
    import re
    # strip 模型推理块 (MiniMax-M3 / DeepSeek-R1 等前缀 <think>...</think>)。
    # 闭合则删 <think>...</think>; 未闭合 (推理超 max_tokens 被截断) 则删到末尾。
    # 之前的 "从第一个 { 截取" 防御会误切 (think 内容含 { 时), 改为 \Z 更安全。
    # Strip reasoning blocks: remove <think>...</think> when closed, or
    # <think>…<end-of-text> when truncated (no closing tag).
    text = re.sub(r'<think>.*?(?:</think>|$)', '', text, flags=re.DOTALL)
    # Try direct parse first
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, TypeError):
        pass

    # Try extracting from markdown code block
    patterns = [
        r'```json\s*\n(.*?)\n\s*```',
        r'```\s*\n(.*?)\n\s*```',
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except (json.JSONDecodeError, TypeError):
                continue

    return None


def structured_call(
    llm_fn: Callable[[str], str],
    prompt: str,
    schema: ResponseSchema,
    max_retries: int = 3,
    system_hint: bool = True,
) -> StructuredResult:
    """
    Call an LLM with structured output validation and retry.
    调用 LLM 并进行结构化输出验证和重试。

    On validation failure, appends the error to the prompt and retries.

    Args:
        llm_fn: Function that takes a prompt string and returns LLM output string
        prompt: The user prompt
        schema: Expected response schema
        max_retries: Maximum number of retry attempts
        system_hint: Whether to append format instructions to the prompt

    Returns:
        StructuredResult with the validated value

    Raises:
        RetryExhausted: If all attempts fail
    """
    start = time.time()
    attempts: List[AttemptRecord] = []

    current_prompt = prompt
    if system_hint:
        current_prompt = f"{prompt}\n\n{schema.to_prompt_hint()}"

    for attempt_num in range(1, max_retries + 1):
        attempt_start = time.time()

        raw_output = llm_fn(current_prompt)
        parsed = extract_json(raw_output)

        if parsed is None:
            error_msg = "Could not extract valid JSON from response"
            attempts.append(AttemptRecord(
                attempt=attempt_num,
                raw_output=raw_output,
                error=error_msg,
                duration_ms=(time.time() - attempt_start) * 1000,
            ))
            current_prompt = (
                f"{prompt}\n\n{schema.to_prompt_hint()}\n\n"
                f"[Previous attempt failed] {error_msg}. "
                f"Your previous response was:\n{raw_output[:300]}\n\n"
                f"Please return ONLY valid JSON, no explanation."
            )
            continue

        validation_error = schema.validate(parsed)
        if validation_error is None:
            attempts.append(AttemptRecord(
                attempt=attempt_num,
                raw_output=raw_output,
                parsed=parsed,
                duration_ms=(time.time() - attempt_start) * 1000,
            ))
            return StructuredResult(
                value=parsed,
                raw_output=raw_output,
                attempts=attempt_num,
                total_duration_ms=(time.time() - start) * 1000,
                history=attempts,
            )

        attempts.append(AttemptRecord(
            attempt=attempt_num,
            raw_output=raw_output,
            parsed=parsed,
            error=validation_error,
            duration_ms=(time.time() - attempt_start) * 1000,
        ))
        current_prompt = (
            f"{prompt}\n\n{schema.to_prompt_hint()}\n\n"
            f"[Previous attempt failed] Validation error: {validation_error}. "
            f"Your previous JSON was:\n{json.dumps(parsed, ensure_ascii=False)[:300]}\n\n"
            f"Please fix the issues and return valid JSON."
        )
        logger.info("Structured output retry %d/%d: %s", attempt_num, max_retries, validation_error)

    raise RetryExhausted(attempts=attempts, last_error=attempts[-1].error or "unknown")
