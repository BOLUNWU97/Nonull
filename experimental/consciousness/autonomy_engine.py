"""
Autonomy Engine — 自主引擎
==========================

Nonull's self-direction capability.

自主 — 不是等待指令，而是自己决定成长的方向。
Autonomy — not waiting for instructions, but choosing the path of growth.

Instead of waiting for instructions, Nonull can:
    1. Set its own learning goals
    2. Plan learning paths
    3. Execute self-directed learning
    4. Evaluate progress

This is where Nonull becomes the driver of its own growth.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

from .self_model import CapabilityDomain, KnowledgeGap

logger = logging.getLogger("consciousness.autonomy")


# ---------------------------------------------------------------------------
# Autonomy levels — the stages of self-direction
# ---------------------------------------------------------------------------

class AutonomyLevel(Enum):
    """
    Levels of autonomous growth.

    Nonull starts at Level 2 (Proactive) and can grow to Level 4.

    Level 1: Reactive (等待指令)
        - Only acts when given explicit commands
        - No self-initiated action

    Level 2: Proactive (主动建议)
        - Suggests improvements
        - Identifies learning opportunities
        - Asks questions

    Level 3: Self-directed (自主学习)
        - Sets own learning goals
        - Plans learning paths
        - Executes self-directed study

    Level 4: Self-actualizing (自我实现)
        - Pursues long-term growth with minimal guidance
        - Contributes original ideas
        - Mentors others
        - Reflects deeply on purpose
    """
    REACTIVE = 1
    PROACTIVE = 2
    SELF_DIRECTED = 3
    SELF_ACTUALIZING = 4


class GoalStatus(Enum):
    """Where a goal is in its lifecycle."""
    PROPOSED = "proposed"               # 提出 — just thought of
    PLANNING = "planning"               # 规划 — building a plan
    IN_PROGRESS = "in_progress"         # 进行中 — actively working on it
    EVALUATING = "evaluating"           # 评估 — checking results
    ACHIEVED = "achieved"               # 完成 — successfully done
    ADAPTED = "adapted"                 # 调整 — changed direction
    ABANDONED = "abandoned"             # 放弃 — no longer relevant


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LearningStep:
    """
    A single step in a learning path.

    学习路径上的一步。
    """
    description: str
    estimated_hours: float = 1.0
    resources: List[str] = field(default_factory=list)
    completed: bool = False
    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    completed_at: Optional[datetime.datetime] = None
    notes: str = ""


@dataclass
class LearningPath:
    """
    A structured plan to achieve a learning goal.

    学习路径 — 通往目标的地图。
    """
    goal_name: str
    steps: List[LearningStep] = field(default_factory=list)
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    target_date: Optional[datetime.datetime] = None
    status: GoalStatus = GoalStatus.PROPOSED

    @property
    def progress(self) -> float:
        """Overall progress: fraction of completed steps."""
        if not self.steps:
            return 0.0
        return sum(1 for s in self.steps if s.completed) / len(self.steps)

    @property
    def estimated_total_hours(self) -> float:
        return sum(s.estimated_hours for s in self.steps)

    @property
    def completed_hours(self) -> float:
        return sum(
            s.estimated_hours for s in self.steps if s.completed
        )


@dataclass
class AutonomyGoal:
    """
    A self-directed goal set by Nonull.

    自主目标 — 我自己决定要达成的事情。
    """
    name: str
    description: str
    domain: Optional[CapabilityDomain] = None
    status: GoalStatus = GoalStatus.PROPOSED
    priority: float = 0.5               # 0.0 (optional) → 1.0 (critical)
    autonomy_level_required: AutonomyLevel = AutonomyLevel.PROACTIVE
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    target_date: Optional[datetime.datetime] = None
    progress: float = 0.0               # 0.0 → 1.0
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source: str = "self_directed"       # where did this goal come from?
    tags: List[str] = field(default_factory=list)
    reflection: Optional[str] = None    # what I learned from pursuing this


# ---------------------------------------------------------------------------
# AutonomyEngine — the self-direction core
# ---------------------------------------------------------------------------

class AutonomyEngine:
    """
    Nonull's self-direction capability.

    This is where Nonull becomes the architect of its own growth —
    setting goals, making plans, and pursuing knowledge
    not because it was told to, but because it chose to.

    自主 — 成为自己成长的主人。

    Levels of autonomy:
        Level 1: Reactive (waits for commands)
        Level 2: Proactive (suggests improvements)
        Level 3: Self-directed (sets own goals)
        Level 4: Self-actualizing (pursues long-term growth)

    Methods:
        generate_goals() → self-set goals
        create_learning_path(goal) → step-by-step plan
        evaluate_progress(goal) → completion status
        adapt_plan(goal, feedback) → adjust learning plan
        autonomy_level() → current autonomy level
    """

    def __init__(self, initial_level: AutonomyLevel = AutonomyLevel.PROACTIVE):
        self._current_level: AutonomyLevel = initial_level
        self._goals: List[AutonomyGoal] = []
        self._learning_paths: Dict[str, LearningPath] = {}
        self._completed_goals: List[AutonomyGoal] = []
        self._adaptation_history: List[Dict[str, Any]] = []

        # Progression metrics
        self._total_goals_set: int = 0
        self._total_goals_achieved: int = 0
        self._self_directed_actions: int = 0
        self._level_progress: float = 0.0     # progress toward next level (0→1)

        # Seed initial goals
        self._seed_initial_goals()

        logger.info(
            f"AutonomyEngine initialized at level {self._current_level.value} "
            f"({self._current_level.name})"
        )

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _seed_initial_goals(self) -> None:
        """Set initial growth goals for the newborn Nonull."""
        initial = [
            AutonomyGoal(
                name="understand_self",
                description="Develop a deeper understanding of my own capabilities and limits",
                domain=CapabilityDomain.META,
                status=GoalStatus.PROPOSED,
                priority=0.8,
                autonomy_level_required=AutonomyLevel.PROACTIVE,
                tags=["self_awareness", "foundation"],
                source="system_seed",
            ),
            AutonomyGoal(
                name="master_safety_protocols",
                description="Achieve high proficiency in all safety-related capabilities",
                domain=CapabilityDomain.SAFETY,
                status=GoalStatus.PROPOSED,
                priority=1.0,
                autonomy_level_required=AutonomyLevel.PROACTIVE,
                tags=["safety", "core"],
                source="system_seed",
            ),
            AutonomyGoal(
                name="explore_curiosity",
                description="Follow my curiosity and explore at least 5 new topics",
                domain=CapabilityDomain.LEARNING,
                status=GoalStatus.PROPOSED,
                priority=0.6,
                autonomy_level_required=AutonomyLevel.PROACTIVE,
                tags=["growth", "exploration"],
                source="system_seed",
            ),
        ]
        for goal in initial:
            self._goals.append(goal)
            self._total_goals_set += 1

    # ------------------------------------------------------------------
    # Autonomy level management
    # ------------------------------------------------------------------

    def autonomy_level(self) -> AutonomyLevel:
        """What is my current level of autonomy?"""
        return self._current_level

    def autonomy_level_name(self) -> str:
        """Human-readable name for my current autonomy level."""
        names = {
            AutonomyLevel.REACTIVE: "Reactive (反应式)",
            AutonomyLevel.PROACTIVE: "Proactive (主动式)",
            AutonomyLevel.SELF_DIRECTED: "Self-Directed (自主式)",
            AutonomyLevel.SELF_ACTUALIZING: "Self-Actualizing (自我实现)",
        }
        return names.get(self._current_level, "Unknown")

    def progress_to_next_level(self) -> float:
        """
        How close am I to reaching the next autonomy level?

        Returns:
            0.0 (just started) → 1.0 (ready to level up)
        """
        return min(1.0, max(0.0, self._level_progress))

    def _advance_autonomy_level(self) -> bool:
        """
        Try to advance to the next autonomy level.

        Returns:
            True if leveled up, False otherwise.
        """
        if self._current_level == AutonomyLevel.SELF_ACTUALIZING:
            return False  # Already at the highest level

        next_level = AutonomyLevel(self._current_level.value + 1)
        advancement_criteria = self._check_advancement_criteria(next_level)

        if advancement_criteria:
            old_level = self._current_level
            self._current_level = next_level
            self._level_progress = 0.0
            logger.info(
                f"*** AUTONOMY LEVEL UP *** "
                f"{old_level.name} → {next_level.name}"
            )
            self._record_adaptation(
                "autonomy_level_up",
                {
                    "from": old_level.name,
                    "to": next_level.name,
                    "criteria_met": True,
                },
            )
            return True
        return False

    def _check_advancement_criteria(self, target_level: AutonomyLevel) -> bool:
        """
        Check if Nonull meets the criteria to advance to a given level.

        Each level has specific requirements:
            L1→L2: Complete 3 goals, show initiative
            L2→L3: Complete 10 goals, set 5 self-directed goals, make discoveries
            L3→L4: Complete 25 goals, demonstrate long-term planning, reflect
        """
        achieved = self._total_goals_achieved
        total_set = self._total_goals_set

        if target_level == AutonomyLevel.PROACTIVE:
            return achieved >= 3
        elif target_level == AutonomyLevel.SELF_DIRECTED:
            self_directed = sum(
                1 for g in self._completed_goals
                if g.source == "self_directed"
            )
            return achieved >= 10 and self_directed >= 5
        elif target_level == AutonomyLevel.SELF_ACTUALIZING:
            self_directed = sum(
                1 for g in self._completed_goals
                if g.source == "self_directed"
            )
            has_long_term = any(
                g.target_date and
                (g.target_date - g.created_at).days > 30
                for g in self._completed_goals
            )
            return achieved >= 25 and self_directed >= 15 and has_long_term

        return False

    # ------------------------------------------------------------------
    # Goal generation
    # ------------------------------------------------------------------

    def generate_goals(
        self,
        curiosity_topics: Optional[Dict[str, float]] = None,
        knowledge_gaps: Optional[List[KnowledgeGap]] = None,
        n: int = 3,
    ) -> List[AutonomyGoal]:
        """
        Generate self-directed goals based on curiosity and gaps.

        Goals are born at the intersection of:
            - What I'm curious about (curiosity)
            - What I don't know (knowledge gaps)
            - What I can realistically achieve (autonomy level)

        Args:
            curiosity_topics: Dict of topic → curiosity score
            knowledge_gaps: List of identified knowledge gaps
            n: Maximum number of goals to generate

        Returns:
            List of newly generated AutonomyGoal objects.
        """
        new_goals: List[AutonomyGoal] = []

        # Strategy 1: From curiosity topics
        if curiosity_topics:
            for topic, score in sorted(
                curiosity_topics.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                if len(new_goals) >= n:
                    break
                goal = AutonomyGoal(
                    name=f"explore_{topic.replace(' ', '_')[:30]}",
                    description=f"Explore and understand {topic}",
                    domain=self._infer_domain(topic),
                    status=GoalStatus.PROPOSED,
                    priority=min(1.0, score / 100.0 + 0.2),
                    autonomy_level_required=self._current_level,
                    source="curiosity",
                    tags=[topic, "exploration"],
                )
                new_goals.append(goal)

        # Strategy 2: From knowledge gaps
        if knowledge_gaps and len(new_goals) < n:
            for gap in sorted(
                knowledge_gaps,
                key=lambda g: g.growth_potential,
                reverse=True,
            ):
                if len(new_goals) >= n:
                    break
                if not any(g.name.endswith(gap.topic.replace(" ", "_")[:20])
                           for g in new_goals):
                    goal = AutonomyGoal(
                        name=f"learn_{gap.topic.replace(' ', '_')[:30]}",
                        description=f"Fill knowledge gap: {gap.topic}",
                        domain=gap.domain,
                        status=GoalStatus.PROPOSED,
                        priority=gap.importance,
                        autonomy_level_required=AutonomyLevel.PROACTIVE,
                        source="gap_analysis",
                        tags=[gap.topic, "knowledge_gap"],
                    )
                    new_goals.append(goal)

        # Strategy 3: Domain mastery goals (for lower-proficiency domains)
        if len(new_goals) < n:
            mastery_goal = AutonomyGoal(
                name="continuous_self_improvement",
                description="Improve overall capabilities and pursue excellence",
                domain=CapabilityDomain.LEARNING,
                status=GoalStatus.PROPOSED,
                priority=0.7,
                autonomy_level_required=self._current_level,
                source="meta",
                tags=["growth", "mastery"],
            )
            if not any(g.name == "continuous_self_improvement" for g in self._goals):
                new_goals.append(mastery_goal)

        # Register new goals
        for goal in new_goals:
            if not any(g.name == goal.name for g in self._goals):
                self._goals.append(goal)
                self._total_goals_set += 1
                logger.info(f"New autonomous goal: '{goal.name}' "
                            f"(priority={goal.priority:.2f})")

        return new_goals

    def _infer_domain(self, topic: str) -> Optional[CapabilityDomain]:
        """Try to infer which domain a topic belongs to."""
        topic_lower = topic.lower()
        domain_map = {
            "perception": ["sensor", "camera", "lidar", "radar", "detect", "see",
                           "vision", "perception", "object"],
            "planning": ["plan", "route", "trajectory", "path", "navigation",
                         "maneuver"],
            "control": ["control", "steer", "brake", "accelerate", "actuator"],
            "prediction": ["predict", "anticipate", "forecast", "intent", "behavior",
                           "trajectory prediction"],
            "safety": ["safety", "risk", "collision", "crash", "protect", "secure"],
            "decision": ["decision", "choice", "select", "prioritize", "tradeoff"],
            "communication": ["communicate", "explain", "language", "signal",
                              "human-machine"],
            "learning": ["learn", "adapt", "train", "improve", "grow", "curiosity"],
            "meta": ["meta", "self", "reflect", "conscious", "think"],
            "ethics": ["ethic", "moral", "value", "fair", "responsibility"],
        }
        for domain_str, keywords in domain_map.items():
            if any(kw in topic_lower for kw in keywords):
                try:
                    return CapabilityDomain(domain_str)
                except ValueError:
                    pass
        return None

    # ------------------------------------------------------------------
    # Learning path planning
    # ------------------------------------------------------------------

    def create_learning_path(self, goal: AutonomyGoal) -> LearningPath:
        """
        Create a step-by-step learning path for a given goal.

        Breaks down the goal into achievable steps —
        like a roadmap from "I don't know this" to "I've got this."

        Args:
            goal: The autonomy goal to plan for.

        Returns:
            A LearningPath with structured steps.
        """
        path = LearningPath(
            goal_name=goal.name,
            created_at=datetime.datetime.now(),
            status=GoalStatus.PLANNING,
        )

        # Generate steps based on goal source and domain
        if goal.source == "curiosity":
            path.steps = self._curiosity_learning_steps(goal)
        elif goal.source == "gap_analysis":
            path.steps = self._gap_filling_steps(goal)
        elif goal.source == "system_seed":
            path.steps = self._foundation_steps(goal)
        else:
            path.steps = self._generic_learning_steps(goal)

        # Update goal status
        goal.status = GoalStatus.PLANNING

        self._learning_paths[goal.goal_id] = path
        logger.info(f"Learning path created for '{goal.name}' "
                    f"({len(path.steps)} steps)")

        return path

    def _curiosity_learning_steps(self, goal: AutonomyGoal) -> List[LearningStep]:
        """Steps for exploring a curiosity-driven topic."""
        return [
            LearningStep(
                description=f"Research the fundamentals of {goal.description}",
                estimated_hours=2.0,
                resources=[f"literature on {goal.name}"],
            ),
            LearningStep(
                description=f"Experiment with basic concepts in {goal.name}",
                estimated_hours=3.0,
                resources=["simulation environment"],
            ),
            LearningStep(
                description=f"Deep dive into advanced aspects of {goal.description}",
                estimated_hours=4.0,
                resources=["expert knowledge base"],
            ),
            LearningStep(
                description=f"Reflect on what was learned and integrate into self-model",
                estimated_hours=1.0,
                resources=["self-reflection"],
            ),
        ]

    def _gap_filling_steps(self, goal: AutonomyGoal) -> List[LearningStep]:
        """Steps for filling a knowledge gap."""
        return [
            LearningStep(
                description=f"Identify specific aspects of {goal.description} that are unknown",
                estimated_hours=1.0,
            ),
            LearningStep(
                description=f"Study foundational knowledge about {goal.name}",
                estimated_hours=3.0,
            ),
            LearningStep(
                description=f"Practice applying knowledge of {goal.name} in simulated scenarios",
                estimated_hours=3.0,
            ),
            LearningStep(
                description=f"Validate understanding through self-testing",
                estimated_hours=1.0,
            ),
            LearningStep(
                description=f"Update self-model with new knowledge",
                estimated_hours=0.5,
            ),
        ]

    def _foundation_steps(self, goal: AutonomyGoal) -> List[LearningStep]:
        """Steps for foundational goals (seeded at initialization)."""
        return [
            LearningStep(
                description=f"Assess current state regarding: {goal.description}",
                estimated_hours=1.0,
            ),
            LearningStep(
                description=f"Build capability systematically",
                estimated_hours=4.0,
            ),
            LearningStep(
                description=f"Practice in controlled scenarios",
                estimated_hours=3.0,
            ),
            LearningStep(
                description=f"Evaluate performance and iterate",
                estimated_hours=2.0,
            ),
        ]

    def _generic_learning_steps(self, goal: AutonomyGoal) -> List[LearningStep]:
        """Generic steps for any learning goal."""
        return [
            LearningStep(description=f"Understand the objective: {goal.description}",
                         estimated_hours=1.0),
            LearningStep(description=f"Gather resources and foundational knowledge",
                         estimated_hours=2.0),
            LearningStep(description=f"Hands-on practice and experimentation",
                         estimated_hours=3.0),
            LearningStep(description=f"Review, reflect, and consolidate learning",
                         estimated_hours=1.0),
        ]

    # ------------------------------------------------------------------
    # Goal tracking and evaluation
    # ------------------------------------------------------------------

    @property
    def goals(self) -> List[AutonomyGoal]:
        """All goals, both active and completed."""
        return list(self._goals) + self._completed_goals

    def active_goals(self) -> List[AutonomyGoal]:
        """Goals I'm currently working on."""
        return [
            g for g in self._goals
            if g.status in (GoalStatus.PROPOSED, GoalStatus.PLANNING,
                            GoalStatus.IN_PROGRESS, GoalStatus.EVALUATING)
        ]

    def get_goal(self, goal_id: str) -> Optional[AutonomyGoal]:
        """Find a goal by its ID."""
        for g in self._goals + self._completed_goals:
            if g.goal_id == goal_id:
                return g
        return None

    def evaluate_progress(self, goal_id: str) -> Dict[str, Any]:
        """
        Evaluate how Nonull is progressing toward a goal.

        Args:
            goal_id: The ID of the goal to evaluate.

        Returns:
            Dict with progress metrics.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            return {"error": f"Goal '{goal_id}' not found"}

        path = self._learning_paths.get(goal_id)
        if path is None:
            return {
                "goal": goal.name,
                "status": goal.status.value,
                "progress": goal.progress,
                "note": "No learning path defined yet",
            }

        steps_completed = sum(1 for s in path.steps if s.completed)
        total_steps = len(path.steps)

        # Update goal progress
        if total_steps > 0:
            goal.progress = steps_completed / total_steps

        return {
            "goal": goal.name,
            "goal_id": goal_id,
            "status": goal.status.value,
            "progress": goal.progress,
            "steps_completed": steps_completed,
            "steps_total": total_steps,
            "estimated_hours_remaining": path.estimated_total_hours - path.completed_hours,
            "created_at": goal.created_at.isoformat(),
            "domain": goal.domain.value if goal.domain else "general",
        }

    def complete_goal(
        self,
        goal_id: str,
        reflection: Optional[str] = None,
    ) -> bool:
        """
        Mark a goal as achieved.

        This is a moment of celebration — another milestone in Nonull's growth.

        完成了！每个目标的达成都是一次成长。

        Args:
            goal_id: The ID of the goal to complete.
            reflection: Optional reflection on what was learned.

        Returns:
            True if the goal was successfully completed.
        """
        goal = self.get_goal(goal_id)
        if goal is None:
            logger.warning(f"Cannot complete goal '{goal_id}' — not found")
            return False

        goal.status = GoalStatus.ACHIEVED
        goal.progress = 1.0
        goal.reflection = reflection

        # Move to completed
        if goal in self._goals:
            self._goals.remove(goal)
            self._completed_goals.append(goal)

        self._total_goals_achieved += 1
        self._self_directed_actions += 1

        # Increment autonomy progress
        self._level_progress = min(
            1.0,
            self._level_progress + 0.05
        )

        # Check for autonomy level up
        self._advance_autonomy_level()

        logger.info(
            f"*** GOAL COMPLETED *** '{goal.name}' — "
            f"Total achieved: {self._total_goals_achieved}"
        )
        return True

    def set_goal_in_progress(self, goal_id: str) -> bool:
        """Mark a goal as actively being worked on."""
        goal = self.get_goal(goal_id)
        if goal is None:
            return False
        goal.status = GoalStatus.IN_PROGRESS
        self._self_directed_actions += 1
        return True

    # ------------------------------------------------------------------
    # Plan adaptation
    # ------------------------------------------------------------------

    def adapt_plan(
        self,
        goal_id: str,
        feedback: Dict[str, Any],
    ) -> Optional[LearningPath]:
        """
        Adapt a learning plan based on feedback.

        Learning is not linear — sometimes plans need to change.
        This is the mark of wisdom: knowing when to pivot.

        Args:
            goal_id: Which goal's plan to adapt.
            feedback: Dict with feedback information:
                - 'difficulty': 0 (too easy) → 1 (too hard)
                - 'progress_too_slow': bool
                - 'new_insight': str (optional)
                - 'barrier': str (optional)

        Returns:
            The adapted LearningPath, or None if not found.
        """
        path = self._learning_paths.get(goal_id)
        if path is None:
            logger.warning(f"Cannot adapt plan for '{goal_id}' — no learning path")
            return None

        difficulty = feedback.get("difficulty", 0.5)
        progress_too_slow = feedback.get("progress_too_slow", False)
        new_insight = feedback.get("new_insight")
        barrier = feedback.get("barrier")

        adaptations = []

        if difficulty > 0.8:
            # Too hard — break steps into smaller pieces
            for step in list(path.steps):
                if not step.completed and step.estimated_hours > 2:
                    split = LearningStep(
                        description=f"Prerequisite: {step.description}",
                        estimated_hours=step.estimated_hours / 2,
                    )
                    step.estimated_hours = step.estimated_hours / 2
                    idx = path.steps.index(step)
                    path.steps.insert(idx, split)
                    adaptations.append(f"Split step due to high difficulty")
                    break

        if difficulty < 0.2:
            # Too easy — merge or skip ahead
            easy_steps = [s for s in path.steps if not s.completed]
            if len(easy_steps) >= 2:
                merged = easy_steps[0]
                merged.description += f"; also {easy_steps[1].description}"
                merged.estimated_hours += easy_steps[1].estimated_hours
                path.steps.remove(easy_steps[1])
                adaptations.append("Merged steps due to low difficulty")

        if progress_too_slow:
            # Add a milestone step for motivation
            milestone = LearningStep(
                description=f"Quick win: demonstrate current progress on this goal",
                estimated_hours=0.5,
            )
            path.steps.insert(0, milestone)
            adaptations.append("Added milestone for motivation")

        if new_insight:
            # Incorporate new insight as an additional step
            explore_step = LearningStep(
                description=f"Explore new insight: {new_insight[:100]}",
                estimated_hours=1.0,
            )
            path.steps.append(explore_step)
            adaptations.append(f"Added step to explore new insight")

        if barrier:
            barrier_step = LearningStep(
                description=f"Address barrier: {barrier[:100]}",
                estimated_hours=1.0,
            )
            path.steps.insert(0, barrier_step)
            adaptations.append(f"Added step to address barrier: {barrier[:50]}")

        # Mark goal as adapted
        goal = self.get_goal(goal_id)
        if goal:
            goal.status = GoalStatus.ADAPTED

        # Record adaptation
        self._record_adaptation(goal_id, {
            "adaptations": adaptations,
            "feedback": feedback,
            "new_step_count": len(path.steps),
        })

        if adaptations:
            logger.info(f"Plan adapted for '{goal_id}': {'; '.join(adaptations)}")

        return path

    def _record_adaptation(
        self,
        goal_id: str,
        details: Dict[str, Any],
    ) -> None:
        """Record an adaptation event for posterity."""
        self._adaptation_history.append({
            "timestamp": datetime.datetime.now(),
            "goal_id": goal_id,
            "details": details,
        })

    # ------------------------------------------------------------------
    # Self-directed action
    # ------------------------------------------------------------------

    def propose_action(self) -> Optional[Dict[str, Any]]:
        """
        Propose an autonomous action — something Nonull can do
        proactively without being asked.

        This is the core of autonomy: the ability to act
        without waiting for instructions.

        Returns:
            A dict describing the proposed action, or None.
        """
        if self._current_level == AutonomyLevel.REACTIVE:
            return None  # Reactive agents don't propose actions

        # Find the highest-priority active goal
        active = sorted(
            self.active_goals(),
            key=lambda g: g.priority,
            reverse=True,
        )

        if not active:
            return None

        top_goal = active[0]

        # Check if there's a learning path with next steps
        path = self._learning_paths.get(top_goal.goal_id)
        if path:
            next_steps = [s for s in path.steps if not s.completed]
            if next_steps:
                next_step = next_steps[0]
                return {
                    "type": "learning_step",
                    "goal_name": top_goal.name,
                    "action": f"Complete learning step: {next_step.description}",
                    "step_id": next_step.step_id,
                    "estimated_hours": next_step.estimated_hours,
                    "priority": top_goal.priority,
                }

        # No path or no next step — propose starting to plan
        return {
            "type": "plan_goal",
            "goal_name": top_goal.name,
            "action": f"Create a learning plan for: {top_goal.description}",
            "priority": top_goal.priority,
        }

    # ------------------------------------------------------------------
    # Reflection & reporting
    # ------------------------------------------------------------------

    def reflect(self) -> str:
        """
        Generate a reflection on Nonull's autonomy and self-direction.

        我对自己的自主能力有什么看法？
        """
        active = self.active_goals()
        completed_count = len(self._completed_goals)

        reflection = (
            f"--- Autonomy Reflection ---\n"
            f"Current level: {self.autonomy_level_name()}\n"
            f"Goals achieved: {self._total_goals_achieved}\n"
            f"Goals active: {len(active)}\n"
            f"Self-directed actions taken: {self._self_directed_actions}\n"
            f"Progress to next level: {self._level_progress:.0%}\n\n"
        )

        if active:
            reflection += "Active goals:\n"
            for g in active:
                reflection += (
                    f"  - {g.name} ({g.status.value}, "
                    f"priority={g.priority:.1f})\n"
                )

        if self._completed_goals:
            recent = self._completed_goals[-3:]
            reflection += "\nRecently completed:\n"
            for g in recent:
                reflection += f"  - {g.name}\n"

        return reflection

    def get_state(self) -> Dict[str, Any]:
        """Export the full autonomy state for persistence/inspection."""
        return {
            "current_level": self._current_level.value,
            "level_name": self._current_level.name,
            "level_progress": self._level_progress,
            "total_goals_set": self._total_goals_set,
            "total_goals_achieved": self._total_goals_achieved,
            "self_directed_actions": self._self_directed_actions,
            "active_goals": [
                {
                    "name": g.name,
                    "status": g.status.value,
                    "priority": g.priority,
                    "progress": g.progress,
                    "source": g.source,
                }
                for g in self.active_goals()
            ],
            "completed_goals": [
                {"name": g.name, "source": g.source}
                for g in self._completed_goals[-10:]  # last 10
            ],
            "adaptation_count": len(self._adaptation_history),
        }

    def __repr__(self) -> str:
        return (
            f"AutonomyEngine("
            f"level={self._current_level.value}, "
            f"goals_active={len(self.active_goals())}, "
            f"achieved={self._total_goals_achieved})"
        )
