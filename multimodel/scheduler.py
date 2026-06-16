"""
混合调度门面 / Hybrid scheduling facade.

把 ModelRegistry + TaskRouter + ModelDispatcher + MultiModelCollaborator 串成
一个统一入口。Nonull 只需持有一个 HybridScheduler, 调 schedule()/aschedule()
即可享受: 自动分类路由 + 多 Key 轮询 + 重试降级 + 超复杂任务多模型协作。

@module: multimodel.scheduler
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .registry import ModelRegistry, ModelTier, PrivacyLevel
from .router import TaskRouter, RoutingStrategy, TaskComplexity
from .dispatcher import ModelDispatcher, CallLogger
from .collaborator import MultiModelCollaborator, CollaborationResult

logger = logging.getLogger("Nonull.multimodel.scheduler")


@dataclass
class ScheduleResult:
    """调度执行结果 / Result of a scheduled task."""
    output: str
    mode: str               # "single" | "collaboration"
    model_used: str
    complexity: str
    privacy: str
    success: bool
    detail: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output": self.output,
            "mode": self.mode,
            "model_used": self.model_used,
            "complexity": self.complexity,
            "privacy": self.privacy,
            "success": self.success,
            "detail": self.detail,
        }


class HybridScheduler:
    """多模型混合调度器 (统一门面) / Unified hybrid-scheduling facade.

    Usage (standalone):
        scheduler = HybridScheduler.from_config(config, cost_tracker=tracker)
        result = await scheduler.aschedule("帮我设计一个限流方案")
        print(result.output, result.mode)  # mode=collaboration (超复杂)

        result = await scheduler.aschedule("翻译: hello world")
        print(result.mode)  # mode=single, 走小模型

    Usage (in Nonull): 见 multimodel/integration_guide.md
    """

    def __init__(
        self,
        registry: ModelRegistry,
        router: Optional[TaskRouter] = None,
        dispatcher: Optional[ModelDispatcher] = None,
        collaborator: Optional[MultiModelCollaborator] = None,
        cost_tracker: Any = None,
        default_strategy: RoutingStrategy = RoutingStrategy.BALANCED,
        enable_collaboration: bool = True,
    ):
        self.registry = registry
        self.cost_tracker = cost_tracker
        self.router = router or TaskRouter(registry, default_strategy=default_strategy)
        self.dispatcher = dispatcher or ModelDispatcher(registry, cost_tracker=cost_tracker)
        self.collaborator = collaborator or MultiModelCollaborator(
            registry, self.router, self.dispatcher,
        )
        self.enable_collaboration = enable_collaboration
        self.call_logger: CallLogger = self.dispatcher.call_logger

    @classmethod
    def from_config(cls, config: Any, cost_tracker: Any = None) -> "HybridScheduler":
        """从 NonullConfig 构建完整调度器 / Build from config in one call."""
        registry = ModelRegistry.from_config(config)
        # 路由策略可从 config 读
        strat = RoutingStrategy.BALANCED
        try:
            s = config.get("routing.strategy", "balanced") if hasattr(config, "get") else "balanced"
            strat = RoutingStrategy(s)
        except Exception:
            pass
        force_local = True
        try:
            force_local = bool(config.get("routing.force_local_on_privacy", True)) \
                if hasattr(config, "get") else True
        except Exception:
            pass
        router = TaskRouter(registry, default_strategy=strat, force_local_on_privacy=force_local)
        dispatcher = ModelDispatcher(registry, cost_tracker=cost_tracker)
        collaborator = MultiModelCollaborator(registry, router, dispatcher)
        return cls(registry, router, dispatcher, collaborator,
                   cost_tracker=cost_tracker, default_strategy=strat)

    # ── 调度 / Schedule ──────────────────────────────────────────

    async def aschedule(
        self,
        task: str,
        *,
        messages: Optional[List[Any]] = None,
        strategy: Optional[RoutingStrategy] = None,
        privacy_override: Optional[PrivacyLevel] = None,
        force_single: bool = False,
    ) -> ScheduleResult:
        """异步调度一个任务 / Schedule a task (async).

        Args:
            task: 任务文本 (用于分类路由)
            messages: 可选完整对话 (传给模型); 默认用 [user: task]
            strategy: 覆盖路由策略
            privacy_override: 显式隐私级别
            force_single: 强制单模型 (跳过协作), 用于子任务避免无限拆解
        """
        decision = self.router.route(task, strategy=strategy, privacy_override=privacy_override)

        # 超复杂 + 启用协作 → 多模型协作
        if (decision.needs_collaboration and self.enable_collaboration and not force_single):
            collab: CollaborationResult = await self.collaborator.collaborate(task)
            return ScheduleResult(
                output=collab.final_output,
                mode="collaboration",
                model_used=f"{collab.total_models_used} models",
                complexity=decision.complexity.value,
                privacy=decision.privacy.value,
                success=bool(collab.final_output),
                detail=collab.to_dict(),
            )

        # 单模型执行
        msgs = messages or [self._msg(task)]
        result = await asyncio.to_thread(
            self.dispatcher.dispatch, decision.model, msgs,
        )
        return ScheduleResult(
            output=result.content,
            mode="single",
            model_used=result.model_used,
            complexity=decision.complexity.value,
            privacy=decision.privacy.value,
            success=result.success,
            detail={"routing": decision.to_dict(), "log": result.log.to_dict()},
        )

    def schedule(self, task: str, **kwargs) -> ScheduleResult:
        """同步调度 (内部跑 event loop) / Sync wrapper."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            raise RuntimeError("schedule() 不能在运行的 event loop 内调用, 请用 aschedule()")
        return asyncio.run(self.aschedule(task, **kwargs))

    def _msg(self, content: str, role: str = "user") -> Any:
        from core.llm_client import LLMMessage
        return LLMMessage(role=role, content=content)

    # ── 可观测 / Observability ───────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """调度统计 (调用日志汇总 + 注册表概览)。"""
        return {
            "models_registered": len(self.registry),
            "models": [e.name for e in self.registry.all()],
            "call_log": self.call_logger.summary(),
        }

    def close(self) -> None:
        """关闭调度器持有的资源 (dispatcher 缓存的 LLMClient)。幂等。

        Closes all cached LLMClients held by the dispatcher. Called by
        Nonull.close() so hybrid usage doesn't leak sockets.
        """
        try:
            if hasattr(self.dispatcher, "close"):
                self.dispatcher.close()
        except Exception:
            logger.debug("HybridScheduler.close 失败", exc_info=True)

    def __repr__(self) -> str:
        return (f"<HybridScheduler models={len(self.registry)} "
                f"strategy={self.router.default_strategy.value} "
                f"collaboration={self.enable_collaboration}>")
