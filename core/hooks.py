"""
Hook system — 钩子系统 (Claude Code style lifecycle hooks). Extracted from agent_core.py.
"""

import asyncio
import logging
from enum import Enum
from threading import Lock
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .errors import HookExecutionError

logger = logging.getLogger("Nonull.agent")


class HookPoint(str, Enum):
    """
    钩子点枚举 / Hook Point Enumeration.

    定义智能体生命周期中的所有可挂载点。
    """
    # ── 全局 ──
    ON_INIT = "on_init"
    ON_SHUTDOWN = "on_shutdown"
    ON_ERROR = "on_error"
    # ── 规划 ──
    PRE_PLAN = "pre_plan"
    POST_PLAN = "post_plan"
    # ── 推理 ──
    PRE_REASON = "pre_reason"
    POST_REASON = "post_reason"
    # ── 执行 ──
    PRE_ACT = "pre_act"
    POST_ACT = "post_act"
    # ── 反思 ──
    PRE_REFLECT = "pre_reflect"
    POST_REFLECT = "post_reflect"
    # ── 安全 ──
    PRE_SAFETY_CHECK = "pre_safety_check"
    POST_SAFETY_CHECK = "post_safety_check"
    # ── 子智能体 ──
    PRE_SPAWN = "pre_spawn"
    POST_SPAWN = "post_spawn"
    # ── 记忆 ──
    PRE_MEMORY_STORE = "pre_memory_store"
    POST_MEMORY_STORE = "post_memory_store"
    # ── 状态 ──
    ON_STATE_CHANGE = "on_state_change"


class HookRegistry:
    """
    钩子注册表 / Hook Registry.

    管理钩子的注册和执行。
    支持同步和异步钩子。
    支持优先级排序。
    """

    def __init__(self) -> None:
        self._hooks: Dict[HookPoint, List[Dict[str, Any]]] = {
            hp: [] for hp in HookPoint
        }
        self._lock = Lock()

    def register(
        self,
        hook_point: HookPoint,
        handler: Callable[..., Any],
        name: Optional[str] = None,
        priority: int = 100,
        async_handler: Optional[Callable[..., Awaitable[Any]]] = None,
    ) -> "HookRegistry":
        """
        注册钩子 / Register a hook.

        Args:
            hook_point:    钩子点
            handler:       同步处理器
            name:          钩子名称
            priority:      优先级 (数值越小越先执行)
            async_handler: 异步处理器（可选）

        Returns:
            self
        """
        if hook_point not in HookPoint:
            raise ValueError(f"无效的钩子点: {hook_point}")
        entry = {
            "name": name or f"{handler.__name__}@{hook_point.value}",
            "handler": handler,
            "async_handler": async_handler,
            "priority": priority,
        }
        with self._lock:
            self._hooks[hook_point].append(entry)
            self._hooks[hook_point].sort(key=lambda h: h["priority"])
        logger.debug("钩子已注册: %s @ %s", entry["name"], hook_point.value)
        return self

    def unregister(self, hook_point: HookPoint, name: str) -> bool:
        """注销钩子 / Unregister a hook."""
        with self._lock:
            before = len(self._hooks[hook_point])
            self._hooks[hook_point] = [
                h for h in self._hooks[hook_point] if h["name"] != name
            ]
            return len(self._hooks[hook_point]) < before

    async def execute(
        self,
        hook_point: HookPoint,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Any]:
        """
        执行指定钩子点的所有处理器 / Execute all handlers for a hook point.

        Args:
            hook_point: 钩子点
            context:    上下文
            **kwargs:   传递给处理器的额外参数

        Returns:
            处理器返回值列表
        """
        results: List[Any] = []
        with self._lock:
            hooks = list(self._hooks[hook_point])

        for hook in hooks:
            try:
                handler = hook["handler"]
                async_handler = hook.get("async_handler")

                if async_handler:
                    result = await async_handler(context=context, **kwargs)
                else:
                    if asyncio.iscoroutinefunction(handler):
                        result = await handler(context=context, **kwargs)
                    else:
                        result = handler(context=context, **kwargs)
                results.append(result)

            except Exception as e:
                logger.error(
                    "钩子执行失败: %s @ %s | %s",
                    hook["name"], hook_point.value, e,
                )
                if isinstance(e, HookExecutionError):
                    raise
                # 非关键钩子异常不传播

        return results

    def has_hooks(self, hook_point: HookPoint) -> bool:
        """检查是否有注册的钩子 / Check if hooks exist for a point."""
        with self._lock:
            return len(self._hooks[hook_point]) > 0

    def list_hooks(self, hook_point: Optional[HookPoint] = None) -> Dict[str, List[str]]:
        """列出所有已注册的钩子 / List all registered hooks."""
        with self._lock:
            if hook_point:
                return {
                    hook_point.value: [h["name"] for h in self._hooks[hook_point]]
                }
            return {
                hp.value: [h["name"] for h in hooks]
                for hp, hooks in self._hooks.items() if hooks
            }

    def clear(self) -> None:
        """清空所有钩子 / Clear all hooks."""
        with self._lock:
            for hp in HookPoint:
                self._hooks[hp] = []


__all__ = ["HookPoint", "HookRegistry"]
