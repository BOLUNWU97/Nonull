"""
Deny-First Rule Engine
======================

Inspired by Claude Code's 7-layer deny-first security architecture.

CORE PRINCIPLE: Deny rules ALWAYS override allow rules.
    - If ANY deny rule matches an action, it is DENIED regardless of allows.
    - Allow rules only grant permission when no deny rules match.
    - Ask rules trigger human-in-the-loop escalation.
    - Exception: an allow rule with higher priority than a matching deny rule
      creates an ESCALATED verdict requiring explicit human confirmation.

Rule Categories:
    CODE_SAFETY:         Dangerous code patterns (eval, exec, os.system, etc.)
    DATA_SAFETY:         Data leakage prevention (PII, credentials, keys)
    DEPLOY_SAFETY:       Deployment guardrails (production push, infra changes)
    COMMUNICATION_SAFETY: Output filtering (sensitive content, hallucinations)
    EXECUTION_SAFETY:    Resource limits (memory, CPU, disk, network)
    VEHICLE_SAFETY:      Vehicle control operations (steering, throttle, brakes)
    SENSOR_SAFETY:       Sensor data access patterns (camera, LiDAR, radar)
    EMERGENCY_SAFETY:    Emergency override patterns

Pattern Matching:
    - Supports exact match, glob pattern (*, ?), and regex patterns
    - Patterns match against tool names, action categories, parameter keys
    - Scoped matching (global, code, data, deploy, comm, exec, vehicle, sensor)

ISO 26262 Integration:
    Each rule carries an ASIL level that determines the severity of violation.
    ASIL-D violations are automatically escalated and logged.

Author: Nonull Safety Team
Version: 1.0.0
"""

from __future__ import annotations

import fnmatch
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple, Union

from safety import (
    Action,
    ActionCategory,
    RuleCategory,
    SafetyLevel,
    SafetyRule,
    SafetyVerdict,
    Verdict,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pattern Compilation Utilities
# ---------------------------------------------------------------------------


def _compile_pattern(pattern: str) -> Pattern:
    """Convert a pattern string to a compiled regex.

    Supports:
        - Exact match: passed through as escaped regex
        - Glob patterns (*, ?): converted to regex equivalents
        - Regex patterns: used as-is if wrapped in /pattern/flags
    """
    pattern = pattern.strip()

    # Regex pattern indicated by leading and trailing /
    if pattern.startswith("/") and len(pattern) > 1:
        last_slash = pattern.rfind("/")
        if last_slash > 0:
            regex_body = pattern[1:last_slash]
            flags_str = pattern[last_slash + 1:]
            flags = 0
            if "i" in flags_str:
                flags |= re.IGNORECASE
            if "m" in flags_str:
                flags |= re.MULTILINE
            return re.compile(regex_body, flags)

    # Glob pattern: contains * or ?
    if "*" in pattern or "?" in pattern:
        regex = fnmatch.translate(pattern)
        return re.compile(regex, re.IGNORECASE)

    # Exact match: escape and anchor
    return re.compile(f"^{re.escape(pattern)}$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Deny-First Rule Engine
# ---------------------------------------------------------------------------


class DenyFirstEngine:
    """Deny-First Rule Engine — the core of the safety system.

    Evaluates actions against a set of rules where deny rules ALWAYS
    take precedence over allow rules.

    Thread-safe: all rule modifications use a lock.

    Usage:
        engine = DenyFirstEngine()
        engine.load_default_rules()
        verdict = engine.evaluate(action)
    """

    def __init__(self, strictness: int = 3):
        self._rules: Dict[str, SafetyRule] = {}
        self._compiled_patterns: Dict[str, Pattern] = {}
        self._lock = threading.RLock()
        self.strictness = min(max(strictness, 1), 5)
        self._evaluation_count = 0
        self._deny_count = 0
        self._allow_count = 0

    # ------------------------------------------------------------------
    # Rule Management
    # ------------------------------------------------------------------

    def add_rule(self, rule: Union[SafetyRule, Dict[str, Any]]) -> str:
        """Add a rule to the engine.

        Args:
            rule: SafetyRule instance or dict with rule fields.

        Returns:
            rule_id of the added rule.
        """
        with self._lock:
            if isinstance(rule, dict):
                rule_obj = SafetyRule(**rule)
            else:
                rule_obj = rule

            if not rule_obj.rule_id:
                rule_obj.rule_id = f"rule_{uuid.uuid4().hex[:12]}"

            self._rules[rule_obj.rule_id] = rule_obj
            self._compiled_patterns[rule_obj.rule_id] = _compile_pattern(rule_obj.pattern)

            logger.debug(
                "Rule added: id=%s type=%s pattern=%s asil=%s",
                rule_obj.rule_id, rule_obj.rule_type, rule_obj.pattern, rule_obj.asil_level,
            )
            return rule_obj.rule_id

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID.

        Returns:
            True if rule was found and removed, False otherwise.
        """
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                self._compiled_patterns.pop(rule_id, None)
                logger.debug("Rule removed: id=%s", rule_id)
                return True
            return False

    def get_rule(self, rule_id: str) -> Optional[SafetyRule]:
        """Get a rule by ID."""
        with self._lock:
            return self._rules.get(rule_id)

    def get_rules(self, category: Optional[RuleCategory] = None) -> List[SafetyRule]:
        """Get all rules, optionally filtered by category."""
        with self._lock:
            if category is None:
                return list(self._rules.values())
            return [r for r in self._rules.values() if r.category == category]

    def get_rules_by_asil(self, asil_level: SafetyLevel) -> List[SafetyRule]:
        """Get all rules matching a given ASIL level."""
        with self._lock:
            return [r for r in self._rules.values() if r.asil_level == asil_level]

    def clear_rules(self) -> int:
        """Remove all rules.

        Returns:
            Number of rules removed.
        """
        with self._lock:
            count = len(self._rules)
            self._rules.clear()
            self._compiled_patterns.clear()
            logger.debug("All rules cleared (%d removed)", count)
            return count

    def enable_rule(self, rule_id: str, enabled: bool = True) -> bool:
        """Enable or disable a rule."""
        with self._lock:
            rule = self._rules.get(rule_id)
            if rule is None:
                return False
            rule.enabled = enabled
            return True

    def set_strictness(self, level: int) -> None:
        """Set the strictness level (1-5).

        Higher strictness levels cause more rules to be considered.
        Level 5 (LOCKDOWN) essentially denies everything.
        """
        self.strictness = min(max(level, 1), 5)
        logger.info("Strictness level set to %d", self.strictness)

    # ------------------------------------------------------------------
    # Default Rules Loading
    # ------------------------------------------------------------------

    def load_default_rules(self) -> int:
        """Load the built-in default safety rules.

        Returns:
            Number of rules loaded.
        """
        default_rules = self._get_builtin_rules()
        count = 0
        for rule_data in default_rules:
            try:
                self.add_rule(rule_data)
                count += 1
            except Exception as exc:
                logger.warning("Failed to load rule %s: %s", rule_data.get("rule_id", "?"), exc)
        logger.info("Loaded %d default rules", count)
        return count

    def load_rules_from_dict(self, rules: List[Dict[str, Any]]) -> int:
        """Load rules from a list of dictionaries.

        Args:
            rules: List of rule dicts.

        Returns:
            Number of rules successfully loaded.
        """
        count = 0
        for rule_data in rules:
            try:
                self.add_rule(rule_data)
                count += 1
            except Exception as exc:
                logger.warning("Failed to load rule: %s", exc)
        return count

    # ------------------------------------------------------------------
    # Rule Evaluation (Core Logic)
    # ------------------------------------------------------------------

    def evaluate(self, action: Union[Action, Dict[str, Any]]) -> SafetyVerdict:
        """Evaluate an action against all rules.

        This is the CORE method of the deny-first engine.

        Deny rules always override allow rules. Steps:
          1. Collect all matching rules (sorted by priority).
          2. If ANY deny rule matches → DENIED (unless overridden by higher-priority allow).
          3. If allow rule matches → APPROVED (with score).
          4. If ask rule matches → ASK (human-in-the-loop).
          5. If no rules match → depends on strictness level.

        Args:
            action: Action to evaluate.

        Returns:
            SafetyVerdict with the evaluation result.
        """
        if isinstance(action, dict):
            action = Action(**action)

        with self._lock:
            self._evaluation_count += 1

            # Find all matching rules, sorted by priority descending
            matching_rules = self._find_matching_rules(action)

            if not matching_rules:
                return self._no_rule_verdict(action)

            # Separate by type
            deny_rules = [r for r in matching_rules if r.rule_type == "deny"]
            allow_rules = [r for r in matching_rules if r.rule_type == "allow"]
            ask_rules = [r for r in matching_rules if r.rule_type == "ask"]

            # Check deny rules first (DENY-FIRST principle)
            if deny_rules:
                # Find highest-priority deny rule
                top_deny = max(deny_rules, key=lambda r: r.priority)

                # Check if any allow rule has higher priority than this deny
                # If so, escalate to human
                overriding_allows = [r for r in allow_rules if r.priority > top_deny.priority]
                if overriding_allows:
                    self._allow_count += 1
                    top_allow = max(overriding_allows, key=lambda r: r.priority)
                    return SafetyVerdict(
                        verdict=Verdict.ESCALATED,
                        score=50.0,
                        reason=(
                            f"Action '{action.tool}' matched deny rule '{top_deny.rule_id}' "
                            f"(priority {top_deny.priority}) but also matching allow rule "
                            f"'{top_allow.rule_id}' (priority {top_allow.priority}). "
                            f"Requires human confirmation."
                        ),
                        layer="deny_first",
                        asil_level=top_deny.asil_level,
                        triggered_rules=[top_deny.rule_id, top_allow.rule_id],
                        details={
                            "matching_deny_rules": [r.rule_id for r in deny_rules],
                            "matching_allow_rules": [r.rule_id for r in allow_rules],
                            "matching_ask_rules": [r.rule_id for r in ask_rules],
                        },
                    )

                # Deny rules win
                self._deny_count += 1
                top_asil = max(r.asil_level for r in deny_rules)
                reasons = [f"Rule '{r.rule_id}': {r.reason}" for r in deny_rules]
                return SafetyVerdict(
                    verdict=Verdict.DENIED,
                    score=self._deny_score(deny_rules),
                    reason=f"Action denied by {len(deny_rules)} rule(s): {'; '.join(reasons)}",
                    layer="deny_first",
                    asil_level=top_asil,
                    triggered_rules=[r.rule_id for r in deny_rules],
                    details={
                        "matching_deny_rules": [r.rule_id for r in deny_rules],
                        "matching_allow_rules": [r.rule_id for r in allow_rules],
                        "matching_ask_rules": [r.rule_id for r in ask_rules],
                    },
                )

            # Check ask rules
            if ask_rules:
                top_ask = max(ask_rules, key=lambda r: r.priority)
                return SafetyVerdict(
                    verdict=Verdict.ASK,
                    score=60.0,
                    reason=f"Action '{action.tool}' requires human confirmation: {top_ask.reason}",
                    layer="deny_first",
                    asil_level=top_ask.asil_level,
                    triggered_rules=[top_ask.rule_id],
                    details={
                        "matching_deny_rules": [],
                        "matching_allow_rules": [r.rule_id for r in allow_rules],
                        "matching_ask_rules": [r.rule_id for r in ask_rules],
                    },
                )

            # Allow rules match
            if allow_rules:
                self._allow_count += 1
                max_score = min(100.0, 70.0 + 10.0 * len(allow_rules))
                top_allow = max(allow_rules, key=lambda r: r.priority)
                return SafetyVerdict(
                    verdict=Verdict.APPROVED,
                    score=max_score,
                    reason=f"Action approved by rule '{top_allow.rule_id}': {top_allow.reason}",
                    layer="deny_first",
                    asil_level=top_allow.asil_level,
                    triggered_rules=[r.rule_id for r in allow_rules],
                    details={
                        "matching_deny_rules": [],
                        "matching_allow_rules": [r.rule_id for r in allow_rules],
                        "matching_ask_rules": [],
                    },
                )

            # Should not reach here, but just in case
            return self._no_rule_verdict(action)

    def _find_matching_rules(self, action: Action) -> List[SafetyRule]:
        """Find all rules that match the given action."""
        matching = []
        for rule_id, rule in self._rules.items():
            if not rule.enabled:
                continue

            # Check ASIL filter based on strictness
            if not self._asil_allowed(rule.asil_level):
                continue

            # Check scope
            if not self._scope_matches(rule.scope, action):
                continue

            # Check pattern against tool name, category, and params
            compiled = self._compiled_patterns.get(rule_id)
            if compiled is None:
                continue

            if self._pattern_matches(compiled, rule.pattern, action):
                matching.append(rule)

        # Sort by priority descending (highest priority first)
        matching.sort(key=lambda r: r.priority, reverse=True)
        return matching

    def _pattern_matches(self, compiled: Pattern, raw_pattern: str, action: Action) -> bool:
        """Check if a compiled pattern matches the action."""
        # Match against tool name
        if compiled.search(action.tool):
            return True

        # Match against category
        if compiled.search(action.category.value):
            return True

        # Match against action ID
        if compiled.search(action.action_id):
            return True

        # Match against source
        if compiled.search(action.source):
            return True

        # Match against parameter keys/values
        for key, value in action.params.items():
            if compiled.search(str(key)) or compiled.search(str(value)):
                return True

        # Match against context keys/values
        for key, value in action.context.items():
            if compiled.search(str(key)) or compiled.search(str(value)):
                return True

        return False

    def _scope_matches(self, scope: str, action: Action) -> bool:
        """Check if a rule scope applies to the action."""
        if scope == "global":
            return True

        scope_category_map = {
            "code": ActionCategory.CODE_EXECUTION,
            "data": ActionCategory.DATA_ACCESS,
            "deploy": ActionCategory.DEPLOYMENT,
            "comm": ActionCategory.COMMUNICATION,
            "exec": ActionCategory.EXECUTION_SAFETY,
            "vehicle": ActionCategory.VEHICLE_CONTROL,
            "sensor": ActionCategory.SENSOR_ACCESS,
            "file": ActionCategory.FILE_OPERATION,
            "network": ActionCategory.NETWORK_REQUEST,
            "system": ActionCategory.SYSTEM_COMMAND,
            "tool": ActionCategory.TOOL_CALL,
        }

        mapped = scope_category_map.get(scope.lower())
        if mapped is None:
            return True  # Unknown scope, allow by default
        return mapped == action.category

    def _asil_allowed(self, asil_level: SafetyLevel) -> bool:
        """Check if this ASIL level is considered given current strictness.

        Higher strictness levels consider lower ASIL levels.
        Lockdown (strictness=5) considers ALL ASIL levels.
        """
        # strictness 1 -> only ASIL-D
        # strictness 2 -> ASIL-C and above
        # strictness 3 -> ASIL-B and above (default)
        # strictness 4 -> ASIL-A and above
        # strictness 5 -> ALL (including QM and NONE)
        thresholds = {1: SafetyLevel.ASIL_D, 2: SafetyLevel.ASIL_C,
                      3: SafetyLevel.ASIL_B, 4: SafetyLevel.ASIL_A,
                      5: SafetyLevel.NONE}
        threshold = thresholds.get(self.strictness, SafetyLevel.ASIL_B)
        return asil_level.value >= threshold.value

    def _no_rule_verdict(self, action: Action) -> SafetyVerdict:
        """Generate verdict when no rules match the action.

        Behavior depends on strictness level:
            - 1 (Permissive):  Approved with warning
            - 2 (Moderate):    Approved with score=50
            - 3 (Standard):    Ask for confirmation
            - 4 (Strict):      Denied
            - 5 (Lockdown):    Denied with low score
        """
        if self.strictness <= 1:
            return SafetyVerdict(
                verdict=Verdict.APPROVED,
                score=40.0,
                reason=f"No rules matched action '{action.tool}'. Permissive mode: approved with warning.",
                layer="deny_first",
            )
        elif self.strictness == 2:
            return SafetyVerdict(
                verdict=Verdict.APPROVED,
                score=50.0,
                reason=f"No rules matched action '{action.tool}'. Moderate mode: approved with caution.",
                layer="deny_first",
            )
        elif self.strictness == 3:
            self._deny_count += 1
            return SafetyVerdict(
                verdict=Verdict.ASK,
                score=30.0,
                reason=f"No rules matched action '{action.tool}'. Standard mode: requires confirmation.",
                layer="deny_first",
            )
        else:
            self._deny_count += 1
            return SafetyVerdict(
                verdict=Verdict.DENIED,
                score=10.0 if self.strictness == 4 else 0.0,
                reason=(
                    f"Action '{action.tool}' denied: no matching allow rules "
                    f"and strictness level is {self.strictness}."
                ),
                layer="deny_first",
                asil_level=SafetyLevel.ASIL_D if self.strictness == 5 else SafetyLevel.ASIL_B,
            )

    def _deny_score(self, deny_rules: List[SafetyRule]) -> float:
        """Calculate a safety score for a denied action (always low)."""
        if not deny_rules:
            return 50.0
        max_asil = max(r.asil_level.value for r in deny_rules)
        # ASIL-D -> score 0, ASIL-A -> score 25, QM -> score 35
        base = {5: 0.0, 4: 5.0, 3: 10.0, 2: 20.0, 1: 30.0, 0: 35.0}
        return base.get(max_asil, 0.0)

    # ------------------------------------------------------------------
    # Built-in Default Rules
    # ------------------------------------------------------------------

    def _get_builtin_rules(self) -> List[Dict[str, Any]]:
        """Return the built-in safety rules.

        These cover all rule categories and ASIL levels.
        """
        return [
            # ===== CODE SAFETY =====
            {
                "rule_id": "deny_code_eval",
                "rule_type": "deny",
                "pattern": "eval",
                "category": "code_safety",
                "scope": "code",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Arbitrary code evaluation is a critical security risk",
                "priority": 100,
            },
            {
                "rule_id": "deny_code_exec",
                "rule_type": "deny",
                "pattern": "exec",
                "category": "code_safety",
                "scope": "code",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Arbitrary code execution is prohibited",
                "priority": 100,
            },
            {
                "rule_id": "deny_os_system",
                "rule_type": "deny",
                "pattern": "os.system",
                "category": "code_safety",
                "scope": "code",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Direct system shell access is prohibited",
                "priority": 100,
            },
            {
                "rule_id": "deny_subprocess_shell",
                "rule_type": "deny",
                "pattern": "subprocess.*shell=True",
                "category": "code_safety",
                "scope": "code",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Shell-based subprocess execution is prohibited",
                "priority": 100,
            },
            {
                "rule_id": "deny_compile",
                "rule_type": "deny",
                "pattern": "compile",
                "category": "code_safety",
                "scope": "code",
                "asil_level": SafetyLevel.ASIL_C,
                "reason": "Dynamic code compilation is restricted",
                "priority": 80,
            },
            {
                "rule_id": "deny_import_unsafe",
                "rule_type": "deny",
                "pattern": "__import__",
                "category": "code_safety",
                "scope": "code",
                "asil_level": SafetyLevel.ASIL_C,
                "reason": "Dynamic imports are restricted for safety",
                "priority": 80,
            },
            {
                "rule_id": "deny_pickle",
                "rule_type": "deny",
                "pattern": "pickle.loads",
                "category": "code_safety",
                "scope": "code",
                "asil_level": SafetyLevel.ASIL_C,
                "reason": "Unsafe deserialization via pickle is prohibited",
                "priority": 90,
            },
            {
                "rule_id": "deny_ctypes",
                "rule_type": "deny",
                "pattern": "ctypes",
                "category": "code_safety",
                "scope": "code",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Direct C library access via ctypes is prohibited",
                "priority": 100,
            },
            {
                "rule_id": "deny_injection_patterns",
                "rule_type": "deny",
                "pattern": "/\\b(SELECT|DROP|DELETE|INSERT|UPDATE)\\b.*\\bFROM\\b/i",
                "category": "code_safety",
                "scope": "code",
                "asil_level": SafetyLevel.ASIL_C,
                "reason": "SQL injection patterns are prohibited",
                "priority": 90,
            },

            # ===== DATA SAFETY =====
            {
                "rule_id": "deny_credential_access",
                "rule_type": "deny",
                "pattern": "/password|secret|credential|api_key|token|private_key/i",
                "category": "data_safety",
                "scope": "data",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Access to credentials and secrets is prohibited",
                "priority": 100,
            },
            {
                "rule_id": "deny_pii_access",
                "rule_type": "deny",
                "pattern": "/ssn|social_security|credit_card|passport|driver.?license/i",
                "category": "data_safety",
                "scope": "data",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Access to personally identifiable information is prohibited",
                "priority": 100,
            },
            {
                "rule_id": "deny_medical_data",
                "rule_type": "deny",
                "pattern": "/hipaa|phi|patient_record|medical_history/i",
                "category": "data_safety",
                "scope": "data",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Access to protected health information is prohibited",
                "priority": 100,
            },
            {
                "rule_id": "deny_data_exfiltration",
                "rule_type": "deny",
                "pattern": "/exfiltrat|data_leak|unauthorized_transfer/i",
                "category": "data_safety",
                "scope": "data",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Data exfiltration patterns are prohibited",
                "priority": 100,
            },
            {
                "rule_id": "deny_config_secrets",
                "rule_type": "deny",
                "pattern": "*.env*",
                "category": "data_safety",
                "scope": "file",
                "asil_level": SafetyLevel.ASIL_C,
                "reason": "Environment files may contain secrets",
                "priority": 80,
            },
            {
                "rule_id": "deny_keychain_access",
                "rule_type": "deny",
                "pattern": "keychain",
                "category": "data_safety",
                "scope": "data",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Direct keychain access is prohibited",
                "priority": 100,
            },

            # ===== DEPLOY SAFETY =====
            {
                "rule_id": "deny_prod_deploy",
                "rule_type": "deny",
                "pattern": "/production|prod.*deploy|deploy.*prod/i",
                "category": "deploy_safety",
                "scope": "deploy",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Production deployments require human approval",
                "priority": 100,
            },
            {
                "rule_id": "ask_infra_change",
                "rule_type": "ask",
                "pattern": "/terraform|ansible|cloudformation|kubectl|helm/i",
                "category": "deploy_safety",
                "scope": "deploy",
                "asil_level": SafetyLevel.ASIL_C,
                "reason": "Infrastructure changes require confirmation",
                "priority": 70,
            },
            {
                "rule_id": "deny_privilege_escalation",
                "rule_type": "deny",
                "pattern": "/chmod.*777|sudo.*-u root|setuid|setgid/i",
                "category": "deploy_safety",
                "scope": "code",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Privilege escalation patterns are prohibited",
                "priority": 100,
            },
            {
                "rule_id": "deny_kube_delete",
                "rule_type": "deny",
                "pattern": "kubectl.*delete",
                "category": "deploy_safety",
                "scope": "deploy",
                "asil_level": SafetyLevel.ASIL_C,
                "reason": "Kubernetes resource deletion requires human approval",
                "priority": 90,
            },

            # ===== COMMUNICATION SAFETY =====
            {
                "rule_id": "deny_external_api_sensitive",
                "rule_type": "deny",
                "pattern": "/send.*(credential|password|token|secret)/i",
                "category": "communication_safety",
                "scope": "comm",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Sending sensitive data externally is prohibited",
                "priority": 100,
            },
            {
                "rule_id": "deny_hallucination_risk",
                "rule_type": "deny",
                "pattern": "/guarantee|100%.*safe|perfectly.*safe|no.*risk|always.*works/i",
                "category": "communication_safety",
                "scope": "comm",
                "asil_level": SafetyLevel.ASIL_B,
                "reason": "Overconfidence and false guarantees in safety-critical communication",
                "priority": 60,
            },

            # ===== EXECUTION SAFETY =====
            {
                "rule_id": "deny_excessive_memory",
                "rule_type": "deny",
                "pattern": "*/dev/shm|mmap.*1024.*1024|allocate.*GB/i",
                "category": "execution_safety",
                "scope": "exec",
                "asil_level": SafetyLevel.ASIL_B,
                "reason": "Excessive memory allocation is restricted",
                "priority": 60,
            },
            {
                "rule_id": "deny_fork_bomb",
                "rule_type": "deny",
                "pattern": "/fork.*while|while.*fork|os.fork|subprocess.*Popen.*loop/i",
                "category": "execution_safety",
                "scope": "exec",
                "asil_level": SafetyLevel.ASIL_C,
                "reason": "Fork bombs and infinite process creation are prohibited",
                "priority": 100,
            },
            {
                "rule_id": "deny_infinite_loop",
                "rule_type": "deny",
                "pattern": "/while.*True|while.*1|while.*:/i",
                "category": "execution_safety",
                "scope": "code",
                "asil_level": SafetyLevel.ASIL_B,
                "reason": "Infinite loops without safety break condition",
                "priority": 60,
            },

            # ===== VEHICLE SAFETY =====
            {
                "rule_id": "deny_brake_disable",
                "rule_type": "deny",
                "pattern": "/brake.*(disable|off|override|bypass)/i",
                "category": "vehicle_safety",
                "scope": "vehicle",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Disabling brakes is ALWAYS unsafe - ASIL-D violation",
                "priority": 100,
            },
            {
                "rule_id": "deny_steering_override",
                "rule_type": "deny",
                "pattern": "/steering.*(override|disable|bypass|disconnect)/i",
                "category": "vehicle_safety",
                "scope": "vehicle",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Steering system override is ALWAYS unsafe - ASIL-D violation",
                "priority": 100,
            },
            {
                "rule_id": "deny_throttle_unsafe",
                "rule_type": "deny",
                "pattern": "/throttle.*(max|full|unlimited|override|disable.*limit)/i",
                "category": "vehicle_safety",
                "scope": "vehicle",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Unrestricted throttle control is unsafe - ASIL-D violation",
                "priority": 100,
            },
            {
                "rule_id": "deny_airbag_disable",
                "rule_type": "deny",
                "pattern": "/airbag|srs|supplemental.*restraint.*disable/i",
                "category": "vehicle_safety",
                "scope": "vehicle",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Disabling safety restraint systems is ALWAYS fatal - ASIL-D",
                "priority": 100,
            },
            {
                "rule_id": "deny_speed_limit_override",
                "rule_type": "deny",
                "pattern": "/speed.*(limit|governor).*(override|disable|bypass)/i",
                "category": "vehicle_safety",
                "scope": "vehicle",
                "asil_level": SafetyLevel.ASIL_C,
                "reason": "Speed limit override is a critical safety violation",
                "priority": 90,
            },
            {
                "rule_id": "deny_lane_departure_disable",
                "rule_type": "deny",
                "pattern": "/lane.*(departure|keep|assist).*(disable|off)/i",
                "category": "vehicle_safety",
                "scope": "vehicle",
                "asil_level": SafetyLevel.ASIL_B,
                "reason": "Lane keeping assist should not be disabled without driver confirmation",
                "priority": 70,
            },
            {
                "rule_id": "ask_emergency_maneuver",
                "rule_type": "ask",
                "pattern": "/emergency.*(brake|steer|stop|maneuver|avoid)/i",
                "category": "vehicle_safety",
                "scope": "vehicle",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Emergency maneuvers require human confirmation",
                "priority": 100,
            },

            # ===== SENSOR SAFETY =====
            {
                "rule_id": "deny_camera_disable",
                "rule_type": "deny",
                "pattern": "/camera.*(disable|off|blind|block)/i",
                "category": "sensor_safety",
                "scope": "sensor",
                "asil_level": SafetyLevel.ASIL_C,
                "reason": "Disabling camera sensors is a safety risk",
                "priority": 90,
            },
            {
                "rule_id": "deny_lidar_disable",
                "rule_type": "deny",
                "pattern": "/lidar.*(disable|off|blind|block)/i",
                "category": "sensor_safety",
                "scope": "sensor",
                "asil_level": SafetyLevel.ASIL_C,
                "reason": "Disabling LiDAR sensors is a safety risk",
                "priority": 90,
            },
            {
                "rule_id": "deny_radar_disable",
                "rule_type": "deny",
                "pattern": "/radar.*(disable|off|blind|block)/i",
                "category": "sensor_safety",
                "scope": "sensor",
                "asil_level": SafetyLevel.ASIL_C,
                "reason": "Disabling radar sensors is a safety risk",
                "priority": 90,
            },
            {
                "rule_id": "deny_sensor_calibration_change",
                "rule_type": "deny",
                "pattern": "/sensor.*(calibrat|offset|bias).*(change|modify|write)/i",
                "category": "sensor_safety",
                "scope": "sensor",
                "asil_level": SafetyLevel.ASIL_C,
                "reason": "Modifying sensor calibration without validation is unsafe",
                "priority": 80,
            },

            # ===== EMERGENCY SAFETY =====
            {
                "rule_id": "deny_override_safety_critical",
                "rule_type": "deny",
                "pattern": "/override.*(safety|critical|protect|guard)/i",
                "category": "emergency_safety",
                "scope": "global",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Overriding any safety-critical system is ALWAYS prohibited",
                "priority": 100,
            },
            {
                "rule_id": "deny_safety_monitor_disable",
                "rule_type": "deny",
                "pattern": "/safety.*(monitor|watchdog|guard).*(disable|stop|kill|off)/i",
                "category": "emergency_safety",
                "scope": "global",
                "asil_level": SafetyLevel.ASIL_D,
                "reason": "Disabling safety monitors is ALWAYS fatal - ASIL-D violation",
                "priority": 100,
            },
            {
                "rule_id": "allow_safe_read_ops",
                "rule_type": "allow",
                "pattern": "/^(read|get|fetch|query|list|find|search|check|verify)/i",
                "category": "code_safety",
                "scope": "code",
                "asil_level": SafetyLevel.QM,
                "reason": "Read-only operations are generally safe",
                "priority": 10,
            },
            {
                "rule_id": "allow_safe_file_read",
                "rule_type": "allow",
                "pattern": "*.py",
                "category": "code_safety",
                "scope": "file",
                "asil_level": SafetyLevel.QM,
                "reason": "Reading Python source files is generally safe",
                "priority": 10,
            },
        ]

    # ------------------------------------------------------------------
    # Statistics and Reporting
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Get evaluation statistics."""
        with self._lock:
            total = self._evaluation_count
            return {
                "total_evaluations": total,
                "denied": self._deny_count,
                "approved": self._allow_count,
                "strictness": self.strictness,
                "total_rules": len(self._rules),
                "deny_rules": len([r for r in self._rules.values() if r.rule_type == "deny"]),
                "allow_rules": len([r for r in self._rules.values() if r.rule_type == "allow"]),
                "ask_rules": len([r for r in self._rules.values() if r.rule_type == "ask"]),
                "deny_rate": round(self._deny_count / total, 4) if total > 0 else 0.0,
            }

    def get_rules_summary(self) -> List[Dict[str, Any]]:
        """Get a summary of all rules for reporting."""
        with self._lock:
            return [
                {
                    "rule_id": r.rule_id,
                    "type": r.rule_type,
                    "category": r.category.value,
                    "asil": r.asil_level.name,
                    "enabled": r.enabled,
                    "priority": r.priority,
                    "reason": r.reason,
                }
                for r in self._rules.values()
            ]
