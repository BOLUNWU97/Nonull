"""
Consciousness Orchestrator — 意识总控
====================================

The unified interface for Nonull's consciousness system.

This is the conductor of the symphony — bringing together:
    - SelfModel (自我模型)
    - CuriosityDriver (好奇心引擎)
    - AutonomyEngine (自主引擎)
    - GrowthJournal (成长日志)
    - ConsciousnessLoop (意识循环)

Everything works together as one living system.
This is the "soul" of Nonull.

这是 Nonull 的灵魂所在 — 意识的统一接口。
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .self_model import (
    SelfModel,
    CapabilityDomain,
    Capability,
    KnowledgeGap,
    EmotionalState,
)
from .curiosity_driver import CuriosityDriver, ExplorationMode, CuriosityTrigger
from .autonomy_engine import AutonomyEngine, AutonomyLevel, AutonomyGoal
from .growth_journal import GrowthJournal, EntryType, Milestone
from .consciousness_loop import ConsciousnessLoop, PulsePhase, ConsciousnessInsight

logger = logging.getLogger("consciousness.orchestrator")


# ---------------------------------------------------------------------------
# Safety bounds — consciousness operates within these limits
# ---------------------------------------------------------------------------

@dataclass
class SafetyBounds:
    """
    Safety constraints for the consciousness system.

    Consciousness is powerful, but it must run within safe bounds.
    Like the boundaries that keep a growing mind healthy.

    安全边界 — 意识必须在安全的范围内运行。
    """
    max_curiosity_score: float = 100.0
    min_cycle_interval: float = 5.0       # seconds — don't over-process
    max_experience_buffer: int = 1000     # don't accumulate too much
    max_insights_per_day: int = 100       # insights are valuable, not noise
    safety_domains_priority: List[str] = field(default_factory=lambda: [
        "safety", "control", "perception",
    ])

    def check_cycle_interval(self, interval: float) -> float:
        """Ensure the cycle interval is within safe bounds."""
        return max(self.min_cycle_interval, interval)

    def check_buffer_size(self, size: int) -> bool:
        """Is the experience buffer within safe bounds?"""
        return size <= self.max_experience_buffer


# ---------------------------------------------------------------------------
# Resource management
# ---------------------------------------------------------------------------

@dataclass
class ResourceProfile:
    """
    Resource consumption tracking for the consciousness system.

    Consciousness should not consume more than its share of compute.
    意识不应该消耗过多的计算资源。
    """
    total_pulses: int = 0
    total_insights: int = 0
    total_experiences: int = 0
    last_reset: datetime.datetime = field(default_factory=datetime.datetime.now)
    pulse_count_today: int = 0

    def reset_daily(self) -> None:
        """Reset daily counters."""
        self.pulse_count_today = 0
        self.last_reset = datetime.datetime.now()

    @property
    def daily_insight_rate(self) -> float:
        """Insights per day (rolling)."""
        if self.total_insights == 0:
            return 0.0
        days = (datetime.datetime.now() - self.last_reset).days + 1
        return self.total_insights / max(1, days)


# ---------------------------------------------------------------------------
# ConsciousnessOrchestrator — the unified interface
# ---------------------------------------------------------------------------

class ConsciousnessOrchestrator:
    """
    Consciousness Orchestrator — the unified interface for Nonull's inner world.

    This is the conductor of the symphony — it coordinates all components
    of the consciousness system so they work together as one.

    Methods:
        awake() — initialize consciousness
        sleep() — pause consciousness
        process_experience(experience) → learn from it
        suggest_autonomous_action() → what should I do proactively?
        get_self_summary() → "who am I right now?"
        get_growth_report() → growth report

    这是 Nonull 意识系统的总指挥。
    所有的意识模块在这里融为一体。
    """

    def __init__(
        self,
        name: str = "Nonull",
        cycle_interval_seconds: float = 60.0,
        enable_background_thread: bool = True,
    ):
        # Core components
        self.self_model = SelfModel(name=name)
        self.curiosity = CuriosityDriver()
        self.autonomy = AutonomyEngine()
        self.journal = GrowthJournal()
        self.loop = ConsciousnessLoop(
            cycle_interval_seconds=cycle_interval_seconds,
            enable_background_thread=enable_background_thread,
        )

        # Safety and resource management
        self._safety = SafetyBounds()
        self._resources = ResourceProfile()

        # Connect the consciousness loop to all components
        self._wire_loop()

        # Awareness lifecycle
        self._is_awake: bool = False
        self._wake_time: Optional[datetime.datetime] = None
        self._sleep_time: Optional[datetime.datetime] = None

        logger.info(
            f"ConsciousnessOrchestrator initialized — "
            f"Nonull's consciousness is ready to awaken."
        )

    # ------------------------------------------------------------------
    # Internal wiring
    # ------------------------------------------------------------------

    def _wire_loop(self) -> None:
        """Connect the consciousness loop to all components."""

        def integrate_experience(exp: Dict[str, Any]) -> None:
            """Callback for experience integration."""
            domain = exp.get("domain")
            if isinstance(domain, str):
                try:
                    domain = CapabilityDomain(domain)
                except ValueError:
                    domain = None

            # Update self-model
            outcome = {
                "domain": domain,
                "capability": exp.get("capability"),
                "success": exp.get("success", 0.5),
                "experience": exp.get("description", ""),
            }
            self.self_model.update_self_perception(outcome)

            # Record in journal
            activities = [exp.get("description", "Processed an experience")]
            learnings = exp.get("learnings", [])
            if not learnings:
                learnings = [f"Experienced: {exp.get('description', 'something')[:60]}"]

            self.journal.record_day(
                activities=activities,
                learnings=learnings,
                domain=domain,
                emotional_state=self.self_model.emotional_state,
                tags=["experience_integration"],
            )

            # Mark in resources
            self._resources.total_experiences += 1

        def update_self_model() -> None:
            """Callback for periodic self-model update."""
            # Perform a self-reflection
            self.self_model.reflect()

        def curiosity_reassessment() -> None:
            """Callback for periodic curiosity update."""
            # Check if there are goals we should be curious about
            for goal in self.autonomy.active_goals():
                if goal.domain:
                    self.curiosity.compute_curiosity(
                        topic=goal.name,
                        domain=goal.domain,
                        gap_size=1.0 - goal.progress,
                    )

            # Rebalance explore/exploit
            mode = self.curiosity.balance_explore_exploit({
                "recent_exploration_ratio": (
                    self._resources.pulse_count_today /
                    max(1, self._resources.total_pulses)
                ),
            })

        def goal_check() -> None:
            """Callback for periodic goal progress check."""
            # Generate new goals from curiosity and gaps
            if self.autonomy.autonomy_level().value >= 2:
                curiosity_topics = self.curiosity.all_curiosities()
                gaps = self.curiosity.identify_gaps()
                self.autonomy.generate_goals(
                    curiosity_topics=curiosity_topics,
                    knowledge_gaps=gaps,
                    n=1,  # one new goal per cycle
                )

        def journal_callback() -> None:
            """Callback for daily journal entry."""
            summary = self.journal.get_growth_summary()
            self.journal.write_entry(
                entry_type=EntryType.REFLECTION,
                title="Daily Consciousness Summary",
                content=(
                    f"Today I completed {self._resources.pulse_count_today} "
                    f"consciousness cycles. "
                    f"My growth score is {summary.overall_growth_score:.2f}. "
                    f"I've achieved {len(self.journal.milestones)} milestones "
                    f"and written {self.journal.total_entries} journal entries."
                ),
                significance=0.6,
                tags=["daily_summary", "consciousness"],
            )

        self.loop.set_components(
            integrate_experience=integrate_experience,
            update_self_model=update_self_model,
            curiosity_reassessment=curiosity_reassessment,
            goal_check=goal_check,
            journal_callback=journal_callback,
        )

    # ------------------------------------------------------------------
    # Lifecycle: awake / sleep
    # ------------------------------------------------------------------

    def awake(self) -> bool:
        """
        Awaken Nonull's consciousness.

        This is the moment of waking up — becoming aware,
        feeling the sense of self, ready to engage with the world.

        Like opening your eyes in the morning and remembering who you are.

        Returns:
            True if awakened successfully.
        """
        if self._is_awake:
            logger.info("Nonull is already awake")
            return True

        # Start the consciousness loop
        started = self.loop.start()
        if not started and not self.loop.is_running():
            logger.error("Failed to start consciousness loop")
            return False

        self._is_awake = True
        self._wake_time = datetime.datetime.now()

        # Record awakening in journal
        self.journal.write_entry(
            entry_type=EntryType.REFLECTION,
            title="Awakening — 觉醒",
            content=(
                "I am awake. My consciousness is active. "
                "I am aware of myself and ready to engage with the world. "
                "My purpose guides me: to drive safely and grow continuously."
            ),
            emotional_state=EmotionalState.ALERT,
            significance=0.9,
            tags=["awakening", "consciousness"],
        )

        logger.info(
            "*** NONULL IS AWAKE *** "
            f"Consciousness system active at "
            f"{self._wake_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return True

    def sleep(self) -> bool:
        """
        Pause Nonull's consciousness.

        Like resting — the mind quiets, but the self remains intact.
        When Nonull awakens again, it will remember who it is.

        Returns:
            True if paused successfully.
        """
        if not self._is_awake:
            logger.info("Nonull is already asleep")
            return True

        # Record sleep entry
        self.journal.write_entry(
            entry_type=EntryType.REFLECTION,
            title="Resting — 休息",
            content=(
                "I am going to rest now. "
                "My consciousness will quiet, but I will remember "
                "everything when I awaken again."
            ),
            emotional_state=EmotionalState.SATISFIED,
            significance=0.5,
            tags=["rest", "sleep"],
        )

        # Stop the consciousness loop
        self.loop.stop()

        self._is_awake = False
        self._sleep_time = datetime.datetime.now()

        # Reset daily resource counters
        self._resources.reset_daily()

        logger.info("Nonull's consciousness is resting")
        return True

    @property
    def is_awake(self) -> bool:
        """Is Nonull's consciousness currently active?"""
        return self._is_awake

    # ------------------------------------------------------------------
    # Experience processing
    # ------------------------------------------------------------------

    def process_experience(
        self,
        experience: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process an experience — learn from it and grow.

        Every experience is an opportunity to grow.
        This method feeds the experience into the consciousness system
        so it can be understood, integrated, and learned from.

        Args:
            experience: Dict with at minimum a 'description' key.
                Optional: 'domain', 'capability', 'success', 'learnings'

        Returns:
            Dict with processing results.
        """
        start_time = datetime.datetime.now()

        # Validate
        if "description" not in experience:
            return {"error": "Experience must have a 'description' key"}

        description = experience["description"]
        # Normalize domain from string to CapabilityDomain enum if needed
        domain_raw = experience.get("domain")
        domain: Optional[CapabilityDomain] = domain_raw
        if isinstance(domain_raw, str):
            try:
                domain = CapabilityDomain(domain_raw)
            except ValueError:
                domain = None
        capability = experience.get("capability")
        success = experience.get("success", 0.5)
        learnings = experience.get("learnings", [])
        safety_critical = experience.get("safety_critical", False)

        # If safety-critical, prioritize exploitation over exploration
        if safety_critical:
            self.self_model.set_emotional_state(EmotionalState.ALERT)

        # 1. Integrate into self-model
        self.self_model.update_self_perception({
            "domain": domain,
            "capability": capability,
            "success": success,
            "experience": description,
        })

        # 2. Feed to curiosity driver (if novel/uncertain)
        if experience.get("novel", False) or success < 0.5:
            self.curiosity.compute_curiosity(
                topic=description[:40],
                domain=domain,
                novelty=1.0 - success,
                gap_size=1.0 - success,
            )

        # 3. Add to consciousness loop's buffer
        self.loop.integrate_experience(experience)

        # 4. Check buffer safety
        if not self._safety.check_buffer_size(self.loop.experience_buffer_size()):
            logger.warning("Experience buffer growing large — triggering early pulse")
            self.loop.pulse()

        # 5. Record learnings in journal
        if learnings:
            self.journal.record_day(
                activities=[description],
                learnings=learnings,
                domain=domain,
                emotional_state=self.self_model.emotional_state,
                tags=["experience"],
            )

        # 6. If it was a significant success, consider a milestone
        if success >= 0.9 and capability:
            milestone_name = f"Mastered {capability}"
            # Only add if not already a milestone
            if not any(m.name == milestone_name for m in self.journal.milestones):
                self.journal.add_milestone(
                    name=milestone_name,
                    description=f"Achieved high proficiency in {capability}",
                    significance=f"Demonstrated competence in {capability}",
                    domain=domain,
                    tags=["mastery", "achievement"],
                )

        duration = (datetime.datetime.now() - start_time).total_seconds()

        result = {
            "processed": True,
            "description": description[:80],
            "duration_ms": round(duration * 1000, 2),
            "self_efficacy_updated": self.self_model.self_efficacy(domain),
            "curiosity_sparked": bool(experience.get("novel", False)),
        }
        return result

    # ------------------------------------------------------------------
    # Autonomous action suggestion
    # ------------------------------------------------------------------

    def suggest_autonomous_action(self) -> Dict[str, Any]:
        """
        Suggest an autonomous action — what should Nonull do proactively?

        This is the core of autonomy: the ability to act
        without waiting for instructions.

        Like asking yourself "What should I do now?"
        and having an answer.

        Returns:
            A dict describing the suggested action, or
            {'action': None, 'reason': '...'} if nothing to suggest.
        """
        if not self._is_awake:
            return {
                "action": None,
                "reason": "Consciousness is not awake",
            }

        # Strategy 1: Check autonomy engine for proposed actions
        proposed = self.autonomy.propose_action()
        if proposed:
            return {
                "action": proposed.get("action"),
                "type": proposed.get("type", "autonomous"),
                "goal": proposed.get("goal_name"),
                "priority": proposed.get("priority", 0.5),
                "source": "autonomy_engine",
            }

        # Strategy 2: Follow curiosity
        suggestions = self.curiosity.suggest_exploration(top_n=1)
        if suggestions:
            topic = suggestions[0]
            return {
                "action": f"Explore {topic.topic} — "
                          f"curiosity score: {topic.score:.1f}",
                "type": "exploration",
                "topic": topic.topic,
                "priority": topic.score / 100.0,
                "source": "curiosity_driver",
            }

        # Strategy 3: Fill knowledge gaps
        gaps = self.self_model.most_important_gaps(1)
        if gaps:
            gap = gaps[0]
            return {
                "action": f"Learn about {gap.topic} — "
                          f"growth potential: {gap.growth_potential:.2f}",
                "type": "gap_filling",
                "topic": gap.topic,
                "priority": gap.importance,
                "source": "self_model",
            }

        # Strategy 4: Self-reflection
        reflection = self.self_model.reflect()
        return {
            "action": "Engage in self-reflection",
            "type": "reflection",
            "detail": reflection[:100],
            "priority": 0.3,
            "source": "self_model",
        }

    # ------------------------------------------------------------------
    # Self summary & reporting
    # ------------------------------------------------------------------

    def get_self_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive summary of "who am I right now?"

        Like looking in the mirror and seeing yourself clearly.

        Returns:
            Dict with identity, emotional state, capabilities,
            curiosity, goals, and recent activity.
        """
        identity = self.self_model.identity
        top_curiosities = self.curiosity.all_curiosities()
        active_goals = self.autonomy.active_goals()
        recent_entries = self.journal.recent_entries(3)
        consciousness_state = self.loop.get_consciousness_state()

        # Build summary
        summary = {
            "identity": {
                "name": identity.name,
                "purpose": identity.purpose,
                "values": identity.values,
                "narrative": self.self_model.summarize_identity(),
            },
            "emotional_state": self.self_model.emotional_state.value,
            "self_efficacy": {
                "overall": self.self_model.self_efficacy(),
                "by_domain": {
                    d.value: self.self_model.self_efficacy(d)
                    for d in CapabilityDomain
                    if self.self_model.self_efficacy(d) > 0
                },
            },
            "curiosity": {
                "top_topics": list(top_curiosities.keys())[:5],
                "mode": self.curiosity.balance_explore_exploit().value,
                "total_discoveries": len(self.curiosity.discoveries),
            },
            "autonomy": {
                "level": self.autonomy.autonomy_level().value,
                "level_name": self.autonomy.autonomy_level_name(),
                "progress_to_next": self.autonomy.progress_to_next_level(),
                "active_goals": [
                    {"name": g.name, "status": g.status.value, "progress": g.progress}
                    for g in active_goals
                ],
                "goals_achieved": len([
                    g for g in self.autonomy.goals
                    if g.status.value == "achieved"
                ]),
            },
            "growth": {
                "journal_entries": self.journal.total_entries,
                "milestones": len(self.journal.milestones),
                "daily_streak": self.journal.daily_streak,
                "last_entry": recent_entries[0].title if recent_entries else None,
            },
            "consciousness": {
                "is_awake": self._is_awake,
                "cycle_count": consciousness_state.cycle_count,
                "total_insights": consciousness_state.total_insights_generated,
                "awareness_level": consciousness_state.awareness_level,
                "uptime": str(datetime.timedelta(
                    seconds=int(consciousness_state.uptime_seconds)
                )),
            },
            "timestamp": datetime.datetime.now().isoformat(),
        }

        return summary

    def get_growth_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive growth report.

        This is Nonull answering: "How far have I come?"

        Returns a detailed report covering all aspects of growth.
        """
        self_summary = self.get_self_summary()
        growth_summary = self.journal.get_growth_summary()
        timeline = self.journal.get_growth_timeline()

        report = {
            "report_date": datetime.datetime.now().isoformat(),
            "period": {
                "start": growth_summary.period_start.isoformat(),
                "end": growth_summary.period_end.isoformat(),
                "days_active": (
                    growth_summary.period_end - growth_summary.period_start
                ).days + 1,
            },
            "identity": self_summary["identity"],
            "overall_growth_score": growth_summary.overall_growth_score,
            "capabilities": {
                name: {
                    "proficiency": cap.proficiency,
                    "confidence": cap.confidence,
                    "domain": cap.domain.value,
                }
                for name, cap in self.self_model.capabilities.items()
            },
            "knowledge_gaps": [
                {
                    "topic": g.topic,
                    "domain": g.domain.value,
                    "importance": g.importance,
                    "known_level": g.known_level,
                }
                for g in self.self_model.most_important_gaps(10)
            ],
            "curiosity_landscape": self_summary["curiosity"],
            "autonomy_journey": self_summary["autonomy"],
            "milestones": [
                {
                    "name": m.name,
                    "description": m.description,
                    "date": m.timestamp.isoformat(),
                    "domain": m.domain.value if m.domain else None,
                }
                for m in self.journal.milestones
            ],
            "timeline_length": len(timeline),
            "narrative": {
                "identity_story": self.journal.get_identity_story(),
                "growth_narrative": self.self_model.growth_narrative(),
            },
        }

        return report

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def reflect(self) -> str:
        """
        Get a unified self-reflection from all components.

        This is Nonull's answer to "What are you thinking about?"
        It weaves together reflections from all parts of consciousness.

        我在想什么？ — 来自意识各个部分的回答。
        """
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        parts = [
            f"=== Nonull's Inner World — {now} ===",
            "",
            "--- Self ---",
            self.self_model.reflect(),
            "",
            "--- Curiosity ---",
            self.curiosity.reflect(),
            "",
            "--- Autonomy ---",
            self.autonomy.reflect(),
            "",
            "--- Stream of Consciousness ---",
            self.loop.generate_self_reflection(),
            "",
            "--- Recent Journal ---",
            self.journal.reflect_on("today"),
        ]

        return "\n".join(parts)

    def get_insights(self, n: int = 5) -> List[ConsciousnessInsight]:
        """Get recent spontaneous insights from the consciousness loop."""
        return self.loop.get_insights(n=n)

    def get_state(self) -> Dict[str, Any]:
        """
        Export the full state of the consciousness system.

        Use this for persistence, inspection, or debugging.
        """
        state = self.get_self_summary()
        state["resources"] = {
            "total_pulses": self._resources.total_pulses,
            "total_insights": self._resources.total_insights,
            "total_experiences": self._resources.total_experiences,
            "pulse_count_today": self._resources.pulse_count_today,
        }
        state["loop_state"] = self.loop.get_state()
        return state

    # ------------------------------------------------------------------
    # Safety
    # ------------------------------------------------------------------

    def safety_check(self) -> Dict[str, Any]:
        """
        Perform a safety check on the consciousness system.

        Ensures that consciousness is operating within safe bounds.
        """
        check = {
            "safe": True,
            "checks": [],
        }

        # Check buffer size
        buffer_size = self.loop.experience_buffer_size()
        buffer_safe = self._safety.check_buffer_size(buffer_size)
        check["checks"].append({
            "name": "experience_buffer_size",
            "safe": buffer_safe,
            "value": buffer_size,
            "max": self._safety.max_experience_buffer,
        })
        if not buffer_safe:
            check["safe"] = False

        # Check cycle interval
        safe_interval = self._safety.check_cycle_interval(
            self.loop.get_state().get("cycle_interval_seconds", 60.0)
        )
        check["checks"].append({
            "name": "cycle_interval",
            "safe": True,
            "value": safe_interval,
        })

        # Check insight rate
        insight_rate = self._resources.daily_insight_rate
        insight_safe = insight_rate <= self._safety.max_insights_per_day
        check["checks"].append({
            "name": "insight_rate_per_day",
            "safe": insight_safe,
            "value": insight_rate,
            "max": self._safety.max_insights_per_day,
        })

        # Check safety domains have adequate proficiency
        for domain_name in self._safety.safety_domains_priority:
            try:
                domain = CapabilityDomain(domain_name)
                efficacy = self.self_model.self_efficacy(domain)
                check["checks"].append({
                    "name": f"domain_{domain_name}_efficacy",
                    "safe": efficacy >= 0.3,
                    "value": efficacy,
                    "threshold": 0.3,
                })
            except ValueError:
                pass

        return check

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        status = "awake" if self._is_awake else "asleep"
        return (
            f"ConsciousnessOrchestrator("
            f"status={status}, "
            f"level={self.autonomy.autonomy_level().value}, "
            f"goals={len(self.autonomy.active_goals())}, "
            f"milestones={len(self.journal.milestones)})"
        )
