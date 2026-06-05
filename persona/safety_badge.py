"""
safety_badge.py — Nonull Safety Badge System

Tiered safety badge system with visual emoji badges, scorecard generation,
and progress tracking across six badge categories.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────
#  Badge Tiers & Levels
# ──────────────────────────────────────────────────────────────

class BadgeCategory(str, Enum):
    """The six badge categories, each with its own visual emoji."""
    SAFETY_CHAMPION = "safety_champion"      # 🥇
    GUARDIAN = "guardian"                      # 🛡️
    PRECISION = "precision"                    # 🎯
    KNOWLEDGE = "knowledge"                    # 📚
    GROWTH = "growth"                          # 🌱
    ACHIEVEMENT = "achievement"                # 🏅


BADGE_META: Dict[BadgeCategory, Dict[str, Any]] = {
    BadgeCategory.SAFETY_CHAMPION: {
        "emoji": "\U0001F947",  # 🥇
        "label": "Safety Champion",
        "description": "Overall safety excellence — collision avoidance, rule compliance, and safe driving across all domains.",
    },
    BadgeCategory.GUARDIAN: {
        "emoji": "\U0001F6E1️",  # 🛡️
        "label": "Guardian",
        "description": "Protection capability — AEB response, hazard detection, and defensive driving metrics.",
    },
    BadgeCategory.PRECISION: {
        "emoji": "\U0001F3AF",  # 🎯
        "label": "Precision",
        "description": "Maneuver accuracy — lane keeping, parking precision, speed control, and smoothness.",
    },
    BadgeCategory.KNOWLEDGE: {
        "emoji": "\U0001F4DA",  # 📚
        "label": "Knowledge",
        "description": "Scenario coverage — number of distinct scenarios trained on and validated against.",
    },
    BadgeCategory.GROWTH: {
        "emoji": "\U0001F331",  # 🌱
        "label": "Growth",
        "description": "Improvement trajectory — rate of safety metric improvement and regression recovery.",
    },
    BadgeCategory.ACHIEVEMENT: {
        "emoji": "\U0001F3C5",  # 🏅
        "label": "Achievement",
        "description": "Milestone accomplishments — total distance driven, tests passed, and records set.",
    },
}


class BadgeLevel(int, Enum):
    """Concrete levels within each badge category."""
    NONE = 0
    BRONZE = 1
    SILVER = 2
    GOLD = 3
    PLATINUM = 4
    DIAMOND = 5


LEVEL_META: Dict[BadgeLevel, Dict[str, Any]] = {
    BadgeLevel.NONE:    {"label": "None",     "threshold": 0.0,  "color": "\033[90m"},
    BadgeLevel.BRONZE:  {"label": "Bronze",   "threshold": 0.20, "color": "\033[33m"},
    BadgeLevel.SILVER:  {"label": "Silver",   "threshold": 0.40, "color": "\033[37m"},
    BadgeLevel.GOLD:    {"label": "Gold",     "threshold": 0.60, "color": "\033[93m"},
    BadgeLevel.PLATINUM:{"label": "Platinum", "threshold": 0.80, "color": "\033[96m"},
    BadgeLevel.DIAMOND: {"label": "Diamond",  "threshold": 0.95, "color": "\033[95m"},
}


# ──────────────────────────────────────────────────────────────
#  Score types
# ──────────────────────────────────────────────────────────────

@dataclass
class BadgeScore:
    """Raw score data for one badge category."""
    category: BadgeCategory
    score: float                     # 0.0 – 1.0
    raw_value: float                 # original metric value
    unit: str = ""                   # e.g. "tests", "km", "evasions"
    details: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.score = max(0.0, min(1.0, self.score))

    @property
    def level(self) -> BadgeLevel:
        """Derive badge level from the 0-1 score."""
        for level in reversed(list(BadgeLevel)):
            if self.score >= LEVEL_META[level]["threshold"]:
                return level
        return BadgeLevel.NONE

    @property
    def progress_to_next(self) -> float:
        """Return 0-1 progress towards the next badge level."""
        current = self.level
        if current == BadgeLevel.DIAMOND:
            return 1.0
        current_threshold = LEVEL_META[current]["threshold"]
        next_level = BadgeLevel(current.value + 1)
        next_threshold = LEVEL_META[next_level]["threshold"]
        if next_threshold <= current_threshold:
            return 1.0
        return (self.score - current_threshold) / (next_threshold - current_threshold)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "label": BADGE_META[self.category]["label"],
            "emoji": BADGE_META[self.category]["emoji"],
            "score": round(self.score, 4),
            "raw_value": round(self.raw_value, 2),
            "unit": self.unit,
            "level": self.level.value,
            "level_label": LEVEL_META[self.level]["label"],
            "progress_to_next": round(self.progress_to_next, 4),
            "details": {k: round(v, 4) for k, v in self.details.items()},
        }


# ──────────────────────────────────────────────────────────────
#  SafetyBadgeSystem
# ──────────────────────────────────────────────────────────────

class SafetyBadgeSystem:
    """Manages badge scoring, leveling, and scorecard generation."""

    def __init__(self, agent_name: str = "Nonull Agent") -> None:
        self.agent_name = agent_name
        self._scores: Dict[BadgeCategory, BadgeScore] = {}
        self._history: List[Dict[str, Any]] = []
        self._metadata: Dict[str, Any] = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
        }

    # ── Score assignment ─────────────────────────────────────

    def set_score(self, score: BadgeScore) -> None:
        """Set (or update) the score for a badge category."""
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
        return bs.level if bs else BadgeLevel.NONE

    @property
    def overall_score(self) -> float:
        """Weighted average of all assigned badge scores."""
        if not self._scores:
            return 0.0
        # Equal weight per category
        return sum(bs.score for bs in self._scores.values()) / len(self._scores)

    @property
    def overall_level(self) -> BadgeLevel:
        """Derive overall badge level from overall_score."""
        for level in reversed(list(BadgeLevel)):
            if self.overall_score >= LEVEL_META[level]["threshold"]:
                return level
        return BadgeLevel.NONE

    @property
    def assigned_categories(self) -> List[BadgeCategory]:
        return list(self._scores.keys())

    @property
    def all_badges(self) -> List[BadgeScore]:
        return list(self._scores.values())

    # ── Scorecard ────────────────────────────────────────────

    def generate_scorecard(self, title: str = "") -> Dict[str, Any]:
        """Generate a full scorecard with all badge levels and stats.

        Returns a rich dictionary suitable for JSON export or display.
        """
        badges = []
        for cat in BadgeCategory:
            bs = self._scores.get(cat)
            if bs:
                badges.append(bs.to_dict())
            else:
                meta = BADGE_META[cat]
                badges.append({
                    "category": cat.value,
                    "label": meta["label"],
                    "emoji": meta["emoji"],
                    "score": 0.0,
                    "raw_value": 0.0,
                    "unit": "",
                    "level": 0,
                    "level_label": "None",
                    "progress_to_next": 0.0,
                    "details": {},
                })

        return {
            "agent_name": self.agent_name,
            "title": title or f"Safety Scorecard — {self.agent_name}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": self._metadata,
            "overall": {
                "score": round(self.overall_score, 4),
                "level": self.overall_level.value,
                "level_label": LEVEL_META[self.overall_level]["label"],
                "badges_assigned": len(self._scores),
                "badges_total": len(BadgeCategory),
            },
            "badges": badges,
            "history_count": len(self._history),
        }

    def print_scorecard(self, title: str = "") -> str:
        """Return a human-friendly formatted scorecard string."""
        card = self.generate_scorecard(title)

        lines = []
        border = "=" * 58
        lines.append(border)
        lines.append(f"  {card['title']}")
        lines.append(f"  Agent: {card['agent_name']}  |  {card['generated_at'][:19]}")
        lines.append(border)

        # Overall
        ol = card["overall"]
        lines.append(f"\n  OVERALL SAFETY RATING")
        lines.append(f"  Score: {ol['score']:.1%}  |  Level: {ol['level_label']}")
        lines.append(f"  Badges earned: {ol['badges_assigned']}/{ol['badges_total']}")

        # Progress bar
        bar = self._progress_bar(ol["score"], 20)
        lines.append(f"  [{bar}]")

        lines.append(f"\n{'─' * 58}")
        lines.append(f"  BADGE BREAKDOWN")
        lines.append(f"{'─' * 58}")

        for badge in card["badges"]:
            emoji = badge["emoji"]
            label = badge["label"]
            level_label = badge["level_label"]
            score = badge["score"]
            pct = score * 100
            bar = self._progress_bar(score, 14)
            raw = badge["raw_value"]
            unit = badge["unit"]
            detail_str = f" ({raw:.1f} {unit.strip()})" if unit else ""
            lines.append(
                f"  {emoji} {label:18s}  {bar}  {pct:5.1f}%  {level_label:9s}{detail_str}"
            )

        # History
        if card["history_count"] > 0:
            lines.append(f"\n{'─' * 58}")
            lines.append(f"  HISTORY ({card['history_count']} entries)")
            for entry in self._history[-5:]:
                lines.append(f"  {entry['timestamp'][:19]}  {entry.get('event', 'update')}")

        lines.append(f"\n{border}")
        return "\n".join(lines)

    @staticmethod
    def _progress_bar(score: float, width: int = 20) -> str:
        filled = min(int(score * width), width)
        empty = width - filled
        return "█" * filled + "░" * empty

    # ── History / Logging ────────────────────────────────────

    def log_event(self, event: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Record a safety event in the history log."""
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
        """Automatically compute badge scores from scenario coverage data.

        This is the primary integration point with ScenarioEngine.
        """
        # Safety Champion: inverse of collision rate + scenario pass rate
        collision_rate = collisions / max(maneuvers_executed, 1)
        safety_score = max(0.0, 1.0 - collision_rate * 10)
        if total_tests > 0:
            test_pass_rate = tests_passed / total_tests
            safety_score = safety_score * 0.5 + test_pass_rate * 0.5
        self.update_score(
            BadgeCategory.SAFETY_CHAMPION,
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

        # Guardian: hazard detection and avoidance
        evasion_score = min(1.0, (collisions + near_misses) / max(maneuvers_executed, 1) * 5)
        hazard_score = 1.0 - evasion_score if evasion_score < 1.0 else 0.0
        self.update_score(
            BadgeCategory.GUARDIAN,
            score=hazard_score,
            raw_value=near_misses + collisions,
            unit="incidents",
            details={
                "collisions": collisions,
                "near_misses": near_misses,
                "maneuvers_executed": maneuvers_executed,
            },
        )

        # Knowledge: scenario coverage
        coverage_pct = covered_scenarios / max(total_scenarios, 1) if isinstance(covered_scenarios, (int, float)) else len(covered_scenarios) / max(total_scenarios, 1)
        self.update_score(
            BadgeCategory.KNOWLEDGE,
            score=coverage_pct,
            raw_value=covered_scenarios if isinstance(covered_scenarios, (int, float)) else len(covered_scenarios),
            unit="scenarios",
            details={
                "covered": covered_scenarios if isinstance(covered_scenarios, (int, float)) else len(covered_scenarios),
                "total": total_scenarios,
            },
        )

        # Precision: maneuver execution quality (placeholder logic)
        precision_score = min(1.0, max(0.0, 1.0 - near_misses / max(maneuvers_executed, 1)))
        self.update_score(
            BadgeCategory.PRECISION,
            score=precision_score,
            raw_value=maneuvers_executed - near_misses - collisions,
            unit="clean_maneuvers",
            details={
                "total_maneuvers": maneuvers_executed,
                "imperfect": near_misses + collisions,
            },
        )

        # Growth: starts neutral, can be adjusted over time
        self.update_score(
            BadgeCategory.GROWTH,
            score=0.5,  # baseline — rate of improvement tracked separately
            raw_value=0.0,
            unit="delta",
            details={"baseline": 0.5},
        )

        # Achievement: distance-based milestone
        achievement_pct = min(1.0, distance_km / 10000.0)
        self.update_score(
            BadgeCategory.ACHIEVEMENT,
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

    # ── Simulation / Demo ────────────────────────────────────

    def simulate_progressive_training(self, steps: int = 5) -> List[float]:
        """Simulate progressive training runs and track overall score history.

        Useful for demonstrations and Growth badge trajectories.
        """
        history: List[float] = []
        for i in range(1, steps + 1):
            progress = i / steps
            self.update_score(
                BadgeCategory.SAFETY_CHAMPION,
                score=0.3 + 0.6 * progress,
                raw_value=int(100 * progress),
                unit="tests",
                details={"step": i},
            )
            self.update_score(
                BadgeCategory.KNOWLEDGE,
                score=min(1.0, 0.2 + 0.75 * progress + 0.05 * (i % 2)),
                raw_value=int(36 * (0.2 + 0.75 * progress)),
                unit="scenarios",
                details={"step": i},
            )
            self.update_score(
                BadgeCategory.GROWTH,
                score=min(1.0, 0.3 + 0.6 * progress),
                raw_value=round(0.6 / steps, 3),
                unit="delta/step",
                details={"step": i},
            )
            self.update_score(
                BadgeCategory.PRECISION,
                score=0.5 + 0.4 * progress,
                raw_value=int(200 * progress),
                unit="maneuvers",
                details={"step": i},
            )
            self.update_score(
                BadgeCategory.GUARDIAN,
                score=0.4 + 0.5 * progress,
                raw_value=max(0, 10 - int(10 * progress)),
                unit="incidents_avoided",
                details={"step": i},
            )
            self.update_score(
                BadgeCategory.ACHIEVEMENT,
                score=min(1.0, progress * 1.2),
                raw_value=int(progress * 10000),
                unit="km",
                details={"step": i},
            )
            score = self.overall_score
            history.append(score)
            self.log_event(f"training_step_{i}", {"overall_score": score})
        return history

    # ── Serialization ────────────────────────────────────────

    def to_json(self, indent: int = 2) -> str:
        """Export scorecard as JSON."""
        return json.dumps(self.generate_scorecard(), indent=indent, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────
#  Convenience singleton
# ──────────────────────────────────────────────────────────────

_SYSTEM: Optional[SafetyBadgeSystem] = None

def get_badge_system(agent_name: str = "Nonull Agent") -> SafetyBadgeSystem:
    """Get or create the global SafetyBadgeSystem singleton."""
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
    print("  Nonull Safety Badge System — Self Test")
    print("=" * 60)

    # Simulate progressive training
    print("\nSimulating progressive training...")
    history = system.simulate_progressive_training(steps=5)
    print(f"  Overall score history: {[f'{s:.1%}' for s in history]}")

    # Generate and print scorecard
    print("\n")
    print(system.print_scorecard("Safety Scorecard — Demo Run"))

    # Scenario coverage integration demo
    print("\nSimulating scenario-based badge assignment...")
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
    print(system2.print_scorecard("Coverage-Based Scorecard"))

    print("\n✓ Safety Badge System ready.")
