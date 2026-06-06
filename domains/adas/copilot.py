"""
Nonull Co-Pilot: Proactive Alert System

Generates contextual driving alerts, tips, and warnings based on the
active persona and real-time telemetry context.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from domains.adas.personas import DrivingPersona, PersonaType


# ---------------------------------------------------------------------------
# Alert severity
# ---------------------------------------------------------------------------

class AlertSeverity(str, enum.Enum):
    """Severity level for a Co-Pilot alert."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    """
    A single alert raised by the Co-Pilot.

    Attributes
    ----------
    message: str
        Human-readable alert text.
    severity: AlertSeverity
        How urgent this alert is.
    category: str
        High-level category (e.g. "speed", "braking", "awareness").
    timestamp: float
        Unix timestamp when the alert was created.
    source: str
        Identifier of the sub-system that raised this alert.
    dismissable: bool
        Whether the user can dismiss this alert manually.
    ttl_seconds: Optional[float]
        If set, the alert expires after this many seconds.
    """

    message: str
    severity: AlertSeverity = AlertSeverity.INFO
    category: str = "general"
    timestamp: float = field(default_factory=time.time)
    source: str = "copilot"
    dismissable: bool = True
    ttl_seconds: Optional[float] = None

    @property
    def expired(self) -> bool:
        """Check whether the alert has exceeded its TTL."""
        if self.ttl_seconds is None:
            return False
        return (time.time() - self.timestamp) > self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category,
            "timestamp": self.timestamp,
            "source": self.source,
            "dismissable": self.dismissable,
            "ttl_seconds": self.ttl_seconds,
        }

    def __repr__(self) -> str:
        return (
            f"Alert({self.message!r}, severity={self.severity.value!r}, "
            f"category={self.category!r})"
        )


# ---------------------------------------------------------------------------
# Telemetry context (lightweight snapshot)
# ---------------------------------------------------------------------------

@dataclass
class TelemetryContext:
    """
    A snapshot of driving conditions at a point in time.

    All numeric fields should be normalised 0.0–1.0 where applicable
    so that rules can compare them uniformly.
    """

    speed_normalised: float = 0.5  # 0 = stopped, 1 = well above limit
    acceleration_jerk: float = 0.0  # 0 = buttery smooth, 1 = jarring
    braking_harshness: float = 0.0  # 0 = gentle, 1 = panic
    following_distance: float = 0.7  # 0 = tailgating, 1 = safe gap
    lane_deviation: float = 0.0  # 0 = centred, 1 = wandering badly
    cornering_force: float = 0.3  # 0 = straight line, 1 =极限 cornering
    mirror_check_rate: float = 0.5  # 0 = never, 1 = constant
    hazard_proximity: float = 0.0  # 0 = clear, 1 = immediate threat
    fatigue_estimate: float = 0.0  # 0 = alert, 1 = dangerously tired

    def __getitem__(self, key: str) -> float:
        return getattr(self, key)

    def __setitem__(self, key: str, value: float) -> None:
        setattr(self, key, value)


# ---------------------------------------------------------------------------
# Rule definition
# ---------------------------------------------------------------------------

@dataclass
class AlertRule:
    """
    A named rule that checks telemetry and emits an Alert when triggered.

    Attributes
    ----------
    name: str
        Unique rule identifier.
    description: str
        What the rule checks.
    condition_fn: callable
        ``fn(context: TelemetryContext) -> bool`` — returns True when alert
        should fire.
    build_alert_fn: callable
        ``fn(context: TelemetryContext) -> Alert`` — constructs the alert.
    cooldown_seconds: float
        Minimum time between consecutive fires for this rule.
    """

    name: str
    description: str
    condition_fn: Any  # Callable[[TelemetryContext], bool]
    build_alert_fn: Any  # Callable[[TelemetryContext], Alert]
    cooldown_seconds: float = 10.0

    _last_fired: float = 0.0

    def check(self, ctx: TelemetryContext, now: float | None = None) -> Optional[Alert]:
        """Evaluate the rule; return an Alert if triggered and off cooldown."""
        now = now or time.time()
        if now - self._last_fired < self.cooldown_seconds:
            return None
        if self.condition_fn(ctx):
            self._last_fired = now
            return self.build_alert_fn(ctx)
        return None


# ---------------------------------------------------------------------------
# CoPilot
# ---------------------------------------------------------------------------

class CoPilot:
    """
    Proactive driving co-pilot that monitors context and raises alerts
    shaped by the active DrivingPersona.

    Usage
    -----
    >>> copilot = CoPilot(persona=DrivingPersona.conservative())
    >>> alert = copilot.evaluate(TelemetryContext(speed_normalised=0.95))
    >>> if alert:
    ...     print(alert.message)
    """

    def __init__(
        self,
        persona: Any = None,
        *,
        rules: Optional[List[AlertRule]] = None,
        enable_default_rules: bool = True,
        alert_history_max: int = 200,
    ) -> None:
        # Allow passing a PersonaType (or a name string) for convenience.
        if persona is None or isinstance(persona, PersonaType):
            pt = persona or PersonaType.VETERAN
            persona = DrivingPersona.for_type(pt)
        elif isinstance(persona, str):
            persona = DrivingPersona.for_type(PersonaType(persona.lower()))

        self.persona = persona
        self._rules: List[AlertRule] = []
        self._alerts: List[Alert] = []
        self._alert_history: List[Alert] = []
        self._alert_history_max = alert_history_max

        if enable_default_rules:
            self._add_default_rules()
        if rules:
            self._rules.extend(rules)

    # ------------------------------------------------------------------
    # Compatibility helpers (used by PersonaOrchestrator)
    # ------------------------------------------------------------------

    def scan_context(self, context: Dict[str, Any]) -> List[Alert]:
        """
        Scan a context dict for issues and return any alerts raised.

        Wraps :meth:`evaluate_all` with a TelemetryContext built from the dict.
        Unknown keys are ignored.
        """
        ctx = TelemetryContext()
        for key, value in (context or {}).items():
            if hasattr(ctx, key) and isinstance(value, (int, float)):
                setattr(ctx, key, max(0.0, min(1.0, float(value))))
        return self.evaluate_all(ctx)

    def get_daily_brief(self) -> str:
        """Generate a brief daily status string in the active persona's voice."""
        stats = {
            "persona": self.persona.persona_type.value,
            "active_alerts": self.active_count,
            "total_raised": self.total_raised,
        }
        if stats["total_raised"] == 0:
            tip = "All clear. Drive safe."
        elif stats["active_alerts"] > 0:
            tip = self.persona.generate_phrase("critical")
        else:
            tip = self.persona.generate_phrase("positive")
        return (
            f"[{stats['persona'].upper()}] "
            f"Active alerts: {stats['active_alerts']} | "
            f"Total raised: {stats['total_raised']} | "
            f"{tip}"
        )

    # ------------------------------------------------------------------
    # Rule registration
    # ------------------------------------------------------------------

    def add_rule(self, rule: AlertRule) -> None:
        """Register a new alert rule."""
        self._rules.append(rule)

    def remove_rule(self, rule_name: str) -> bool:
        """Remove a rule by name. Returns True if found and removed."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != rule_name]
        return len(self._rules) < before

    # ------------------------------------------------------------------
    # Core evaluation
    # ------------------------------------------------------------------

    def evaluate(self, context: TelemetryContext) -> Optional[Alert]:
        """
        Run all rules against *context*. Returns the **highest-severity**
        alert that fires (or None if nothing triggered).
        """
        fired: List[Alert] = []
        for rule in self._rules:
            alert = rule.check(context)
            if alert is not None:
                fired.append(alert)

        if not fired:
            return None

        # Pick most severe; break ties by timestamp (oldest first → more urgent)
        fired.sort(key=lambda a: (
            {"critical": 0, "warning": 1, "info": 2}[a.severity.value],
            a.timestamp,
        ))
        winner = fired[0]

        self._alerts.append(winner)
        self._alert_history.append(winner)
        if len(self._alert_history) > self._alert_history_max:
            self._alert_history.pop(0)

        return winner

    def evaluate_all(self, context: TelemetryContext) -> List[Alert]:
        """
        Run all rules and return **every** alert that fires (no dedup).
        """
        fired: List[Alert] = []
        for rule in self._rules:
            alert = rule.check(context)
            if alert is not None:
                fired.append(alert)
                self._alerts.append(alert)
                self._alert_history.append(alert)

        # Trim history
        if len(self._alert_history) > self._alert_history_max:
            self._alert_history = self._alert_history[-self._alert_history_max:]

        return fired

    # ------------------------------------------------------------------
    # Active alerts management
    # ------------------------------------------------------------------

    def active_alerts(self) -> List[Alert]:
        """Return alerts that are still active (not expired)."""
        now = time.time()
        active = []
        for a in self._alerts:
            if a.expired:
                continue
            if a.ttl_seconds is not None and (now - a.timestamp) > a.ttl_seconds:
                continue
            active.append(a)
        # Keep only active
        self._alerts = active
        return active

    def dismiss_alert(self, alert: Alert) -> bool:
        """Remove a specific alert from the active list."""
        try:
            self._alerts.remove(alert)
            return True
        except ValueError:
            return False

    def dismiss_all(self) -> int:
        """Dismiss all active alerts. Returns count removed."""
        count = len(self._alerts)
        self._alerts.clear()
        return count

    def clear_history(self) -> None:
        """Wipe the alert history log."""
        self._alert_history.clear()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def active_count(self) -> int:
        """Number of currently active (non-expired) alerts."""
        return len(self.active_alerts())

    @property
    def total_raised(self) -> int:
        """Total alerts ever raised by this CoPilot instance."""
        return len(self._alert_history)

    # ------------------------------------------------------------------
    # Persona-aware helpers
    # ------------------------------------------------------------------

    def persona_based_tip(self) -> str:
        """
        Return a single driving tip phrased in the active persona's voice.
        """
        return self.persona.generate_phrase("positive")

    def persona_based_warning(self) -> str:
        """
        Return a single warning phrased in the active persona's voice.
        """
        return self.persona.generate_phrase("critical")

    # ------------------------------------------------------------------
    # Default rules — one set per persona type
    # ------------------------------------------------------------------

    def _add_default_rules(self) -> None:
        """Populate default rules based on the current persona."""
        pt = self.persona.persona_type

        # ── Speed limit ──────────────────────────────────────────────
        self.add_rule(AlertRule(
            name="speed_excessive",
            description="Triggered when speed exceeds a persona-determined threshold.",
            condition_fn=lambda ctx: (
                ctx.speed_normalised > self._speed_threshold(pt)
            ),
            build_alert_fn=lambda ctx: Alert(
                message=self._speed_message(pt, ctx),
                severity=AlertSeverity.WARNING,
                category="speed",
                ttl_seconds=15.0,
            ),
            cooldown_seconds=20.0,
        ))

        # ── Harsh braking ────────────────────────────────────────────
        self.add_rule(AlertRule(
            name="harsh_braking",
            description="Triggered on sudden hard braking events.",
            condition_fn=lambda ctx: (
                ctx.braking_harshness > 0.75
                and self.persona.persona_type != PersonaType.SPORTY
            ),
            build_alert_fn=lambda ctx: Alert(
                message="Hard braking detected. Try to anticipate stops earlier.",
                severity=AlertSeverity.WARNING,
                category="braking",
                ttl_seconds=10.0,
            ),
            cooldown_seconds=15.0,
        ))

        # ── Following distance ───────────────────────────────────────
        self.add_rule(AlertRule(
            name="following_distance",
            description="Triggered when the gap closes below safe threshold.",
            condition_fn=lambda ctx: ctx.following_distance < self._gap_threshold(pt),
            build_alert_fn=lambda ctx: Alert(
                message=self._gap_message(pt, ctx),
                severity=(
                    AlertSeverity.CRITICAL
                    if ctx.following_distance < 0.2
                    else AlertSeverity.WARNING
                ),
                category="following_distance",
                ttl_seconds=20.0,
            ),
            cooldown_seconds=25.0,
        ))

        # ── Fatigue / inattention ────────────────────────────────────
        self.add_rule(AlertRule(
            name="fatigue",
            description="Triggered when fatigue estimate is dangerously high.",
            condition_fn=lambda ctx: ctx.fatigue_estimate > 0.8,
            build_alert_fn=lambda ctx: Alert(
                message="Signs of fatigue detected. Consider a break.",
                severity=AlertSeverity.CRITICAL,
                category="fatigue",
                ttl_seconds=120.0,
            ),
            cooldown_seconds=300.0,
        ))

        # ── Lane discipline (conservative / veteran only) ────────────
        if pt in (PersonaType.CONSERVATIVE, PersonaType.VETERAN):
            self.add_rule(AlertRule(
                name="lane_wandering",
                description="Triggered on excessive lane deviation.",
                condition_fn=lambda ctx: ctx.lane_deviation > 0.6,
                build_alert_fn=lambda ctx: Alert(
                    message="Lane position drifting. Check your grip and attention.",
                    severity=AlertSeverity.WARNING,
                    category="lane_discipline",
                    ttl_seconds=15.0,
                ),
                cooldown_seconds=20.0,
            ))

        # ── Cornering (sporty only) ──────────────────────────────────
        if pt == PersonaType.SPORTY:
            self.add_rule(AlertRule(
                name="cornering_grip",
                description="Sporty: note high cornering force for performance feedback.",
                condition_fn=lambda ctx: ctx.cornering_force > 0.85,
                build_alert_fn=lambda ctx: Alert(
                    message="High cornering forces — that's pushing the limit!",
                    severity=AlertSeverity.INFO,
                    category="cornering",
                    ttl_seconds=10.0,
                ),
                cooldown_seconds=30.0,
            ))

        # ── Hazard proximity (veteran only) ──────────────────────────
        if pt == PersonaType.VETERAN:
            self.add_rule(AlertRule(
                name="hazard_near",
                description="Veteran: early hazard detection alert.",
                condition_fn=lambda ctx: ctx.hazard_proximity > 0.5,
                build_alert_fn=lambda ctx: Alert(
                    message="Hazard detected ahead. Position for an out.",
                    severity=(
                        AlertSeverity.CRITICAL
                        if ctx.hazard_proximity > 0.8
                        else AlertSeverity.WARNING
                    ),
                    category="hazard_awareness",
                    ttl_seconds=30.0,
                ),
                cooldown_seconds=10.0,
            ))

    # ------------------------------------------------------------------
    # Threshold helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _speed_threshold(pt: PersonaType) -> float:
        return {"conservative": 0.70, "sporty": 0.90, "veteran": 0.75}[pt.value]

    @staticmethod
    def _gap_threshold(pt: PersonaType) -> float:
        return {"conservative": 0.45, "sporty": 0.25, "veteran": 0.40}[pt.value]

    @staticmethod
    def _speed_message(pt: PersonaType, ctx: TelemetryContext) -> str:
        if pt == PersonaType.SPORTY:
            return (
                f"Speed at {ctx.speed_normalised:.0%} — you're pushing hard, "
                "keep it on the track."
            )
        return (
            f"Speed at {ctx.speed_normalised:.0%} — ease off for safety."
        )

    @staticmethod
    def _gap_message(pt: PersonaType, ctx: TelemetryContext) -> str:
        if pt == PersonaType.SPORTY:
            return "Closing fast — late braking works on track, not public roads."
        return "Following distance too close. Drop back for safety."
