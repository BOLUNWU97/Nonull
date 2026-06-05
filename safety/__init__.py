"""
Nonull Safety Guardian System
=======================================

智驾智能体安全守护系统 — Critical safety layer for autonomous driving AI agent.

DESIGN PHILOSOPHY:
    Claude Code 7-layer deny-first safety +
    ISO 26262 automotive functional safety +
    OpenClaw sandbox isolation principles.

This package provides multi-layer safety validation for all agent actions,
including tool pre-filtering, rule-based checking, score-based risk assessment,
context-aware validation, and post-action verification.

Architecture Layers:
    Layer 1 - Tool Pre-filtering:     Deny dangerous tools before execution
    Layer 2 - Rule-based Checking:    Deny-first rule engine with priority evaluation
    Layer 3 - Score-based Risk:       Risk scoring (0-100) for all actions
    Layer 4 - Context-aware:          Validate action within current driving context
    Layer 5 - Post-action Verify:     Confirm action result is safe

ASIL Integration:
    ASIL-A:  General driver assistance
    ASIL-B:  Basic driving functions
    ASIL-C:  Advanced driving functions
    ASIL-D:  Safety-critical (steering, braking, airbag)

Author: Nonull Safety Team
Version: 1.0.0
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Common Enumerations
# ---------------------------------------------------------------------------


class SafetyLevel(enum.IntEnum):
    """Safety integrity levels aligned with ISO 26262 ASIL."""

    NONE = 0       # No safety requirement
    QM = 1         # Quality Management (no ASIL)
    ASIL_A = 2     # ASIL-A: General assistance
    ASIL_B = 3     # ASIL-B: Basic driving
    ASIL_C = 4     # ASIL-C: Advanced driving
    ASIL_D = 5     # ASIL-D: Safety-critical


class StrictnessLevel(enum.IntEnum):
    """Strictness level for the safety guardian (1-5)."""

    PERMISSIVE = 1       # Allow with warnings
    MODERATE = 2         # Allow but log and score
    STANDARD = 3         # Default: deny risky, allow safe
    STRICT = 4           # Deny most non-essential actions
    LOCKDOWN = 5         # Deny ALL actions except pre-approved safe list


class ActionCategory(enum.Enum):
    """Categories of agent actions for safety evaluation."""

    TOOL_CALL = "tool_call"
    CODE_EXECUTION = "code_execution"
    FILE_OPERATION = "file_operation"
    NETWORK_REQUEST = "network_request"
    DATA_ACCESS = "data_access"
    DEPLOYMENT = "deployment"
    SYSTEM_COMMAND = "system_command"
    VEHICLE_CONTROL = "vehicle_control"
    SENSOR_ACCESS = "sensor_access"
    COMMUNICATION = "communication"
    UNKNOWN = "unknown"


class RuleCategory(enum.Enum):
    """Categories for deny-first rules."""

    CODE_SAFETY = "code_safety"
    DATA_SAFETY = "data_safety"
    DEPLOY_SAFETY = "deploy_safety"
    COMMUNICATION_SAFETY = "communication_safety"
    EXECUTION_SAFETY = "execution_safety"
    VEHICLE_SAFETY = "vehicle_safety"
    SENSOR_SAFETY = "sensor_safety"
    EMERGENCY_SAFETY = "emergency_safety"


class Verdict(enum.Enum):
    """Possible safety verdicts for an action."""

    APPROVED = "approved"
    DENIED = "denied"
    ASK = "ask"
    ESCALATED = "escalated"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    VERIFICATION_FAILED = "verification_failed"


# ---------------------------------------------------------------------------
# Core Data Structures
# ---------------------------------------------------------------------------


@dataclass
class SafetyVerdict:
    """Verdict returned from a safety check layer."""
    verdict: Verdict
    score: float          # 0.0 (unsafe) to 100.0 (completely safe)
    reason: str           # Human-readable explanation
    layer: str            # Which layer produced this verdict
    asil_level: Optional[SafetyLevel] = None
    triggered_rules: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def is_approved(self) -> bool:
        """Check if this verdict is an approval."""
        return self.verdict == Verdict.APPROVED or self.verdict == Verdict.VERIFIED

    def is_denied(self) -> bool:
        """Check if this verdict is a denial."""
        return self.verdict == Verdict.DENIED or self.verdict == Verdict.VERIFICATION_FAILED

    def __bool__(self) -> bool:
        """Boolean convenience: True if approved, False otherwise."""
        return self.is_approved()


@dataclass
class Action:
    """Represents an agent action to be safety-checked."""
    action_id: str
    category: ActionCategory
    tool: str
    params: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)
    source: str = "agent"

    def __post_init__(self):
        if isinstance(self.category, str):
            try:
                self.category = ActionCategory(self.category)
            except ValueError:
                self.category = ActionCategory.UNKNOWN


@dataclass
class SafetyRule:
    """A single safety rule in the deny-first rule engine."""
    rule_id: str
    rule_type: str                     # 'allow' | 'deny' | 'ask'
    pattern: str                       # Tool/action pattern (regex or glob)
    category: RuleCategory
    scope: str = "global"              # global, code, data, deploy, comm, exec
    asil_level: SafetyLevel = SafetyLevel.QM
    reason: str = "No reason provided"
    priority: int = 0                  # Higher = higher priority
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.category, str):
            try:
                self.category = RuleCategory(self.category)
            except ValueError:
                self.category = RuleCategory.CODE_SAFETY
        if isinstance(self.asil_level, int):
            try:
                self.asil_level = SafetyLevel(self.asil_level)
            except ValueError:
                self.asil_level = SafetyLevel.QM


# ---------------------------------------------------------------------------
# Package-level convenience exports
# ---------------------------------------------------------------------------

__all__ = [
    "SafetyLevel",
    "StrictnessLevel",
    "ActionCategory",
    "RuleCategory",
    "Verdict",
    "SafetyVerdict",
    "Action",
    "SafetyRule",
    "SafetyGuardian",
    "DenyFirstEngine",
    "ComplianceChecker",
]

# Lazy imports to avoid circular dependencies
def get_guardian_class():
    """Lazy import for SafetyGuardian class. Returns the class, not an instance."""
    from safety.guardian import SafetyGuardian as GuardianClass
    return GuardianClass


def get_deny_first_engine_class():
    """Lazy import for DenyFirstEngine class. Returns the class, not an instance."""
    from safety.deny_first import DenyFirstEngine as DenyFirstEngineClass
    return DenyFirstEngineClass


def get_compliance_checker_class():
    """Lazy import for ComplianceChecker class. Returns the class, not an instance."""
    from safety.compliance import ComplianceChecker as ComplianceCheckerClass
    return ComplianceCheckerClass


# Module-level re-exports of the most commonly used classes. We use PEP 562
# module-level `__getattr__` (instead of eager `from safety.guardian import
# ...`) to avoid circular-import issues: the guardian / deny_first / compliance
# submodules themselves do `from safety import ...` at the top, so re-entering
# `safety/__init__.py` mid-load would be problematic. PEP 562 defers the
# submodule import until the caller actually accesses the name, by which time
# the safety package has finished initializing.
_LAZY_EXPORTS = {
    "SafetyGuardian": "safety.guardian",
    "DenyFirstEngine": "safety.deny_first",
    "ComplianceChecker": "safety.compliance",
}


def __getattr__(name: str):  # PEP 562
    if name in _LAZY_EXPORTS:
        import importlib
        module = importlib.import_module(_LAZY_EXPORTS[name])
        value = getattr(module, name)
        globals()[name] = value  # cache for subsequent lookups
        return value
    if name == "Guardian":  # backward-compat alias
        return __getattr__("SafetyGuardian")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + list(_LAZY_EXPORTS.keys()) + ["Guardian"])
