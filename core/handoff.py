"""
Agent Handoff Protocol — 智能体交接协议

Typed handoff protocol for multi-agent coordination. Inspired by:
- LangGraph Supervisor/Swarm patterns
- OpenAI Agents SDK handoff primitives
- Google A2A Agent Card discovery

Enables agents to transfer control with context preservation,
capability discovery, and audit trails.

@module: core.handoff
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence

logger = logging.getLogger("Nonull.handoff")


class HandoffStrategy(Enum):
    """How control transfers between agents."""
    DELEGATE = "delegate"
    COLLABORATE = "collaborate"
    ESCALATE = "escalate"
    FALLBACK = "fallback"


class HandoffStatus(Enum):
    """Handoff lifecycle states."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass
class AgentCard:
    """
    Agent capability advertisement (inspired by Google A2A).

    Agents publish cards describing what they can do,
    enabling dynamic discovery and routing.
    """
    agent_id: str
    name: str
    description: str
    capabilities: List[str] = field(default_factory=list)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    max_concurrent: int = 1
    priority: int = 0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches(self, query: str) -> bool:
        """Check if this agent can handle a query based on capabilities."""
        q = query.lower()
        return any(cap.lower() in q or q in cap.lower() for cap in self.capabilities)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HandoffContext:
    """Context carried during a handoff."""
    task: str
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    working_memory: List[str] = field(default_factory=list)
    partial_results: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HandoffRequest:
    """A request to transfer control to another agent."""
    handoff_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_agent: str = ""
    target_agent: str = ""
    strategy: HandoffStrategy = HandoffStrategy.DELEGATE
    context: HandoffContext = field(default_factory=HandoffContext)
    reason: str = ""
    timeout_seconds: float = 300.0
    created_at: float = field(default_factory=time.time)
    status: HandoffStatus = HandoffStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["strategy"] = self.strategy.value
        d["status"] = self.status.value
        return d


@dataclass
class HandoffResult:
    """Result of a completed handoff."""
    handoff_id: str
    output: Any = None
    status: HandoffStatus = HandoffStatus.COMPLETED
    duration_seconds: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class AgentRegistry:
    """
    Registry of available agents for handoff routing.

    Agents register their AgentCards. The router matches
    tasks to capable agents.
    """

    def __init__(self):
        self._agents: Dict[str, AgentCard] = {}
        self._handlers: Dict[str, Callable] = {}

    def register(self, card: AgentCard, handler: Optional[Callable] = None) -> None:
        """Register an agent with its capability card."""
        self._agents[card.agent_id] = card
        if handler:
            self._handlers[card.agent_id] = handler
        logger.info("Registered agent: %s (%s)", card.name, card.agent_id)

    def unregister(self, agent_id: str) -> None:
        """Remove an agent from the registry."""
        self._agents.pop(agent_id, None)
        self._handlers.pop(agent_id, None)

    def discover(self, query: str) -> List[AgentCard]:
        """Find agents capable of handling a query."""
        matches = [card for card in self._agents.values() if card.matches(query)]
        return sorted(matches, key=lambda c: c.priority, reverse=True)

    def get(self, agent_id: str) -> Optional[AgentCard]:
        """Get an agent card by ID."""
        return self._agents.get(agent_id)

    def get_handler(self, agent_id: str) -> Optional[Callable]:
        """Get the handler for an agent."""
        return self._handlers.get(agent_id)

    def list_all(self) -> List[AgentCard]:
        """List all registered agents."""
        return list(self._agents.values())

    def __len__(self) -> int:
        return len(self._agents)


class HandoffManager:
    """
    Manages handoffs between agents.

    Handles the full lifecycle: request → accept → execute → complete.
    Maintains an audit trail of all handoffs.
    """

    def __init__(self, registry: Optional[AgentRegistry] = None):
        self._registry = registry or AgentRegistry()
        self._history: List[HandoffRequest] = []
        self._active: Dict[str, HandoffRequest] = {}

    @property
    def registry(self) -> AgentRegistry:
        return self._registry

    def create_handoff(
        self,
        source: str,
        target: str,
        task: str,
        strategy: HandoffStrategy = HandoffStrategy.DELEGATE,
        context: Optional[HandoffContext] = None,
        reason: str = "",
        timeout: float = 300.0,
    ) -> HandoffRequest:
        """Create a new handoff request."""
        if context is None:
            context = HandoffContext(task=task)

        request = HandoffRequest(
            source_agent=source,
            target_agent=target,
            strategy=strategy,
            context=context,
            reason=reason,
            timeout_seconds=timeout,
        )
        self._history.append(request)
        self._active[request.handoff_id] = request
        logger.info(
            "Handoff %s: %s -> %s (%s) reason=%s",
            request.handoff_id, source, target, strategy.value, reason
        )
        return request

    def accept(self, handoff_id: str) -> bool:
        """Accept a pending handoff."""
        req = self._active.get(handoff_id)
        if req and req.status == HandoffStatus.PENDING:
            req.status = HandoffStatus.ACCEPTED
            return True
        return False

    def reject(self, handoff_id: str, reason: str = "") -> bool:
        """Reject a pending or accepted handoff."""
        req = self._active.get(handoff_id)
        if req and req.status in (HandoffStatus.PENDING, HandoffStatus.ACCEPTED):
            req.status = HandoffStatus.REJECTED
            self._active.pop(handoff_id, None)
            logger.info("Handoff %s rejected: %s", handoff_id, reason)
            return True
        return False

    def complete(self, handoff_id: str, result: Any = None, error: Optional[str] = None) -> HandoffResult:
        """Complete a handoff."""
        req = self._active.pop(handoff_id, None)
        if req is None:
            return HandoffResult(handoff_id=handoff_id, status=HandoffStatus.FAILED, error="unknown handoff")

        duration = time.time() - req.created_at
        status = HandoffStatus.COMPLETED if error is None else HandoffStatus.FAILED
        req.status = status

        result_obj = HandoffResult(
            handoff_id=handoff_id,
            output=result,
            status=status,
            duration_seconds=round(duration, 3),
            error=error,
        )
        logger.info("Handoff %s %s (%.1fs)", handoff_id, status.value, duration)
        return result_obj

    def execute(self, handoff_id: str) -> HandoffResult:
        """Execute a handoff by invoking the target agent's handler."""
        req = self._active.get(handoff_id)
        if req is None:
            return HandoffResult(handoff_id=handoff_id, status=HandoffStatus.FAILED, error="unknown handoff")

        if req.status == HandoffStatus.PENDING:
            req.status = HandoffStatus.ACCEPTED

        if req.status != HandoffStatus.ACCEPTED:
            return HandoffResult(handoff_id=handoff_id, status=HandoffStatus.FAILED,
                                 error=f"cannot execute handoff in {req.status.value} state")

        handler = self._registry.get_handler(req.target_agent)
        if handler is None:
            return self.complete(handoff_id, error=f"no handler for {req.target_agent}")

        req.status = HandoffStatus.IN_PROGRESS
        try:
            result = handler(req.context)
            return self.complete(handoff_id, result=result)
        except Exception as e:
            logger.error("Handoff %s execution failed: %s", handoff_id, e)
            return self.complete(handoff_id, error=str(e))

    def auto_route(
        self,
        source: str,
        task: str,
        strategy: HandoffStrategy = HandoffStrategy.DELEGATE,
        context: Optional[HandoffContext] = None,
    ) -> Optional[HandoffRequest]:
        """Auto-route a task to the best available agent."""
        candidates = self._registry.discover(task)
        candidates = [c for c in candidates if c.agent_id != source]

        if not candidates:
            logger.warning("No agent found for task: %s", task[:80])
            return None

        target = candidates[0]
        return self.create_handoff(
            source=source,
            target=target.agent_id,
            task=task,
            strategy=strategy,
            context=context,
        )

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get handoff history."""
        return [h.to_dict() for h in self._history[-limit:]]

    def get_active(self) -> List[Dict[str, Any]]:
        """Get currently active handoffs."""
        return [h.to_dict() for h in self._active.values()]
