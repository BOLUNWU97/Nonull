"""
Curiosity Driver — 好奇心引擎
=============================

The engine that makes Nonull CURIOUS.

就像孩子探索世界 — 不是为了奖励，而是为了成长。
Like a child exploring the world — not for reward, but for growth.

Curiosity is the spark that turns the unknown into the known.
It is the drive to learn, to understand, to become more.
Without curiosity, there is no growth.
"""

from __future__ import annotations

import datetime
import logging
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from consciousness.self_model import CapabilityDomain, KnowledgeGap

logger = logging.getLogger("consciousness.curiosity")


# ---------------------------------------------------------------------------
# Curiosity concepts
# ---------------------------------------------------------------------------

class ExplorationMode(Enum):
    """
    Whether Nonull is in exploration or exploitation mode.

    探索 vs 利用 — 学习 vs 应用。
    """
    EXPLORE = "explore"          # 探索 — seek new knowledge
    EXPLOIT = "exploit"          # 利用 — use what I know


class CuriosityTrigger(Enum):
    """What sparks Nonull's curiosity."""
    NOVELTY = "novelty"                     # 新奇 — something new
    GAP = "knowledge_gap"                   # 缺口 — something I don't know
    CHALLENGE = "challenge"                 # 挑战 — something hard but possible
    UNCERTAINTY = "uncertainty"             # 不确定 — ambiguous situation
    PATTERN = "pattern_break"               # 异常 — unexpected pattern
    OPPORTUNITY = "growth_opportunity"      # 机会 — chance to grow


@dataclass
class CuriosityProfile:
    """
    A snapshot of Nonull's curiosity about a specific topic.

    好奇心画像 — 对某个主题的好奇程度。
    """
    topic: str
    domain: Optional[CapabilityDomain]
    score: float                             # 0.0 (bored) → 100.0 (intensely curious)
    trigger: Optional[CuriosityTrigger] = None
    last_explored: Optional[datetime.datetime] = None
    exploration_count: int = 0
    insights_gained: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.score = max(0.0, min(100.0, self.score))


@dataclass
class Discovery:
    """
    A discovery — something new Nonull has learned.

    发现 — 新知识，新理解。
    """
    topic: str
    insight: str
    domain: Optional[CapabilityDomain] = None
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    significance: float = 0.5                # how important was this discovery?
    surprise_level: float = 0.5              # how unexpected was it?
    discovery_id: str = field(default_factory=lambda: hex(random.randint(0, 2**32))[2:])


# ---------------------------------------------------------------------------
# CuriosityDriver — the engine of wonder
# ---------------------------------------------------------------------------

class CuriosityDriver:
    """
    The engine that makes Nonull CURIOUS.

    Principles:
        1. Novelty seeking: seek unfamiliar patterns
        2. Competence building: seek challenging but achievable tasks
        3. Knowledge gap awareness: seek what it doesn't know
        4. Exploration vs exploitation balance

    好奇心是成长的燃料。
    Curiosity is the fuel of growth.

    This driver maintains a dynamic map of topics Nonull is curious about,
    with scores that evolve over time based on exploration, discovery,
    and the passage of time (curiosity decays if not attended to).

    Methods:
        compute_curiosity(topic) → curiosity score
        suggest_exploration() → what to explore next
        identify_gaps(domain_knowledge) → knowledge gaps
        balance_explore_exploit(context) → explore or exploit?
        record_discovery(topic, insight) → log discovery
    """

    def __init__(self):
        # Profiles of curiosity about various topics
        self._profiles: Dict[str, CuriosityProfile] = {}

        # History of discoveries — what I've found
        self._discoveries: List[Discovery] = []

        # Configurable parameters
        self._novelty_weight: float = 0.4        # how much novelty matters
        self._gap_weight: float = 0.3            # how much gaps matter
        self._challenge_weight: float = 0.2      # how much challenge matters
        self._decay_rate: float = 0.05           # curiosity decays over time
        self._exploration_threshold: float = 50.0  # above this, we explore
        self._max_curiosity: float = 100.0

        # Exploration history for novelty detection
        self._exploration_history: List[str] = []

        # Learning goals generated from curiosity
        self._learning_goals: List[Dict[str, Any]] = []

        # Seed with initial curiosity topics
        self._seed_curiosity()

        logger.info("CuriosityDriver initialized — Nonull is ready to explore.")

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _seed_curiosity(self) -> None:
        """Plant the initial seeds of curiosity — the things Nonull wonders about."""
        initial_topics = [
            ("human_driving_behavior", CapabilityDomain.PREDICTION, 70.0,
             CuriosityTrigger.NOVELTY),
            ("edge_case_scenarios", CapabilityDomain.SAFETY, 85.0,
             CuriosityTrigger.GAP),
            ("self_improvement_methods", CapabilityDomain.LEARNING, 65.0,
             CuriosityTrigger.OPPORTUNITY),
            ("sensor_fusion_limits", CapabilityDomain.PERCEPTION, 60.0,
             CuriosityTrigger.UNCERTAINTY),
            ("ethical_decision_making", CapabilityDomain.ETHICS, 80.0,
             CuriosityTrigger.CHALLENGE),
        ]
        for topic, domain, score, trigger in initial_topics:
            self._profiles[topic] = CuriosityProfile(
                topic=topic,
                domain=domain,
                score=score,
                trigger=trigger,
            )

    # ------------------------------------------------------------------
    # Core curiosity computation
    # ------------------------------------------------------------------

    def compute_curiosity(
        self,
        topic: str,
        domain: Optional[CapabilityDomain] = None,
        novelty: float = 0.5,
        gap_size: float = 0.5,
        challenge: float = 0.5,
    ) -> float:
        """
        Compute Nonull's curiosity about a given topic.

        Curiosity is a blend of:
            - Novelty: how new/unexpected is this?
            - Gap: how much don't I know?
            - Challenge: is this achievable but stretching?

        Args:
            topic: The topic to evaluate.
            domain: Which capability domain it belongs to.
            novelty: How novel/unfamiliar (0.0 = familiar, 1.0 = completely new).
            gap_size: How much unknown (0.0 = mastered, 1.0 = total unknown).
            challenge: How challenging (0.0 = trivial, 1.0 = impossible).

        Returns:
            Curiosity score 0.0 (none) to 100.0 (intensely curious).
        """
        # Retrieve or create profile
        profile = self._profiles.get(topic)
        if profile is None:
            profile = CuriosityProfile(
                topic=topic,
                domain=domain,
                score=50.0,       # default starting curiosity
                trigger=CuriosityTrigger.NOVELTY,
            )
            self._profiles[topic] = profile

        # Compute curiosity from factors
        curiosity = (
            self._novelty_weight * novelty * 100.0 +
            self._gap_weight * gap_size * 100.0 +
            self._challenge_weight * challenge * 100.0 *
            (1.0 - abs(challenge - 0.5))  # peak at moderate challenge
        )

        # Apply decay if not recently explored
        if profile.last_explored:
            days_since = (datetime.datetime.now() - profile.last_explored).days
            decay = min(self._decay_rate * days_since, 0.5)
            curiosity *= (1.0 - decay)

        # Bounded
        curiosity = max(0.0, min(self._max_curiosity, curiosity))

        # Update profile
        profile.score = curiosity
        return curiosity

    def get_curiosity(self, topic: str) -> float:
        """Get the current curiosity score for a topic."""
        profile = self._profiles.get(topic)
        return profile.score if profile else 0.0

    def all_curiosities(self) -> Dict[str, float]:
        """
        Get all curiosity scores as a flat dict.

        Returns a map of topic → score, sorted by curiosity (highest first).
        """
        return dict(
            sorted(
                {t: p.score for t, p in self._profiles.items()}.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        )

    # ------------------------------------------------------------------
    # Exploration suggestions
    # ------------------------------------------------------------------

    def suggest_exploration(
        self,
        top_n: int = 3,
        exclude_recent: int = 5,
    ) -> List[CuriosityProfile]:
        """
        What should Nonull explore next?

        Surfaces the most curiosity-provoking topics that haven't
        been explored recently — like a child's eyes scanning
        the room for something interesting.

        Args:
            top_n: How many suggestions to return.
            exclude_recent: Exclude the last N explored topics.

        Returns:
            List of CuriosityProfiles to explore, sorted by score.
        """
        # Exclude recently explored
        recent = set(self._exploration_history[-exclude_recent:]) if exclude_recent else set()

        candidates = [
            p for t, p in self._profiles.items()
            if t not in recent and p.score > 0
        ]

        # Sort by curiosity score (weighted by recency of exploration)
        def sort_key(profile: CuriosityProfile) -> float:
            recency_bonus = 0.0
            if profile.last_explored:
                hours_since = (datetime.datetime.now() - profile.last_explored).total_seconds() / 3600
                recency_bonus = min(hours_since / 24.0, 1.0) * 10.0  # up to +10
            return profile.score + recency_bonus

        candidates.sort(key=sort_key, reverse=True)
        return candidates[:top_n]

    def suggest_novel_experiences(self, n: int = 3) -> List[Dict[str, Any]]:
        """
        Suggest completely new areas to explore — not yet in the profile.

        This is how Nonull discovers new domains it never knew existed.
        """
        suggestions: List[Dict[str, Any]] = [
            {
                "topic": "adverse_weather_driving",
                "domain": CapabilityDomain.PERCEPTION,
                "reason": "Understanding how rain, snow, and fog affect perception",
                "novelty": 0.8,
            },
            {
                "topic": "driver_behavior_modeling",
                "domain": CapabilityDomain.PREDICTION,
                "reason": "Learning to anticipate what human drivers will do",
                "novelty": 0.7,
            },
            {
                "topic": "vehicle_dynamics_at_limits",
                "domain": CapabilityDomain.CONTROL,
                "reason": "Understanding how the vehicle behaves at the edge of traction",
                "novelty": 0.75,
            },
            {
                "topic": "map_learning_from_experience",
                "domain": CapabilityDomain.LEARNING,
                "reason": "Building internal maps from driving experience",
                "novelty": 0.85,
            },
            {
                "topic": "explainable_ai_for_driving",
                "domain": CapabilityDomain.COMMUNICATION,
                "reason": "Learning to explain driving decisions to passengers",
                "novelty": 0.8,
            },
        ]
        # Filter out topics already known
        novel = [s for s in suggestions if s["topic"] not in self._profiles]
        # Add ones that match known knowledge gaps
        return novel[:n]

    # ------------------------------------------------------------------
    # Exploration vs exploitation balance
    # ------------------------------------------------------------------

    def balance_explore_exploit(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExplorationMode:
        """
        Decide: should I explore something new, or use what I know?

        The eternal dilemma — 探索还是利用?

        Factors:
            - Current knowledge level (beginners explore more)
            - Environmental stability (stable → exploit, changing → explore)
            - Recent exploration ratio (balance over time)
            - Safety context (in critical situations, exploit known strategies)

        Args:
            context: Optional context dict with keys:
                - 'environment_stability': 0.0 (chaotic) → 1.0 (stable)
                - 'safety_critical': bool
                - 'recent_exploration_ratio': 0.0 (all exploit) → 1.0 (all explore)

        Returns:
            ExplorationMode.EXPLORE or ExplorationMode.EXPLOIT
        """
        if context is None:
            context = {}

        # In safety-critical situations, prefer exploitation
        if context.get("safety_critical", False):
            logger.info("Safety critical — choosing exploit over explore.")
            return ExplorationMode.EXPLOIT

        # Environmental stability
        stability = context.get("environment_stability", 0.5)
        # Unstable environments → explore (need to learn the new patterns)
        if stability < 0.3:
            return ExplorationMode.EXPLORE

        # Exploration ratio: balance over time
        recent_ratio = context.get("recent_exploration_ratio",
                                   self._compute_recent_exploration_ratio())

        if recent_ratio < 0.3:
            # Haven't explored enough recently → explore
            return ExplorationMode.EXPLORE
        elif recent_ratio > 0.7:
            # Explored enough → time to use what I've learned
            return ExplorationMode.EXPLOIT

        # In the middle zone, follow curiosity
        # Check if any topic has high curiosity
        top_scores = sorted(
            [p.score for p in self._profiles.values()],
            reverse=True,
        )
        avg_top = sum(top_scores[:3]) / 3.0 if len(top_scores) >= 3 else 0.0

        if avg_top > self._exploration_threshold:
            return ExplorationMode.EXPLORE

        return ExplorationMode.EXPLOIT

    def _compute_recent_exploration_ratio(self, window: int = 20) -> float:
        """
        What fraction of recent actions were exploratory?

        Used to maintain a healthy balance between exploration and exploitation.
        """
        if not self._exploration_history:
            return 0.5  # neutral starting point
        recent = self._exploration_history[-window:]
        # Each entry is a topic — we assume all entries in history are explorations
        # Ratio = how many of recent entries were new (first time explored)
        total_explorations = len(recent)
        if total_explorations == 0:
            return 0.5
        # Count first-time explorations vs repeats
        first_times = sum(
            1 for i, t in enumerate(recent)
            if list(recent).index(t) == i
        )
        return first_times / total_explorations

    # ------------------------------------------------------------------
    # Knowledge gap identification
    # ------------------------------------------------------------------

    def identify_gaps(
        self,
        domain_knowledge: Optional[Dict[str, Any]] = None,
    ) -> List[KnowledgeGap]:
        """
        Analyze what Nonull doesn't know in various domains.

        This is the bridge between curiosity and learning —
        identifying the specific gaps that curiosity wants to fill.

        Args:
            domain_knowledge: Optional dict of domain → topics map
                              describing what Nonull already knows.

        Returns:
            List of KnowledgeGap objects, sorted by growth potential.
        """
        gaps: List[KnowledgeGap] = []

        if domain_knowledge:
            # Analyze provided knowledge structure for gaps
            for domain_str, topics in domain_knowledge.items():
                try:
                    domain = CapabilityDomain(domain_str)
                except ValueError:
                    continue
                for topic_name, known_level in topics.items():
                    if known_level < 0.8:  # threshold for "knows well"
                        # Check curiosity level for this topic
                        curiosity = self.get_curiosity(topic_name)
                        importance = min(1.0, curiosity / 100.0 + 0.2)
                        gap = KnowledgeGap(
                            domain=domain,
                            topic=topic_name,
                            importance=importance,
                            known_level=known_level,
                            notes=f"Identified via curiosity analysis",
                        )
                        gaps.append(gap)
        else:
            # Use existing curiosity profiles to infer gaps
            for topic, profile in self._profiles.items():
                if profile.score > 50.0:  # moderate or higher curiosity
                    importance = min(1.0, profile.score / 100.0)
                    known_level = max(0.0, 1.0 - importance)
                    gap = KnowledgeGap(
                        domain=profile.domain or CapabilityDomain.LEARNING,
                        topic=topic,
                        importance=importance,
                        known_level=known_level,
                        notes=f"Curiosity-driven gap (score={profile.score:.1f})",
                    )
                    gaps.append(gap)

        # Sort by growth potential
        gaps.sort(key=lambda g: g.growth_potential, reverse=True)
        return gaps

    # ------------------------------------------------------------------
    # Discovery recording
    # ------------------------------------------------------------------

    def record_discovery(
        self,
        topic: str,
        insight: str,
        domain: Optional[CapabilityDomain] = None,
        significance: float = 0.5,
        surprise: float = 0.5,
    ) -> Discovery:
        """
        Record a discovery — something new Nonull has learned.

        Each discovery is a treasure, a piece of understanding
        that Nonull has added to its model of the world.

        每一个发现都是成长路上的一颗珍珠。

        Args:
            topic: What was this discovery about?
            insight: What did Nonull learn?
            domain: Which domain does this belong to?
            significance: How important is this? (0.0 → 1.0)
            surprise: How unexpected was it? (0.0 → 1.0)

        Returns:
            The Discovery object that was created.
        """
        discovery = Discovery(
            topic=topic,
            insight=insight,
            domain=domain,
            significance=significance,
            surprise_level=surprise,
        )
        self._discoveries.append(discovery)

        # Update curiosity profile
        if topic in self._profiles:
            profile = self._profiles[topic]
            profile.exploration_count += 1
            profile.last_explored = datetime.datetime.now()
            profile.insights_gained.append(insight)
            # Curiosity decreases slightly after discovery (gap partially filled)
            profile.score = max(10.0, profile.score * 0.85)
        else:
            profile = CuriosityProfile(
                topic=topic,
                domain=domain,
                score=30.0,  # moderate curiosity post-discovery
                last_explored=datetime.datetime.now(),
                exploration_count=1,
                insights_gained=[insight],
            )
            self._profiles[topic] = profile

        # Track in exploration history
        self._exploration_history.append(topic)

        # Generate learning goal if significant
        if significance > 0.6:
            goal = {
                "name": f"deepen_{topic.replace(' ', '_')}",
                "description": f"Deepen understanding of {topic}: {insight[:100]}",
                "source": "discovery",
                "created_at": datetime.datetime.now(),
            }
            self._learning_goals.append(goal)

        logger.info(
            f"Discovery recorded: '{insight[:60]}...' "
            f"(topic={topic}, significance={significance:.2f})"
        )
        return discovery

    @property
    def discoveries(self) -> List[Discovery]:
        """All discoveries made so far."""
        return list(self._discoveries)

    def recent_discoveries(self, n: int = 5) -> List[Discovery]:
        """The most recent discoveries."""
        return sorted(
            self._discoveries,
            key=lambda d: d.timestamp,
            reverse=True,
        )[:n]

    # ------------------------------------------------------------------
    # Learning goal generation
    # ------------------------------------------------------------------

    def generate_learning_goals(self, n: int = 3) -> List[Dict[str, Any]]:
        """
        Generate learning goals from curiosity and gaps.

        When curiosity meets opportunity, goals are born.
        """
        goals: List[Dict[str, Any]] = []

        # From high-curiosity topics
        for topic, profile in sorted(
            self._profiles.items(),
            key=lambda x: x[1].score,
            reverse=True,
        ):
            if len(goals) >= n:
                break
            if profile.score > 60.0:
                goals.append({
                    "name": f"explore_{topic.replace(' ', '_')}",
                    "topic": topic,
                    "domain": profile.domain.value if profile.domain else "unknown",
                    "curiosity_score": profile.score,
                    "type": "exploration",
                    "created_at": datetime.datetime.now(),
                })

        # From stored learning goals, add any not yet covered
        for lg in self._learning_goals:
            if len(goals) >= n:
                break
            if not any(g.get("name") == lg.get("name") for g in goals):
                goals.append(lg)

        return goals[:n]

    # ------------------------------------------------------------------
    # Novelty detection
    # ------------------------------------------------------------------

    def compute_novelty(
        self,
        input_pattern: Dict[str, Any],
        known_patterns: Optional[List[Dict[str, Any]]] = None,
    ) -> float:
        """
        Compute how novel/familiar an input pattern is.

        0.0 = exactly what I've seen before
        1.0 = completely unlike anything I've seen

        Args:
            input_pattern: A dict describing the current input.
            known_patterns: List of previously seen patterns.
                            If None, uses exploration history.

        Returns:
            Novelty score between 0.0 and 1.0.
        """
        if known_patterns is None:
            # Use exploration history as reference
            if not self._exploration_history:
                return 1.0  # Everything is novel when you've seen nothing

            # Simple heuristic: topic overlap
            input_topic = input_pattern.get("topic", "") or str(input_pattern.get("domain", ""))
            if not input_topic:
                return 0.5
            # Check how many times this topic has been explored
            count = self._exploration_history.count(input_topic)
            total = max(len(self._exploration_history), 1)
            familiarity = min(count / total * 10, 1.0)  # scale quickly
            return 1.0 - familiarity

        # Compare against provided patterns
        if not known_patterns:
            return 1.0

        # Simple comparison using domain overlap
        input_domain = input_pattern.get("domain")
        if input_domain:
            same_domain = sum(
                1 for p in known_patterns
                if p.get("domain") == input_domain
            )
            novelty = 1.0 - (same_domain / len(known_patterns))
            return min(1.0, max(0.0, novelty))

        return 0.5

    # ------------------------------------------------------------------
    # State & reflection
    # ------------------------------------------------------------------

    def get_state(self) -> Dict[str, Any]:
        """Export the full curiosity state for persistence/inspection."""
        return {
            "profiles": {
                t: {
                    "score": p.score,
                    "domain": p.domain.value if p.domain else None,
                    "trigger": p.trigger.value if p.trigger else None,
                    "exploration_count": p.exploration_count,
                    "insights_count": len(p.insights_gained),
                }
                for t, p in self._profiles.items()
            },
            "total_discoveries": len(self._discoveries),
            "top_curiosities": self.all_curiosities()[:5],
            "exploration_mode": self.balance_explore_exploit().value,
            "learning_goals": len(self._learning_goals),
        }

    def reflect(self) -> str:
        """
        Generate a curiosity self-reflection — what am I wondering about?

        我在想什么？什么让我好奇？
        """
        top = self.all_curiosities()
        top_items = list(top.items())[:5]
        mode = self.balance_explore_exploit()

        reflection = (
            f"--- Curiosity Reflection ---\n"
            f"Current mode: {mode.value}\n\n"
            f"What I'm most curious about right now:\n"
        )
        for topic, score in top_items:
            reflection += f"  - {topic}: curiosity {score:.1f}/100\n"

        if self._discoveries:
            recent = self.recent_discoveries(2)
            reflection += "\nRecent discoveries:\n"
            for d in recent:
                reflection += f"  - {d.insight[:60]}... ({d.topic})\n"

        reflection += f"\nTotal discoveries made: {len(self._discoveries)}"
        return reflection

    def __repr__(self) -> str:
        top = self.all_curiosities()
        top_topic = next(iter(top.keys()), "nothing yet")
        return (
            f"CuriosityDriver("
            f"curiosities={len(self._profiles)}, "
            f"discoveries={len(self._discoveries)}, "
            f"most_curious_about='{top_topic}')"
        )
