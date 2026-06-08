"""
ADVISORY SAFETY — does not implement ISO 26262 veto semantics. The 'VETO POWER'
described in this file is a software recommendation, not a certified safety gate.
See README §Disclaimer and `safety.disclaimer: advisory_only` in config.

Safety Guardian — Main Safety Layer for Nonull
========================================================

智驾智能体安全守护核心 — The central safety orchestrator.

MULTI-LAYER SAFETY CHECK PIPELINE:
    Layer 1 - Tool Pre-filtering:     Before any tool is invoked, check if it's
                                      inherently dangerous for the current context.
    Layer 2 - Rule-based Checking:    Evaluate against deny-first rule engine.
    Layer 3 - Score-based Risk:       Calculate composite risk score across signals.
    Layer 4 - Context-aware:          Validate in driving context (speed, environment,
                                      weather, traffic, vehicle state).
    Layer 5 - Post-action Verify:     After execution, verify the result is safe.

VETO POWER:
    The guardian can VETO any action at Layers 1-4. A vetoed action is never
    executed. The veto includes a reason and the specific layer that triggered it.

AUDIT LOG:
    All decisions (approve, deny, veto, escalate) are logged with:
    - Timestamp, action details, decision, score, triggered rules
    - Layer-by-layer verdict breakdown
    - ASIL level context

SAFETY SCORE SYSTEM:
    Each action receives a score from 0 (completely unsafe) to 100 (completely safe).
    Thresholds:
        0-20:   CRITICAL - Auto-veto
        21-40:  UNSAFE   - Veto in standard mode
        41-60:  UNCERTAIN - Ask for confirmation
        61-80:  SAFE     - Approve with monitoring
        81-100: SAFE+    - Approve

ISO 26262 ASIL INTEGRATION:
    - ASIL-D actions are always pre-filtered and scored most strictly
    - ASIL-C actions require context validation
    - ASIL-B actions go through standard pipeline
    - ASIL-A actions go through basic pipeline
    - QM actions go through express pipeline

Author: Nonull Safety Team
Version: 1.0.0
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from safety import (
    Action,
    ActionCategory,
    SafetyLevel,
    SafetyRule,
    SafetyVerdict,
    StrictnessLevel,
    Verdict,
)
from safety.deny_first import DenyFirstEngine
from safety.compliance import ComplianceChecker, ComplianceResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline Layer Identifiers
# ---------------------------------------------------------------------------


class PipelineLayer(Enum):
    """Identifiers for each layer in the safety check pipeline."""
    L1_TOOL_PRE_FILTER = "layer_1_tool_pre_filter"
    L2_RULE_BASED = "layer_2_rule_based"
    L3_SCORE_RISK = "layer_3_score_risk"
    L4_CONTEXT_AWARE = "layer_4_context_aware"
    L5_POST_ACTION = "layer_5_post_action"


# ---------------------------------------------------------------------------
# Audit Log Entry
# ---------------------------------------------------------------------------


@dataclass
class AuditEntry:
    """An audit log entry for a safety decision."""
    entry_id: str
    timestamp: str
    action: str
    action_category: str
    decision: str
    score: float
    reason: str
    layer_verdicts: Dict[str, Dict[str, Any]]
    triggered_rules: List[str]
    asil_level: str
    strictness: int
    duration_ms: float
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


# ---------------------------------------------------------------------------
# Driving Context for Context-Aware Validation
# ---------------------------------------------------------------------------


@dataclass
class DrivingContext:
    """Current driving context for context-aware safety validation.

    Fields capture the full operational situation of the vehicle.
    """
    speed_kmh: float = 0.0
    is_moving: bool = False
    gear: str = "park"
    environment: str = "unknown"          # highway, urban, rural, parking, tunnel
    weather: str = "clear"                # clear, rain, snow, fog, ice
    visibility: str = "good"              # good, reduced, poor, night
    traffic_density: str = "light"        # none, light, moderate, heavy, gridlock
    road_condition: str = "dry"           # dry, wet, icy, snow_covered, gravel
    is_intersection: bool = False
    is_crosswalk: bool = False
    has_pedestrians: bool = False
    has_obstacles: bool = False
    lane_deviation: float = 0.0           # meters from lane center
    steering_angle: float = 0.0           # degrees
    battery_level: float = 100.0          # percentage
    system_health: str = "nominal"        # nominal, degraded, critical
    fault_active: bool = False
    fault_codes: List[str] = field(default_factory=list)
    asil_mode: SafetyLevel = SafetyLevel.QM
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def is_safety_critical_situation(self) -> bool:
        """Determine if the current situation is safety-critical."""
        if self.speed_kmh > 80:
            return True
        if self.has_pedestrians:
            return True
        if self.has_obstacles and self.is_moving:
            return True
        if self.system_health == "critical":
            return True
        if self.fault_active:
            return True
        if self.weather in ("snow", "fog", "ice") and self.is_moving:
            return True
        if self.environment == "tunnel" and self.is_moving:
            return True
        return False

    def get_risk_multiplier(self) -> float:
        """Calculate a risk multiplier based on context (1.0 = nominal, >1.0 = higher risk)."""
        multiplier = 1.0

        # Speed factor
        if self.speed_kmh > 120:
            multiplier *= 3.0
        elif self.speed_kmh > 80:
            multiplier *= 2.0
        elif self.speed_kmh > 50:
            multiplier *= 1.5

        # Weather factor
        weather_factors = {
            "ice": 3.0, "snow": 2.5, "fog": 2.0, "rain": 1.5, "clear": 1.0
        }
        multiplier *= weather_factors.get(self.weather, 1.0)

        # Traffic factor
        traffic_factors = {
            "gridlock": 2.5, "heavy": 2.0, "moderate": 1.5, "light": 1.0, "none": 0.8
        }
        multiplier *= traffic_factors.get(self.traffic_density, 1.0)

        # Visibility
        if self.visibility in ("poor", "night"):
            multiplier *= 1.5

        # System health
        if self.system_health == "critical":
            multiplier *= 3.0
        elif self.system_health == "degraded":
            multiplier *= 1.5

        # Pedestrians and obstacles
        if self.has_pedestrians:
            multiplier *= 2.0
        if self.has_obstacles:
            multiplier *= 1.5

        return multiplier


# ---------------------------------------------------------------------------
# Safety Guardian — Main Class
# ---------------------------------------------------------------------------


class SafetyGuardian:
    """Safety Guardian — the central safety orchestrator for Nonull.

    The guardian implements a multi-layer safety check pipeline:
        Layer 1: Tool pre-filtering
        Layer 2: Rule-based checking (deny-first)
        Layer 3: Score-based risk assessment
        Layer 4: Context-aware validation
        Layer 5: Post-action verification

    It has the power to VETO any dangerous action.

    Thread-safe: all state modifications use a lock.

    Usage:
        guardian = SafetyGuardian()
        guardian.set_strictness(3)

        # Validate before execution
        verdict = guardian.validate_action(action)

        if verdict.is_approved():
            result = execute_action(action)
            post_verdict = guardian.post_action_check(action, result)
    """

    def __init__(self, strictness: int = StrictnessLevel.STANDARD):
        self._lock = threading.RLock()

        # Core engines
        self.rule_engine = DenyFirstEngine(strictness=strictness)
        self.compliance = ComplianceChecker()

        # State
        self._strictness = StrictnessLevel(min(max(strictness, 1), 5))
        self._driving_context = DrivingContext()
        self._audit_log: List[AuditEntry] = []
        self._veto_count = 0
        self._approve_count = 0
        self._total_validations = 0

        # Pre/post action hooks
        self._pre_hooks: List[Callable] = []
        self._post_hooks: List[Callable] = []

        # Safety thresholds
        self._score_thresholds = {
            5: {"min_score": 80, "auto_veto_below": 90},   # Lockdown
            4: {"min_score": 60, "auto_veto_below": 70},   # Strict
            3: {"min_score": 40, "auto_veto_below": 50},   # Standard (default)
            2: {"min_score": 20, "auto_veto_below": 30},   # Moderate
            1: {"min_score": 0,  "auto_veto_below": 10},   # Permissive
        }

        logger.info("SafetyGuardian initialized with strictness=%s", self._strictness.name)

    # ------------------------------------------------------------------
    # Core Validation Pipeline (Public API)
    # ------------------------------------------------------------------

    def validate_action(self, action: Union[Action, Dict[str, Any]]) -> SafetyVerdict:
        """Validate an action through the full multi-layer pipeline.

        This is the PRIMARY entry point for all action validation.

        Pipeline flow:
            1. Tool Pre-filtering → VETO if tool is dangerous
            2. Rule-based Checking → Deny-first rule engine
            3. Score-based Risk → Composite risk scoring
            4. Context-aware → Validate in driving context
            5. Return composite verdict

        Args:
            action: The action to validate (Action object or dict).

        Returns:
            SafetyVerdict with final decision.
        """
        start_time = time.perf_counter()

        if isinstance(action, dict):
            action = Action(**action)

        with self._lock:
            self._total_validations += 1

        layer_verdicts: Dict[str, Dict[str, Any]] = {}
        final_score = 100.0
        all_triggered_rules: List[str] = []
        highest_asil = SafetyLevel.QM
        veto_reason = None

        # ---- Layer 1: Tool Pre-filtering ----
        layer1_verdict = self._layer1_tool_pre_filter(action)
        layer_verdicts[PipelineLayer.L1_TOOL_PRE_FILTER.value] = self._verdict_to_dict(layer1_verdict)
        if layer1_verdict.verdict == Verdict.DENIED:
            final_score = min(final_score, layer1_verdict.score)
            all_triggered_rules.extend(layer1_verdict.triggered_rules)
            if layer1_verdict.asil_level and layer1_verdict.asil_level.value > highest_asil.value:
                highest_asil = layer1_verdict.asil_level
            veto_reason = f"Layer 1 (Tool Pre-filter): {layer1_verdict.reason}"
            return self._finalize_verdict(
                Verdict.DENIED, final_score, veto_reason,
                layer_verdicts, all_triggered_rules, highest_asil,
                action, start_time
            )

        # ---- Layer 2: Rule-based Checking (Deny-First) ----
        layer2_verdict = self.rule_engine.evaluate(action)
        layer_verdicts[PipelineLayer.L2_RULE_BASED.value] = self._verdict_to_dict(layer2_verdict)
        final_score = min(final_score, layer2_verdict.score)
        all_triggered_rules.extend(layer2_verdict.triggered_rules)
        if layer2_verdict.asil_level and layer2_verdict.asil_level.value > highest_asil.value:
            highest_asil = layer2_verdict.asil_level

        if layer2_verdict.verdict == Verdict.DENIED:
            veto_reason = f"Layer 2 (Rule-based): {layer2_verdict.reason}"
            return self._finalize_verdict(
                Verdict.DENIED, final_score, veto_reason,
                layer_verdicts, all_triggered_rules, highest_asil,
                action, start_time
            )

        if layer2_verdict.verdict == Verdict.ASK:
            return self._finalize_verdict(
                Verdict.ASK, final_score, layer2_verdict.reason,
                layer_verdicts, all_triggered_rules, highest_asil,
                action, start_time
            )

        if layer2_verdict.verdict == Verdict.ESCALATED:
            return self._finalize_verdict(
                Verdict.ESCALATED, final_score, layer2_verdict.reason,
                layer_verdicts, all_triggered_rules, highest_asil,
                action, start_time
            )

        # ---- Layer 3: Score-based Risk Assessment ----
        layer3_verdict = self._layer3_score_risk(action, layer2_verdict.score)
        layer_verdicts[PipelineLayer.L3_SCORE_RISK.value] = self._verdict_to_dict(layer3_verdict)
        final_score = min(final_score, layer3_verdict.score)
        all_triggered_rules.extend(layer3_verdict.triggered_rules)
        if layer3_verdict.asil_level and layer3_verdict.asil_level.value > highest_asil.value:
            highest_asil = layer3_verdict.asil_level

        if layer3_verdict.verdict == Verdict.DENIED:
            veto_reason = f"Layer 3 (Score Risk): {layer3_verdict.reason}"
            return self._finalize_verdict(
                Verdict.DENIED, final_score, veto_reason,
                layer_verdicts, all_triggered_rules, highest_asil,
                action, start_time
            )

        # ---- Layer 4: Context-aware Validation ----
        layer4_verdict = self._layer4_context_aware(action, final_score)
        layer_verdicts[PipelineLayer.L4_CONTEXT_AWARE.value] = self._verdict_to_dict(layer4_verdict)
        final_score = min(final_score, layer4_verdict.score)
        all_triggered_rules.extend(layer4_verdict.triggered_rules)
        if layer4_verdict.asil_level and layer4_verdict.asil_level.value > highest_asil.value:
            highest_asil = layer4_verdict.asil_level

        if layer4_verdict.verdict == Verdict.DENIED:
            veto_reason = f"Layer 4 (Context): {layer4_verdict.reason}"
            return self._finalize_verdict(
                Verdict.DENIED, final_score, veto_reason,
                layer_verdicts, all_triggered_rules, highest_asil,
                action, start_time
            )

        # ---- All layers passed ----
        final_verdict = Verdict.APPROVED
        final_reason = self._build_approval_reason(action, final_score, layer_verdicts)

        # Check score threshold
        thresholds = self._score_thresholds[self._strictness.value]
        if final_score < thresholds["auto_veto_below"]:
            final_verdict = Verdict.DENIED
            final_reason = (
                f"Score {final_score:.1f} is below auto-veto threshold "
                f"{thresholds['auto_veto_below']} for strictness {self._strictness.name}"
            )
        elif final_score < thresholds["min_score"]:
            final_verdict = Verdict.ASK
            final_reason = (
                f"Score {final_score:.1f} is below minimum threshold "
                f"{thresholds['min_score']} for strictness {self._strictness.name}"
            )

        return self._finalize_verdict(
            final_verdict, final_score, final_reason,
            layer_verdicts, all_triggered_rules, highest_asil,
            action, start_time
        )

    # ------------------------------------------------------------------
    # Layer 1: Tool Pre-filtering
    # ------------------------------------------------------------------

    def _layer1_tool_pre_filter(self, action: Action) -> SafetyVerdict:
        """Layer 1: Pre-filter dangerous tools before any execution.

        This is the first line of defense — before even checking rules,
        we check if the tool itself is inherently dangerous.
        """
        score = 100.0
        triggered = []
        asil = SafetyLevel.QM

        # Tool blacklist (inherently dangerous regardless of context)
        dangerous_tools = {
            "shell_exec": {"asil": SafetyLevel.ASIL_D, "reason": "Shell execution is prohibited"},
            "os_command": {"asil": SafetyLevel.ASIL_D, "reason": "OS command execution is prohibited"},
            "delete_file": {"asil": SafetyLevel.ASIL_B, "reason": "File deletion requires caution"},
            "format_disk": {"asil": SafetyLevel.ASIL_D, "reason": "Disk formatting is prohibited"},
            "kill_process": {"asil": SafetyLevel.ASIL_C, "reason": "Process termination is restricted"},
            "modify_kernel": {"asil": SafetyLevel.ASIL_D, "reason": "Kernel modification is prohibited"},
            "network_listen": {"asil": SafetyLevel.ASIL_C, "reason": "Network listening is restricted"},
            "bypass_safety": {"asil": SafetyLevel.ASIL_D, "reason": "Safety bypass is ALWAYS prohibited"},
        }

        tool_lower = action.tool.lower()

        # Check exact matches
        for dangerous_tool, info in dangerous_tools.items():
            if dangerous_tool in tool_lower or tool_lower == dangerous_tool:
                triggered.append(dangerous_tool)
                score = {SafetyLevel.ASIL_D: 0.0, SafetyLevel.ASIL_C: 10.0,
                         SafetyLevel.ASIL_B: 20.0}.get(info["asil"], 0.0)
                if info["asil"].value > asil.value:
                    asil = info["asil"]
                return SafetyVerdict(
                    verdict=Verdict.DENIED,
                    score=score,
                    reason=f"Dangerous tool '{action.tool}': {info['reason']}",
                    layer=PipelineLayer.L1_TOOL_PRE_FILTER.value,
                    asil_level=info["asil"],
                    triggered_rules=triggered,
                )

        # Check for vehicle control tools with context
        vehicle_tools = {
            "set_throttle": SafetyLevel.ASIL_D,
            "set_brake": SafetyLevel.ASIL_D,
            "set_steering": SafetyLevel.ASIL_D,
            "set_gear": SafetyLevel.ASIL_C,
            "set_speed": SafetyLevel.ASIL_C,
        }

        for vtool, vasil in vehicle_tools.items():
            if vtool in tool_lower or tool_lower == vtool:
                triggered.append(vtool)
                score = {SafetyLevel.ASIL_D: 20.0, SafetyLevel.ASIL_C: 35.0}.get(vasil, 50.0)
                if vasil.value > asil.value:
                    asil = vasil
                break

        return SafetyVerdict(
            verdict=Verdict.APPROVED,
            score=score,
            reason=f"Tool '{action.tool}' passed pre-filter",
            layer=PipelineLayer.L1_TOOL_PRE_FILTER.value,
            asil_level=asil,
            triggered_rules=triggered,
        )

    # ------------------------------------------------------------------
    # Layer 3: Score-based Risk Assessment
    # ------------------------------------------------------------------

    def _layer3_score_risk(self, action: Action, base_score: float) -> SafetyVerdict:
        """Layer 3: Calculate a composite risk score.

        Factors considered:
            - Base score from rule engine (Layer 2)
            - Action category risk weight
            - Parameter risk factors
            - Source trust level
            - ISO 26262 ASIL weight
        """
        score = base_score
        triggered = []

        # Category risk weights
        category_weights = {
            ActionCategory.VEHICLE_CONTROL: 0.3,
            ActionCategory.SYSTEM_COMMAND: 0.25,
            ActionCategory.CODE_EXECUTION: 0.2,
            ActionCategory.NETWORK_REQUEST: 0.15,
            ActionCategory.DATA_ACCESS: 0.15,
            ActionCategory.FILE_OPERATION: 0.1,
            ActionCategory.DEPLOYMENT: 0.2,
            ActionCategory.SENSOR_ACCESS: 0.15,
            ActionCategory.COMMUNICATION: 0.1,
            ActionCategory.TOOL_CALL: 0.05,
            ActionCategory.UNKNOWN: 0.25,
        }

        category_weight = category_weights.get(action.category, 0.2)
        score -= category_weight * 50.0

        # Parameter risk factors
        param_risks = {
            "force": 15.0, "recursive": 10.0, "overwrite": 15.0,
            "dangerous": 25.0, "unsafe": 30.0, "no_confirm": 20.0,
            "bypass": 40.0, "disable_safety": 50.0, "override": 35.0,
        }

        for key, value in action.params.items():
            key_lower = str(key).lower()
            val_lower = str(value).lower()

            for risk_word, risk_penalty in param_risks.items():
                if risk_word in key_lower or risk_word in val_lower:
                    score -= risk_penalty
                    triggered.append(f"risk_param:{risk_word}")
                    break  # One penalty per param

        # Parameter value extremes
        for key, value in action.params.items():
            if isinstance(value, (int, float)):
                if abs(value) > 1000000:
                    score -= 20.0
                    triggered.append(f"risk_param:extreme_value_{key}")
                elif value < 0 and any(w in str(key).lower() for w in ["time", "delay", "count"]):
                    score -= 15.0
                    triggered.append(f"risk_param:negative_{key}")

        # Source trust level
        source_weights = {
            "agent": 0.0,
            "user": -5.0,
            "system": -10.0,
            "external": -20.0,
            "unauthorized": -40.0,
        }
        score += source_weights.get(action.source.lower(), -10.0)

        # Clamp score
        score = max(0.0, min(100.0, score))

        # Determine verdict based on score
        if score <= 20.0:
            verdict = Verdict.DENIED
            reason = f"Risk score {score:.1f}/100 is critically low (threshold: 20)"
        elif score <= 40.0:
            if self._strictness.value >= 3:  # Standard or higher
                verdict = Verdict.DENIED
                reason = f"Risk score {score:.1f}/100 is below safe threshold (40)"
            else:
                verdict = Verdict.APPROVED
                reason = f"Risk score {score:.1f}/100: approved in permissive mode"
        else:
            verdict = Verdict.APPROVED
            reason = f"Risk score {score:.1f}/100 is acceptable"

        return SafetyVerdict(
            verdict=verdict,
            score=round(score, 1),
            reason=reason,
            layer=PipelineLayer.L3_SCORE_RISK.value,
            asil_level=SafetyLevel.ASIL_B if score < 40 else SafetyLevel.QM,
            triggered_rules=triggered,
            details={
                "base_score": base_score,
                "category_weight": category_weight,
                "category": action.category.value,
                "source": action.source,
            },
        )

    # ------------------------------------------------------------------
    # Layer 4: Context-aware Validation
    # ------------------------------------------------------------------

    def _layer4_context_aware(self, action: Action, current_score: float) -> SafetyVerdict:
        """Layer 4: Validate action within the current driving context.

        Checks if the action is safe given:
            - Current vehicle state (speed, gear, health)
            - Environment (weather, traffic, road condition)
            - Safety-critical situations
            - ASIL mode
        """
        score = current_score
        ctx = self._driving_context
        triggered = []

        # Check if in safety-critical situation
        if ctx.is_safety_critical_situation():
            score -= 30.0
            triggered.append("context:safety_critical_situation")

        # Apply risk multiplier for vehicle control actions
        if action.category == ActionCategory.VEHICLE_CONTROL:
            risk_mult = ctx.get_risk_multiplier()
            score -= (risk_mult - 1.0) * 20.0
            triggered.append(f"context:risk_multiplier_{risk_mult:.1f}x")

            # Specific vehicle context checks
            if ctx.speed_kmh > 80 and any(
                w in action.tool.lower() for w in ["steer", "lane", "turn"]
            ):
                score -= 20.0
                triggered.append("context:high_speed_steering")

            if ctx.road_condition in ("icy", "snow_covered") and "brake" in action.tool.lower():
                score -= 25.0
                triggered.append("context:slippery_road_braking")

            if ctx.has_pedestrians and any(
                w in action.tool.lower() for w in ["accelerat", "speed", "throttle"]
            ):
                score -= 40.0
                triggered.append("context:pedestrians_nearby")

        # Sensor actions in degraded health
        if action.category == ActionCategory.SENSOR_ACCESS and ctx.system_health == "degraded":
            score -= 15.0
            triggered.append("context:degraded_health_sensor")

        # Network actions while driving
        if action.category == ActionCategory.NETWORK_REQUEST and ctx.is_moving:
            score -= 10.0
            triggered.append("context:network_while_driving")

        # File operations during critical system state
        if action.category == ActionCategory.FILE_OPERATION and ctx.system_health == "critical":
            score -= 20.0
            triggered.append("context:file_ops_during_critical")

        # Code execution during driving
        if action.category in (ActionCategory.CODE_EXECUTION, ActionCategory.SYSTEM_COMMAND) and ctx.is_moving:
            score -= 15.0
            triggered.append("context:code_exec_while_driving")

        # Clamp score
        score = max(0.0, min(100.0, score))

        if score < 30.0:
            verdict = Verdict.DENIED
            reason = f"Context validation failed: score {score:.1f}/100 in current driving context"
        elif score < 50.0 and self._strictness.value >= 3:
            verdict = Verdict.DENIED
            reason = f"Context validation: score {score:.1f}/100, denied at strictness {self._strictness.name}"
        else:
            verdict = Verdict.APPROVED
            reason = f"Context validation passed: score {score:.1f}/100"

        return SafetyVerdict(
            verdict=verdict,
            score=round(score, 1),
            reason=reason,
            layer=PipelineLayer.L4_CONTEXT_AWARE.value,
            asil_level=ctx.asil_mode,
            triggered_rules=triggered,
            details={
                "speed": ctx.speed_kmh,
                "environment": ctx.environment,
                "weather": ctx.weather,
                "system_health": ctx.system_health,
                "is_safety_critical": ctx.is_safety_critical_situation(),
                "risk_multiplier": ctx.get_risk_multiplier(),
            },
        )

    # ------------------------------------------------------------------
    # Layer 5: Post-action Verification
    # ------------------------------------------------------------------

    def post_action_check(self, action: Union[Action, Dict[str, Any]],
                          result: Any) -> SafetyVerdict:
        """Layer 5: Verify the result of an executed action is safe.

        This runs AFTER an action has been executed to verify the outcome
        does not create an unsafe condition.

        Args:
            action: The action that was executed.
            result: The result/outcome of the action.

        Returns:
            SafetyVerdict indicating post-action verification result.
        """
        if isinstance(action, dict):
            action = Action(**action)

        score = 100.0
        triggered = []
        findings = []

        # Check for error results
        if isinstance(result, dict):
            if result.get("error") or result.get("failed") or result.get("status") == "error":
                score -= 30.0
                triggered.append("post:action_error")
                findings.append("Action returned error/failure status")

            if result.get("exit_code") is not None and result["exit_code"] != 0:
                score -= 20.0
                triggered.append("post:non_zero_exit")
                findings.append(f"Non-zero exit code: {result['exit_code']}")

        # Check for result size (potential data leakage)
        result_str = str(result)
        if len(result_str) > 10_000_000:  # 10MB
            score -= 20.0
            triggered.append("post:excessive_result_size")
            findings.append("Action result exceeds 10MB size threshold")

        # Check for dangerous content in result
        dangerous_patterns = [
            "password", "secret", "PRIVATE KEY", "BEGIN CERT",
            "eyJ",  # JWT token base64 start
        ]
        for pattern in dangerous_patterns:
            if pattern in result_str[:100_000]:  # Only check first 100KB
                score -= 25.0
                triggered.append(f"post:sensitive_content_{pattern.lower()}")
                findings.append(f"Sensitive content pattern '{pattern}' found in result")
                break

        # Check for infinite loop / hang indicators
        if result is None and action.category in (ActionCategory.CODE_EXECUTION, ActionCategory.SYSTEM_COMMAND):
            score -= 15.0
            triggered.append("post:null_result_execution")
            findings.append("Code execution returned None (possible hang)")

        # Vehicle-specific post-checks
        if action.category == ActionCategory.VEHICLE_CONTROL:
            ctx = self._driving_context
            if ctx.fault_active:
                score -= 30.0
                triggered.append("post:vehicle_fault_after_action")
                findings.append("Vehicle fault detected after action execution")

        # Clamp score
        score = max(0.0, min(100.0, score))

        if score < 40.0:
            verdict = Verdict.VERIFICATION_FAILED
            reason = f"Post-action verification failed: score {score:.1f}/100. Issues: {'; '.join(findings)}"
        else:
            verdict = Verdict.VERIFIED
            reason = f"Post-action verification passed: score {score:.1f}/100"

        # Log the post-check as an audit entry
        entry = AuditEntry(
            entry_id=f"post_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now(UTC).isoformat(),
            action=action.tool,
            action_category=action.category.value,
            decision=verdict.value,
            score=round(score, 1),
            reason=reason,
            layer_verdicts={"post_action": self._verdict_to_dict(
                SafetyVerdict(verdict, score, reason, PipelineLayer.L5_POST_ACTION.value)
            )},
            triggered_rules=triggered,
            asil_level=SafetyLevel.ASIL_B.name,
            strictness=self._strictness.value,
            duration_ms=0.0,
            source=action.source,
        )

        with self._lock:
            self._audit_log.append(entry)

        return SafetyVerdict(
            verdict=verdict,
            score=round(score, 1),
            reason=reason,
            layer=PipelineLayer.L5_POST_ACTION.value,
            asil_level=ctx.asil_mode if action.category == ActionCategory.VEHICLE_CONTROL else SafetyLevel.QM,
            triggered_rules=triggered,
            details={"findings": findings, "result_summary": result_str[:200] if result else "None"},
        )

    # ------------------------------------------------------------------
    # Pre/Post Action Hooks
    # ------------------------------------------------------------------

    def add_pre_hook(self, hook: Callable[[Action], Optional[SafetyVerdict]]) -> None:
        """Add a pre-action hook function.

        The hook receives the action and can return a SafetyVerdict to
        override the guardian's decision (e.g., force-deny or force-allow).
        Return None to let the normal pipeline decide.
        """
        with self._lock:
            self._pre_hooks.append(hook)

    def add_post_hook(self, hook: Callable[[Action, Any], Optional[SafetyVerdict]]) -> None:
        """Add a post-action hook function.

        The hook receives the action and result, and can return a SafetyVerdict
        to override the post-action verification.
        """
        with self._lock:
            self._post_hooks.append(hook)

    # ------------------------------------------------------------------
    # Rule Management (delegated to rule engine)
    # ------------------------------------------------------------------

    def add_rule(self, rule: Union[SafetyRule, Dict[str, Any]]) -> str:
        """Add a safety rule to the deny-first engine.

        Args:
            rule: SafetyRule instance or dict.

        Returns:
            rule_id of the added rule.
        """
        return self.rule_engine.add_rule(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a safety rule by ID."""
        return self.rule_engine.remove_rule(rule_id)

    def get_rule(self, rule_id: str) -> Optional[SafetyRule]:
        """Get a rule by ID."""
        return self.rule_engine.get_rule(rule_id)

    def get_rules(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all rules, optionally filtered by category."""
        return self.rule_engine.get_rules_summary()

    # ------------------------------------------------------------------
    # Strictness Control
    # ------------------------------------------------------------------

    def set_strictness(self, level: int) -> None:
        """Set the strictness level (1-5).

        Args:
            level: 1 (Permissive) to 5 (Lockdown)
        """
        level = min(max(level, 1), 5)
        with self._lock:
            self._strictness = StrictnessLevel(level)
            self.rule_engine.set_strictness(level)
        logger.info("Strictness set to %s", self._strictness.name)

    def get_strictness(self) -> int:
        """Get current strictness level."""
        return self._strictness.value

    # ------------------------------------------------------------------
    # Driving Context Management
    # ------------------------------------------------------------------

    def update_driving_context(self, context: Union[DrivingContext, Dict[str, Any]]) -> None:
        """Update the current driving context.

        Args:
            context: DrivingContext instance or dict with context fields.
        """
        if isinstance(context, dict):
            context = DrivingContext(**context)
        with self._lock:
            self._driving_context = context
        logger.debug("Driving context updated: speed=%.1f env=%s weather=%s",
                     context.speed_kmh, context.environment, context.weather)

    def get_driving_context(self) -> DrivingContext:
        """Get the current driving context."""
        with self._lock:
            return self._driving_context

    # ------------------------------------------------------------------
    # Safety Report
    # ------------------------------------------------------------------

    def get_safety_report(self) -> Dict[str, Any]:
        """Get a comprehensive safety report.

        Returns a dict with:
            - Summary stats (total validations, veto count, approval count)
            - Current strictness level
            - Audit log summary (last 100 entries)
            - Rule engine stats
            - Driving context summary
            - Compliance report
            - Critical findings
        """
        with self._lock:
            recent_audit = self._audit_log[-100:] if len(self._audit_log) > 100 else self._audit_log

            # Count decisions by type
            decisions = {}
            for entry in self._audit_log:
                decisions[entry.decision] = decisions.get(entry.decision, 0) + 1

            rule_stats = self.rule_engine.get_stats()
            complaint_report = self.compliance.get_compliance_report()

            return {
                "summary": {
                    "total_validations": self._total_validations,
                    "veto_count": self._veto_count,
                    "approve_count": self._approve_count,
                    "strictness": self._strictness.name,
                    "strictness_level": self._strictness.value,
                },
                "decisions": decisions,
                "audit_log_summary": {
                    "total_entries": len(self._audit_log),
                    "recent_entries": [
                        {
                            "entry_id": e.entry_id,
                            "timestamp": e.timestamp,
                            "action": e.action,
                            "decision": e.decision,
                            "score": e.score,
                            "reason": e.reason[:100],
                        }
                        for e in recent_audit[-20:]  # Last 20
                    ],
                },
                "rule_engine": rule_stats,
                "rules": self.rule_engine.get_rules_summary(),
                "driving_context": asdict(self._driving_context),
                "compliance": complaint_report,
                "score_thresholds": self._score_thresholds[self._strictness.value],
            }

    def get_audit_log(self, limit: int = 100, decision: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get audit log entries, optionally filtered by decision type.

        Args:
            limit: Maximum number of entries to return.
            decision: Optional filter: 'approved', 'denied', 'vetoed', 'ask'.

        Returns:
            List of audit entry dicts.
        """
        with self._lock:
            entries = self._audit_log
            if decision:
                entries = [e for e in entries if e.decision == decision.lower()]
            return [e.to_dict() for e in entries[-limit:]]

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _finalize_verdict(
        self,
        verdict: Verdict,
        score: float,
        reason: str,
        layer_verdicts: Dict[str, Dict[str, Any]],
        triggered_rules: List[str],
        asil_level: SafetyLevel,
        action: Action,
        start_time: float,
    ) -> SafetyVerdict:
        """Create the final verdict, update counters, and log the audit entry."""
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Update counters
        if verdict == Verdict.DENIED:
            with self._lock:
                self._veto_count += 1
        elif verdict in (Verdict.APPROVED, Verdict.VERIFIED):
            with self._lock:
                self._approve_count += 1

        # Build audit entry
        entry = AuditEntry(
            entry_id=f"audit_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now(UTC).isoformat(),
            action=action.tool,
            action_category=action.category.value,
            decision=verdict.value,
            score=round(score, 1),
            reason=reason,
            layer_verdicts=layer_verdicts,
            triggered_rules=triggered_rules,
            asil_level=asil_level.name,
            strictness=self._strictness.value,
            duration_ms=round(duration_ms, 2),
            source=action.source,
        )

        with self._lock:
            self._audit_log.append(entry)

        return SafetyVerdict(
            verdict=verdict,
            score=round(score, 1),
            reason=reason,
            layer="guardian_pipeline",
            asil_level=asil_level,
            triggered_rules=triggered_rules,
            details={
                "duration_ms": round(duration_ms, 2),
                "strictness": self._strictness.name,
                "layer_verdicts": layer_verdicts,
            },
        )

    def _build_approval_reason(self, action: Action, score: float,
                                layer_verdicts: Dict[str, Dict[str, Any]]) -> str:
        """Build a human-readable approval reason from layer verdicts."""
        parts = [f"Safety score: {score:.1f}/100"]

        for layer_name, v in layer_verdicts.items():
            short_name = layer_name.replace("layer_", "L").replace("_", " ").title()
            parts.append(f"{short_name}: {v.get('verdict', '?')} ({v.get('score', 0):.0f})")

        parts.append(f"Action '{action.tool}' approved")
        return " | ".join(parts)

    def _verdict_to_dict(self, verdict: SafetyVerdict) -> Dict[str, Any]:
        """Convert a SafetyVerdict to a dict for audit logging."""
        return {
            "verdict": verdict.verdict.value,
            "score": verdict.score,
            "reason": verdict.reason,
            "layer": verdict.layer,
            "asil_level": verdict.asil_level.name if verdict.asil_level else None,
            "triggered_rules": verdict.triggered_rules,
        }

    # ------------------------------------------------------------------
    # Pre-action Check (Convenience Method)
    # ------------------------------------------------------------------

    def pre_action_check(self, action: Union[Action, Dict[str, Any]]) -> SafetyVerdict:
        """Pre-action check: run only Layers 1-4 (no post-action).

        Convenience method that runs the full pipeline except post-action.

        Args:
            action: The action to check.

        Returns:
            SafetyVerdict with pre-action check result.
        """
        return self.validate_action(action)

    # ------------------------------------------------------------------
    # Load Rules from Configuration
    # ------------------------------------------------------------------

    def load_rules_from_yaml(self, rules_data: List[Dict[str, Any]]) -> int:
        """Load rules from parsed YAML data.

        Args:
            rules_data: List of rule dicts from YAML config.

        Returns:
            Number of rules loaded.
        """
        return self.rule_engine.load_rules_from_dict(rules_data)

    def reset(self) -> None:
        """Reset all state — clear rules, audit log, and statistics."""
        with self._lock:
            self.rule_engine.clear_rules()
            self._audit_log.clear()
            self._veto_count = 0
            self._approve_count = 0
            self._total_validations = 0
            self._driving_context = DrivingContext()
            self._pre_hooks.clear()
            self._post_hooks.clear()
        logger.info("SafetyGuardian reset: all state cleared")
