"""
Guardrail Pipeline — 护栏管道

Composable input/output validation for LLM-generated agent actions.
Inspired by Guardrails AI validator hub and NeMo Guardrails Colang 2.0.

Features:
- Chain multiple validators in sequence
- Configurable failure actions (BLOCK / FIX / REASK / LOG)
- Built-in validators for common patterns
- Integration with EventStream for audit logging

@module: core.guardrails
"""
from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

logger = logging.getLogger("Nonull.guardrails")


class OnFail(Enum):
    """Action to take when validation fails. / 验证失败时的动作。"""
    BLOCK = "block"
    FIX = "fix"
    REASK = "reask"
    LOG = "log"


class ValidatorStatus(Enum):
    """Validator result status. / 验证结果状态。"""
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


@dataclass
class ValidationResult:
    """
    Result of a single validation check.
    单次验证检查结果。
    """
    status: ValidatorStatus
    message: str = ""
    fix_value: Any = None
    validator_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == ValidatorStatus.PASS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "validator": self.validator_name,
            "metadata": self.metadata,
        }


class Validator(ABC):
    """
    Base class for all validators. / 所有验证器的基类。

    Subclass and implement validate() to create custom validators.
    """

    name: str = "base_validator"
    description: str = ""
    on_fail: OnFail = OnFail.BLOCK

    def __init__(self, on_fail: OnFail = OnFail.BLOCK):
        self.on_fail = on_fail

    @abstractmethod
    def validate(self, value: Any, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """
        Validate a value. / 验证一个值。

        Args:
            value: The value to validate
            metadata: Optional context metadata

        Returns:
            ValidationResult with status and optional fix
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(on_fail={self.on_fail.value})"


# ── Built-in Validators ─────────────────────────────────────────


class JsonValidator(Validator):
    """Validates that output is valid JSON. / 验证输出是否为有效 JSON。"""
    name = "json_validator"

    def validate(self, value: Any, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        if isinstance(value, (dict, list)):
            return ValidationResult(status=ValidatorStatus.PASS, validator_name=self.name)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return ValidationResult(
                    status=ValidatorStatus.PASS,
                    fix_value=parsed,
                    validator_name=self.name,
                )
            except json.JSONDecodeError as e:
                return ValidationResult(
                    status=ValidatorStatus.FAIL,
                    message=f"Invalid JSON: {e}",
                    validator_name=self.name,
                )
        return ValidationResult(
            status=ValidatorStatus.FAIL,
            message=f"Expected JSON string or dict, got {type(value).__name__}",
            validator_name=self.name,
        )


class LengthValidator(Validator):
    """Validates string length bounds. / 验证字符串长度范围。"""
    name = "length_validator"

    def __init__(self, min_length: int = 0, max_length: int = 10000, on_fail: OnFail = OnFail.BLOCK):
        super().__init__(on_fail)
        self.min_length = min_length
        self.max_length = max_length

    def validate(self, value: Any, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        text = str(value)
        if len(text) < self.min_length:
            return ValidationResult(
                status=ValidatorStatus.FAIL,
                message=f"Too short: {len(text)} < {self.min_length}",
                validator_name=self.name,
            )
        if len(text) > self.max_length:
            return ValidationResult(
                status=ValidatorStatus.FAIL,
                message=f"Too long: {len(text)} > {self.max_length}",
                fix_value=text[:self.max_length],
                validator_name=self.name,
            )
        return ValidationResult(status=ValidatorStatus.PASS, validator_name=self.name)


class RegexValidator(Validator):
    """Validates against a regex pattern. / 正则表达式验证。"""
    name = "regex_validator"

    def __init__(self, pattern: str, on_fail: OnFail = OnFail.BLOCK):
        super().__init__(on_fail)
        self._pattern = re.compile(pattern)

    def validate(self, value: Any, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        if self._pattern.search(str(value)):
            return ValidationResult(status=ValidatorStatus.PASS, validator_name=self.name)
        return ValidationResult(
            status=ValidatorStatus.FAIL,
            message=f"Does not match pattern: {self._pattern.pattern}",
            validator_name=self.name,
        )


class ProhibitedPatternValidator(Validator):
    """
    Rejects values containing prohibited patterns.
    拒绝包含禁止模式的值。
    """
    name = "prohibited_pattern"

    def __init__(self, patterns: List[str], on_fail: OnFail = OnFail.BLOCK):
        super().__init__(on_fail)
        self._patterns = [re.compile(p, re.IGNORECASE) for p in patterns]

    def validate(self, value: Any, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        text = str(value)
        for pat in self._patterns:
            match = pat.search(text)
            if match:
                return ValidationResult(
                    status=ValidatorStatus.FAIL,
                    message=f"Prohibited pattern found: {match.group()!r}",
                    validator_name=self.name,
                )
        return ValidationResult(status=ValidatorStatus.PASS, validator_name=self.name)


class NumericRangeValidator(Validator):
    """Validates numeric values are within a range. / 验证数值在范围内。"""
    name = "numeric_range"

    def __init__(self, min_val: float = float("-inf"), max_val: float = float("inf"),
                 on_fail: OnFail = OnFail.FIX):
        super().__init__(on_fail)
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, value: Any, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return ValidationResult(
                status=ValidatorStatus.FAIL,
                message=f"Not a number: {value!r}",
                validator_name=self.name,
            )
        if num < self.min_val or num > self.max_val:
            clamped = max(self.min_val, min(self.max_val, num))
            return ValidationResult(
                status=ValidatorStatus.FAIL,
                message=f"Value {num} outside range [{self.min_val}, {self.max_val}]",
                fix_value=clamped,
                validator_name=self.name,
            )
        return ValidationResult(status=ValidatorStatus.PASS, validator_name=self.name)


class SchemaValidator(Validator):
    """
    Validates a dict has required keys with correct types.
    验证字典包含必需的键且类型正确。
    """
    name = "schema_validator"

    def __init__(self, required_keys: Dict[str, type], on_fail: OnFail = OnFail.BLOCK):
        super().__init__(on_fail)
        self._required = required_keys

    def validate(self, value: Any, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        if not isinstance(value, dict):
            return ValidationResult(
                status=ValidatorStatus.FAIL,
                message=f"Expected dict, got {type(value).__name__}",
                validator_name=self.name,
            )
        missing = []
        type_errors = []
        for key, expected_type in self._required.items():
            if key not in value:
                missing.append(key)
            elif not isinstance(value[key], expected_type):
                type_errors.append(f"{key}: expected {expected_type.__name__}, got {type(value[key]).__name__}")
        errors = []
        if missing:
            errors.append(f"Missing keys: {missing}")
        if type_errors:
            errors.append(f"Type errors: {type_errors}")
        if errors:
            return ValidationResult(
                status=ValidatorStatus.FAIL,
                message="; ".join(errors),
                validator_name=self.name,
            )
        return ValidationResult(status=ValidatorStatus.PASS, validator_name=self.name)


class LambdaValidator(Validator):
    """
    Custom validator using a lambda/function.
    使用 lambda/函数的自定义验证器。
    """
    name = "lambda_validator"

    def __init__(self, check_fn: Callable[[Any], bool], message: str = "Validation failed",
                 on_fail: OnFail = OnFail.BLOCK):
        super().__init__(on_fail)
        self._check_fn = check_fn
        self._message = message

    def validate(self, value: Any, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        try:
            if self._check_fn(value):
                return ValidationResult(status=ValidatorStatus.PASS, validator_name=self.name)
            return ValidationResult(
                status=ValidatorStatus.FAIL, message=self._message, validator_name=self.name,
            )
        except Exception as e:
            return ValidationResult(
                status=ValidatorStatus.FAIL, message=f"Validator error: {e}", validator_name=self.name,
            )


# ── Guard Pipeline ──────────────────────────────────────────────


@dataclass
class GuardReport:
    """
    Complete report from a guard pipeline run.
    护栏管道运行的完整报告。
    """
    passed: bool
    value: Any
    original_value: Any
    results: List[ValidationResult] = field(default_factory=list)
    reask_messages: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "results": [r.to_dict() for r in self.results],
            "reask_messages": self.reask_messages,
            "duration_ms": round(self.duration_ms, 2),
        }


class Guard:
    """
    Composable guard pipeline. / 可组合的护栏管道。

    Usage:
        guard = Guard().use(
            JsonValidator(on_fail=OnFail.BLOCK),
            LengthValidator(max_length=5000, on_fail=OnFail.FIX),
            ProhibitedPatternValidator(["password", "secret"], on_fail=OnFail.BLOCK),
        )
        report = guard.validate(llm_output)
        if report.passed:
            process(report.value)
    """

    def __init__(self, name: str = "default"):
        self._name = name
        self._validators: List[Validator] = []

    def use(self, *validators: Validator) -> "Guard":
        """Add validators to the pipeline. / 添加验证器到管道。"""
        self._validators.extend(validators)
        return self

    def validate(self, value: Any, metadata: Optional[Dict[str, Any]] = None) -> GuardReport:
        """
        Run all validators in sequence. / 按顺序运行所有验证器。
        """
        start = time.time()
        results: List[ValidationResult] = []
        reask_messages: List[str] = []
        current_value = value

        for validator in self._validators:
            result = validator.validate(current_value, metadata)
            results.append(result)

            if result.passed:
                if result.fix_value is not None:
                    current_value = result.fix_value
                continue

            if validator.on_fail == OnFail.LOG:
                logger.warning("Guard [%s] %s: %s", self._name, validator.name, result.message)
                continue

            if validator.on_fail == OnFail.FIX and result.fix_value is not None:
                logger.info("Guard [%s] %s: auto-fixed", self._name, validator.name)
                current_value = result.fix_value
                continue

            if validator.on_fail == OnFail.REASK:
                reask_messages.append(
                    f"Validation failed ({validator.name}): {result.message}. "
                    f"Please fix and try again."
                )
                continue

            # OnFail.BLOCK — stop pipeline
            duration = (time.time() - start) * 1000
            logger.warning("Guard [%s] BLOCKED by %s: %s", self._name, validator.name, result.message)
            return GuardReport(
                passed=False,
                value=current_value,
                original_value=value,
                results=results,
                reask_messages=reask_messages,
                duration_ms=duration,
            )

        duration = (time.time() - start) * 1000
        passed = len(reask_messages) == 0
        return GuardReport(
            passed=passed,
            value=current_value,
            original_value=value,
            results=results,
            reask_messages=reask_messages,
            duration_ms=duration,
        )

    def __repr__(self) -> str:
        names = [v.name for v in self._validators]
        return f"Guard({self._name}, validators={names})"
