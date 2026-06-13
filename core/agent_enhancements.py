"""
Nonull — Experimental Module Integration Layer
================================================

轻量级整合实验性意识与进化模块到核心智能体生命周期。
Lightweight integration of experimental consciousness and evolution modules
into the core Nonull agent lifecycle.

该层为 Nonull 智能体提供可选的自我进化能力，包括：
- SelfModel: 能力跟踪与成长评估
- CuriosityDriver: 好奇心驱动的探索建议
- AutonomyEngine: 自主目标管理
- GrowthJournal: 经验日志与里程碑追踪
- ExperienceMiner: 经验挖掘与模式提取
- MetaCognition: 元认知与自我评估
- KnowledgeConsolidator: 知识整合与最佳实践生成

WARNING: 所有实验模块均为非确定性、研究用途代码。
实验模块不兼容 ISO 26262 "免于不可接受风险" 的要求。
禁止将其接入任何安全关键管道。

WARNING: All experimental modules are non-deterministic, research-only code.
They are incompatible with ISO 26262 "freedom from unacceptable risk".
Do NOT wire them into any safety-critical pipeline.

Module Design Principles:
  - No hard dependencies: every experimental import is wrapped in try/except.
  - Graceful degradation: if experimental code is missing, the layer degrades
    to a no-op without raising errors.
  - Zero impact on core stability: failed enhancements never propagate as
    exceptions into the main agent lifecycle.

Usage::
    from core.agent_enhancements import AgentEnhancements

    enhancements = AgentEnhancements()
    if enhancements.enabled:
        context = await enhancements.on_task_start("analyze sensor data", ctx)
        # ... agent processes task ...
        await enhancements.on_action_result("tool:read_lidar", result, success=True)
        # ... later, during reflection ...
        await enhancements.on_reflection(reflection_data)

@module: core.agent_enhancements
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Nonull.enhancements")


class AgentEnhancements:
    """
    实验模块集成层 / Experimental Module Integration Layer.

    为 Nonull 智能体提供可选的自我进化能力。所有实验模块导入均使用
    try/except 保护，确保实验代码不可用时不会导致核心功能崩溃。

    Provides optional self-evolution capabilities to the Nonull agent.
    All experimental module imports are wrapped in try/except to ensure
    graceful degradation when experimental code is unavailable.

    Capabilities / 能力:
      - Self-awareness via SelfModel (capability tracking, growth assessment)
      - Curiosity-driven suggestions (exploration topics, related skills)
      - Growth journaling (experience logging, milestone tracking)
      - Knowledge consolidation (pattern extraction, best practice generation)
      - Meta-cognition (self-assessment, improvement plans)

    Attributes:
        _enabled:     是否至少启用了某个实验模块 / Whether any module is enabled
        _self_model:           SelfModel 实例（可选）/ SelfModel instance (optional)
        _curiosity_driver:     CuriosityDriver 实例（可选）/ CuriosityDriver instance (optional)
        _autonomy_engine:      AutonomyEngine 实例（可选）/ AutonomyEngine instance (optional)
        _growth_journal:       GrowthJournal 实例（可选）/ GrowthJournal instance (optional)
        _experience_miner:     ExperienceMiner 实例（可选）/ ExperienceMiner instance (optional)
        _meta_cognition:       MetaCognition 实例（可选）/ MetaCognition instance (optional)
        _knowledge_consolidator: KnowledgeConsolidator 实例（可选）/ KnowledgeConsolidator instance (optional)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化增强模块 / Initialize enhancement modules.

        每个模块都是可选的，导入失败时静默跳过。
        Each module is optional — missing modules are silently skipped.

        Args:
            config: 可选配置字典 / Optional configuration dict
        """
        self._config = config or {}
        self._enabled = False
        self._self_model: Any = None
        self._curiosity_driver: Any = None
        self._autonomy_engine: Any = None
        self._growth_journal: Any = None
        self._experience_miner: Any = None
        self._meta_cognition: Any = None
        self._knowledge_consolidator: Any = None
        self._prompt_optimizer: Any = None

        # 尝试初始化意识模块（SelfModel 作为基础模块）
        # Try to initialize the consciousness module (SelfModel as the base)
        try:
            from experimental.consciousness import SelfModel

            self._self_model = SelfModel()
            self._enabled = True
            logger.debug("SelfModel 已加载 | SelfModel loaded")
        except ImportError as e:
            logger.debug("SelfModel 不可用: %s | SelfModel unavailable: %s", e.__class__.__name__, e)

        try:
            from experimental.consciousness import CuriosityDriver

            self._curiosity_driver = CuriosityDriver()
            self._enabled = True
            logger.debug("CuriosityDriver 已加载 | CuriosityDriver loaded")
        except ImportError as e:
            logger.debug("CuriosityDriver 不可用: %s", e)

        try:
            from experimental.consciousness import AutonomyEngine

            self._autonomy_engine = AutonomyEngine()
            self._enabled = True
            logger.debug("AutonomyEngine 已加载 | AutonomyEngine loaded")
        except ImportError as e:
            logger.debug("AutonomyEngine 不可用: %s", e)

        try:
            from experimental.consciousness import GrowthJournal

            self._growth_journal = GrowthJournal()
            self._enabled = True
            logger.debug("GrowthJournal 已加载 | GrowthJournal loaded")
        except ImportError as e:
            logger.debug("GrowthJournal 不可用: %s", e)

        # 尝试初始化进化模块
        # Try to initialize the evolution modules
        try:
            from experimental.evolution import ExperienceMiner

            self._experience_miner = ExperienceMiner()
            self._enabled = True
            logger.debug("ExperienceMiner 已加载 | ExperienceMiner loaded")
        except ImportError as e:
            logger.debug("ExperienceMiner 不可用: %s", e)

        try:
            from experimental.evolution import MetaCognition

            self._meta_cognition = MetaCognition()
            self._enabled = True
            logger.debug("MetaCognition 已加载 | MetaCognition loaded")
        except ImportError as e:
            logger.debug("MetaCognition 不可用: %s", e)

        try:
            from experimental.evolution import KnowledgeConsolidator

            self._knowledge_consolidator = KnowledgeConsolidator()
            self._enabled = True
            logger.debug("KnowledgeConsolidator 已加载 | KnowledgeConsolidator loaded")
        except ImportError as e:
            logger.debug("KnowledgeConsolidator 不可用: %s", e)

        # 也尝试加载 PromptOptimizer（通过 MetaCognition 使用）
        # Also try PromptOptimizer (used via MetaCognition)
        try:
            from experimental.evolution import PromptOptimizer

            self._prompt_optimizer = PromptOptimizer()
            self._enabled = True
            logger.debug("PromptOptimizer 已加载 | PromptOptimizer loaded")
        except ImportError:
            self._prompt_optimizer = None

        if self._enabled:
            logger.info(
                "AgentEnhancements 已启用（实验性模块）| "
                "Enhancements enabled (experimental modules)"
            )
        else:
            logger.info(
                "AgentEnhancements 未启用（所有实验模块不可用）| "
                "Enhancements disabled (all experimental modules unavailable)"
            )

    # ─────────────────────────────────────────────────────────────
    # 属性 / Properties
    # ─────────────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        """
        是否至少有一个增强模块可用 / Whether at least one enhancement module is available.

        Returns:
            True 如果已加载至少一个实验模块 / True if at least one module was loaded
        """
        return self._enabled

    # ─────────────────────────────────────────────────────────────
    # 任务启动 / Task Start
    # ─────────────────────────────────────────────────────────────

    async def on_task_start(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        任务启动时丰富上下文：能力评估与探索建议。
        Enrich task context on start: capability assessment and exploration suggestions.

        在智能体开始处理任务前，通过 SelfModel 评估当前能力匹配度，
        并通过 CuriosityDriver 提供相关探索方向建议。

        Before the agent starts processing a task, assess capability match
        via SelfModel and provide related exploration directions via
        CuriosityDriver.

        Args:
            task:   任务描述 / Task description
            context: 当前上下文 / Current context

        Returns:
            丰富的上下文字典，可能包含:
              - "capabilities": 能力评分 / capability scores
              - "gaps": 能力缺口列表 / list of capability gaps
              - "exploration_suggestions": 探索建议 / exploration suggestions
        """
        if not self._enabled:
            return {}

        result: Dict[str, Any] = {}

        # SelfModel: 评估执行此任务的能力
        # SelfModel: assess capabilities for this task
        if self._self_model is not None:
            try:
                result["capabilities"] = self._self_model.self_efficacy()
            except Exception as e:
                logger.warning("self_efficacy() 失败: %s | self_efficacy() failed: %s", e.__class__.__name__, e)
                result["capabilities"] = {}

            try:
                gaps = getattr(self._self_model, "gaps", [])
                result["gaps"] = [g.domain if hasattr(g, "domain") else str(g) for g in gaps]
            except Exception as e:
                logger.warning("获取能力缺口失败: %s | failed to get gaps: %s", e.__class__.__name__, e)
                result["gaps"] = []

        # CuriosityDriver: 提供相关探索建议
        # CuriosityDriver: suggest related exploration
        if self._curiosity_driver is not None:
            try:
                suggestions = self._curiosity_driver.suggest_exploration(task)
                result["exploration_suggestions"] = suggestions
            except Exception as e:
                logger.warning("suggest_exploration() 失败: %s", e)
                result["exploration_suggestions"] = []

        # 如果有能力缺口，记录到成长日志
        # If there are capability gaps, log them to growth journal
        if self._growth_journal is not None and result.get("gaps"):
            try:
                self._growth_journal.log_entry(
                    "gap_identified",
                    {
                        "task": task,
                        "gaps": result["gaps"],
                        "timestamp": time.time(),
                    },
                )
            except Exception as e:
                logger.warning("gap_identified 日志失败: %s", e)

        return result

    # ─────────────────────────────────────────────────────────────
    # 动作结果 / Action Result
    # ─────────────────────────────────────────────────────────────

    async def on_action_result(
        self,
        action: str,
        result: Any,
        success: bool,
    ) -> Dict[str, Any]:
        """
        记录动作结果用于成长追踪。
        Log action result for growth tracking.

        成功时更新 SelfModel 的感知能力，失败时记录错误到 GrowthJournal，
        同时将执行痕迹喂给 ExperienceMiner 进行模式分析。

        On success, update SelfModel's self-perception of capabilities.
        On failure, log errors to GrowthJournal. Feed execution traces to
        ExperienceMiner for pattern analysis.

        Args:
            action:  执行的动作描述 / Description of the executed action
            result:  执行结果 / Execution result
            success: 是否成功 / Whether the action succeeded

        Returns:
            记录摘要字典 / Record summary dict
        """
        if not self._enabled:
            return {}

        result_data: Dict[str, Any] = {}

        # SelfModel: 根据执行结果更新自我感知
        # SelfModel: update self-perception based on outcome
        if self._self_model is not None:
            try:
                self._self_model.update_self_perception(action, success=success)
            except Exception as e:
                logger.warning("update_self_perception() 失败: %s", e)

        # GrowthJournal: 记录执行事件
        # GrowthJournal: log execution event
        if self._growth_journal is not None:
            try:
                entry = {
                    "event": "action_completed",
                    "action": action,
                    "success": success,
                    "timestamp": time.time(),
                }
                if not success:
                    entry["error"] = str(result) if result else "unknown error"
                self._growth_journal.log_entry("experience", entry)
                result_data["logged"] = True
            except Exception as e:
                logger.warning("growth journal log failed: %s", e)

        # ExperienceMiner: 喂入执行痕迹
        # ExperienceMiner: feed execution trace
        if self._experience_miner is not None:
            try:
                trace = {
                    "action": action,
                    "result": str(result)[:500],  # 截断以避免过大 / truncate to avoid oversized payloads
                    "success": success,
                    "timestamp": time.time(),
                }
                self._experience_miner.record_trace(trace)
                result_data["trace_recorded"] = True
            except Exception as e:
                logger.warning("experience_miner.record_trace() failed: %s", e)

        # MetaCognition: 对成功或失败进行快速自我评估
        # MetaCognition: quick self-assessment on success or failure
        if self._meta_cognition is not None:
            try:
                self._meta_cognition.assess(action, success=success, result=result)
            except Exception as e:
                logger.warning("meta_cognition.assess() failed: %s", e)

        return result_data

    # ─────────────────────────────────────────────────────────────
    # 反思处理 / Reflection
    # ─────────────────────────────────────────────────────────────

    async def on_reflection(self, reflection: Dict[str, Any]) -> Dict[str, Any]:
        """
        对反思结果提供元认知分析。
        Provide meta-cognitive analysis of reflection results.

        如果反思评分较低，通过 PromptOptimizer 提供提示词改进建议。
        如果反思中发现具体问题，通过 KnowledgeConsolidator 提取经验教训。

        If the reflection score is low, provide prompt improvement suggestions
        via PromptOptimizer. If specific issues are found, extract lessons
        learned via KnowledgeConsolidator.

        Args:
            reflection: 反思结果字典，包含:
                - "score":        自我评分 (0-1)
                - "task":         任务描述
                - "issues":       发现的问题列表
                - "improvements": 改进建议列表
                / reflection dict with score, task, issues, improvements

        Returns:
            增强后的反思结果 / Enhanced reflection result
        """
        if not self._enabled:
            return {}

        result: Dict[str, Any] = {}
        score = reflection.get("score", 0.5)

        # PromptOptimizer: 评分低时提供提示改进建议
        # PromptOptimizer: suggest prompt improvements when score is low
        prompt_optimizer = getattr(self, "_prompt_optimizer", None)
        if prompt_optimizer is not None and score < 0.5:
            try:
                result["prompt_suggestions"] = prompt_optimizer.optimize("general")
            except Exception as e:
                logger.warning("prompt_optimizer.optimize() failed: %s", e)

        # KnowledgeConsolidator: 提取经验教训
        # KnowledgeConsolidator: extract lessons learned
        if self._knowledge_consolidator is not None and reflection.get("issues"):
            try:
                insights = {
                    "task": reflection.get("task", ""),
                    "issues": reflection.get("issues", []),
                    "improvements": reflection.get("improvements", []),
                }
                self._knowledge_consolidator.consolidate(insights)
                result["consolidated"] = True
            except Exception as e:
                logger.warning("knowledge_consolidator.consolidate() failed: %s", e)

        # GrowthJournal: 记录反思事件
        # GrowthJournal: log reflection event
        if self._growth_journal is not None:
            try:
                self._growth_journal.log_entry(
                    "reflection",
                    {
                        "score": score,
                        "task": reflection.get("task", ""),
                        "issues_count": len(reflection.get("issues", [])),
                        "timestamp": time.time(),
                    },
                )
            except Exception as e:
                logger.warning("growth journal reflection log failed: %s", e)

        return result

    # ─────────────────────────────────────────────────────────────
    # 空闲处理 / Idle
    # ─────────────────────────────────────────────────────────────

    async def on_idle(self) -> Dict[str, Any]:
        """
        提供空闲时的自主学习建议。
        Provide idle-time suggestions for autonomous learning.

        在智能体空闲期间，触发好奇心驱动、自主引擎和成长摘要，
        以维持持续的自我改进循环。

        During agent idle periods, trigger curiosity-driven exploration,
        autonomy engine goals, and growth summaries to maintain continuous
        self-improvement loops.

        Returns:
            建议字典，可能包含:
              - "explore_exploit_balance": 探索与利用的平衡 / explore-exploit balance
              - "active_goals": 自主引擎的活跃目标 / active goals from autonomy engine
              - "growth_summary": 成长摘要信息 / growth summary data
        """
        if not self._enabled:
            return {}

        suggestions: Dict[str, Any] = {}

        # CuriosityDriver: 下次探索什么？
        # CuriosityDriver: what to explore next?
        if self._curiosity_driver is not None:
            try:
                balance = self._curiosity_driver.balance_explore_exploit()
                suggestions["explore_exploit_balance"] = balance
            except Exception as e:
                logger.warning("balance_explore_exploit() failed: %s", e)

        # AutonomyEngine: 获取自主目标
        # AutonomyEngine: get active self-directed goals
        if self._autonomy_engine is not None:
            try:
                goals = self._autonomy_engine.get_active_goals()
                suggestions["active_goals"] = goals
            except Exception as e:
                logger.warning("autonomy_engine.get_active_goals() failed: %s", e)

        # GrowthJournal: 成长摘要
        # GrowthJournal: growth summary
        if self._growth_journal is not None:
            try:
                summary = self._growth_journal.get_summary()
                suggestions["growth_summary"] = {
                    "total_entries": summary.get("total_entries", 0),
                    "milestones": summary.get("milestones", []),
                    "growth_score": summary.get("overall_score", 0),
                }
            except Exception as e:
                logger.warning("growth journal summary failed: %s", e)

        return suggestions

    # ─────────────────────────────────────────────────────────────
    # 摘要 / Summary
    # ─────────────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, Any]:
        """
        返回所有增强模块的综合摘要。
        Return a comprehensive summary of all enhancement modules.

        可用于监控面板、日志记录或调试目的。

        Useful for dashboards, logging, or debugging.

        Returns:
            汇总字典，格式如下:
              - 无增强时: {"enabled": False}
              - 有增强时: {
                  "enabled": True,
                  "self_model": { "growth_score", "capabilities_count", "gaps_count" },
                  "growth_journal": { "total_entries", "milestones", "growth_score" },
                  "curiosity": { "active_topics", "top_topic" },
                  ...
                }
        """
        if not self._enabled:
            return {"enabled": False}

        summary: Dict[str, Any] = {"enabled": True}

        # SelfModel 摘要
        # SelfModel summary
        if self._self_model is not None:
            try:
                summary["self_model"] = {
                    "growth_score": self._self_model.self_efficacy(),
                    "capabilities_count": len(getattr(self._self_model, "capabilities", [])),
                    "gaps_count": len(getattr(self._self_model, "gaps", [])),
                }
            except Exception as e:
                logger.warning("self_model summary failed: %s", e)
                summary["self_model"] = {"error": str(e)}

        # GrowthJournal 摘要
        # GrowthJournal summary
        if self._growth_journal is not None:
            try:
                journal_summary = self._growth_journal.get_summary()
                summary["growth_journal"] = {
                    "total_entries": journal_summary.get("total_entries", 0),
                    "milestones": len(journal_summary.get("milestones", [])),
                    "growth_score": journal_summary.get("overall_score", 0),
                }
            except Exception as e:
                logger.warning("growth_journal summary failed: %s", e)
                summary["growth_journal"] = {"error": str(e)}

        # CuriosityDriver 摘要
        # CuriosityDriver summary
        if self._curiosity_driver is not None:
            try:
                topics = self._curiosity_driver.get_active_topics()
                summary["curiosity"] = {
                    "active_topics": len(topics),
                    "top_topic": topics[0] if topics else None,
                }
            except Exception as e:
                logger.warning("curiosity_driver summary failed: %s", e)
                summary["curiosity"] = {"error": str(e)}

        return summary

    # ─────────────────────────────────────────────────────────────
    # 内部 / Internal
    # ─────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        """简短表示增强层状态 / Short repr of enhancement layer state."""
        return (
            f"<AgentEnhancements enabled={self._enabled} "
            f"self_model={'yes' if self._self_model else 'no'} "
            f"curiosity={'yes' if self._curiosity_driver else 'no'} "
            f"autonomy={'yes' if self._autonomy_engine else 'no'} "
            f"journal={'yes' if self._growth_journal else 'no'} "
            f"miner={'yes' if self._experience_miner else 'no'} "
            f"meta={'yes' if self._meta_cognition else 'no'} "
            f"consolidator={'yes' if self._knowledge_consolidator else 'no'}>"
        )
