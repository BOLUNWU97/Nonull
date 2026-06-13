"""
Safety Guardian — 安全监护器 (Claude Code deny-first 风格).

ADVISORY ONLY — this is a software gate pattern, NOT a certified safety
mechanism. 仅为建议性软件门控，非认证安全机制。Extracted from agent_core.py.

ADVISORY SAFETY — The deny-first validation and risk-scoring code in this
file (SafetyGuardian) is an ADVISORY software gate. Risk scores and the
"max_risk_score" threshold are developer-configured heuristics, NOT certified
ISO 26262 ASIL-D (or any ASIL) classifications. The "deny-first" label is
borrowed from Claude Code's security pattern, not from a certified safety
process. See README §Disclaimer and `safety.disclaimer: advisory_only` in
config.

@module: core.safety
"""

import logging
import os
import re
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple

from .config import NonullConfig
from .errors import SafetyViolation

logger = logging.getLogger("Nonull.agent")

# ===================================================================
# 安全监护 / Safety Guardian  (Claude Code deny-first 风格)
# ===================================================================


class SafetyGuardian:
    """
    安全监护器 / Safety Guardian.

    采用 Claude Code 风格的 Deny-First 安全策略：
      - 默认拒绝所有操作
      - 仅显式允许的操作可通过
      - 每次动作执行前检查
      - 风险评分机制

    特性:
      - 命令白名单 / Command allowlist
      - 正则模式黑名单 / Regex pattern blocklist
      - 风险评分 / Risk scoring
      - 上下文物联网关 / Context-aware gating
    """

    def __init__(self, config: Optional[NonullConfig] = None) -> None:
        self._config = config or NonullConfig.instance()
        self._allowed_commands: Set[str] = set(
            self._config.get("safety.allowed_commands", [])
        )
        self._blocked_patterns: List[str] = list(
            self._config.get("safety.blocked_patterns", [])
        )
        self._deny_first: bool = self._config.get("safety.deny_first", True)
        self._max_risk_score: float = self._config.get("safety.max_risk_score", 0.7)
        self._enabled: bool = self._config.get("safety.enabled", True)
        self._violation_log: List[SafetyViolation] = []
        self._lock = Lock()
        # 导入 re 惰性
        import re
        self._compiled_patterns = [re.compile(p) for p in self._blocked_patterns]
        logger.info(
            "SafetyGuardian 已初始化 | deny_first=%s | max_risk=%.2f | enabled=%s",
            self._deny_first, self._max_risk_score, self._enabled,
        )

    # ── 核心检查 ──────────────────────────────────────────────

    def validate(
        self,
        action: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, float, str]:
        """
        校验操作是否安全 / Validate whether an action is safe.

        Args:
            action:  操作描述 (如 "exec:ls -la", "file:write:/tmp/x")
            context: 可选的上下文信息

        Returns:
            (is_safe, risk_score, reason) 三元组
        """
        context = context or {}
        risk_score = 0.0
        reason = ""

        if not self._enabled:
            return True, 0.0, "safety_disabled"

        # 0) Deny-first: 默认拒绝
        # ADVISORY: "deny-first" here is a software gate pattern, not a certified
        # safety mechanism. The 0.5 starting risk_score is an arbitrary heuristic,
        # NOT an ASIL rating (there is no ASIL mapping in this file).
        if self._deny_first:
            risk_score = 0.5  # 起步分数 (advisory heuristic, not ASIL)

        # 1) 正则黑名单检查
        import re
        for pattern, compiled in zip(self._blocked_patterns, self._compiled_patterns):
            if compiled.search(action):
                # ADVISORY: 1.0 risk_score is "denied" in this heuristic; it does
                # NOT mean the action is ASIL-D or worse in any certified sense.
                risk_score = 1.0
                reason = f"命中黑名单模式: {pattern}"
                logger.warning("安全拦截: %s | %s", action, reason)
                self._log_violation(action, reason, risk_score)
                return False, risk_score, reason

        # 2) 命令白名单检查
        action_type = action.split(":")[0] if ":" in action else action
        if self._allowed_commands and action_type not in self._allowed_commands:
            # ADVISORY: the +0.3 increment and max_risk_score threshold are
            # developer-configured heuristics, not safety-rated limits.
            risk_score = min(1.0, risk_score + 0.3)
            if risk_score > self._max_risk_score:
                reason = f"操作类型不在白名单中: {action_type}"
                logger.warning("安全拦截: %s | %s", action, reason)
                self._log_violation(action, reason, risk_score)
                return False, risk_score, reason

        # 3) 上下文风险评估
        context_risk = self._evaluate_context_risk(action, context)
        risk_score = min(1.0, risk_score + context_risk)

        if risk_score > self._max_risk_score:
            reason = f"风险评分超限: {risk_score:.2f} > {self._max_risk_score:.2f}"
            logger.warning("安全拦截(风险): %s | %s", action, reason)
            self._log_violation(action, reason, risk_score)
            return False, risk_score, reason

        return True, risk_score, "ok"

    def validate_or_raise(
        self,
        action: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        校验操作，不通过则抛出 SafetyViolation / Validate or raise.

        Args:
            action:  操作描述
            context: 上下文

        Raises:
            SafetyViolation: 当操作不安全时
        """
        is_safe, risk, reason = self.validate(action, context)
        if not is_safe:
            raise SafetyViolation(
                action=action,
                reason=reason,
                risk_score=risk,
                details={"context": context},
            )

    # ── 配置 ───────────────────────────────────────────────────

    def allow_command(self, command: str) -> "SafetyGuardian":
        """添加命令到白名单 / Add command to allowlist."""
        with self._lock:
            self._allowed_commands.add(command)
        return self

    def block_pattern(self, pattern: str) -> "SafetyGuardian":
        """添加拦截正则模式 / Add blocked regex pattern."""
        import re
        with self._lock:
            self._blocked_patterns.append(pattern)
            self._compiled_patterns.append(re.compile(pattern))
        return self

    def set_max_risk(self, score: float) -> "SafetyGuardian":
        """设置最大风险评分 / Set max risk score."""
        self._max_risk_score = max(0.0, min(1.0, score))
        return self

    # ── 查询 ───────────────────────────────────────────────────

    @property
    def violation_count(self) -> int:
        """违规次数 / Violation count."""
        return len(self._violation_log)

    def recent_violations(self, n: int = 10) -> List[SafetyViolation]:
        """最近的违规记录 / Recent violations."""
        with self._lock:
            return list(self._violation_log[-n:])

    # ── 内部 ───────────────────────────────────────────────────

    def _evaluate_context_risk(self, action: str, context: Dict[str, Any]) -> float:
        """评估上下文风险 / Evaluate contextual risk."""
        risk = 0.0
        # 文件系统操作
        if "write" in action.lower() or "delete" in action.lower():
            risk += 0.2
        # 网络操作
        if "network" in action.lower() or "http" in action.lower():
            risk += 0.1
        # 系统命令
        if action.startswith("exec:"):
            cmd = action[5:]
            dangerous = ["rm -rf", "format", "del /f", "shutdown", "reboot"]
            if any(d in cmd.lower() for d in dangerous):
                risk += 0.5
        # 文件路径
        target = context.get("target", "")
        if isinstance(target, str):
            import os
            dangerous_paths = ["/etc", "/proc", "/sys", "/bin", "/boot", "/dev"]
            if os.name == "nt":
                dangerous_paths += ["C:\\Windows", "C:\\Program Files", "C:\\System32"]
            if ".." in target or any(target.startswith(p) for p in dangerous_paths):
                risk += 0.4
        return risk

    def _log_violation(self, action: str, reason: str, risk: float) -> None:
        """记录违规 / Log violation."""
        with self._lock:
            self._violation_log.append(
                SafetyViolation(action=action, reason=reason, risk_score=risk)
            )

    def __repr__(self) -> str:
        return (
            f"<SafetyGuardian enabled={self._enabled} "
            f"allowlist={len(self._allowed_commands)} "
            f"blocklist={len(self._blocked_patterns)} "
            f"violations={len(self._violation_log)}>"
        )


__all__ = ["SafetyGuardian"]
