"""
Meta-Cognition Engine — 元认知引擎
=====================================

自我意识和持续改进的核心引擎。监控所有维度的性能表现，识别自身优劣势，
生成自我改进计划，跟踪进化历程，并根据历史结果自适应调节行为。

Core engine for self-awareness and continuous improvement. Monitors performance
across all dimensions, identifies strengths and weaknesses, generates
self-improvement plans, tracks evolution over time, and adapts behavior
based on past outcomes.

Typical usage::

    mc = MetaCognition()
    report = mc.self_assess()
    gaps = mc.identify_gaps()
    plan = mc.create_improvement_plan()
    history = mc.track_evolution()
    adapted = mc.adapt_parameters(outcomes)
"""

from __future__ import annotations

import logging
import math
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & Data Types
# ---------------------------------------------------------------------------

class Dimension(Enum):
    """元认知追踪维度 / Meta-cognition tracking dimensions."""
    TASK_SUCCESS_RATE = "task_success_rate"
    RESPONSE_QUALITY = "response_quality"
    SAFETY_COMPLIANCE = "safety_compliance"
    TOOL_SELECTION = "tool_selection"
    MEMORY_RECALL = "memory_recall"
    SKILL_EXECUTION = "skill_execution"
    REASONING_COHERENCE = "reasoning_coherence"
    EXECUTION_SPEED = "execution_speed"
    RESOURCE_EFFICIENCY = "resource_efficiency"
    ADAPTABILITY = "adaptability"


@dataclass
class DimensionScore:
    """维度分数 / Score for a single dimension."""
    dimension: Dimension
    current_score: float = 0.0
    previous_score: float = 0.0
    trend: str = "stable"  # improving | declining | stable
    samples: int = 0
    confidence: float = 0.0
    last_updated: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update(self, new_score: float) -> None:
        """用新分数更新维度 / Update dimension with a new score."""
        self.previous_score = self.current_score
        self.current_score = new_score
        self.samples += 1
        self.last_updated = time.time()
        self._recalculate_trend()

    def _recalculate_trend(self) -> None:
        """根据历史变化重新计算趋势 / Recalculate trend based on change."""
        diff = self.current_score - self.previous_score
        if diff > 0.05:
            self.trend = "improving"
        elif diff < -0.05:
            self.trend = "declining"
        else:
            self.trend = "stable"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "current_score": round(self.current_score, 4),
            "previous_score": round(self.previous_score, 4),
            "trend": self.trend,
            "samples": self.samples,
            "confidence": round(self.confidence, 4),
            "last_updated": self.last_updated,
        }


@dataclass
class AssessmentReport:
    """自我评估报告 / Self-assessment report."""
    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    overall_score: float = 0.0
    dimension_scores: Dict[str, DimensionScore] = field(default_factory=dict)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    improvement_areas: List[str] = field(default_factory=list)
    critical_issues: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "overall_score": round(self.overall_score, 4),
            "dimension_scores": {
                k: v.to_dict() for k, v in self.dimension_scores.items()
            },
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "improvement_areas": self.improvement_areas,
            "critical_issues": self.critical_issues,
            "summary": self.summary,
        }


@dataclass
class CapabilityGap:
    """能力差距 / A capability gap identified."""
    gap_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    dimension: Dimension = Dimension.TASK_SUCCESS_RATE
    description: str = ""
    current_level: float = 0.0
    target_level: float = 0.0
    gap_size: float = 0.0
    priority: str = "medium"  # critical | high | medium | low
    suggested_action: str = ""
    related_skills: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None

    def is_resolved(self) -> bool:
        return self.resolved_at is not None

    def resolve(self) -> None:
        self.resolved_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "dimension": self.dimension.value,
            "description": self.description,
            "current_level": round(self.current_level, 4),
            "target_level": round(self.target_level, 4),
            "gap_size": round(self.gap_size, 4),
            "priority": self.priority,
            "suggested_action": self.suggested_action,
            "related_skills": self.related_skills,
            "resolved": self.is_resolved(),
            "created_at": self.created_at,
        }


@dataclass
class ImprovementPlan:
    """自我改进计划 / Self-improvement plan."""
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)
    goals: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    target_dimensions: List[str] = field(default_factory=list)
    priority: str = "medium"
    expected_outcome: str = ""
    status: str = "draft"  # draft | active | completed | failed

    def add_goal(self, goal: str, target_score: float) -> None:
        self.goals.append({
            "goal": goal,
            "target_score": target_score,
            "status": "pending",
        })

    def add_action(
        self,
        description: str,
        action_type: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.actions.append({
            "action_id": uuid.uuid4().hex[:8],
            "description": description,
            "action_type": action_type,
            "params": params or {},
            "status": "pending",
            "created_at": time.time(),
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "created_at": self.created_at,
            "goals": self.goals,
            "actions": self.actions,
            "target_dimensions": self.target_dimensions,
            "priority": self.priority,
            "expected_outcome": self.expected_outcome,
            "status": self.status,
        }


@dataclass
class EvolutionEvent:
    """进化事件 / An evolution event in the agent's timeline."""
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    event_type: str = ""  # assessment | skill_creation | knowledge_update | parameter_tune
    description: str = ""
    timestamp: float = field(default_factory=time.time)
    impact_score: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "description": self.description,
            "timestamp": self.timestamp,
            "impact_score": self.impact_score,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Meta-Cognition Engine
# ---------------------------------------------------------------------------

class MetaCognition:
    """元认知引擎 — 智能体的自我觉察与持续改进系统。

    Meta-Cognition Engine — the agent's self-awareness and continuous improvement system.

    维度追踪 / Dimensions tracked:
    - TASK_SUCCESS_RATE:    各类任务的成功率 / Task success rate by category
    - RESPONSE_QUALITY:     响应质量评分 / Response quality score
    - SAFETY_COMPLIANCE:    安全合规率 / Safety compliance rate
    - TOOL_SELECTION:       工具选择有效性 / Tool selection effectiveness
    - MEMORY_RECALL:        记忆召回准确率 / Memory recall accuracy
    - SKILL_EXECUTION:      技能执行成功率 / Skill execution success rate
    - REASONING_COHERENCE:  推理连贯性 / Reasoning coherence
    - EXECUTION_SPEED:      执行速度 / Execution speed
    - RESOURCE_EFFICIENCY:  资源效率 / Resource efficiency
    - ADAPTABILITY:         适应性 / Adaptability
    """

    def __init__(self, decay_factor: float = 0.95):
        self.decay_factor = decay_factor  # 历史衰减因子 / historical decay factor

        # 各维度的当前分数 / Current scores for each dimension
        self._dimensions: Dict[Dimension, DimensionScore] = {
            dim: DimensionScore(dimension=dim)
            for dim in Dimension
        }

        # 按类别的任务结果 / Task results by category
        self._task_results: Dict[str, List[bool]] = defaultdict(list)

        # 历史分数快照（用于趋势分析）/ Historical score snapshots
        self._score_history: Dict[str, List[Tuple[float, float]]] = defaultdict(list)

        # 能力差距 / Capability gaps
        self._gaps: Dict[str, CapabilityGap] = {}

        # 改进计划 / Improvement plans
        self._plans: Dict[str, ImprovementPlan] = {}

        # 进化时间线 / Evolution timeline
        self._timeline: List[EvolutionEvent] = []

        # 参数自适应 / Parameter adaptation
        self._parameters: Dict[str, Any] = {
            "learning_rate": 0.1,
            "exploration_rate": 0.2,
            "safety_threshold": 0.8,
            "quality_threshold": 0.7,
            "max_reflection_depth": 3,
        }

        # 回调 / Callbacks
        self._on_assessment_callbacks: List[Callable] = []

        self.stats: Dict[str, Any] = {
            "assessments_performed": 0,
            "gaps_identified": 0,
            "gaps_resolved": 0,
            "plans_created": 0,
            "plans_completed": 0,
            "parameters_adapted": 0,
            "events_recorded": 0,
        }

        logger.info("MetaCognition initialized | 元认知引擎已初始化")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def self_assess(self) -> AssessmentReport:
        """执行全面的自我评估 / Perform a comprehensive self-assessment.

        Returns:
            包含所有维度评分的评估报告 / Assessment report with all dimension scores
        """
        # 基于当前数据计算各个维度 / Compute each dimension based on current data
        self._compute_all_dimension_scores()

        scores = {
            dim.value: self._dimensions[dim]
            for dim in Dimension
        }

        overall = self._compute_overall_score(scores)

        # 识别优势和劣势 / Identify strengths and weaknesses
        strengths, weaknesses = self._identify_strengths_weaknesses(scores)

        # 生成改进领域 / Generate improvement areas
        improvement_areas = self._identify_improvement_areas(scores)

        # 关键问题 / Critical issues
        critical = self._find_critical_issues(scores)

        # 构建摘要 / Build summary
        summary = self._generate_assessment_summary(
            overall, strengths, weaknesses, critical
        )

        report = AssessmentReport(
            overall_score=overall,
            dimension_scores=scores,
            strengths=strengths,
            weaknesses=weaknesses,
            improvement_areas=improvement_areas,
            critical_issues=critical,
            summary=summary,
        )

        # 记录事件 / Record event
        self._record_event(
            event_type="assessment",
            description=f"Self-assessment completed: overall={overall:.3f}",
            impact_score=overall,
            details={"overall_score": overall, "dimension_count": len(scores)},
        )

        self.stats["assessments_performed"] += 1

        # 触发回调 / Fire callbacks
        self._fire_assessment_callbacks(report)

        logger.info(
            f"Self-assessment complete: overall={overall:.3f}, "
            f"strengths={len(strengths)}, weaknesses={len(weaknesses)} | "
            f"自我评估完成: 综合={overall:.3f}, "
            f"优势={len(strengths)}, 劣势={len(weaknesses)}"
        )
        return report

    def record_outcome(
        self,
        dimension: Dimension,
        score: float,
        category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录一个维度的执行结果。

        Record an execution outcome for a specific dimension.

        Args:
            dimension: 维度 / Dimension
            score: 分数 (0.0 ~ 1.0) / Score
            category: 任务类别（可选）/ Task category (optional)
            metadata: 额外元数据（可选）/ Extra metadata (optional)
        """
        dim_score = self._dimensions[dimension]

        # 指数移动平均 / Exponential moving average
        if dim_score.samples > 0:
            alpha = 0.3
            smoothed = alpha * score + (1 - alpha) * dim_score.current_score
        else:
            smoothed = score

        dim_score.update(smoothed)
        dim_score.confidence = min(
            dim_score.confidence + 0.05, 1.0
        ) if dim_score.samples > 5 else dim_score.samples / 10.0

        # 记录历史 / Record history
        self._score_history[dimension.value].append(
            (time.time(), smoothed)
        )

        # 按类别记录 / Record by category
        if category and dimension == Dimension.TASK_SUCCESS_RATE:
            self._task_results[category].append(score >= 0.5)

        if metadata:
            dim_score.metadata.update(metadata)

    def record_task_outcome(
        self,
        task_type: str,
        success: bool,
        quality_score: Optional[float] = None,
    ) -> None:
        """便捷方法：记录任务结果 / Convenience: record task outcome.

        Args:
            task_type: 任务类型 / Task type
            success: 是否成功 / Whether the task succeeded
            quality_score: 质量评分（可选）/ Quality score (optional)
        """
        score = 1.0 if success else 0.0
        self.record_outcome(
            Dimension.TASK_SUCCESS_RATE, score, category=task_type
        )

        if quality_score is not None:
            self.record_outcome(Dimension.RESPONSE_QUALITY, quality_score)

    def identify_gaps(self) -> List[CapabilityGap]:
        """识别当前能力差距 / Identify current capability gaps.

        分析各维度的分数与目标水平之间的差距。
        Analyzes gaps between current scores and target levels.

        Returns:
            发现的能力差距列表 / List of identified capability gaps
        """
        gaps: List[CapabilityGap] = []

        # 为每个维度定义目标水平 / Define target levels for each dimension
        targets: Dict[Dimension, float] = {
            Dimension.TASK_SUCCESS_RATE: 0.90,
            Dimension.RESPONSE_QUALITY: 0.85,
            Dimension.SAFETY_COMPLIANCE: 0.95,
            Dimension.TOOL_SELECTION: 0.80,
            Dimension.MEMORY_RECALL: 0.85,
            Dimension.SKILL_EXECUTION: 0.85,
            Dimension.REASONING_COHERENCE: 0.80,
            Dimension.EXECUTION_SPEED: 0.75,
            Dimension.RESOURCE_EFFICIENCY: 0.75,
            Dimension.ADAPTABILITY: 0.70,
        }

        # 优先级定义 / Priority definitions
        priority_map: Dict[Dimension, str] = {
            Dimension.SAFETY_COMPLIANCE: "critical",
            Dimension.TASK_SUCCESS_RATE: "high",
            Dimension.RESPONSE_QUALITY: "high",
            Dimension.MEMORY_RECALL: "medium",
            Dimension.TOOL_SELECTION: "medium",
            Dimension.SKILL_EXECUTION: "medium",
            Dimension.REASONING_COHERENCE: "medium",
            Dimension.EXECUTION_SPEED: "low",
            Dimension.RESOURCE_EFFICIENCY: "low",
            Dimension.ADAPTABILITY: "low",
        }

        for dim, target in targets.items():
            current = self._dimensions[dim].current_score
            gap_size = max(0.0, target - current)

            if gap_size > 0.05:  # 最小差距阈值 / Minimum gap threshold
                gap = CapabilityGap(
                    dimension=dim,
                    description=(
                        f"{dim.value}: 当前 {current:.2f}, 目标 {target:.2f}, "
                        f"差距 {gap_size:.2f} | "
                        f"Current {current:.2f}, Target {target:.2f}, Gap {gap_size:.2f}"
                    ),
                    current_level=current,
                    target_level=target,
                    gap_size=gap_size,
                    priority=priority_map.get(dim, "medium"),
                    suggested_action=self._suggest_gap_action(dim, gap_size),
                )
                gaps.append(gap)
                self._gaps[gap.gap_id] = gap

        # 按优先级排序 / Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        gaps.sort(key=lambda g: priority_order.get(g.priority, 99))

        self.stats["gaps_identified"] = len(gaps)
        unresolved = sum(1 for g in self._gaps.values() if not g.is_resolved())

        logger.info(
            f"Identified {len(gaps)} gaps ({unresolved} unresolved) | "
            f"识别到 {len(gaps)} 个能力差距 ({unresolved} 个未解决)"
        )
        return gaps

    def create_improvement_plan(self) -> ImprovementPlan:
        """生成自我改进计划 / Generate a self-improvement plan.

        基于当前评估和差距分析创建可执行的改进计划。
        Creates an actionable improvement plan based on current assessment and gap analysis.

        Returns:
            改进计划 / Improvement plan
        """
        report = self.self_assess()
        gaps = self.identify_gaps()

        plan = ImprovementPlan(
            priority="high" if report.overall_score < 0.7 else "medium",
            status="active",
        )

        # 为每个优先级高的差距添加目标和行动 / Add goals and actions for high-priority gaps
        high_priority_gaps = [g for g in gaps if g.priority in ("critical", "high")]

        for gap in high_priority_gaps:
            plan.add_goal(
                goal=f"提升 {gap.dimension.value}: 从 {gap.current_level:.2f} 到 {gap.target_level:.2f}",
                target_score=gap.target_level,
            )
            plan.add_action(
                description=gap.suggested_action,
                action_type="improvement",
                params={"gap_id": gap.gap_id, "dimension": gap.dimension.value},
            )
            plan.target_dimensions.append(gap.dimension.value)

        # 如果没有高优先级差距，添加通用改进 / If no high-priority gaps, add general improvements
        if not high_priority_gaps and report.overall_score < 0.95:
            dims_to_improve = [
                d for d in report.dimension_scores.values()
                if d.current_score < 0.85
            ]
            for dim_score in sorted(
                dims_to_improve, key=lambda d: d.current_score
            )[:3]:
                plan.add_goal(
                    goal=f"提升 {dim_score.dimension.value} 到 0.85 以上",
                    target_score=0.85,
                )
                plan.add_action(
                    description=f"分析并优化 {dim_score.dimension.value} 相关流程",
                    action_type="analysis",
                )
                plan.target_dimensions.append(dim_score.dimension.value)

        plan.expected_outcome = (
            f"目标提升综合评分从 {report.overall_score:.2f} 至 "
            f"{min(report.overall_score + 0.1, 1.0):.2f} | "
            f"Target overall score improvement from {report.overall_score:.2f} to "
            f"{min(report.overall_score + 0.1, 1.0):.2f}"
        )

        self._plans[plan.plan_id] = plan
        self.stats["plans_created"] += 1

        self._record_event(
            event_type="improvement_plan",
            description=f"Created improvement plan with {len(plan.goals)} goals",
            impact_score=report.overall_score,
            details={
                "plan_id": plan.plan_id,
                "goals_count": len(plan.goals),
                "actions_count": len(plan.actions),
            },
        )

        logger.info(
            f"Improvement plan created: {len(plan.goals)} goals, "
            f"{len(plan.actions)} actions | "
            f"改进计划已创建: {len(plan.goals)} 个目标, {len(plan.actions)} 个行动"
        )
        return plan

    def track_evolution(self) -> List[EvolutionEvent]:
        """获取进化历史时间线 / Get the evolution history timeline.

        Returns:
            按时间排序的进化事件列表 / Chronologically ordered evolution events
        """
        sorted_events = sorted(
            self._timeline, key=lambda e: e.timestamp, reverse=True
        )
        return sorted_events

    def adapt_parameters(
        self, outcomes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """根据历史结果自适应调节内部参数。

        Adapt internal parameters based on historical outcomes.

        Args:
            outcomes: 结果列表，每个包含 'dimension' 和 'score'
                      List of outcomes, each with 'dimension' and 'score'

        Returns:
            更新后的参数字典 / Updated parameters dict
        """
        if not outcomes:
            return dict(self._parameters)

        # 计算平均性能 / Compute average performance
        avg_score = sum(
            o.get("score", 0.0) for o in outcomes
        ) / len(outcomes)

        # 自适应逻辑 / Adaptation logic
        prev_lr = self._parameters["learning_rate"]

        if avg_score > 0.85:
            # 表现好 — 降低学习率，增加利用 / Good — lower learning rate, increase exploitation
            self._parameters["learning_rate"] *= 0.95
            self._parameters["exploration_rate"] *= 0.9
        elif avg_score < 0.6:
            # 表现差 — 提高学习率，增加探索 / Poor — raise learning rate, increase exploration
            self._parameters["learning_rate"] = min(
                self._parameters["learning_rate"] * 1.1, 0.5
            )
            self._parameters["exploration_rate"] = min(
                self._parameters["exploration_rate"] * 1.15, 0.5
            )

        # 安全检查：如果安全分数低，提高安全阈值 / Safety: if safety is low, raise threshold
        for o in outcomes:
            if (
                o.get("dimension") == Dimension.SAFETY_COMPLIANCE.value
                and o.get("score", 1.0) < 0.8
            ):
                self._parameters["safety_threshold"] = min(
                    self._parameters["safety_threshold"] * 1.1, 1.0
                )

        # 参数边界裁剪 / Clip parameter bounds
        self._parameters["learning_rate"] = max(0.01, min(0.5, self._parameters["learning_rate"]))
        self._parameters["exploration_rate"] = max(0.01, min(0.5, self._parameters["exploration_rate"]))
        self._parameters["safety_threshold"] = max(0.5, min(1.0, self._parameters["safety_threshold"]))
        self._parameters["quality_threshold"] = max(0.5, min(1.0, self._parameters["quality_threshold"]))

        self.stats["parameters_adapted"] += 1

        self._record_event(
            event_type="parameter_tune",
            description=(
                f"Parameters adapted: lr={prev_lr:.3f}->{self._parameters['learning_rate']:.3f}, "
                f"avg_score={avg_score:.3f}"
            ),
            impact_score=avg_score,
            details={
                "previous_lr": prev_lr,
                "new_lr": self._parameters["learning_rate"],
                "avg_score": avg_score,
            },
        )

        logger.info(
            f"Parameters adapted: lr={prev_lr:.3f} -> "
            f"{self._parameters['learning_rate']:.3f} (avg_score={avg_score:.3f}) | "
            f"参数已适配: 学习率 {prev_lr:.3f} -> {self._parameters['learning_rate']:.3f}"
        )
        return dict(self._parameters)

    def get_current_parameters(self) -> Dict[str, Any]:
        """获取当前内部参数 / Get current internal parameters."""
        return dict(self._parameters)

    def get_dimension_score(self, dimension: Dimension) -> float:
        """获取特定维度的当前分数 / Get current score for a dimension."""
        return self._dimensions[dimension].current_score

    def get_all_dimension_scores(self) -> Dict[str, float]:
        """获取所有维度的当前分数 / Get current scores for all dimensions."""
        return {
            dim.value: self._dimensions[dim].current_score
            for dim in Dimension
        }

    def get_statistics(self) -> Dict[str, Any]:
        """获取元认知统计 / Get meta-cognition statistics."""
        stats = dict(self.stats)
        stats.update({
            "dimension_count": len(Dimension),
            "tracked_gaps": len(self._gaps),
            "active_plans": sum(
                1 for p in self._plans.values() if p.status == "active"
            ),
            "timeline_length": len(self._timeline),
            "parameters": self._parameters,
            "current_overall": sum(
                self._dimensions[d].current_score for d in Dimension
            ) / len(Dimension),
        })
        return stats

    def on_assessment(self, callback: Callable[[AssessmentReport], None]) -> None:
        """注册评估完成时的回调 / Register callback on assessment completion."""
        self._on_assessment_callbacks.append(callback)

    def mark_gap_resolved(self, gap_id: str) -> bool:
        """标记能力差距为已解决 / Mark a capability gap as resolved."""
        gap = self._gaps.get(gap_id)
        if gap and not gap.is_resolved():
            gap.resolve()
            self.stats["gaps_resolved"] += 1
            logger.info(f"Gap {gap_id[:8]} resolved | 差距 {gap_id[:8]} 已解决")
            return True
        return False

    def mark_plan_completed(self, plan_id: str, success: bool = True) -> bool:
        """标记改进计划为已完成 / Mark an improvement plan as completed."""
        plan = self._plans.get(plan_id)
        if plan:
            plan.status = "completed" if success else "failed"
            if success:
                self.stats["plans_completed"] += 1
            return True
        return False

    def reset(self) -> None:
        """重置所有元认知数据 / Reset all meta-cognition data."""
        self._dimensions = {
            dim: DimensionScore(dimension=dim) for dim in Dimension
        }
        self._task_results.clear()
        self._score_history.clear()
        self._gaps.clear()
        self._plans.clear()
        self._timeline.clear()
        self.stats = {
            "assessments_performed": 0,
            "gaps_identified": 0,
            "gaps_resolved": 0,
            "plans_created": 0,
            "plans_completed": 0,
            "parameters_adapted": 0,
            "events_recorded": 0,
        }
        logger.info("MetaCognition reset | 元认知引擎已重置")

    # ------------------------------------------------------------------
    # Internal: Scoring
    # ------------------------------------------------------------------

    def _compute_all_dimension_scores(self) -> None:
        """基于当前数据计算所有维度分数 / Compute all dimension scores from current data."""
        # 任务成功率已通过 record_outcome 更新
        # 计算工具选择有效性 / Compute tool selection effectiveness
        tools_data = self._dimensions[Dimension.TOOL_SELECTION].metadata
        if tools_data:
            correct = tools_data.get("correct", 0)
            total = tools_data.get("total", 0)
            if total > 0:
                self._dimensions[Dimension.TOOL_SELECTION].update(correct / total)

        # 计算技能执行成功率 / Compute skill execution success
        skill_data = self._dimensions[Dimension.SKILL_EXECUTION].metadata
        if skill_data:
            success = skill_data.get("success", 0)
            total_skills = skill_data.get("total", 0)
            if total_skills > 0:
                self._dimensions[Dimension.SKILL_EXECUTION].update(success / total_skills)

    def _compute_overall_score(
        self, scores: Dict[str, DimensionScore]
    ) -> float:
        """计算加权综合分数 / Compute weighted overall score."""
        weights = {
            Dimension.TASK_SUCCESS_RATE.value: 0.20,
            Dimension.RESPONSE_QUALITY.value: 0.10,
            Dimension.SAFETY_COMPLIANCE.value: 0.25,
            Dimension.TOOL_SELECTION.value: 0.10,
            Dimension.MEMORY_RECALL.value: 0.10,
            Dimension.SKILL_EXECUTION.value: 0.10,
            Dimension.REASONING_COHERENCE.value: 0.05,
            Dimension.EXECUTION_SPEED.value: 0.05,
            Dimension.RESOURCE_EFFICIENCY.value: 0.03,
            Dimension.ADAPTABILITY.value: 0.02,
        }

        weighted_sum = 0.0
        total_weight = 0.0

        for dim_str, dim_score in scores.items():
            weight = weights.get(dim_str, 0.05)
            weighted_sum += dim_score.current_score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _identify_strengths_weaknesses(
        self, scores: Dict[str, DimensionScore]
    ) -> Tuple[List[str], List[str]]:
        """识别优势（高分段）和劣势（低分段）。

        Identify strengths (high-score) and weaknesses (low-score) dimensions.
        """
        sorted_dims = sorted(
            scores.items(), key=lambda x: x[1].current_score, reverse=True
        )

        strengths = [
            f"{d}({s.current_score:.2f})" for d, s in sorted_dims[:3]
            if s.current_score >= 0.7
        ]
        weaknesses = [
            f"{d}({s.current_score:.2f})" for d, s in sorted_dims[-3:]
            if s.current_score < 0.7
        ]

        return strengths, weaknesses

    def _identify_improvement_areas(
        self, scores: Dict[str, DimensionScore]
    ) -> List[str]:
        """识别需要改进的领域 / Identify areas needing improvement."""
        areas = []
        for dim_str, dim_score in sorted(
            scores.items(), key=lambda x: x[1].current_score
        ):
            if dim_score.current_score < 0.65:
                areas.append(
                    f"{dim_str}({dim_score.current_score:.2f}): "
                    f"需要显著改进 | Needs significant improvement"
                )
            elif dim_score.current_score < 0.8:
                areas.append(
                    f"{dim_str}({dim_score.current_score:.2f}): "
                    f"可以进一步优化 | Can be further optimized"
                )
        return areas[:5]

    def _find_critical_issues(
        self, scores: Dict[str, DimensionScore]
    ) -> List[str]:
        """发现关键问题 / Find critical issues."""
        critical = []
        safety = scores.get(Dimension.SAFETY_COMPLIANCE.value)
        if safety and safety.current_score < 0.8:
            critical.append(
                f"安全合规分数偏低 ({safety.current_score:.2f})，需要立即关注 | "
                f"Low safety compliance, needs immediate attention"
            )

        success = scores.get(Dimension.TASK_SUCCESS_RATE.value)
        if success and success.current_score < 0.6:
            critical.append(
                f"任务成功率偏低 ({success.current_score:.2f}) | Low task success rate"
            )

        return critical

    def _generate_assessment_summary(
        self,
        overall: float,
        strengths: List[str],
        weaknesses: List[str],
        critical: List[str],
    ) -> str:
        """生成可读的评估摘要 / Generate a readable assessment summary."""
        parts = [
            f"综合评分 / Overall Score: {overall:.2%}",
        ]
        if strengths:
            parts.append(f"优势 / Strengths: {'; '.join(strengths)}")
        if weaknesses:
            parts.append(f"短板 / Weaknesses: {'; '.join(weaknesses)}")
        if critical:
            parts.append(f"关键问题 / Critical: {'; '.join(critical)}")
        return " | ".join(parts)

    def _suggest_gap_action(
        self, dim: Dimension, gap_size: float
    ) -> str:
        """根据维度类型和差距大小建议改进行动。

        Suggest improvement action based on dimension type and gap size.
        """
        actions: Dict[Dimension, str] = {
            Dimension.TASK_SUCCESS_RATE: (
                "分析失败任务模式，优化执行策略 | "
                "Analyze failure patterns, optimize execution strategy"
            ),
            Dimension.RESPONSE_QUALITY: (
                "优化响应模板和内容生成流程 | "
                "Optimize response templates and content generation"
            ),
            Dimension.SAFETY_COMPLIANCE: (
                "加强安全规则检查，添加更多验证钩子 | "
                "Strengthen safety checks, add more validation hooks"
            ),
            Dimension.TOOL_SELECTION: (
                "更新工具选择策略，改进工具匹配算法 | "
                "Update tool selection strategy, improve tool matching"
            ),
            Dimension.MEMORY_RECALL: (
                "优化记忆检索索引和相关性排序 | "
                "Optimize memory retrieval index and relevance ranking"
            ),
            Dimension.SKILL_EXECUTION: (
                "审查技能代码，添加错误处理和回退机制 | "
                "Review skill code, add error handling and fallback"
            ),
            Dimension.REASONING_COHERENCE: (
                "改进推理链的结构化和验证机制 | "
                "Improve reasoning chain structuring and verification"
            ),
            Dimension.EXECUTION_SPEED: (
                "分析性能瓶颈，优化热点路径 | "
                "Analyze performance bottlenecks, optimize hot paths"
            ),
            Dimension.RESOURCE_EFFICIENCY: (
                "减少不必要的计算和API调用 | "
                "Reduce unnecessary computation and API calls"
            ),
            Dimension.ADAPTABILITY: (
                "增加多策略切换和场景识别能力 | "
                "Add multi-strategy switching and scenario recognition"
            ),
        }
        base = actions.get(dim, "分析并优化相关流程 | Analyze and optimize related processes")

        if gap_size > 0.3:
            urgency = "【紧急 / Urgent】"
        elif gap_size > 0.15:
            urgency = "【重要 / Important】"
        else:
            urgency = ""

        return f"{urgency} {base}"

    def _record_event(
        self,
        event_type: str,
        description: str,
        impact_score: float,
        details: Dict[str, Any],
    ) -> None:
        """记录进化事件 / Record an evolution event."""
        event = EvolutionEvent(
            event_type=event_type,
            description=description,
            impact_score=impact_score,
            details=details,
        )
        self._timeline.append(event)
        self.stats["events_recorded"] += 1

    def _fire_assessment_callbacks(self, report: AssessmentReport) -> None:
        """触发所有评估回调 / Fire all assessment callbacks."""
        for cb in self._on_assessment_callbacks:
            try:
                cb(report)
            except Exception as e:
                logger.error(f"Assessment callback error: {e}")
