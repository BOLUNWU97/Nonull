"""
Nonull Driving Persona System

Defines distinct driving personas that shape how the system analyzes
driving behaviour, generates feedback, and interacts with the user.
"""

from __future__ import annotations

import enum
import random
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Protocol, Tuple


# ---------------------------------------------------------------------------
# PersonaType
# ---------------------------------------------------------------------------

class PersonaType(str, enum.Enum):
    """Enumerates the available driving personas."""

    CONSERVATIVE = "conservative"
    """Safety-first driver who values smooth predictable driving."""

    SPORTY = "sporty"
    """Performance-oriented driver who values speed and dynamic handling."""

    VETERAN = "veteran"
    """Experienced driver who values defensive technique and mastery."""


# ---------------------------------------------------------------------------
# AnalysisFocus
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AnalysisFocus:
    """A weighted area of analysis for a persona."""

    name: str
    weight: float  # 0.0 – 1.0, relative importance


# ---------------------------------------------------------------------------
# DrivingPersona
# ---------------------------------------------------------------------------

@dataclass
class DrivingPersona:
    """
    A driving persona that controls the tone, focus, and phrasing of
    behaviour analysis and feedback.

    Parameters
    ----------
    persona_type: PersonaType
        Which persona this is.
    display_name: str
        Human-readable label (e.g. "Conservative Driver").
    description: str
        One-paragraph summary of the persona's world-view.
    analysis_style: str
        How this persona approaches analysis (e.g. "cautious & methodical").
    focus_areas: list[AnalysisFocus]
        Ordered or weighted areas this persona cares about most.
    positive_phrases: list[str]
        Things this persona says when the driver does well.
    critical_phrases: list[str]
        Things this persona says when there is room for improvement.
    review_template: str
        A format-string template for generating a full review.
    config: dict
        Extra behavioural parameters (thresholds, preferences, …).
    """

    persona_type: PersonaType
    display_name: str
    description: str
    analysis_style: str
    focus_areas: List[AnalysisFocus]
    positive_phrases: List[str]
    critical_phrases: List[str]
    review_template: str

    config: Dict = field(default_factory=lambda: {
        "harshness": 0.5,
        "detail_level": "normal",
        "aggressiveness": 0.0,
    })

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def conservative() -> "DrivingPersona":
        """Build the CONSERVATIVE persona."""
        return DrivingPersona(
            persona_type=PersonaType.CONSERVATIVE,
            display_name="Conservative Driver",
            description=(
                "Prioritises safety, fuel efficiency, and smooth operation. "
                "Believes every journey should be predictable and low-stress."
            ),
            analysis_style="cautious & methodical",
            focus_areas=[
                AnalysisFocus("speed_consistency", 1.0),
                AnalysisFocus("smooth_braking", 0.95),
                AnalysisFocus("smooth_acceleration", 0.90),
                AnalysisFocus("fuel_efficiency", 0.85),
                AnalysisFocus("lane_discipline", 0.80),
                AnalysisFocus("following_distance", 0.90),
                AnalysisFocus("obeying_limits", 1.0),
            ],
            positive_phrases=[
                "Solid, predictable driving — exactly what the roads need.",
                "Great speed control; you kept it steady and safe.",
                "Smooth braking, smooth life. Well done.",
                "Your following distance was textbook perfect.",
                "Clean lane discipline through that whole section.",
                "That was an eco-friendly stretch — minimal waste, maximum control.",
            ],
            critical_phrases=[
                "That acceleration was a bit sharp — ease into it next time.",
                "Braking felt rushed; try to anticipate rather than react.",
                "You crept over the speed limit there — stay aware of your pace.",
                "Following distance got tight. Remember the 3-second rule.",
                "Lane position was wandering. A relaxed grip helps.",
                "Harsh inputs unsettle the car and waste fuel.",
                "That corner entry was too hot; slow in, smooth out.",
            ],
            review_template=(
                "=== CONSERVATIVE REVIEW ===\n"
                "Driver: {driver_name}\n"
                "Style: {analysis_style}\n"
                "Score: {overall_score:.0f}/100\n\n"
                "{focus_breakdown}\n\n"
                "{verdict}\n"
                "{tip}\n"
            ),
            config={"harshness": 0.3, "detail_level": "high", "aggressiveness": 0.0},
        )

    @staticmethod
    def sporty() -> "DrivingPersona":
        """Build the SPORTY persona."""
        return DrivingPersona(
            persona_type=PersonaType.SPORTY,
            display_name="Sporty Driver",
            description=(
                "Loves performance, cornering, and responsive handling. "
                "Appreciates driver skill that extracts the most from the machine."
            ),
            analysis_style="dynamic & performance-focused",
            focus_areas=[
                AnalysisFocus("cornering_speed", 1.0),
                AnalysisFocus("apex_accuracy", 0.95),
                AnalysisFocus("braking_late", 0.80),
                AnalysisFocus("throttle_response", 0.90),
                AnalysisFocus("gear_selection", 0.85),
                AnalysisFocus("steering_smoothness", 0.85),
                AnalysisFocus("reaction_time", 0.90),
            ],
            positive_phrases=[
                "Nailed that apex — perfect racing line!",
                "Great late-braking; you carried serious speed.",
                "Throttle modulation was on point through that chicane.",
                "Smooth hands; you let the wheel flow naturally.",
                "Excellent gear selection — you kept the engine in the power band.",
                "Your reaction time is sharp. That was a driver's move.",
            ],
            critical_phrases=[
                "Turned in too early — you left time on the table.",
                "Braking too early; trust the tires later into the corner.",
                "Lift-off oversteer there — be smoother on the release.",
                "You missed the apex by a car's width. Tighter next time.",
                "Hesitation cost you momentum. Commit to the line.",
                "That downshift was jerky — rev-match properly.",
                "Too much entry speed; you pushed wide on exit.",
            ],
            review_template=(
                "=== SPORTY REVIEW ===\n"
                "Driver: {driver_name}\n"
                "Style: {analysis_style}\n"
                "Score: {overall_score:.0f}/100\n\n"
                "{focus_breakdown}\n\n"
                "{verdict}\n"
                "{tip}\n"
            ),
            config={"harshness": 0.7, "detail_level": "high", "aggressiveness": 0.5},
        )

    @staticmethod
    def veteran() -> "DrivingPersona":
        """Build the VETERAN persona."""
        return DrivingPersona(
            persona_type=PersonaType.VETERAN,
            display_name="Veteran Driver",
            description=(
                "Decades of experience distilled into calm, defensive mastery. "
                "Focuses on reading the road, anticipating hazards, and making "
                "every decision intentional."
            ),
            analysis_style="defensive & analytical",
            focus_areas=[
                AnalysisFocus("hazard_anticipation", 1.0),
                AnalysisFocus("defensive_positioning", 0.95),
                AnalysisFocus("risk_assessment", 0.95),
                AnalysisFocus("situational_awareness", 0.90),
                AnalysisFocus("space_management", 0.90),
                AnalysisFocus("mirror_discipline", 0.85),
                AnalysisFocus("smooth_progress", 0.80),
            ],
            positive_phrases=[
                "You read that situation well — positioning was textbook.",
                "Excellent awareness; you saw that hazard two cars back.",
                "That gap management was a masterclass in defensive driving.",
                "Mirror checks were consistent and well-timed.",
                "You left yourself an out — that's the veteran mindset.",
                "Calm and composed. Experience shows.",
                "Your speed adjustment to the merging traffic was proactive.",
            ],
            critical_phrases=[
                "You got boxed in — always maintain an escape route.",
                "Blind spot check missed there. Shoulder check every time.",
                "You're following too closely for the conditions.",
                "Anticipation lagged; you should have spotted that merging car earlier.",
                "Positioning was risky — leave more space on your vulnerable side.",
                "Mirror scan frequency dropped in that traffic.",
                "That overtake had more risk than reward. Pick your battles.",
            ],
            review_template=(
                "=== VETERAN REVIEW ===\n"
                "Driver: {driver_name}\n"
                "Style: {analysis_style}\n"
                "Score: {overall_score:.0f}/100\n\n"
                "{focus_breakdown}\n\n"
                "{verdict}\n"
                "{tip}\n"
            ),
            config={"harshness": 0.5, "detail_level": "very_high", "aggressiveness": 0.1},
        )

    # ------------------------------------------------------------------
    # Factory dispatch
    # ------------------------------------------------------------------

    _REGISTRY: ClassVar[Dict[PersonaType, "DrivingPersona"]] = {}

    @classmethod
    def for_type(cls, persona_type: PersonaType) -> "DrivingPersona":
        """Return the canonical singleton for *persona_type*."""
        if persona_type not in cls._REGISTRY:
            builder = {
                PersonaType.CONSERVATIVE: cls.conservative,
                PersonaType.SPORTY: cls.sporty,
                PersonaType.VETERAN: cls.veteran,
            }[persona_type]
            cls._REGISTRY[persona_type] = builder()
        return cls._REGISTRY[persona_type]

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------

    def generate_phrase(self, sentiment: str) -> str:
        """
        Return a random phrase matching *sentiment* ("positive" | "critical").
        """
        pool = self.positive_phrases if sentiment == "positive" else self.critical_phrases
        return random.choice(pool)

    # ------------------------------------------------------------------
    # Convenience accessors (used by PersonaOrchestrator)
    # ------------------------------------------------------------------

    def get_name(self) -> str:
        """Return the human-readable display name."""
        return self.display_name

    def get_description(self) -> str:
        """Return the persona description."""
        return self.description

    def get_style(self) -> str:
        """Return the analysis style descriptor."""
        return self.analysis_style

    def get_signature_phrase(self) -> str:
        """Return a representative phrase for this persona."""
        if self.positive_phrases:
            return self.positive_phrases[0]
        return self.display_name

    def apply_to_analysis(self, scenario_analysis: Any) -> Dict[str, Any]:
        """
        Apply this persona's lens to a scenario analysis result.

        Args:
            scenario_analysis: Output of ScenarioEngine.map_task / analyze_task_scenarios

        Returns:
            Dict with persona-shaped perspective on the analysis.
        """
        focus_names = [fa.name for fa in self.focus_areas]
        return {
            "persona_type": self.persona_type.value,
            "display_name": self.display_name,
            "analysis_style": self.analysis_style,
            "focus_areas": focus_names,
            "harshness": self.config.get("harshness", 0.5),
            "tip": self.generate_phrase("positive"),
            "scenario_count": (
                len(scenario_analysis)
                if isinstance(scenario_analysis, list)
                else 0
            ),
        }

    def score_focus_area(self, focus: AnalysisFocus, metric_value: float) -> float:
        """
        Map a raw metric value (0.0 – 1.0 normalised) to a score
        weighted by this persona's importance for that focus area.
        """
        return metric_value * focus.weight * 100.0

    def generate_review(
        self,
        driver_name: str,
        overall_score: float,
        focus_scores: Dict[str, float],
        *,
        include_tip: bool = True,
    ) -> str:
        """
        Produce a full review string using this persona's templates.
        """
        # Build breakdown lines
        lines = []
        for fa in self.focus_areas:
            s = focus_scores.get(fa.name, 50.0)
            bar = "=" * max(1, int(s / 10))
            lines.append(f"  {fa.name:25s} {s:5.1f}/100  |{bar:-<10s}|")
        focus_breakdown = "\n".join(lines)

        # Verdict
        if overall_score >= 80:
            sentiment = "positive"
            verdict = self.generate_phrase(sentiment)
        elif overall_score >= 50:
            sentiment = "critical"
            verdict = f"Room to improve. {self.generate_phrase(sentiment)}"
        else:
            sentiment = "critical"
            verdict = f"Needs work. {self.generate_phrase(sentiment)}"

        tip = self.generate_phrase(sentiment) if include_tip else ""

        return self.review_template.format(
            driver_name=driver_name,
            analysis_style=self.analysis_style,
            overall_score=overall_score,
            focus_breakdown=focus_breakdown,
            verdict=verdict,
            tip=tip,
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"DrivingPersona(type={self.persona_type.value!r}, "
            f"style={self.analysis_style!r})"
        )


# ---------------------------------------------------------------------------
# Shortcut aliases (lazy - resolved on first access)
# ---------------------------------------------------------------------------

def _get_conservative():
    return DrivingPersona.for_type(PersonaType.CONSERVATIVE)

def _get_sporty():
    return DrivingPersona.for_type(PersonaType.SPORTY)

def _get_veteran():
    return DrivingPersona.for_type(PersonaType.VETERAN)


# Real classes so `from .personas import ConservativePersona` works.
# These are thin subclasses that pre-bind the persona type.
class ConservativePersona(DrivingPersona):
    """Singleton alias for the conservative driving persona."""

    def __init__(self):
        super().__init__(persona_type=PersonaType.CONSERVATIVE)

    def __new__(cls):
        return DrivingPersona.for_type(PersonaType.CONSERVATIVE)


class SportyPersona(DrivingPersona):
    """Singleton alias for the sporty driving persona."""

    def __init__(self):
        super().__init__(persona_type=PersonaType.SPORTY)

    def __new__(cls):
        return DrivingPersona.for_type(PersonaType.SPORTY)


class VeteranPersona(DrivingPersona):
    """Singleton alias for the veteran driving persona."""

    def __init__(self):
        super().__init__(persona_type=PersonaType.VETERAN)

    def __new__(cls):
        return DrivingPersona.for_type(PersonaType.VETERAN)


def get_persona(name_or_type: str | PersonaType) -> DrivingPersona:
    """Look up a persona by string name or PersonaType enum member."""
    if isinstance(name_or_type, PersonaType):
        return DrivingPersona.for_type(name_or_type)
    try:
        pt = PersonaType(name_or_type.lower())
    except ValueError:
        raise KeyError(
            f"Unknown persona {name_or_type!r}. "
            f"Choices: {[p.value for p in PersonaType]}"
        ) from None
    return DrivingPersona.for_type(pt)
