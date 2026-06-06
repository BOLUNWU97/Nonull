"""
safety_badge.py — Nonull Safety Metrics (advisory)

DISCLAIMER
==========
This module provides safety METRICS (advisory). It is not a safety mechanism.
Do not use these scores in any safety case argument.

These numbers are internal engineering telemetry intended to help developers
spot trends during development. They are NOT a substitute for ISO 26262
hazard analysis, ASIL classification, FMEA, or any other functional-safety
activity. Nonull is an internal ADAS engineering assistant; it is not a
certified safety element out of context (SEooC) and must not be represented
as one.

The module name retains "badge" for backward compatibility with existing
imports, but the framing here is metric tracking, not gamification. There
are no tiers to "earn", no rewards, and no competitive scoring. The output
is plain text and the categories use descriptive engineering labels.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────
#  Metric categories
# ──────────────────────────────────────────────────────────────

class BadgeCategory(str, Enum):
    """The six safety-metric categories tracked by the system.

    The enum names retain their legacy identifiers for backward compatibility
    with existing call sites, but the public-facing labels are engineering
    descriptions (see ``CATEGORY_META``).
    """
    AGGREGATE_SAFETY = "aggregate_safety"
    HAZARD_RESPONSE = "hazard_response"
    MANEUVER_PRECISION = "maneuver_precision"
    SCENARIO_COVERAGE = "scenario_coverage"
    IMPROVEMENT_RATE = "improvement_rate"
    OPERATIONAL_MILESTONES = "operational_milestones"


# Engineering-friendly labels and descriptions. No emoji, no game framing.
CATEGORY_META: Dict[BadgeCategory, Dict[str, Any]] = {
    BadgeCategory.AGGREGATE_SAFETY: {
        "label": "Aggregate safety metric",
        "description": (
            "Composite of collision avoidance, rule compliance, and pass rate "
            "across recorded tests. Higher is better; 0.0 = no data."
        ),
    },
    BadgeCategory.HAZARD_RESPONSE: {
        "label": "Hazard detection and response",
        "description": (
            "Inverse of incident rate (collisions + near-misses per maneuver). "
            "Higher means fewer incidents relative to maneuvers executed."
        ),
    },
    BadgeCategory.MANEUVER_PRECISION: {
        "label": "Maneuver execution quality",
        "description": (
            "Fraction of clean maneuvers (no near-miss, no collision). "
            "Higher means more maneuvers completed without incident."
        ),
    },
    BadgeCategory.SCENARIO_COVERAGE: {
        "label": "Scenario coverage",
        "description": (
            "Fraction of the catalogued scenario set that has been executed "
            "or validated at least once. 1.0 = full coverage."
        ),
    },
    BadgeCategory.IMPROVEMENT_RATE: {
        "label": "Improvement trajectory",
        "description": (
            "Trend signal — how the aggregate safety metric changes over "
            "consecutive interactions. Baseline 0.5 until history is "
            "available."
        ),
    },
    BadgeCategory.OPERATIONAL_MILESTONES: {
        "label": "Operational distance / tests run",
        "description": (
            "Cumulative operational volume in kilometers (and/or tests). "
            "Reaches 1.0 at 10,000 km equivalent."
        ),
    },
}


# ──────────────────────────────────────────────────────────────
#  Metric levels (numeric; no bronze/silver/gold framing)
# ──────────────────────────────────────────────────────────────

class BadgeLevel(int, Enum):
    """Numeric levels derived from a 0-1 metric score.

    The names are intentionally numeric (``LEVEL_0`` … ``LEVEL_5``) so the
    output reads as a measurement, not a "rank". The thresholds are
    unchanged from the previous gamified version.
    """
    LEVEL_0 = 0
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3
    LEVEL_4 = 4
    LEVEL_5 = 5


LEVEL_META: Dict[BadgeLevel, Dict[str, Any]] = {
    BadgeLevel.LEVEL_0: {"label": "Level 0", "threshold": 0.0},
    BadgeLevel.LEVEL_1: {"label": "Level 1", "threshold": 0.20},
    BadgeLevel.LEVEL_2: {"label": "Level 2", "threshold": 0.40},
    BadgeLevel.LEVEL_3: {"label": "Level 3", "threshold": 0.60},
    BadgeLevel.LEVEL_4: {"label": "Level 4", "threshold": 0.80},
    BadgeLevel.LEVEL_5: {"label": "Level 5", "threshold": 0.95},
}


# ──────────────────────────────────────────────────────────────
#  Score types
# ──────────────────────────────────────────────────────────────

@dataclass
class BadgeScore:
    """Raw score data for one safety-metric category."""
    category: BadgeCategory
    score: float                     # 0.0 – 1.0
    raw_value: float                 # original metric value
    unit: str = ""                   # e.g. "tests", "km", "incidents"
    details: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.score = max(0.0, min(1.0, self.score))

    @property
    def level(self) -> BadgeLevel:
        """Derive numeric level from the 0-1 score."""
        for level in reversed(list(BadgeLevel)):
            if self.score >= LEVEL_META[level]["threshold"]:
                return level
        return BadgeLevel.LEVEL_0

    @property
    def progress_to_next(self) -> float:
        """Return 0-1 progress towards the next level threshold."""
        current = self.level
        if current == BadgeLevel.LEVEL_5:
            return 1.0
        current_threshold = LEVEL_META[current]["threshold"]
        next_level = BadgeLevel(current.value + 1)
        next_threshold = LEVEL_META[next_level]["threshold"]
        if next_threshold <= current_threshold:
            return 1.0
        return (self.score - current_threshold) / (next_threshold - current_threshold)

    def to_dict(self) -> Dict[str, Any]:
        meta = CATEGORY_META[self.category]
        return {
            "category": self.category.value,
            "label": meta["label"],
            "score": round(self.score, 4),
            "raw_value": round(self.raw_value, 2),
            "unit": self.unit,
            "level": self.level.value,
            "level_label": LEVEL_META[self.level]["label"],
            "progress_to_next": round(self.progress_to_next, 4),
            "details": {k: round(v, 4) for k, v in self.details.items()},
        }


# ──────────────────────────────────────────────────────────────
#  SafetyMetricsSystem
# ──────────────────────────────────────────────────────────────

class SafetyBadgeSystem:
    """Tracks safety-metric scores, derived numeric levels, and history.

    The class name ``SafetyBadgeSystem`` is retained for backward
    compatibility with existing imports. The behavior is pure metric
    accounting — no tiers to "earn", no rewards, no progress bars in
    user-facing output.
    """

    def __init__(self, agent_name: str = "Nonull Agent") -> None:
        self.agent_name = agent_name
        self._scores: Dict[BadgeCategory, BadgeScore] = {}
        self._history: List[Dict[str, Any]] = []
        self._interactions: List[Dict[str, Any]] = []
        self._total_interactions: int = 0
        self._total_score: float = 0.0
        self._metadata: Dict[str, Any] = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": "2.0.0-metrics",
            "framing": "advisory_safety_metrics",
            "disclaimer": (
                "Advisory only. Not a safety mechanism. Do not use in any "
                "safety case argument. See module docstring."
            ),
        }

    # ── Interaction evaluation (used by PersonaOrchestrator) ──

    def evaluate_interaction(self, context: Dict[str, Any]) -> float:
        """
        Record an interaction and return a 0-1 safety-metric score.

        Args:
            context: Dict describing the interaction. Recognized keys:
                - ``score`` (float): explicit score 0-1, optional.
                - ``safety_score`` (float): alternative explicit score.
                - ``risk`` (float): risk level 0-1 (inverted to score).
                - ``outcome`` (str): "success" | "warning" | "violation".
                - ``category`` (BadgeCategory | str): which category to bump.

        Returns:
            The resulting safety-metric score (0.0 - 1.0).
        """
        # Derive a score from context
        if "score" in context:
            score = float(context["score"])
        elif "safety_score" in context:
            score = float(context["safety_score"])
        elif "risk" in context:
            score = max(0.0, min(1.0, 1.0 - float(context["risk"])))
        else:
            outcome = str(context.get("outcome", "success")).lower()
            if outcome in ("violation", "fail", "failed"):
                score = 0.2
            elif outcome in ("warning", "warn", "near_miss"):
                score = 0.5
            else:
                score = 0.85

        score = max(0.0, min(1.0, score))
        self._interactions.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context,
            "score": score,
        })
        self._total_interactions += 1
        self._total_score += score

        # Update the aggregate category so the scorecard reflects activity.
        # Legacy callers may pass the old enum name; map if so.
        cat_raw = context.get("category", BadgeCategory.AGGREGATE_SAFETY)
        cat = self._coerce_category(cat_raw)

        previous = self.get_score(cat)
        if previous is None:
            self.update_score(
                category=cat,
                score=score,
                raw_value=self._total_interactions,
                unit="interactions",
            )
        else:
            # Running average
            new_score = (previous.score * 0.7) + (score * 0.3)
            self.update_score(
                category=cat,
                score=new_score,
                raw_value=self._total_interactions,
                unit="interactions",
            )

        return score

    def _coerce_category(self, raw: Any) -> BadgeCategory:
        """Coerce a string/old-name/None to a current ``BadgeCategory``."""
        if isinstance(raw, BadgeCategory):
            return raw
        if raw is None:
            return BadgeCategory.AGGREGATE_SAFETY
        try:
            return BadgeCategory(str(raw))
        except ValueError:
            # Accept legacy enum *values* (e.g. "safety_champion") as well
            # as the new ones, so old call sites keep working.
            legacy_map = {
                "safety_champion": BadgeCategory.AGGREGATE_SAFETY,
                "guardian": BadgeCategory.HAZARD_RESPONSE,
                "precision": BadgeCategory.MANEUVER_PRECISION,
                "knowledge": BadgeCategory.SCENARIO_COVERAGE,
                "growth": BadgeCategory.IMPROVEMENT_RATE,
                "achievement": BadgeCategory.OPERATIONAL_MILESTONES,
            }
            return legacy_map.get(str(raw), BadgeCategory.AGGREGATE_SAFETY)

    def check_and_record(self) -> Optional[Dict[str, Any]]:
        """
        Check whether the current scores cross a level threshold and record it.

        Note
        ----
        This method returns METRIC PROGRESS, not a game reward. It records
        the fact that a category's 0-1 score has just crossed into a new
        numeric level band (LEVEL_1 .. LEVEL_5). There is no "award",
        "prize", "achievement", or other gamification artifact associated
        with the crossing — the returned dict is informational telemetry
        only. Do not use it in any safety case argument.

        Returns:
            Dict describing the newly crossed level, or None if no new
            threshold was crossed. The returned dict has the keys:
            ``category``, ``label``, ``level`` (int 1-5), ``level_label``,
            ``score`` (0-1), ``timestamp``, and ``advisory_note``.
        """
        recorded: Optional[Dict[str, Any]] = None
        for cat, bs in self._scores.items():
            level = bs.level
            if level == BadgeLevel.LEVEL_0:
                continue
            already = self._metadata.get("recorded_levels", {}).get(cat.value, 0)
            if level.value > already:
                self._metadata.setdefault("recorded_levels", {})[cat.value] = level.value
                recorded = {
                    "category": cat.value,
                    "label": CATEGORY_META[cat]["label"],
                    "level": level.value,
                    "level_label": LEVEL_META[level]["label"],
                    "score": round(bs.score, 4),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "advisory_note": "Crossed threshold — informational only.",
                }
                self.log_event("level_threshold_crossed", recorded)
                break
        return recorded

    # Deprecated alias — kept for backward compatibility with callers
    # written against the gamified API. Will be removed in a future major
    # version. The name "award" is misleading: this method does not
    # grant, award, or unlock anything.
    def check_and_award(self) -> Optional[Dict[str, Any]]:
        """Deprecated: use :meth:`check_and_record` instead.

        This alias returns METRIC PROGRESS, not a game reward. It exists
        only for backward compatibility and will be removed in a future
        major version.
        """
        warnings.warn(
            "SafetyBadgeSystem.check_and_award is deprecated; "
            "use check_and_record instead. The method returns metric "
            "progress, not a game reward.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.check_and_record()

    def get_achieved_levels(self) -> List[Dict[str, Any]]:
        """Return a list of metric dicts for all non-zero categories.

        Note
        ----
        This method returns METRIC PROGRESS, not "earned badges" or
        other gamification artifacts. Each item is a reading of a
        category's 0-1 score together with its derived numeric level
        (LEVEL_0 .. LEVEL_5). The output is plain engineering telemetry
        and must not be interpreted as a reward, achievement, prize,
        unlock, or competitive score. Do not use it in any safety case
        argument.

        Returns:
            List of dicts, one per category whose level is above
            LEVEL_0. Each dict has the keys ``category``, ``label``,
            ``level`` (int 1-5), ``level_label``, and ``score`` (0-1).
        """
        result: List[Dict[str, Any]] = []
        for cat, bs in self._scores.items():
            if bs.level == BadgeLevel.LEVEL_0:
                continue
            result.append({
                "category": cat.value,
                "label": CATEGORY_META[cat]["label"],
                "level": bs.level.value,
                "level_label": LEVEL_META[bs.level]["label"],
                "score": round(bs.score, 4),
            })
        return result

    # Deprecated alias — kept for backward compatibility with callers
    # written against the gamified API. Will be removed in a future major
    # version. The name "earned_badges" is misleading: this method does
    # not return prizes, rewards, or unlocks.
    def get_earned_badges(self) -> List[Dict[str, Any]]:
        """Deprecated: use :meth:`get_achieved_levels` instead.

        This alias returns METRIC PROGRESS, not "earned badges" or other
        gamification artifacts. It exists only for backward compatibility
        and will be removed in a future major version.
        """
        warnings.warn(
            "SafetyBadgeSystem.get_earned_badges is deprecated; "
            "use get_achieved_levels instead. The method returns metric "
            "progress, not earned badges.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.get_achieved_levels()

    def get_scorecard(self) -> Dict[str, Any]:
        """Alias for :meth:`generate_scorecard` (used by PersonaOrchestrator)."""
        return self.generate_scorecard()

    @property
    def total_interactions(self) -> int:
        """Total interactions recorded via :meth:`evaluate_interaction`."""
        return self._total_interactions

    @property
    def average_score(self) -> float:
        """Average score across all recorded interactions (0.0 if none)."""
        if self._total_interactions == 0:
            return 0.0
        return self._total_score / self._total_interactions

    # ── Score assignment ─────────────────────────────────────

    def set_score(self, score: BadgeScore) -> None:
        """Set (or update) the score for a metric category."""
        self._scores[score.category] = score

    def update_score(
        self,
        category: BadgeCategory,
        score: float,
        raw_value: float,
        unit: str = "",
        details: Optional[Dict[str, float]] = None,
    ) -> BadgeScore:
        """Convenience method to create and store a BadgeScore."""
        bs = BadgeScore(
            category=category,
            score=score,
            raw_value=raw_value,
            unit=unit,
            details=details or {},
        )
        self.set_score(bs)
        return bs

    def bulk_update(self, scores: Dict[BadgeCategory, Tuple[float, float, str, Dict[str, float]]]) -> None:
        """Update multiple scores at once.

        Keys are BadgeCategory, values are (score, raw_value, unit, details).
        """
        for cat, (score, raw, unit, details) in scores.items():
            self.update_score(cat, score, raw, unit, details)

    # ── Accessors ────────────────────────────────────────────

    def get_score(self, category: BadgeCategory) -> Optional[BadgeScore]:
        return self._scores.get(category)

    def get_level(self, category: BadgeCategory) -> BadgeLevel:
        bs = self._scores.get(category)
        return bs.level if bs else BadgeLevel.LEVEL_0

    @property
    def overall_score(self) -> float:
        """Weighted average of all assigned metric scores."""
        if not self._scores:
            return 0.0
        # Equal weight per category
        return sum(bs.score for bs in self._scores.values()) / len(self._scores)

    @property
    def overall_level(self) -> BadgeLevel:
        """Derive overall numeric level from overall_score."""
        for level in reversed(list(BadgeLevel)):
            if self.overall_score >= LEVEL_META[level]["threshold"]:
                return level
        return BadgeLevel.LEVEL_0

    @property
    def assigned_categories(self) -> List[BadgeCategory]:
        return list(self._scores.keys())

    @property
    def all_badges(self) -> List[BadgeScore]:
        return list(self._scores.values())

    # ── Scorecard ────────────────────────────────────────────

    def generate_scorecard(self, title: str = "") -> Dict[str, Any]:
        """Generate a full metric scorecard.

        Returns a rich dictionary suitable for JSON export or display.
        """
        metrics = []
        for cat in BadgeCategory:
            bs = self._scores.get(cat)
            if bs:
                metrics.append(bs.to_dict())
            else:
                meta = CATEGORY_META[cat]
                metrics.append({
                    "category": cat.value,
                    "label": meta["label"],
                    "score": 0.0,
                    "raw_value": 0.0,
                    "unit": "",
                    "level": 0,
                    "level_label": LEVEL_META[BadgeLevel.LEVEL_0]["label"],
                    "progress_to_next": 0.0,
                    "details": {},
                })

        return {
            "agent_name": self.agent_name,
            "title": title or f"Safety Metrics — {self.agent_name}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": (
                "Advisory safety metrics. Not a safety mechanism. Do not "
                "use in any safety case argument."
            ),
            "metadata": self._metadata,
            "overall": {
                "score": round(self.overall_score, 4),
                "level": self.overall_level.value,
                "level_label": LEVEL_META[self.overall_level]["label"],
                "metrics_assigned": len(self._scores),
                "metrics_total": len(BadgeCategory),
            },
            "metrics": metrics,
            "history_count": len(self._history),
        }

    def print_scorecard(self, title: str = "") -> str:
        """Return a plain-text, tabular scorecard string (no emoji)."""
        card = self.generate_scorecard(title)

        lines: List[str] = []
        border = "=" * 72
        lines.append(border)
        lines.append(f"  {card['title']}")
        lines.append(f"  Agent: {card['agent_name']}  |  {card['generated_at'][:19]}")
        lines.append(f"  {card['disclaimer']}")
        lines.append(border)

        # Overall
        ol = card["overall"]
        lines.append("")
        lines.append("  OVERALL METRIC")
        lines.append(f"  Score: {ol['score']:.1%}  |  Level: {ol['level_label']}")
        lines.append(f"  Metrics assigned: {ol['metrics_assigned']}/{ol['metrics_total']}")

        lines.append("")
        lines.append("-" * 72)
        lines.append("  METRIC BREAKDOWN")
        lines.append("-" * 72)
        # Plain ASCII table: column widths chosen for readability.
        header = (
            f"  {'Category':<32s}  {'Score':>7s}  {'Level':>9s}  {'Raw':>14s}"
        )
        lines.append(header)
        lines.append("  " + "-" * 68)

        for metric in card["metrics"]:
            label = metric["label"]
            if len(label) > 32:
                label = label[:29] + "..."
            level_label = metric["level_label"]
            score = metric["score"]
            raw = metric["raw_value"]
            unit = metric.get("unit", "")
            raw_str = f"{raw:.1f} {unit}".strip() if unit else f"{raw:.1f}"
            if len(raw_str) > 14:
                raw_str = raw_str[:11] + "..."
            lines.append(
                f"  {label:<32s}  {score:>6.1%}  {level_label:>9s}  {raw_str:>14s}"
            )

        # History
        if card["history_count"] > 0:
            lines.append("")
            lines.append("-" * 72)
            lines.append(f"  HISTORY (last 5 of {card['history_count']} entries)")
            for entry in self._history[-5:]:
                ts = entry.get("timestamp", "")[:19]
                ev = entry.get("event", "update")
                lines.append(f"  {ts}  {ev}")

        lines.append("")
        lines.append(border)
        lines.append(
            "  Advisory only. Not a safety mechanism. Do not use in any"
        )
        lines.append(
            "  safety case argument. See module docstring for full disclaimer."
        )
        return "\n".join(lines)

    # ── History / Logging ────────────────────────────────────

    def log_event(self, event: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Record a metric event in the history log."""
        self._history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "details": details or {},
        })

    # ── Scenario integration helper ──────────────────────────

    def from_scenario_coverage(
        self,
        covered_scenarios: List[str],
        total_scenarios: int,
        collisions: int = 0,
        near_misses: int = 0,
        maneuvers_executed: int = 0,
        tests_passed: int = 0,
        total_tests: int = 0,
        distance_km: float = 0.0,
    ) -> None:
        """Compute metric scores from scenario coverage data.

        This is the primary integration point with ScenarioEngine.
        """
        # Aggregate safety: inverse of collision rate + scenario pass rate
        collision_rate = collisions / max(maneuvers_executed, 1)
        safety_score = max(0.0, 1.0 - collision_rate * 10)
        if total_tests > 0:
            test_pass_rate = tests_passed / total_tests
            safety_score = safety_score * 0.5 + test_pass_rate * 0.5
        self.update_score(
            BadgeCategory.AGGREGATE_SAFETY,
            score=safety_score,
            raw_value=tests_passed if total_tests > 0 else collisions,
            unit="tests" if total_tests > 0 else "collisions",
            details={
                "collisions": collisions,
                "near_misses": near_misses,
                "tests_passed": tests_passed,
                "total_tests": total_tests,
                "collision_rate": round(collision_rate, 4),
            },
        )

        # Hazard response: hazard detection and avoidance
        evasion_score = min(1.0, (collisions + near_misses) / max(maneuvers_executed, 1) * 5)
        hazard_score = 1.0 - evasion_score if evasion_score < 1.0 else 0.0
        self.update_score(
            BadgeCategory.HAZARD_RESPONSE,
            score=hazard_score,
            raw_value=near_misses + collisions,
            unit="incidents",
            details={
                "collisions": collisions,
                "near_misses": near_misses,
                "maneuvers_executed": maneuvers_executed,
            },
        )

        # Scenario coverage
        coverage_pct = covered_scenarios / max(total_scenarios, 1) if isinstance(covered_scenarios, (int, float)) else len(covered_scenarios) / max(total_scenarios, 1)
        self.update_score(
            BadgeCategory.SCENARIO_COVERAGE,
            score=coverage_pct,
            raw_value=covered_scenarios if isinstance(covered_scenarios, (int, float)) else len(covered_scenarios),
            unit="scenarios",
            details={
                "covered": covered_scenarios if isinstance(covered_scenarios, (int, float)) else len(covered_scenarios),
                "total": total_scenarios,
            },
        )

        # Maneuver precision
        precision_score = min(1.0, max(0.0, 1.0 - near_misses / max(maneuvers_executed, 1)))
        self.update_score(
            BadgeCategory.MANEUVER_PRECISION,
            score=precision_score,
            raw_value=maneuvers_executed - near_misses - collisions,
            unit="clean_maneuvers",
            details={
                "total_maneuvers": maneuvers_executed,
                "imperfect": near_misses + collisions,
            },
        )

        # Improvement trajectory: starts neutral, can be adjusted over time
        self.update_score(
            BadgeCategory.IMPROVEMENT_RATE,
            score=0.5,  # baseline — rate of improvement tracked separately
            raw_value=0.0,
            unit="delta",
            details={"baseline": 0.5},
        )

        # Operational milestones: distance-based
        achievement_pct = min(1.0, distance_km / 10000.0)
        self.update_score(
            BadgeCategory.OPERATIONAL_MILESTONES,
            score=achievement_pct,
            raw_value=distance_km,
            unit="km",
            details={"target_km": 10000},
        )

        self.log_event("scorecard_from_coverage", {
            "covered_scenarios": covered_scenarios if isinstance(covered_scenarios, (int, float)) else len(covered_scenarios),
            "total_scenarios": total_scenarios,
            "collisions": collisions,
            "near_misses": near_misses,
            "maneuvers_executed": maneuvers_executed,
            "distance_km": distance_km,
        })

    # NOTE: ``simulate_progressive_training`` was removed in the 2.0
    # metrics refactor. It fabricated synthetic score trajectories for
    # gamification demos and was inappropriate for an ADAS engineering
    # tool. Any future synthetic-data demo MUST live under
    # ``experimental/`` and is NOT suitable for any safety-relevant
    # decision. Production code (anything under ``persona/``, ``core/``,
    # ``safety/``, etc.) is forbidden from importing from
    # ``experimental/`` — see ``tests/test_no_experimental_imports.py``.

    # ── Serialization ────────────────────────────────────────

    def to_json(self, indent: int = 2) -> str:
        """Export scorecard as JSON."""
        return json.dumps(self.generate_scorecard(), indent=indent, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────
#  Convenience singleton
# ──────────────────────────────────────────────────────────────

_SYSTEM: Optional[SafetyBadgeSystem] = None

def get_badge_system(agent_name: str = "Nonull Agent") -> SafetyBadgeSystem:
    """Get or create the global SafetyMetrics singleton."""
    global _SYSTEM
    if _SYSTEM is None:
        _SYSTEM = SafetyBadgeSystem(agent_name)
    return _SYSTEM


# ──────────────────────────────────────────────────────────────
#  Quick self-test
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    system = get_badge_system("Nonull ADAS Agent v1")

    print("=" * 60)
    print("  Nonull Safety Metrics — Self Test")
    print("=" * 60)
    print("  Advisory only. Not a safety mechanism.")
    print()

    # Populate from scenario coverage (real-feeling data, not synthetic
    # training curves).
    system.from_scenario_coverage(
        covered_scenarios=24,
        total_scenarios=36,
        collisions=1,
        near_misses=3,
        maneuvers_executed=200,
        tests_passed=180,
        total_tests=200,
        distance_km=2500.0,
    )
    # A couple of explicit interactions
    system.evaluate_interaction({"outcome": "success", "category": BadgeCategory.AGGREGATE_SAFETY})
    system.evaluate_interaction({"outcome": "warning", "category": BadgeCategory.HAZARD_RESPONSE})

    print(system.print_scorecard("Safety Metrics — Demo Run"))

    # Coverage-based scorecard on a second instance
    print()
    system2 = SafetyBadgeSystem("Coverage Test Agent")
    system2.from_scenario_coverage(
        covered_scenarios=24,
        total_scenarios=36,
        collisions=1,
        near_misses=3,
        maneuvers_executed=200,
        tests_passed=180,
        total_tests=200,
        distance_km=2500.0,
    )
    print(system2.print_scorecard("Coverage-Based Metrics"))

    print()
    print("  Safety metrics ready. Advisory only — not a safety mechanism.")
