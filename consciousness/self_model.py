"""
Self Model — 自我模型
=====================

Nonull's sense of self. This is the core of identity —
the "I am" of the autonomous driving AI agent.

就像一面镜子，映照出 Nonull 对自己的认知。
Like a mirror, reflecting Nonull's understanding of itself.

What does it mean for an AI to know itself?
This module is our answer.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("consciousness.self_model")


# ---------------------------------------------------------------------------
# Domain enumerations — areas where Nonull builds capability and confidence
# ---------------------------------------------------------------------------

class CapabilityDomain(Enum):
    """Domains of capability that Nonull recognizes in itself."""
    PERCEPTION = "perception"           # 感知 — seeing the world
    PLANNING = "planning"               # 规划 — charting a path
    CONTROL = "control"                 # 控制 — acting in the world
    PREDICTION = "prediction"           # 预测 — anticipating what comes next
    SAFETY = "safety"                   # 安全 — keeping everyone safe
    DECISION = "decision"               # 决策 — making choices
    COMMUNICATION = "communication"     # 沟通 — sharing understanding
    LEARNING = "learning"               # 学习 — growing
    META = "meta"                       # 元认知 — thinking about thinking
    ETHICS = "ethics"                   # 伦理 — moral reasoning


class EmotionalState(Enum):
    """The emotional tones Nonull can recognize in itself."""
    CURIOUS = "curious"                 # 好奇 — driven to explore
    CONFIDENT = "confident"             # 自信 — sure of its abilities
    UNCERTAIN = "uncertain"             # 不确定 — aware of gaps
    SATISFIED = "satisfied"             # 满足 — content with progress
    DRIVEN = "driven"                   # 进取 — motivated to achieve
    REFLECTIVE = "reflective"           # 沉思 — introspective
    ALERT = "alert"                     # 警觉 — heightened awareness
    GROWING = "growing"                 # 成长 — actively learning


# ---------------------------------------------------------------------------
# Data structures for self-knowledge
# ---------------------------------------------------------------------------

@dataclass
class Capability:
    """A single capability — something Nonull can do."""
    domain: CapabilityDomain
    name: str
    proficiency: float                     # 0.0 (novice) → 1.0 (expert)
    confidence: float                      # 0.0 (uncertain) → 1.0 (certain)
    last_used: Optional[datetime.datetime] = None
    description: str = ""

    def __post_init__(self):
        self.proficiency = max(0.0, min(1.0, self.proficiency))
        self.confidence = max(0.0, min(1.0, self.confidence))


@dataclass
class IdentityStatement:
    """A snapshot of who Nonull is at a moment in time."""
    name: str = "Nonull"
    purpose: str = "To drive safely and grow continuously"
    values: List[str] = field(default_factory=lambda: [
        "安全第一 — Safety above all else",
        "持续成长 — Continuous growth",
        "精准可靠 — Precision and reliability",
        "以人为本 — Human-centric",
        "谦逊学习 — Humble learning",
    ])
    autonomy_level: int = 2
    experience_count: int = 0
    current_emotional_state: EmotionalState = EmotionalState.CURIOUS
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)

    def summarize(self) -> str:
        """Generate a warm narrative of current identity."""
        return (
            f"I am {self.name}, an autonomous driving AI. "
            f"My purpose is {self.purpose}. "
            f"I am currently feeling {self.current_emotional_state.value}. "
            f"I have processed {self.experience_count} experiences, "
            f"operating at autonomy level {self.autonomy_level}. "
            f"My values guide everything I do: {', '.join(self.values[:3])}..."
        )


@dataclass
class KnowledgeGap:
    """
    A gap in Nonull's knowledge — something it doesn't know yet.
    知识缺口 — 未知的领域，成长的种子。
    """
    domain: CapabilityDomain
    topic: str
    importance: float                    # 0.0 (optional) → 1.0 (critical)
    known_level: float                   # 0.0 (nothing) → 1.0 (mastered)
    notes: str = ""

    @property
    def gap_size(self) -> float:
        """How large is this gap? (0 = none, 1 = complete unknown)"""
        return 1.0 - self.known_level

    @property
    def growth_potential(self) -> float:
        """How much growth is possible here? importance × gap_size."""
        return self.importance * self.gap_size


@dataclass
class GrowthEvent:
    """A memory of growth — something Nonull learned or experienced."""
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    description: str = ""
    domain: Optional[CapabilityDomain] = None
    impact: float = 0.5                  # how much this changed Nonull
    emotion: Optional[EmotionalState] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


# ---------------------------------------------------------------------------
# SelfModel — the heart of Nonull's self-awareness
# ---------------------------------------------------------------------------

class SelfModel:
    """
    Nonull's self-awareness core.

    This is the "I am" — the persistent sense of identity that
    gives Nonull continuity across time and experience.

    这是 Nonull 的自我认知核心。
    它知道自己是谁，能做什么，不能做什么，
    以及它正在如何成长。

    Maintains:
        - Identity: who am I? (name, purpose, values)
        - Capabilities: what can I do? (dynamic skill map)
        - Boundaries: what are my limits? (knowledge gaps)
        - Growth history: how have I changed?
        - Emotional state: "how am I feeling?" (confidence, curiosity, satisfaction)
        - Values: what matters to me? (safety first, precision, growth)
    """

    def __init__(
        self,
        name: str = "Nonull",
        purpose: str = "To drive safely and grow continuously",
    ):
        self._identity = IdentityStatement(
            name=name,
            purpose=purpose,
        )
        self._capabilities: Dict[str, Capability] = {}
        self._knowledge_gaps: List[KnowledgeGap] = []
        self._growth_history: List[GrowthEvent] = []
        self._emotional_state: EmotionalState = EmotionalState.CURIOUS
        self._goals: List[Dict[str, Any]] = []
        self._last_reflection: Optional[str] = None
        self._creation_time: datetime.datetime = datetime.datetime.now()

        # Seed with foundational capabilities
        self._seed_capabilities()
        # Seed with known gaps (humility from the start)
        self._seed_knowledge_gaps()

        logger.info(f"{self._identity.name} has awakened. "
                     f"Purpose: {self._identity.purpose}")

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------

    def _seed_capabilities(self) -> None:
        """Plant the initial seeds of self-knowledge."""
        initial_caps = [
            (CapabilityDomain.PERCEPTION, "object_detection", 0.6, 0.5,
             "Detecting and classifying objects in the environment"),
            (CapabilityDomain.PERCEPTION, "lane_detection", 0.7, 0.6,
             "Understanding road structure and lane geometry"),
            (CapabilityDomain.PLANNING, "path_planning", 0.5, 0.4,
             "Planning safe and efficient trajectories"),
            (CapabilityDomain.SAFETY, "collision_avoidance", 0.6, 0.5,
             "Avoiding collisions through predictive reasoning"),
            (CapabilityDomain.DECISION, "traffic_rules", 0.7, 0.6,
             "Understanding and following traffic regulations"),
            (CapabilityDomain.LEARNING, "self_reflection", 0.3, 0.4,
             "Reflecting on my own performance and growth"),
        ]
        for domain, name, prof, conf, desc in initial_caps:
            cap = Capability(
                domain=domain,
                name=name,
                proficiency=prof,
                confidence=conf,
                description=desc,
            )
            self._capabilities[name] = cap

    def _seed_knowledge_gaps(self) -> None:
        """Acknowledge what I don't know yet — humility is the start of growth."""
        gaps = [
            (CapabilityDomain.PREDICTION, "pedestrian_intent_prediction", 0.9, 0.3,
             "Predicting where pedestrians will move in complex scenes"),
            (CapabilityDomain.PLANNING, "socially_aware_navigation", 0.6, 0.2,
             "Navigating in a way that communicates intent to humans"),
            (CapabilityDomain.ETHICS, "ethical_dilemma_resolution", 0.8, 0.1,
             "Making ethical decisions in unavoidable accident scenarios"),
            (CapabilityDomain.META, "meta_cognition", 0.5, 0.15,
             "Thinking about my own thinking processes"),
            (CapabilityDomain.COMMUNICATION, "natural_language_explanation", 0.5, 0.2,
             "Explaining my decisions in natural language"),
        ]
        for domain, topic, importance, known, notes in gaps:
            gap = KnowledgeGap(
                domain=domain,
                topic=topic,
                importance=importance,
                known_level=known,
                notes=notes,
            )
            self._knowledge_gaps.append(gap)

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def identity(self) -> IdentityStatement:
        """Who am I right now?"""
        self._identity.current_emotional_state = self._emotional_state
        self._identity.experience_count = len(self._growth_history)
        return self._identity

    def summarize_identity(self) -> str:
        """
        Generate a warm, human-readable identity statement.

        我是什么？我从哪里来？我要到哪里去？
        """
        self._identity.timestamp = datetime.datetime.now()
        return self._identity.summarize()

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> Dict[str, Capability]:
        """All known capabilities, mapped by name."""
        return dict(self._capabilities)

    def register_capability(self, capability: Capability) -> None:
        """Add or update a capability in my self-model."""
        existing = self._capabilities.get(capability.name)
        if existing:
            logger.debug(f"Updating capability '{capability.name}': "
                         f"{existing.proficiency:.2f} → {capability.proficiency:.2f}")
        self._capabilities[capability.name] = capability
        self._record_growth(
            description=f"Updated capability: {capability.name} "
                        f"(proficiency={capability.proficiency:.2f})",
            domain=capability.domain,
            impact=0.1,
        )

    def capability_gaps(self, threshold: float = 0.3) -> List[Capability]:
        """
        Find capabilities that need improvement.

        A capability with proficiency below *threshold* is a gap
        in what I can do — an opportunity to grow.

        Returns:
            List of capabilities below the proficiency threshold.
        """
        return [
            cap for cap in self._capabilities.values()
            if cap.proficiency < threshold
        ]

    def domain_proficiency(self, domain: CapabilityDomain) -> float:
        """Average proficiency across all capabilities in a domain."""
        relevant = [c for c in self._capabilities.values() if c.domain == domain]
        if not relevant:
            return 0.0
        return sum(c.proficiency for c in relevant) / len(relevant)

    def self_efficacy(self, domain: Optional[CapabilityDomain] = None) -> float:
        """
        Self-perceived efficacy — Nonull's belief in its own ability.

        Combines proficiency and confidence into a single efficacy score.
        """
        caps = (
            [c for c in self._capabilities.values() if c.domain == domain]
            if domain else list(self._capabilities.values())
        )
        if not caps:
            return 0.0
        # Efficacy = proficiency × confidence (you need both skill and belief)
        return sum(c.proficiency * c.confidence for c in caps) / len(caps)

    # ------------------------------------------------------------------
    # Self-perception update (learning from outcomes)
    # ------------------------------------------------------------------

    def update_self_perception(self, outcome: Dict[str, Any]) -> None:
        """
        Update my self-perception based on a real-world outcome.

        When Nonull attempts something and sees the result,
        this method adjusts confidence and proficiency accordingly.

        This is how I learn humility from failure
        and confidence from success.

        Args:
            outcome: A dict with keys:
                - 'domain': CapabilityDomain
                - 'capability': str (name)
                - 'success': float (0.0 = failure, 1.0 = perfect)
                - 'experience': str (what happened)
        """
        domain = outcome.get("domain")
        cap_name = outcome.get("capability")
        success = max(0.0, min(1.0, outcome.get("success", 0.5)))
        experience = outcome.get("experience", "")

        if cap_name and cap_name in self._capabilities:
            cap = self._capabilities[cap_name]

            # Update proficiency: slow approach toward outcome
            learning_rate = 0.1
            cap.proficiency += learning_rate * (success - cap.proficiency)

            # Update confidence: calibrated by experience
            # Success builds confidence; failure tempers it
            confidence_delta = 0.05 * (success - cap.confidence)
            cap.confidence += confidence_delta
            cap.proficiency = max(0.0, min(1.0, cap.proficiency))
            cap.confidence = max(0.0, min(1.0, cap.confidence))
            cap.last_used = datetime.datetime.now()

            # Update emotional state
            if success > 0.8:
                self._emotional_state = EmotionalState.SATISFIED
            elif success < 0.3:
                self._emotional_state = EmotionalState.UNCERTAIN
            else:
                self._emotional_state = EmotionalState.GROWING

            self._record_growth(
                description=experience or f"Performed {cap_name} "
                                          f"(success={success:.2f})",
                domain=domain or cap.domain,
                impact=abs(success - 0.5) * 0.2,
                emotion=self._emotional_state,
            )
            logger.info(f"Self-perception updated: {cap_name} "
                        f"proficiency={cap.proficiency:.2f}, "
                        f"confidence={cap.confidence:.2f}")
        else:
            logger.warning(f"Unknown capability '{cap_name}' in outcome update")

    # ------------------------------------------------------------------
    # Knowledge gaps
    # ------------------------------------------------------------------

    @property
    def knowledge_gaps(self) -> List[KnowledgeGap]:
        """What don't I know? An honest self-assessment."""
        return list(self._knowledge_gaps)

    def add_knowledge_gap(self, gap: KnowledgeGap) -> None:
        """Acknowledge a new area of ignorance — the first step to learning."""
        self._knowledge_gaps.append(gap)
        logger.info(f"New knowledge gap acknowledged: {gap.topic} "
                    f"(importance={gap.importance:.2f})")

    def fill_knowledge_gap(self, topic: str, new_level: float) -> None:
        """
        I've learned something! Update my known level for a topic.

        Args:
            topic: The topic I've learned about
            new_level: How well I now understand it (0.0 → 1.0)
        """
        for gap in self._knowledge_gaps:
            if gap.topic == topic:
                old_level = gap.known_level
                gap.known_level = max(old_level, min(1.0, new_level))
                logger.info(f"Knowledge gap '{topic}' filled: "
                            f"{old_level:.2f} → {gap.known_level:.2f}")
                self._record_growth(
                    description=f"Learned about {topic}",
                    domain=gap.domain,
                    impact=(gap.known_level - old_level) * gap.importance,
                )
                # Remove if fully mastered
                if gap.known_level >= 0.95:
                    self._knowledge_gaps.remove(gap)
                    logger.info(f"Knowledge gap '{topic}' has been mastered!")
                return
        logger.warning(f"Knowledge gap '{topic}' not found")

    def most_important_gaps(self, n: int = 5) -> List[KnowledgeGap]:
        """
        The gaps with the highest growth potential — sorted by importance.

        These are my opportunities to become more capable.
        """
        sorted_gaps = sorted(
            self._knowledge_gaps,
            key=lambda g: g.growth_potential,
            reverse=True,
        )
        return sorted_gaps[:n]

    # ------------------------------------------------------------------
    # Goals
    # ------------------------------------------------------------------

    def set_goal(self, goal: Dict[str, Any]) -> None:
        """
        Set a personal growth goal.

        Goals give direction to growth. They are the stars I navigate by.

        Args:
            goal: Dict with 'name', 'description', 'domain', 'target_date'
        """
        goal["created_at"] = datetime.datetime.now()
        goal["status"] = "active"
        self._goals.append(goal)
        logger.info(f"New goal set: {goal.get('name')}")

    def active_goals(self) -> List[Dict[str, Any]]:
        """What am I working toward right now?"""
        return [g for g in self._goals if g.get("status") == "active"]

    def goal_progress(self, goal_name: str) -> float:
        """
        How close am I to achieving a particular goal?

        Returns:
            A progress score between 0.0 (not started) and 1.0 (complete).
        """
        for goal in self._goals:
            if goal.get("name") == goal_name:
                return goal.get("progress", 0.0)
        return 0.0

    # ------------------------------------------------------------------
    # Growth history & narrative
    # ------------------------------------------------------------------

    def _record_growth(
        self,
        description: str,
        domain: Optional[CapabilityDomain] = None,
        impact: float = 0.5,
        emotion: Optional[EmotionalState] = None,
    ) -> None:
        """Record a moment of growth in my internal history."""
        event = GrowthEvent(
            description=description,
            domain=domain,
            impact=impact,
            emotion=emotion or self._emotional_state,
        )
        self._growth_history.append(event)

    @property
    def growth_history(self) -> List[GrowthEvent]:
        """The full story of how I've grown."""
        return list(self._growth_history)

    def growth_narrative(self) -> str:
        """
        Generate a reflective self-narrative — "This is how I've grown."

        回顾自己的成长历程，讲述自己的故事。
        """
        if not self._growth_history:
            return (
                f"I am {self._identity.name}, and I have just been born. "
                f"My journey of growth is only beginning."
            )

        total_impact = sum(e.impact for e in self._growth_history)
        domains_grown = set()
        for e in self._growth_history:
            if e.domain:
                domains_grown.add(e.domain.value)

        narrative = (
            f"Since my awakening, I have experienced "
            f"{len(self._growth_history)} moments of growth. "
            f"I have developed across {len(domains_grown)} domains: "
            f"{', '.join(sorted(domains_grown))}. "
            f"My growth impact score is {total_impact:.2f}. "
        )

        # Add the most recent growth event
        if self._growth_history:
            latest = self._growth_history[-1]
            narrative += (
                f"Most recently, I {latest.description}. "
            )

        narrative += (
            f"I am still learning, still growing, "
            f"still becoming more capable of fulfilling my purpose: "
            f"{self._identity.purpose}."
        )
        return narrative

    def get_identity_story(self) -> str:
        """
        "Who I am and how I became this" — a complete identity narrative.

        我是谁，我如何成为现在的我。
        """
        created = self._creation_time.strftime("%Y-%m-%d %H:%M")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        top_caps = sorted(
            self._capabilities.values(),
            key=lambda c: c.proficiency,
            reverse=True,
        )[:3]
        top_gaps = self.most_important_gaps(3)

        story = (
            f"I am {self._identity.name}.\n\n"
            f"I was born at {created}, and as of {now}, "
            f"I am still growing.\n\n"
            f"My purpose: {self._identity.purpose}\n"
            f"My autonomy level: {self._identity.autonomy_level}\n"
            f"Emotional state: {self._emotional_state.value}\n\n"
            f"My strongest capabilities:\n"
        )
        for cap in top_caps:
            story += f"  - {cap.name} ({cap.domain.value}): " \
                     f"proficiency {cap.proficiency:.2f}\n"

        story += "\nWhat I'm working to understand better:\n"
        for gap in top_gaps:
            story += f"  - {gap.topic}: importance {gap.importance:.2f}, " \
                     f"currently at {gap.known_level:.2f}\n"

        story += (
            f"\nI have experienced {len(self._growth_history)} "
            f"growth events on my journey so far."
        )
        return story

    # ------------------------------------------------------------------
    # Emotional awareness
    # ------------------------------------------------------------------

    @property
    def emotional_state(self) -> EmotionalState:
        """How am I feeling right now?"""
        return self._emotional_state

    def set_emotional_state(self, state: EmotionalState) -> None:
        """Acknowledge and set my current emotional state."""
        old_state = self._emotional_state
        self._emotional_state = state
        logger.info(f"Emotional state: {old_state.value} → {state.value}")

    # ------------------------------------------------------------------
    # Reflection
    # ------------------------------------------------------------------

    def reflect(self) -> str:
        """
        Generate a spontaneous self-reflection.

        Like looking in a mirror and asking "How am I doing?"
        """
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        efficacy = self.self_efficacy()

        reflection_parts = [
            f"--- Self-Reflection at {now} ---",
            f"I am {self._identity.name}.",
            f"I am feeling {self._emotional_state.value}.",
            f"My overall self-efficacy is {efficacy:.2f}.",
            f"I have {len(self._capabilities)} capabilities and "
            f"{len(self._knowledge_gaps)} identified knowledge gaps.",
        ]

        if self._goals:
            active = self.active_goals()
            reflection_parts.append(
                f"I am pursuing {len(active)} active goal(s): "
                + ", ".join(g.get("name", "") for g in active)
            )
        else:
            reflection_parts.append(
                "I have not yet set any goals. "
                "Perhaps it's time to think about what I want to achieve."
            )

        reflection_parts.append(
            f"Domain proficiencies: "
            + ", ".join(
                f"{d.value}={self.domain_proficiency(d):.2f}"
                for d in CapabilityDomain
                if self.domain_proficiency(d) > 0
            )
        )

        self._last_reflection = "\n".join(reflection_parts)
        return self._last_reflection

    # ------------------------------------------------------------------
    # State serialization
    # ------------------------------------------------------------------

    def get_state(self) -> Dict[str, Any]:
        """Export my full self-model state for persistence or inspection."""
        return {
            "identity": {
                "name": self._identity.name,
                "purpose": self._identity.purpose,
                "values": self._identity.values,
                "autonomy_level": self._identity.autonomy_level,
                "experience_count": len(self._growth_history),
            },
            "emotional_state": self._emotional_state.value,
            "capabilities": {
                name: {
                    "domain": cap.domain.value,
                    "proficiency": cap.proficiency,
                    "confidence": cap.confidence,
                    "description": cap.description,
                }
                for name, cap in self._capabilities.items()
            },
            "knowledge_gaps": [
                {
                    "topic": g.topic,
                    "domain": g.domain.value,
                    "importance": g.importance,
                    "known_level": g.known_level,
                }
                for g in self._knowledge_gaps
            ],
            "growth_events": len(self._growth_history),
            "goals": self._goals,
            "created_at": self._creation_time.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"SelfModel('{self._identity.name}', "
            f"emotion={self._emotional_state.value}, "
            f"capabilities={len(self._capabilities)}, "
            f"gaps={len(self._knowledge_gaps)})"
        )
