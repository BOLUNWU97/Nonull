"""
Event Stream — 事件流架构 / Event-sourcing for agent actions.

Inspired by OpenHands event-stream pattern. All agent actions and observations
flow through a unified event stream, enabling replay, branching, and
time-travel debugging.

@module: core.event_stream
"""
from __future__ import annotations

import json
import time
import uuid
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence
from collections import defaultdict

logger = logging.getLogger("Nonull.events")


class EventType(Enum):
    """Agent event types."""
    # State transitions
    STATE_CHANGE = "state_change"
    # Agent actions
    ACTION_PLAN = "action_plan"
    ACTION_REASON = "action_reason"
    ACTION_EXECUTE = "action_execute"
    ACTION_REFLECT = "action_reflect"
    # Tool/skill invocations
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    SKILL_CALL = "skill_call"
    SKILL_RESULT = "skill_result"
    # LLM interactions
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    # Memory operations
    MEMORY_STORE = "memory_store"
    MEMORY_RETRIEVE = "memory_retrieve"
    # Safety
    SAFETY_CHECK = "safety_check"
    SAFETY_VIOLATION = "safety_violation"
    # Agent lifecycle
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"
    AGENT_ERROR = "agent_error"
    # Handoff
    HANDOFF = "handoff"
    # User interaction
    USER_INPUT = "user_input"
    AGENT_OUTPUT = "agent_output"


@dataclass
class Event:
    """A single event in the stream."""
    event_type: EventType
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str = "main"
    parent_id: Optional[str] = None
    iteration: int = 0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        d = d.copy()
        d["event_type"] = EventType(d["event_type"])
        return cls(**d)

    def __repr__(self) -> str:
        return f"Event({self.event_type.value}, id={self.event_id}, t={self.timestamp:.3f})"


class EventStream:
    """
    Central event bus for agent execution.

    Features:
    - Append-only event log
    - Subscribe to specific event types
    - Snapshot/restore for time-travel
    - Export to JSON for replay
    - Filter and query events
    """

    def __init__(self, agent_id: str = "main", max_events: int = 10000):
        self._events: List[Event] = []
        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = defaultdict(list)
        self._global_subscribers: List[Callable[[Event], None]] = []
        self._agent_id = agent_id
        self._max_events = max_events
        self._snapshots: Dict[str, int] = {}

    def emit(self, event_type: EventType, data: Dict[str, Any], **kwargs) -> Event:
        """Emit an event to the stream."""
        event = Event(
            event_type=event_type,
            data=data,
            agent_id=kwargs.get("agent_id", self._agent_id),
            parent_id=kwargs.get("parent_id"),
            iteration=kwargs.get("iteration", 0),
            tags=kwargs.get("tags", []),
        )
        self._events.append(event)

        if len(self._events) > self._max_events:
            evict_count = len(self._events) - self._max_events
            self._events = self._events[evict_count:]
            for snap_name in list(self._snapshots):
                self._snapshots[snap_name] = max(0, self._snapshots[snap_name] - evict_count)

        for callback in self._subscribers.get(event_type, []):
            try:
                callback(event)
            except Exception as e:
                logger.warning("Event subscriber error: %s", e)

        for callback in self._global_subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.warning("Global subscriber error: %s", e)

        return event

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """Subscribe to a specific event type."""
        self._subscribers[event_type].append(callback)

    def subscribe_all(self, callback: Callable[[Event], None]) -> None:
        """Subscribe to all events."""
        self._global_subscribers.append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """Remove a subscription."""
        subs = self._subscribers.get(event_type, [])
        if callback in subs:
            subs.remove(callback)

    def snapshot(self, name: str) -> str:
        """Take a named snapshot of current position."""
        self._snapshots[name] = len(self._events)
        return name

    def restore(self, name: str) -> List[Event]:
        """Get events since a named snapshot."""
        pos = self._snapshots.get(name, 0)
        return self._events[pos:]

    def replay(self, from_index: int = 0, to_index: Optional[int] = None) -> List[Event]:
        """Get events in a range for replay."""
        return self._events[from_index:to_index]

    def query(
        self,
        event_types: Optional[Sequence[EventType]] = None,
        agent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        since: Optional[float] = None,
        limit: int = 100,
    ) -> List[Event]:
        """Query events with filters."""
        results = self._events
        if event_types:
            type_set = set(event_types)
            results = [e for e in results if e.event_type in type_set]
        if agent_id:
            results = [e for e in results if e.agent_id == agent_id]
        if tags:
            tag_set = set(tags)
            results = [e for e in results if tag_set.intersection(e.tags)]
        if since:
            results = [e for e in results if e.timestamp >= since]
        return results[-limit:]

    def export_json(self, filepath: Optional[str] = None) -> str:
        """Export events to JSON."""
        data = [e.to_dict() for e in self._events]
        json_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_str)
        return json_str

    @classmethod
    def from_json(cls, json_str: str) -> "EventStream":
        """Load events from JSON."""
        data = json.loads(json_str)
        stream = cls()
        for d in data:
            stream._events.append(Event.from_dict(d))
        return stream

    def summary(self) -> Dict[str, Any]:
        """Get a summary of the event stream."""
        type_counts: Dict[str, int] = defaultdict(int)
        for e in self._events:
            type_counts[e.event_type.value] += 1

        duration = 0.0
        if len(self._events) >= 2:
            duration = self._events[-1].timestamp - self._events[0].timestamp

        return {
            "total_events": len(self._events),
            "event_types": dict(type_counts),
            "duration_seconds": round(duration, 3),
            "snapshots": list(self._snapshots.keys()),
            "agents": list(set(e.agent_id for e in self._events)),
        }

    def __len__(self) -> int:
        return len(self._events)

    def __repr__(self) -> str:
        return f"EventStream(events={len(self._events)}, agent={self._agent_id})"
