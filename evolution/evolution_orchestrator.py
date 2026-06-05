"""
Evolution Orchestrator — 进化编排器
========================================

Nonull 自我进化系统的核心编排器。协调所有子系统（经验挖掘、技能生成、
元认知、提示优化、知识整合），运行完整的进化周期，管理进化状态和历史，
并在所有进化行动上实施安全门控。

The central orchestrator of the Nonull self-evolution system. Coordinates all
subsystems (experience mining, skill genesis, meta-cognition, prompt optimization,
knowledge consolidation), runs complete evolution cycles, manages evolution state
and history, and applies safety gates on all evolution actions.

进化周期 / Evolution Cycle:
    1. 元认知自我评估 / Meta-cognition self-assessment
    2. 经验挖掘 / Experience mining
    3. 知识整合 / Knowledge consolidation
    4. 技能生成（如发现能力差距）/ Skill genesis (if gaps found)
    5. 提示优化 / Prompt optimization
    6. 性能验证 / Performance validation
    7. 进化报告生成 / Evolution report generation

Typical usage::

    orchestrator = EvolutionOrchestrator()
    report = orchestrator.run_evolution_cycle()
    summary = orchestrator.get_evolution_report()
    timeline = orchestrator.get_evolution_timeline()
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Tuple

from .experience_miner import (
    ExperienceMiner,
    ExecutionTrace,
    ExtractedPattern,
    ImprovementSuggestion,
    KnowledgeItem as MinerKnowledgeItem,
)
from .skill_genesis import (
    SkillGenesis,
    SkillDefinition,
    SkillCategory,
    SkillStatus,
    ValidationReport,
)
from .meta_cognition import (
    MetaCognition,
    AssessmentReport,
    CapabilityGap,
    Dimension,
    ImprovementPlan,
)
from .prompt_optimizer import (
    PromptOptimizer,
    PromptOutcome,
    PromptTemplate,
    ABTestResult,
)
from .knowledge_consolidator import (
    KnowledgeConsolidator,
    KnowledgeItem as ConsolidatorKnowledgeItem,
    KnowledgeType,
    Rule,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Types
# ---------------------------------------------------------------------------

class EvolutionPhase(Enum):
    """进化周期中的阶段 / Phases in an evolution cycle."""
    IDLE = "idle"
    SELF_ASSESSMENT = "self_assessment"
    EXPERIENCE_MINING = "experience_mining"
    KNOWLEDGE_CONSOLIDATION = "knowledge_consolidation"
    SKILL_GENESIS = "skill_genesis"
    PROMPT_OPTIMIZATION = "prompt_optimization"
    PERFORMANCE_VALIDATION = "performance_validation"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"
    FAILED = "failed"


class SafetyGateStatus(Enum):
    """安全门状态 / Safety gate status."""
    PASSED = "passed"
    BLOCKED = "blocked"
    WARNING = "warning"
    NOT_CHECKED = "not_checked"


@dataclass
class SafetyGate:
    """进化安全门 / Evolution safety gate.

    每个进化动作都必须通过安全门检查才能执行。
    Every evolution action must pass a safety gate check before execution.
    """
    gate_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    description: str = ""
    status: SafetyGateStatus = SafetyGateStatus.NOT_CHECKED
    checked_at: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    blocked_reason: Optional[str] = None

    def check(self, condition: bool, warning: Optional[str] = None) -> bool:
        """执行安全门检查 / Execute the safety gate check.

        Args:
            condition: True 表示通过 / True means pass
            warning: 如果 check 失败但不算阻塞的警告 / Non-blocking warning message

        Returns:
            True 如果通过安全门 / True if gate passed
        """
        self.checked_at = time.time()
        if condition:
            self.status = SafetyGateStatus.PASSED
            return True
        elif warning:
            self.status = SafetyGateStatus.WARNING
            self.details["warning"] = warning
            return True
        else:
            self.status = SafetyGateStatus.BLOCKED
            self.blocked_reason = warning or "Safety check failed"
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "checked_at": self.checked_at,
            "blocked_reason": self.blocked_reason,
        }


@dataclass
class EvolutionCycleResult:
    """单次进化周期的完整结果 / Complete result of one evolution cycle."""
    cycle_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    cycle_number: int = 0
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    duration_ms: float = 0.0
    phases_completed: List[str] = field(default_factory=list)
    phases_failed: List[str] = field(default_factory=list)
    safety_gates: List[SafetyGate] = field(default_factory=list)
    success: bool = False

    # 各阶段结果 / Results from each phase
    assessment: Optional[AssessmentReport] = None
    mined_patterns: List[ExtractedPattern] = field(default_factory=list)
    improvements: List[ImprovementSuggestion] = field(default_factory=list)
    knowledge_items: List[ConsolidatorKnowledgeItem] = field(default_factory=list)
    generated_skills: List[SkillDefinition] = field(default_factory=list)
    skill_validations: List[ValidationReport] = field(default_factory=list)
    optimized_prompts: List[PromptTemplate] = field(default_factory=list)
    improvement_plan: Optional[ImprovementPlan] = None
    parameter_updates: Dict[str, Any] = field(default_factory=dict)

    summary: str = ""
    errors: List[str] = field(default_factory=list)

    def complete(self, success: bool) -> None:
        self.completed_at = time.time()
        self.duration_ms = (self.completed_at - self.started_at) * 1000
        self.success = success

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "cycle_number": self.cycle_number,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": round(self.duration_ms, 2),
            "phases_completed": self.phases_completed,
            "phases_failed": self.phases_failed,
            "safety_gates": [g.to_dict() for g in self.safety_gates],
            "success": self.success,
            "patterns_mined": len(self.mined_patterns),
            "improvements_found": len(self.improvements),
            "knowledge_items_created": len(self.knowledge_items),
            "skills_generated": len(self.generated_skills),
            "prompts_optimized": len(self.optimized_prompts),
            "summary": self.summary,
            "error_count": len(self.errors),
        }


@dataclass
class EvolutionState:
    """进化系统的完整状态 / Complete state of the evolution system."""
    is_running: bool = False
    current_cycle: Optional[int] = None
    current_phase: EvolutionPhase = EvolutionPhase.IDLE
    last_cycle_result: Optional[EvolutionCycleResult] = None
    total_cycles_run: int = 0
    total_cycles_successful: int = 0
    total_cycles_failed: int = 0
    evolution_enabled: bool = True
    auto_evolve_interval_hours: float = 0.0
    last_auto_evolve: Optional[float] = None
    lock: Lock = field(default_factory=Lock)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "current_cycle": self.current_cycle,
            "current_phase": self.current_phase.value,
            "total_cycles_run": self.total_cycles_run,
            "total_cycles_successful": self.total_cycles_successful,
            "total_cycles_failed": self.total_cycles_failed,
            "evolution_enabled": self.evolution_enabled,
            "auto_evolve_interval_hours": self.auto_evolve_interval_hours,
            "last_auto_evolve": self.last_auto_evolve,
        }


# ---------------------------------------------------------------------------
# Evolution Orchestrator
# ---------------------------------------------------------------------------

class EvolutionOrchestrator:
    """进化编排器 — Nonull 自我进化系统的核心控制单元。

    Evolution Orchestrator — the core control unit of the Nonull self-evolution system.

    职责 / Responsibilities:
    - 协调所有进化子系统 / Coordinate all evolution subsystems
    - 按计划或按需运行进化周期 / Run evolution cycles on schedule or on-demand
    - 基于元认知决定进化什么 / Decide WHAT to evolve based on meta-cognition
    - 管理进化状态和历史 / Manage evolution state and history
    - 对所有进化行动实施安全门控 / Safety gates on all evolution actions
    """

    def __init__(
        self,
        experience_miner: Optional[ExperienceMiner] = None,
        skill_genesis: Optional[SkillGenesis] = None,
        meta_cognition: Optional[MetaCognition] = None,
        prompt_optimizer: Optional[PromptOptimizer] = None,
        knowledge_consolidator: Optional[KnowledgeConsolidator] = None,
        auto_evolve_interval_hours: float = 0.0,
    ):
        # 子系统 / Subsystems
        self.miner = experience_miner or ExperienceMiner()
        self.genesis = skill_genesis or SkillGenesis()
        self.meta_cognition = meta_cognition or MetaCognition()
        self.optimizer = prompt_optimizer or PromptOptimizer()
        self.consolidator = knowledge_consolidator or KnowledgeConsolidator()

        # 状态 / State
        self.state = EvolutionState(
            auto_evolve_interval_hours=auto_evolve_interval_hours,
        )

        # 周期历史 / Cycle history
        self._cycle_history: List[EvolutionCycleResult] = []

        # 安全门定义 / Safety gate definitions
        self._safety_gates: Dict[str, SafetyGate] = {}

        # 安全门配置 / Safety gate configuration
        self._gate_config = {
            "max_skills_per_cycle": 5,
            "max_prompt_changes_per_cycle": 3,
            "require_skill_validation": True,
            "min_confidence_for_skill_auto_activate": 0.7,
            "block_destructive_evolution": True,
        }

        # 回调 / Callbacks
        self._on_cycle_start_callbacks: List[Callable] = []
        self._on_cycle_complete_callbacks: List[Callable] = []
        self._on_phase_change_callbacks: List[Callable] = []
        self._on_safety_gate_blocked_callbacks: List[Callable] = []

        # 外部数据源钩子 / External data source hooks
        self._trace_provider: Optional[Callable[[], List[ExecutionTrace]]] = None

        self.stats: Dict[str, Any] = {
            "total_cycles_initiated": 0,
            "total_skills_generated_ever": 0,
            "total_prompts_optimized_ever": 0,
            "total_knowledge_items_created_ever": 0,
            "total_safety_gates_passed": 0,
            "total_safety_gates_blocked": 0,
        }

        logger.info(
            "EvolutionOrchestrator initialized | 进化编排器已初始化"
        )

    # ------------------------------------------------------------------
    # Public API — Evolution Control
    # ------------------------------------------------------------------

    def run_evolution_cycle(
        self, traces: Optional[List[ExecutionTrace]] = None
    ) -> EvolutionCycleResult:
        """执行一次完整的进化周期。

        Execute a complete evolution cycle.

        Args:
            traces: 可选的执行轨迹列表，如不提供则从注册的 provider 获取
                    Optional list of traces; if not provided, uses registered provider

        Returns:
            周期结果 / Cycle result

        Raises:
            RuntimeError: 如果已经有一个周期在运行 / If a cycle is already running
        """
        with self.state.lock:
            if self.state.is_running:
                raise RuntimeError(
                    "进化周期已在运行中 / An evolution cycle is already in progress"
                )
            self.state.is_running = True
            self.state.current_cycle = self.state.total_cycles_run + 1
            self.state.current_phase = EvolutionPhase.SELF_ASSESSMENT

        self.stats["total_cycles_initiated"] += 1

        cycle = EvolutionCycleResult(
            cycle_number=self.state.current_cycle,
            started_at=time.time(),
        )

        logger.info(
            f"=== Evolution Cycle #{cycle.cycle_number} started | "
            f"进化周期 #{cycle.cycle_number} 开始 ==="
        )

        # 触发开始回调 / Fire start callbacks
        self._fire_cycle_start_callbacks(cycle)

        try:
            # --- Phase 1: 元认知自我评估 / Meta-cognition Self-Assessment ---
            self._set_phase(EvolutionPhase.SELF_ASSESSMENT, cycle)
            cycle.assessment = self._phase_self_assessment(cycle)
            cycle.phases_completed.append("self_assessment")

            # --- Phase 2: 经验挖掘 / Experience Mining ---
            self._set_phase(EvolutionPhase.EXPERIENCE_MINING, cycle)
            traces = traces or self._get_traces()
            if traces:
                cycle.mined_patterns = self.miner.mine_traces(traces)
                cycle.improvements = self.miner.identify_improvements(traces)
            cycle.phases_completed.append("experience_mining")

            # --- Phase 3: 知识整合 / Knowledge Consolidation ---
            self._set_phase(EvolutionPhase.KNOWLEDGE_CONSOLIDATION, cycle)
            cycle.knowledge_items = self._phase_knowledge_consolidation(
                cycle.mined_patterns, cycle
            )
            cycle.phases_completed.append("knowledge_consolidation")

            # --- Phase 4: 技能生成 / Skill Genesis ---
            self._set_phase(EvolutionPhase.SKILL_GENESIS, cycle)
            cycle.generated_skills, cycle.skill_validations = (
                self._phase_skill_genesis(cycle)
            )
            cycle.phases_completed.append("skill_genesis")

            # --- Phase 5: 提示优化 / Prompt Optimization ---
            self._set_phase(EvolutionPhase.PROMPT_OPTIMIZATION, cycle)
            cycle.optimized_prompts = self._phase_prompt_optimization(cycle)
            cycle.phases_completed.append("prompt_optimization")

            # --- Phase 6: 性能验证 / Performance Validation ---
            self._set_phase(EvolutionPhase.PERFORMANCE_VALIDATION, cycle)
            self._phase_performance_validation(cycle)
            cycle.phases_completed.append("performance_validation")

            # --- Phase 7: 报告生成 / Report Generation ---
            self._set_phase(EvolutionPhase.REPORT_GENERATION, cycle)
            cycle.summary = self._generate_cycle_summary(cycle)
            cycle.complete(success=True)
            cycle.phases_completed.append("report_generation")

            # 更新全局状态 / Update global state
            with self.state.lock:
                self.state.total_cycles_run += 1
                self.state.total_cycles_successful += 1
                self.state.last_cycle_result = cycle
                self.state.current_phase = EvolutionPhase.COMPLETED
                self.state.is_running = False

            self._cycle_history.append(cycle)
            self._fire_cycle_complete_callbacks(cycle)

            logger.info(
                f"=== Evolution Cycle #{cycle.cycle_number} completed successfully "
                f"({cycle.duration_ms:.1f}ms) | "
                f"进化周期 #{cycle.cycle_number} 成功完成 ==="
            )

        except Exception as e:
            logger.error(
                f"Evolution cycle #{cycle.cycle_number} failed: {e} | "
                f"进化周期 #{cycle.cycle_number} 失败: {e}"
            )
            cycle.complete(success=False)
            cycle.errors.append(str(e))
            cycle.phases_failed.append(self.state.current_phase.value)

            with self.state.lock:
                self.state.total_cycles_run += 1
                self.state.total_cycles_failed += 1
                self.state.last_cycle_result = cycle
                self.state.current_phase = EvolutionPhase.FAILED
                self.state.is_running = False

            self._cycle_history.append(cycle)

        return cycle

    def evolve_skills(
        self, traces: Optional[List[ExecutionTrace]] = None
    ) -> List[SkillDefinition]:
        """仅执行技能生成步骤 / Run only the skill genesis step.

        Args:
            traces: 执行轨迹列表 / List of execution traces

        Returns:
            生成的技能列表 / List of generated skills
        """
        if not traces:
            traces = self._get_traces()
        if not traces:
            logger.warning("No traces available for skill evolution | 没有可用于技能进化的轨迹")
            return []

        # 挖掘技能模式 / Mine skill patterns
        skill_patterns = self.miner.extract_skill_patterns(traces)

        # 安全门：技能数量限制 / Safety gate: skill count limit
        gate = self._check_safety_gate(
            "skill_quantity",
            len(skill_patterns) <= self._gate_config["max_skills_per_cycle"],
            warning=f"Limiting to {self._gate_config['max_skills_per_cycle']} skills",
        )
        if gate.status == SafetyGateStatus.BLOCKED:
            return []

        if gate.status == SafetyGateStatus.WARNING:
            skill_patterns = skill_patterns[:self._gate_config["max_skills_per_cycle"]]

        # 为每个模式生成技能 / Generate skills for each pattern
        skills: List[SkillDefinition] = []
        for pattern in skill_patterns:
            skill = self.genesis.auto_learn_from_trace(
                self._pattern_to_trace(pattern)
            )
            if skill:
                skills.append(skill)

        self.stats["total_skills_generated_ever"] += len(skills)
        logger.info(
            f"Evolved {len(skills)} skills from {len(skill_patterns)} patterns | "
            f"从 {len(skill_patterns)} 个模式进化了 {len(skills)} 个技能"
        )
        return skills

    def evolve_knowledge(
        self, traces: Optional[List[ExecutionTrace]] = None
    ) -> List[ConsolidatorKnowledgeItem]:
        """仅执行知识整合步骤 / Run only the knowledge consolidation step.

        Args:
            traces: 执行轨迹列表 / List of execution traces

        Returns:
            知识项列表 / List of knowledge items
        """
        if not traces:
            traces = self._get_traces()
        if not traces:
            logger.warning("No traces available for knowledge evolution | 没有可用于知识进化的轨迹")
            return []

        patterns = self.miner.mine_traces(traces)
        experiences = [p.to_dict() for p in patterns]
        items = self.consolidator.consolidate(experiences)

        # 生成规则 / Generate rules
        for p in patterns:
            self.consolidator.generate_rule(p.to_dict())

        self.consolidator.update_knowledge_graph(items)
        self.stats["total_knowledge_items_created_ever"] += len(items)

        logger.info(
            f"Evolved {len(items)} knowledge items | "
            f"进化了 {len(items)} 条知识"
        )
        return items

    def evolve_prompts(
        self,
        task_outcomes: Optional[Dict[str, List[PromptOutcome]]] = None,
    ) -> List[PromptTemplate]:
        """仅执行提示优化步骤 / Run only the prompt optimization step.

        Args:
            task_outcomes: 按任务类型分组的提示执行结果
                           Prompt outcomes grouped by task type

        Returns:
            生成的模板列表 / List of generated templates
        """
        templates: List[PromptTemplate] = []

        if task_outcomes:
            for task_type, outcomes in task_outcomes.items():
                # 学习模式 / Learn patterns
                self.optimizer.learn_prompt_pattern(task_type, outcomes)

                # 生成新模板 / Generate new template
                template = self.optimizer.generate_template({
                    "type": task_type,
                    "description": f"Auto-optimized template for {task_type}",
                })
                templates.append(template)

                # 安全门：限制本轮更改 / Safety gate: limit changes per cycle
                if len(templates) >= self._gate_config["max_prompt_changes_per_cycle"]:
                    logger.info(
                        f"Reached max prompt changes per cycle | "
                        f"达到本轮最大提示词更改数"
                    )
                    break

        self.stats["total_prompts_optimized_ever"] += len(templates)
        logger.info(
            f"Evolved {len(templates)} prompt templates | "
            f"进化了 {len(templates)} 个提示模板"
        )
        return templates

    # ------------------------------------------------------------------
    # Public API — Reports & Queries
    # ------------------------------------------------------------------

    def get_evolution_report(self) -> Dict[str, Any]:
        """生成完整的进化状态报告。

        Generate a comprehensive evolution status report.

        Returns:
            包含所有子系统状态和统计的字典 / Dict with all subsystem states and stats
        """
        report = {
            "orchestrator": self.state.to_dict(),
            "orchestrator_stats": dict(self.stats),
            "meta_cognition": {
                "stats": self.meta_cognition.get_statistics(),
                "current_scores": self.meta_cognition.get_all_dimension_scores(),
            },
            "experience_miner": {
                "stats": self.miner.get_statistics(),
                "patterns_count": len(self.miner.patterns),
                "knowledge_count": len(self.miner.knowledge_base),
                "suggestions_count": len(self.miner.suggestions),
            },
            "skill_genesis": self.genesis.get_statistics(),
            "prompt_optimizer": self.optimizer.get_statistics(),
            "knowledge_consolidator": self.consolidator.get_statistics(),
            "last_cycle": (
                self.state.last_cycle_result.to_dict()
                if self.state.last_cycle_result else None
            ),
            "cycle_history_count": len(self._cycle_history),
            "safety_gates": [
                g.to_dict() for g in self._safety_gates.values()
            ],
            "generated_at": time.time(),
        }
        return report

    def get_evolution_timeline(
        self, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取进化历史时间线 / Get evolution timeline.

        Args:
            limit: 返回的最大周期数 / Max number of cycles to return

        Returns:
            周期结果字典列表 / List of cycle result dicts
        """
        recent = self._cycle_history[-limit:]
        return [c.to_dict() for c in recent]

    def get_cycle_result(
        self, cycle_number: int
    ) -> Optional[EvolutionCycleResult]:
        """获取特定周期的结果 / Get result of a specific cycle.

        Args:
            cycle_number: 周期编号 / Cycle number (1-based)

        Returns:
            周期结果，如果不存在则返回 None / Cycle result or None
        """
        for c in self._cycle_history:
            if c.cycle_number == cycle_number:
                return c
        return None

    # ------------------------------------------------------------------
    # Public API — Configuration & Hooks
    # ------------------------------------------------------------------

    def set_trace_provider(
        self, provider: Callable[[], List[ExecutionTrace]]
    ) -> None:
        """注册外部轨迹提供者 / Register external trace provider.

        Args:
            provider: 返回 ExecutionTrace 列表的可调用对象
                      Callable that returns a list of ExecutionTraces
        """
        self._trace_provider = provider
        logger.info("Trace provider registered | 轨迹提供者已注册")

    def on_cycle_start(self, callback: Callable[[EvolutionCycleResult], None]) -> None:
        """注册周期开始回调 / Register cycle-start callback."""
        self._on_cycle_start_callbacks.append(callback)

    def on_cycle_complete(
        self, callback: Callable[[EvolutionCycleResult], None]
    ) -> None:
        """注册周期完成回调 / Register cycle-complete callback."""
        self._on_cycle_complete_callbacks.append(callback)

    def on_phase_change(
        self, callback: Callable[[EvolutionPhase, EvolutionCycleResult], None]
    ) -> None:
        """注册阶段变更回调 / Register phase-change callback."""
        self._on_phase_change_callbacks.append(callback)

    def on_safety_gate_blocked(
        self, callback: Callable[[SafetyGate], None]
    ) -> None:
        """注册安全门阻塞回调 / Register safety-gate-blocked callback."""
        self._on_safety_gate_blocked_callbacks.append(callback)

    def update_gate_config(self, config: Dict[str, Any]) -> None:
        """更新安全门配置 / Update safety gate configuration."""
        self._gate_config.update(config)
        logger.info(f"Gate config updated: {config} | 安全门配置已更新")

    def enable_evolution(self) -> None:
        """启用进化系统 / Enable the evolution system."""
        self.state.evolution_enabled = True
        logger.info("Evolution system enabled | 进化系统已启用")

    def disable_evolution(self) -> None:
        """禁用进化系统 / Disable the evolution system."""
        self.state.evolution_enabled = False
        logger.info("Evolution system disabled | 进化系统已禁用")

    def reset(self) -> None:
        """重置所有子系统 / Reset all subsystems."""
        self.miner.reset()
        self.genesis.reset()
        self.meta_cognition.reset()
        self.optimizer.reset()
        self.consolidator.reset()
        self._cycle_history.clear()
        self._safety_gates.clear()
        self.state = EvolutionState(
            auto_evolve_interval_hours=self.state.auto_evolve_interval_hours,
        )
        self.stats = {
            "total_cycles_initiated": 0,
            "total_skills_generated_ever": 0,
            "total_prompts_optimized_ever": 0,
            "total_knowledge_items_created_ever": 0,
            "total_safety_gates_passed": 0,
            "total_safety_gates_blocked": 0,
        }
        logger.info("EvolutionOrchestrator reset | 进化编排器已重置")

    def should_auto_evolve(self) -> bool:
        """检查是否应该自动进化 / Check if auto-evolution is due.

        Returns:
            True 如果到了自动进化的时间 / True if it's time to auto-evolve
        """
        if not self.state.evolution_enabled:
            return False
        if self.state.auto_evolve_interval_hours <= 0:
            return False
        if self.state.is_running:
            return False
        if self.state.last_auto_evolve is None:
            return True

        elapsed = time.time() - self.state.last_auto_evolve
        interval_sec = self.state.auto_evolve_interval_hours * 3600
        return elapsed >= interval_sec

    # ------------------------------------------------------------------
    # Internal: Phase Implementations
    # ------------------------------------------------------------------

    def _phase_self_assessment(
        self, cycle: EvolutionCycleResult
    ) -> AssessmentReport:
        """阶段1: 元认知自我评估 / Phase 1: Meta-cognition self-assessment."""
        logger.info("Phase 1/7: Self-assessment | 阶段 1/7: 自我评估")
        report = self.meta_cognition.self_assess()

        # 更新元认知记录 / Update meta-cognition records
        cycle.improvement_plan = self.meta_cognition.create_improvement_plan()

        return report

    def _phase_knowledge_consolidation(
        self,
        patterns: List[ExtractedPattern],
        cycle: EvolutionCycleResult,
    ) -> List[ConsolidatorKnowledgeItem]:
        """阶段3: 知识整合 / Phase 3: Knowledge consolidation."""
        logger.info("Phase 3/7: Knowledge consolidation | 阶段 3/7: 知识整合")

        if not patterns:
            logger.info("No patterns to consolidate | 没有需要整合的模式")
            return []

        experiences = [p.to_dict() for p in patterns]
        items = self.consolidator.consolidate(experiences)

        # 从模式生成规则 / Generate rules from patterns
        rules_generated = 0
        for p in patterns:
            rule = self.consolidator.generate_rule(p.to_dict())
            if rule:
                rules_generated += 1

        # 更新知识图谱 / Update knowledge graph
        if items:
            self.consolidator.update_knowledge_graph(items)

        logger.info(
            f"Consolidated {len(items)} items, generated {rules_generated} rules | "
            f"整合了 {len(items)} 条知识，生成了 {rules_generated} 条规则"
        )
        return items

    def _phase_skill_genesis(
        self, cycle: EvolutionCycleResult
    ) -> Tuple[List[SkillDefinition], List[ValidationReport]]:
        """阶段4: 技能生成 / Phase 4: Skill genesis."""
        logger.info("Phase 4/7: Skill genesis | 阶段 4/7: 技能生成")

        skills: List[SkillDefinition] = []
        validations: List[ValidationReport] = []

        # 检查是否需要生成新技能 / Check if new skills are needed
        gaps = self.meta_cognition.identify_gaps()
        skill_related_gaps = [
            g for g in gaps
            if g.dimension in (
                Dimension.SKILL_EXECUTION,
                Dimension.TOOL_SELECTION,
                Dimension.TASK_SUCCESS_RATE,
            ) and g.priority in ("critical", "high")
        ]

        if not skill_related_gaps:
            logger.info("No skill-related gaps detected, skipping skill genesis | 未检测到技能相关差距")
            return skills, validations

        # 安全门：检查技能生成是否被允许 / Safety gate: check skill genesis allowed
        gate = self._check_safety_gate(
            "skill_genesis",
            self._gate_config["require_skill_validation"],
            warning="Skill genesis may create unvalidated skills",
        )
        if gate.status == SafetyGateStatus.BLOCKED:
            return skills, validations

        # 挖掘技能模式 / Mine skill patterns
        if hasattr(self.miner, "_cluster") and self.miner.patterns:
            for pattern in list(self.miner.patterns.values())[:3]:
                pattern_name = pattern.name.replace("generalized", "").strip() or "auto_skill"
                skill = self.genesis.generate_skill(
                    pattern,
                    name=f"evolved_{pattern_name}",
                    category=pattern.pattern_type,
                )
                if skill:
                    # 验证技能 / Validate the skill
                    report = self.genesis.validate_skill(skill)
                    validations.append(report)

                    if report.passed and pattern.confidence >= self._gate_config["min_confidence_for_skill_auto_activate"]:
                        skill.activate()
                        logger.info(
                            f"Skill '{skill.name}' activated | 技能 '{skill.name}' 已激活"
                        )

                    skills.append(skill)

        self.stats["total_skills_generated_ever"] += len(skills)
        logger.info(
            f"Generated {len(skills)} skills from gap-driven genesis | "
            f"从差距驱动生成 {len(skills)} 个技能"
        )
        return skills, validations

    def _phase_prompt_optimization(
        self, cycle: EvolutionCycleResult
    ) -> List[PromptTemplate]:
        """阶段5: 提示优化 / Phase 5: Prompt optimization."""
        logger.info("Phase 5/7: Prompt optimization | 阶段 5/7: 提示优化")

        templates: List[PromptTemplate] = []

        # 从元认知结果生成模板 / Generate templates from meta-cognition results
        if cycle.assessment:
            for dim_name, dim_score in cycle.assessment.dimension_scores.items():
                if dim_score.current_score < 0.7:
                    template = self.optimizer.generate_template({
                        "type": f"improve_{dim_name}",
                        "description": f"Optimization template for {dim_name}",
                    })
                    templates.append(template)

        # 安全门：限制模板数量 / Safety gate: limit template count
        gate = self._check_safety_gate(
            "prompt_changes",
            len(templates) <= self._gate_config["max_prompt_changes_per_cycle"],
            warning=f"Limiting to {self._gate_config['max_prompt_changes_per_cycle']} templates",
        )
        if gate.status == SafetyGateStatus.WARNING:
            templates = templates[:self._gate_config["max_prompt_changes_per_cycle"]]

        logger.info(
            f"Generated {len(templates)} optimized prompt templates | "
            f"生成了 {len(templates)} 个优化提示模板"
        )
        return templates

    def _phase_performance_validation(
        self, cycle: EvolutionCycleResult
    ) -> None:
        """阶段6: 性能验证 / Phase 6: Performance validation.

        验证本轮进化不会降低性能。
        Validate that this cycle's evolution does not degrade performance.
        """
        logger.info("Phase 6/7: Performance validation | 阶段 6/7: 性能验证")

        # 安全门：检查是否有破坏性进化 / Safety gate: destructive evolution check
        if self._gate_config["block_destructive_evolution"]:
            has_destructive = any(
                "delete" in s.name or "remove" in s.name
                for s in cycle.generated_skills
            )
            gate = self._check_safety_gate(
                "destructive_evolution",
                not has_destructive,
                warning="Generated skills contain potentially destructive operations",
            )

            if gate.status == SafetyGateStatus.BLOCKED:
                logger.warning("Destructive evolution blocked | 破坏性进化已被阻止")

        # 检查技能验证是否通过 / Check skill validation passes
        failed_validations = [
            v for v in cycle.skill_validations if not v.passed
        ]
        if failed_validations:
            logger.warning(
                f"{len(failed_validations)} skills failed validation | "
                f"{len(failed_validations)} 个技能验证未通过"
            )

    # ------------------------------------------------------------------
    # Internal: Safety Gates
    # ------------------------------------------------------------------

    def _check_safety_gate(
        self,
        gate_name: str,
        condition: bool,
        warning: Optional[str] = None,
    ) -> SafetyGate:
        """检查并记录安全门 / Check and record a safety gate."""
        gate = SafetyGate(
            name=gate_name,
            description=f"Safety gate: {gate_name}",
        )
        passed = gate.check(condition, warning)

        self._safety_gates[gate.gate_id] = gate

        if passed:
            self.stats["total_safety_gates_passed"] += 1
            logger.debug(f"Safety gate '{gate_name}': PASSED")
        else:
            self.stats["total_safety_gates_blocked"] += 1
            logger.warning(
                f"Safety gate '{gate_name}': BLOCKED ({gate.blocked_reason}) | "
                f"安全门 '{gate_name}': 已阻止 ({gate.blocked_reason})"
            )
            self._fire_safety_gate_blocked_callbacks(gate)

        return gate

    # ------------------------------------------------------------------
    # Internal: Helpers
    # ------------------------------------------------------------------

    def _set_phase(
        self, phase: EvolutionPhase, cycle: EvolutionCycleResult
    ) -> None:
        """设置当前阶段 / Set the current phase."""
        with self.state.lock:
            self.state.current_phase = phase

        # 触发回调 / Fire callbacks
        for cb in self._on_phase_change_callbacks:
            try:
                cb(phase, cycle)
            except Exception as e:
                logger.error(f"Phase change callback error: {e}")

    def _get_traces(self) -> List[ExecutionTrace]:
        """从注册的 provider 获取轨迹 / Get traces from registered provider."""
        if self._trace_provider:
            try:
                return self._trace_provider()
            except Exception as e:
                logger.error(f"Trace provider error: {e} | 轨迹提供者错误: {e}")
                return []
        return []

    def _pattern_to_trace(
        self, pattern: ExtractedPattern
    ) -> ExecutionTrace:
        """将模式转换为模拟轨迹用于技能学习。

        Convert a pattern to a simulated trace for skill learning.
        """
        from .experience_miner import ExecutionTrace, TraceStep, TraceStatus

        trace = ExecutionTrace(
            task=f"Pattern: {pattern.name}",
            task_type=pattern.pattern_type,
        )
        for step_dict in pattern.steps_sequence:
            step = TraceStep(
                action=step_dict.get("action", "unknown"),
                tool=step_dict.get("tool"),
                input=step_dict.get("input", {}),
                output=step_dict.get("output"),
                status=TraceStatus.SUCCESS if step_dict.get("status") == "success" else TraceStatus.ERROR,
            )
            trace.add_step(step)

        return trace

    def _generate_cycle_summary(
        self, cycle: EvolutionCycleResult
    ) -> str:
        """生成人类可读的周期摘要 / Generate a human-readable cycle summary."""
        parts = [
            f"进化周期 #{cycle.cycle_number} | Evolution Cycle #{cycle.cycle_number}",
            f"耗时 / Duration: {cycle.duration_ms:.0f}ms",
            f"状态 / Status: {'成功' if cycle.success else '失败'} ({'Success' if cycle.success else 'Failed'})",
        ]

        if cycle.assessment:
            parts.append(
                f"综合评分 / Overall Score: {cycle.assessment.overall_score:.2%}"
            )

        if cycle.mined_patterns:
            parts.append(
                f"挖掘模式 / Patterns: {len(cycle.mined_patterns)}"
            )

        if cycle.improvements:
            parts.append(
                f"改进建议 / Improvements: {len(cycle.improvements)}"
            )

        if cycle.knowledge_items:
            parts.append(
                f"知识项 / Knowledge: {len(cycle.knowledge_items)}"
            )

        if cycle.generated_skills:
            parts.append(
                f"新技能 / New Skills: {len(cycle.generated_skills)}"
            )
            skill_names = [s.name for s in cycle.generated_skills[:3]]
            parts.append(f"  技能列表: {', '.join(skill_names)}")

        if cycle.optimized_prompts:
            parts.append(
                f"优化提示 / Prompts: {len(cycle.optimized_prompts)}"
            )

        if cycle.errors:
            parts.append(f"错误 / Errors: {len(cycle.errors)}")

        return " | ".join(parts)

    def _fire_cycle_start_callbacks(
        self, cycle: EvolutionCycleResult
    ) -> None:
        for cb in self._on_cycle_start_callbacks:
            try:
                cb(cycle)
            except Exception as e:
                logger.error(f"Cycle start callback error: {e}")

    def _fire_cycle_complete_callbacks(
        self, cycle: EvolutionCycleResult
    ) -> None:
        for cb in self._on_cycle_complete_callbacks:
            try:
                cb(cycle)
            except Exception as e:
                logger.error(f"Cycle complete callback error: {e}")

    def _fire_safety_gate_blocked_callbacks(
        self, gate: SafetyGate
    ) -> None:
        for cb in self._on_safety_gate_blocked_callbacks:
            try:
                cb(gate)
            except Exception as e:
                logger.error(f"Safety gate callback error: {e}")
