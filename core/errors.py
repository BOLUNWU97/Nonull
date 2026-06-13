"""
Exception hierarchy — 异常体系. Extracted from agent_core.py.
"""

from typing import Any, Dict, Optional


class NonullError(Exception):
    """智能体基础异常 / Base agent exception."""
    pass


class SafetyViolation(NonullError):
    """
    安全违规异常 / Safety Violation Exception.

    当 Safety Guardian 拒绝某个操作时抛出。
    """

    def __init__(
        self,
        action: str,
        reason: str,
        risk_score: float = 1.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.action = action
        self.reason = reason
        self.risk_score = risk_score
        self.details = details or {}
        super().__init__(f"SafetyViolation: {reason} (action={action!r}, risk={risk_score:.2f})")


class RecoveryFailedError(NonullError):
    """恢复失败异常 / Recovery failed error."""
    pass


class SubagentError(NonullError):
    """子智能体异常 / Subagent error."""
    pass


class HookExecutionError(NonullError):
    """钩子执行异常 / Hook execution error."""
    pass


__all__ = [
    "NonullError",
    "SafetyViolation",
    "RecoveryFailedError",
    "SubagentError",
    "HookExecutionError",
]
