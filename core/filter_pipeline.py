"""
Filter Pipeline — 过滤器管道

Composable middleware chain for intercepting and transforming agent operations.
Inspired by Semantic Kernel's AutoFunctionInvocationFilter.

@module: core.filter_pipeline
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("Nonull.filters")


@dataclass
class InvocationContext:
    """调用上下文 | Context passed through the filter chain."""

    operation: str
    input_data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)
    agent_id: str = "main"
    cancelled: bool = False
    error: Optional[str] = None


@dataclass
class FilterResult:
    """过滤器结果 | Result wrapper from a single filter invocation."""

    modified: bool = False
    context: InvocationContext = field(default_factory=lambda: InvocationContext(
        operation="", input_data={}
    ))
    filter_name: str = ""


class Filter(ABC):
    """过滤器基类 | Abstract base for all pipeline filters."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def on_before(self, context: InvocationContext) -> InvocationContext:
        ...

    @abstractmethod
    def on_after(self, context: InvocationContext) -> InvocationContext:
        ...

    @abstractmethod
    def on_error(self, context: InvocationContext, error: Exception) -> InvocationContext:
        ...


# ---------------------------------------------------------------------------
# Built-in filters
# ---------------------------------------------------------------------------


class LoggingFilter(Filter):
    """日志过滤器 | Logs operation details before and after execution."""

    @property
    def name(self) -> str:
        return "logging"

    def on_before(self, context: InvocationContext) -> InvocationContext:
        logger.info(
            "[%s] before %s | agent=%s | keys=%s",
            self.name,
            context.operation,
            context.agent_id,
            list(context.input_data.keys()),
        )
        return context

    def on_after(self, context: InvocationContext) -> InvocationContext:
        logger.info(
            "[%s] after %s | agent=%s | has_output=%s",
            self.name,
            context.operation,
            context.agent_id,
            context.output_data is not None,
        )
        return context

    def on_error(self, context: InvocationContext, error: Exception) -> InvocationContext:
        logger.error(
            "[%s] error in %s | agent=%s | %s: %s",
            self.name,
            context.operation,
            context.agent_id,
            type(error).__name__,
            error,
        )
        return context


class TimingFilter(Filter):
    """计时过滤器 | Measures operation duration in milliseconds."""

    def __init__(self) -> None:
        self._starts: Dict[int, float] = {}
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "timing"

    def on_before(self, context: InvocationContext) -> InvocationContext:
        with self._lock:
            self._starts[id(context)] = time.perf_counter()
        return context

    def on_after(self, context: InvocationContext) -> InvocationContext:
        with self._lock:
            start = self._starts.pop(id(context), None)
        if start is not None:
            context.metadata["duration_ms"] = round((time.perf_counter() - start) * 1000, 2)
        return context

    def on_error(self, context: InvocationContext, error: Exception) -> InvocationContext:
        with self._lock:
            start = self._starts.pop(id(context), None)
        if start is not None:
            context.metadata["duration_ms"] = round((time.perf_counter() - start) * 1000, 2)
        return context


class TokenCountFilter(Filter):
    """令牌计数过滤器 | Estimates token count using len/4 heuristic."""

    @property
    def name(self) -> str:
        return "token_count"

    def on_before(self, context: InvocationContext) -> InvocationContext:
        raw = str(context.input_data)
        estimated = len(raw) // 4
        context.metadata["estimated_tokens"] = estimated
        return context

    def on_after(self, context: InvocationContext) -> InvocationContext:
        if context.output_data is not None:
            raw = str(context.output_data)
            context.metadata["estimated_output_tokens"] = len(raw) // 4
        return context

    def on_error(self, context: InvocationContext, error: Exception) -> InvocationContext:
        return context


class CacheFilter(Filter):
    """缓存过滤器 | Dict-based LRU cache for LLM responses keyed by input hash."""

    def __init__(self, maxsize: int = 128) -> None:
        self._maxsize = maxsize
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "cache"

    @staticmethod
    def _hash_input(input_data: Dict[str, Any]) -> str:
        serialized = json.dumps(input_data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def on_before(self, context: InvocationContext) -> InvocationContext:
        if context.operation != "llm_call":
            return context

        key = self._hash_input(context.input_data)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                context.output_data = self._cache[key]
                context.cancelled = True
                context.metadata["cache_hit"] = True
                logger.debug("[%s] cache hit for %s", self.name, key[:12])
                return context

        context.metadata["_cache_key"] = key
        context.metadata["cache_hit"] = False
        return context

    def on_after(self, context: InvocationContext) -> InvocationContext:
        if context.operation != "llm_call":
            return context

        key = context.metadata.get("_cache_key")
        if key is None or context.output_data is None:
            return context

        with self._lock:
            self._cache[key] = context.output_data
            while len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

        return context

    def on_error(self, context: InvocationContext, error: Exception) -> InvocationContext:
        return context


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class FilterPipeline:
    """过滤器管道 | Composable middleware chain with priority-based ordering.

    Filters execute in onion model: on_before runs highest-priority first,
    on_after runs in reverse order (lowest-priority first).
    """

    def __init__(self) -> None:
        self._filters: List[Tuple[int, Filter]] = []
        self._lock = threading.Lock()

    def add(self, filter_instance: Filter, priority: int = 0) -> None:
        with self._lock:
            self._filters.append((priority, filter_instance))
            self._filters.sort(key=lambda pf: pf[0], reverse=True)

    def remove(self, name: str) -> bool:
        with self._lock:
            before = len(self._filters)
            self._filters = [(p, f) for p, f in self._filters if f.name != name]
            return len(self._filters) < before

    def list_filters(self) -> List[str]:
        with self._lock:
            return [f.name for _, f in self._filters]

    def _get_ordered_filters(self) -> List[Filter]:
        with self._lock:
            return [f for _, f in self._filters]

    def execute(
        self,
        operation: str,
        input_data: Dict[str, Any],
        run_fn: Callable,
        **metadata: Any,
    ) -> Any:
        if asyncio.iscoroutinefunction(run_fn):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                # Already inside an event loop — caller must await us; return coroutine.
                return self._execute_async(operation, input_data, run_fn, **metadata)
            else:
                return asyncio.run(
                    self._execute_async(operation, input_data, run_fn, **metadata)
                )

        return self._execute_sync(operation, input_data, run_fn, **metadata)

    def _execute_sync(
        self,
        operation: str,
        input_data: Dict[str, Any],
        run_fn: Callable,
        **metadata: Any,
    ) -> Any:
        context = InvocationContext(
            operation=operation,
            input_data=input_data,
            metadata=metadata,
        )

        ordered = self._get_ordered_filters()
        executed_before: List[Filter] = []

        for f in ordered:
            context = f.on_before(context)
            executed_before.append(f)
            if context.cancelled:
                logger.info("Operation %s cancelled by filter %s", operation, f.name)
                return context.output_data

        try:
            result = run_fn(context.input_data)
            context.output_data = result if isinstance(result, dict) else {"result": result}
        except Exception as exc:
            context.error = str(exc)
            for f in reversed(executed_before):
                context = f.on_error(context, exc)
            raise

        for f in reversed(executed_before):
            context = f.on_after(context)

        return context.output_data

    async def _execute_async(
        self,
        operation: str,
        input_data: Dict[str, Any],
        run_fn: Callable,
        **metadata: Any,
    ) -> Any:
        context = InvocationContext(
            operation=operation,
            input_data=input_data,
            metadata=metadata,
        )

        ordered = self._get_ordered_filters()
        executed_before: List[Filter] = []

        for f in ordered:
            context = f.on_before(context)
            executed_before.append(f)
            if context.cancelled:
                logger.info("Operation %s cancelled by filter %s", operation, f.name)
                return context.output_data

        try:
            result = await run_fn(context.input_data)
            context.output_data = result if isinstance(result, dict) else {"result": result}
        except Exception as exc:
            context.error = str(exc)
            for f in reversed(executed_before):
                context = f.on_error(context, exc)
            raise

        for f in reversed(executed_before):
            context = f.on_after(context)

        return context.output_data
