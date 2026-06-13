"""
Lightweight Agent Tracing — 轻量级智能体追踪

Inspired by OpenTelemetry GenAI conventions and W&B Weave's @weave.op() pattern.
Provides structured tracing for agent execution with zero external dependencies.

Features:
- Hierarchical span tree (parent-child relationships)
- Auto-instrumentation via @trace decorator
- Token/cost tracking per LLM call
- Export to JSON for analysis
- Summary statistics

@module: core.tracing
"""
from __future__ import annotations

import functools
import json
import logging
import time
import uuid
from collections import defaultdict
from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("Nonull.tracing")


class SpanKind(Enum):
    """Types of traced operations."""
    AGENT = "agent"
    LLM = "llm"
    TOOL = "tool"
    SKILL = "skill"
    MEMORY = "memory"
    SAFETY = "safety"
    INTERNAL = "internal"


class SpanStatus(Enum):
    """Span completion status."""
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class Span:
    """A single traced operation."""
    name: str
    kind: SpanKind
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    parent_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: SpanStatus = SpanStatus.OK
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def finish(self, status: SpanStatus = SpanStatus.OK, error: Optional[str] = None) -> None:
        self.end_time = time.time()
        self.status = status
        if error:
            self.error = error

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["status"] = self.status.value
        d["duration_ms"] = round(self.duration_ms, 2)
        return d


class Tracer:
    """
    Collects and manages spans for agent execution tracing.

    Usage:
        tracer = Tracer()

        with tracer.span("plan", SpanKind.AGENT) as s:
            s.set_attribute("task", "navigate to waypoint")
            # ... do work ...

        # Or use the decorator
        @tracer.trace(kind=SpanKind.TOOL)
        def search_memory(query):
            ...
    """

    def __init__(self, service_name: str = "Nonull", enabled: bool = True):
        self._service_name = service_name
        self._enabled = enabled
        self._spans: List[Span] = []
        self._active_span_var: ContextVar[Optional[Span]] = ContextVar("active_span", default=None)
        self._token_usage: Dict[str, float] = defaultdict(float)
        self._callbacks: List[Callable[[Span], None]] = []

    @contextmanager
    def span(self, name: str, kind: SpanKind = SpanKind.INTERNAL, attributes: Optional[Dict[str, Any]] = None):
        """Context manager for creating a traced span."""
        if not self._enabled:
            yield _NoopSpan()
            return

        active = self._active_span_var.get()
        s = Span(
            name=name,
            kind=kind,
            parent_id=active.span_id if active else None,
        )
        if attributes:
            s.attributes.update(attributes)

        token = self._active_span_var.set(s)

        try:
            yield s
            s.finish(SpanStatus.OK)
        except Exception as e:
            s.finish(SpanStatus.ERROR, error=str(e))
            raise
        finally:
            self._active_span_var.reset(token)
            self._spans.append(s)
            for cb in self._callbacks:
                try:
                    cb(s)
                except Exception:
                    pass

    def trace(self, kind: SpanKind = SpanKind.INTERNAL, name: Optional[str] = None):
        """Decorator for tracing function calls (sync and async)."""
        import inspect as _inspect

        def decorator(func: Callable) -> Callable:
            span_name = name or func.__name__

            if _inspect.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    with self.span(span_name, kind) as s:
                        s.set_attribute("args_count", len(args))
                        return await func(*args, **kwargs)
                return async_wrapper

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self.span(span_name, kind) as s:
                    s.set_attribute("args_count", len(args))
                    return func(*args, **kwargs)

            return wrapper
        return decorator

    def record_llm_usage(self, model: str, prompt_tokens: int, completion_tokens: int, cost: float = 0.0) -> None:
        """Record LLM token usage."""
        self._token_usage["prompt_tokens"] += prompt_tokens
        self._token_usage["completion_tokens"] += completion_tokens
        self._token_usage["total_tokens"] += prompt_tokens + completion_tokens
        self._token_usage["total_cost"] += cost

        if self._active_span_var.get():
            active = self._active_span_var.get()
            active.set_attribute("gen_ai.usage.prompt_tokens", prompt_tokens)
            active.set_attribute("gen_ai.usage.completion_tokens", completion_tokens)
            active.set_attribute("gen_ai.system", model)

    def on_span_end(self, callback: Callable[[Span], None]) -> None:
        """Register a callback for when spans complete."""
        self._callbacks.append(callback)

    def get_spans(self, kind: Optional[SpanKind] = None, limit: int = 100) -> List[Span]:
        """Get recorded spans, optionally filtered by kind."""
        spans = self._spans
        if kind:
            spans = [s for s in spans if s.kind == kind]
        return spans[-limit:]

    def build_tree(self) -> List[Dict[str, Any]]:
        """Build a hierarchical tree of spans."""
        spans_by_id = {s.span_id: s.to_dict() for s in self._spans}
        for node in spans_by_id.values():
            node["children"] = []
        roots = []

        for s in self._spans:
            node = spans_by_id[s.span_id]
            if s.parent_id and s.parent_id in spans_by_id:
                spans_by_id[s.parent_id]["children"].append(node)
            else:
                roots.append(node)

        return roots

    def summary(self) -> Dict[str, Any]:
        """Get a summary of all traced operations."""
        kind_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "total_ms": 0.0, "errors": 0})

        for s in self._spans:
            stats = kind_stats[s.kind.value]
            stats["count"] += 1
            stats["total_ms"] += s.duration_ms
            if s.status == SpanStatus.ERROR:
                stats["errors"] += 1

        for stats in kind_stats.values():
            if stats["count"] > 0:
                stats["avg_ms"] = round(stats["total_ms"] / stats["count"], 2)
            stats["total_ms"] = round(stats["total_ms"], 2)

        return {
            "service": self._service_name,
            "total_spans": len(self._spans),
            "by_kind": dict(kind_stats),
            "token_usage": dict(self._token_usage),
        }

    def export_json(self, filepath: Optional[str] = None) -> str:
        """Export all spans to JSON."""
        data = {
            "service": self._service_name,
            "spans": [s.to_dict() for s in self._spans],
            "token_usage": dict(self._token_usage),
        }
        json_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_str)
        return json_str

    def reset(self) -> None:
        """Clear all recorded spans."""
        self._spans.clear()
        self._token_usage.clear()

    def __repr__(self) -> str:
        return f"Tracer(service={self._service_name}, spans={len(self._spans)})"


class _NoopSpan:
    """No-op span used when tracing is disabled."""
    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        pass

    def finish(self, status: SpanStatus = SpanStatus.OK, error: Optional[str] = None) -> None:
        pass


_global_tracer: Optional[Tracer] = None


def get_tracer(service_name: str = "Nonull") -> Tracer:
    """Get or create the global tracer instance."""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = Tracer(service_name=service_name)
    return _global_tracer
