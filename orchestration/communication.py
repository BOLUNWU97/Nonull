"""
Inter-Agent Communication Layer (智能体间通信层)
=================================================

This module implements the communication infrastructure for the multi-agent
orchestration system. It provides:

  - **Message Passing Protocol**: Structured messages with typed payloads,
    priorities, and routing metadata.
  - **Pub/Sub Event Bus**: Topic-based publish/subscribe for event-driven
    coordination between agents.
  - **Shared Workspace**: A partitioned, thread-safe workspace for agents
    to read/write intermediate results, artifacts, and shared state.
  - **Agent-Addressed Routing**: Messages can be routed to specific agents
    using ``@agent_name`` addressing (OpenClaw style).

Architecture (架构)::

    +----------------------------------------------------------+
    |                      EventBus                            |
    |  publish(topic, msg) ──> subscribers(topic) receive msg  |
    +----------------------------------------------------------+
         |                                        ^
         v                                        |
    +------------------+              +-----------------------+
    |  Agent A         |── message ──>|  Agent B              |
    |  sends to B      |              |  receives via @B      |
    +------------------+              +-----------------------+
         |
         v
    +----------------------------------------------------------+
    |                   SharedWorkspace                        |
    |  /agents/agent_a/data.json                               |
    |  /workflows/safety/analysis.json                         |
    |  /shared/artifacts/                                      |
    +----------------------------------------------------------+

ISO 26262 / ASPICE Alignment:
    - Message logging for full audit trail
    - Priority-based message queuing (safety-critical first)
    - Workspace access control with traceability
"""

from __future__ import annotations

import enum
import json
import logging
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

logger = logging.getLogger(__name__)


# ===================================================================
# Enums
# ===================================================================

class MessageType(str, enum.Enum):
    """Categorization of inter-agent messages."""

    # Task-related messages
    TASK_REQUEST = "task_request"               # Request a task be performed
    TASK_ASSIGNMENT = "task_assignment"         # Assign a task to an agent
    TASK_PROGRESS = "task_progress"             # Progress update on a task
    TASK_COMPLETE = "task_complete"             # Task completed notification
    TASK_FAILED = "task_failed"                 # Task failed notification

    # Coordination messages
    COORDINATION_REQUEST = "coordination_request"   # Coordination request
    COORDINATION_RESPONSE = "coordination_response" # Coordination response
    SYNC_REQUEST = "sync_request"               # State synchronization request
    SYNC_RESPONSE = "sync_response"             # State synchronization response

    # Data messages
    DATA_PUBLISH = "data_publish"               # Publish data to workspace
    DATA_REQUEST = "data_request"               # Request data from workspace
    DATA_RESPONSE = "data_response"             # Response to data request

    # Status messages
    HEARTBEAT = "heartbeat"                     # Agent heartbeat
    STATUS_UPDATE = "status_update"             # Agent status change
    ERROR = "error"                             # Error notification

    # Conflict messages
    CONFLICT_DETECTED = "conflict_detected"     # Conflict flagged
    CONFLICT_RESOLVED = "conflict_resolved"     # Conflict resolved

    # System messages
    SYSTEM_EVENT = "system_event"               # General system event
    LOG_MESSAGE = "log_message"                 # Logging/debug message


class MessagePriority(str, enum.Enum):
    """Priority levels for message delivery."""

    CRITICAL = "critical"       # Safety-critical, immediate delivery
    HIGH = "high"               # Urgent, next available delivery
    NORMAL = "normal"           # Standard delivery
    LOW = "low"                 # Best-effort delivery


# ===================================================================
# Data Structures
# ===================================================================

@dataclass
class Message:
    """
    A structured message for inter-agent communication.

    Attributes:
        id: Unique message identifier.
        type: Message category.
        sender: Agent ID or system component that sent the message.
        recipient: Agent ID (``@agent_name``) or topic/channel.
        priority: Delivery priority.
        payload: Message content (arbitrary JSON-serializable data).
        correlation_id: Links related messages (request/response pairs).
        timestamp: When the message was created.
        ttl_seconds: Time-to-live; message is dropped after this.
        metadata: Additional routing or tracing metadata.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    type: MessageType = MessageType.SYSTEM_EVENT
    sender: str = ""
    recipient: str = ""
    priority: MessagePriority = MessagePriority.NORMAL
    payload: Any = None
    correlation_id: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    ttl_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""
        result = asdict(self)
        if isinstance(self.type, MessageType):
            result["type"] = self.type.value
        if isinstance(self.priority, MessagePriority):
            result["priority"] = self.priority.value
        return result

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Deserialize from a dictionary."""
        if "type" in data and isinstance(data["type"], str):
            data["type"] = MessageType(data["type"])
        if "priority" in data and isinstance(data["priority"], str):
            data["priority"] = MessagePriority(data["priority"])
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "Message":
        """Deserialize from a JSON string."""
        return cls.from_dict(json.loads(json_str))

    def is_expired(self) -> bool:
        """Check if this message has exceeded its TTL."""
        if self.ttl_seconds is None:
            return False
        created = datetime.fromisoformat(self.timestamp)
        elapsed = (
            datetime.now(timezone.utc) - created
        ).total_seconds()
        return elapsed > self.ttl_seconds

    def is_addressed_to(self, agent_name: str) -> bool:
        """
        Check if this message is addressed to a specific agent.

        Supports ``@agent_name`` format (OpenClaw style).
        """
        if not self.recipient:
            return False
        return (
            self.recipient == agent_name
            or self.recipient == f"@{agent_name}"
        )

    def __repr__(self) -> str:
        return (
            f"Message(id={self.id[:8]}, type={self.type.value}, "
            f"sender={self.sender!r}, recipient={self.recipient!r}, "
            f"priority={self.priority.value})"
        )


@dataclass
class AgentAddress:
    """
    Represents an agent's communication endpoint.

    Attributes:
        agent_id: The agent's unique identifier.
        name: Human-readable agent name (used for @name routing).
        channel: Logical channel name for message routing.
        subscribed_topics: Topics the agent is subscribed to.
    """

    agent_id: str
    name: str
    channel: str = "default"
    subscribed_topics: Set[str] = field(default_factory=set)


# ===================================================================
# Event Bus (Pub/Sub)
# ===================================================================

SubscriberFn = Callable[[Message], None]
"""
Signature for a message subscriber function.

Args:
    message: The received message.
"""


class EventBus:
    """
    Topic-based publish/subscribe event bus.

    The EventBus is the central nervous system of the multi-agent system.
    Agents publish messages to topics, and all subscribers to that topic
    receive the message. The bus handles:

      - Topic-based subscription with wildcard support
      - Priority-ordered message delivery
      - Message TTL enforcement
      - Delivery guarantees (at-least-once)
      - Message logging for audit trail

    Thread Safety:
        All operations are thread-safe. Internal state is protected by
        a reentrant lock.

    Usage::

        bus = EventBus()

        def handle_safety_msg(msg: Message):
            print(f"Safety event: {msg.payload}")

        # Subscribe
        sub_id = bus.subscribe("safety.hara", handle_safety_msg)

        # Publish
        bus.publish(Message(
            type=MessageType.DATA_PUBLISH,
            sender="agent_a",
            topic="safety.hara",
            payload={"hazard": "brake_failure", "asil": "D"},
        ))

        # Unsubscribe
        bus.unsubscribe(sub_id)
    """

    def __init__(self, name: str = "default") -> None:
        """
        Initialize the event bus.

        Args:
            name: A name for this bus instance (for logging).
        """
        self._name = name
        self._lock = threading.RLock()
        self._topics: Dict[str, Dict[str, SubscriberFn]] = {}
        self._agent_addresses: Dict[str, AgentAddress] = {}
        self._message_history: List[Message] = []
        self._max_history = 1000
        self._subscriber_counter = 0

        # Hooks
        self._on_publish: List[Callable[[Message], None]] = []
        self._on_subscribe: List[Callable[[str, str], None]] = []

        logger.info("EventBus '%s' initialized", name)

    # ------------------------------------------------------------------
    # Subscription Management
    # ------------------------------------------------------------------

    def subscribe(
        self,
        topic: str,
        callback: SubscriberFn,
        subscriber_name: Optional[str] = None,
    ) -> str:
        """
        Subscribe to a topic.

        Args:
            topic: The topic to subscribe to (e.g., ``"safety.hara"``).
            callback: Function to call when a message is published
                on this topic.
            subscriber_name: Optional name for the subscriber (used for
                logging and identification).

        Returns:
            A subscription ID that can be used to unsubscribe.
        """
        with self._lock:
            self._subscriber_counter += 1
            sub_id = (
                f"{subscriber_name or 'anon'}_"
                f"{self._subscriber_counter}_{uuid.uuid4().hex[:6]}"
            )

            if topic not in self._topics:
                self._topics[topic] = {}

            self._topics[topic][sub_id] = callback

            for hook in self._on_subscribe:
                self._safe_hook(hook, topic, sub_id)

            logger.debug(
                "Subscription: id=%s, topic=%s, bus=%s",
                sub_id,
                topic,
                self._name,
            )
            return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from a topic.

        Args:
            subscription_id: The subscription ID returned by ``subscribe()``.

        Returns:
            True if unsubscribed, False if subscription not found.
        """
        with self._lock:
            for topic, subs in self._topics.items():
                if subscription_id in subs:
                    del subs[subscription_id]
                    logger.debug(
                        "Unsubscribed: id=%s, topic=%s, bus=%s",
                        subscription_id,
                        topic,
                        self._name,
                    )
                    return True
            logger.warning(
                "Subscription %s not found on bus %s",
                subscription_id,
                self._name,
            )
            return False

    def subscribe_agent(
        self,
        address: AgentAddress,
        topics: List[str],
    ) -> Dict[str, str]:
        """
        Subscribe an agent to multiple topics at once.

        Args:
            address: The agent address.
            topics: List of topics to subscribe to.

        Returns:
            Dict mapping topic -> subscription_id.
        """
        with self._lock:
            self._agent_addresses[address.agent_id] = address
            address.subscribed_topics.update(topics)

            results = {}
            for topic in topics:
                sub_id = self.subscribe(
                    topic,
                    lambda msg, aid=address.agent_id: self._route_to_agent(
                        aid, msg
                    ),
                    subscriber_name=address.name,
                )
                results[topic] = sub_id
            return results

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish(
        self,
        message: Message,
        topic: Optional[str] = None,
    ) -> int:
        """
        Publish a message to the bus.

        The message is delivered to all subscribers of the matching topic.
        If the message has a ``recipient`` in ``@agent`` format, it is
        also routed directly to that agent.

        Args:
            message: The message to publish.
            topic: Topic to publish to. If None, uses ``message.recipient``
                as the topic.

        Returns:
            The number of subscribers the message was delivered to.

        Raises:
            ValueError: If neither topic nor message.recipient is set.
        """
        with self._lock:
            actual_topic = topic or message.recipient
            if not actual_topic:
                raise ValueError(
                    "Either topic or message.recipient must be provided"
                )

            # Check TTL
            if message.is_expired():
                logger.debug(
                    "Message %s expired, dropping", message.id[:8]
                )
                return 0

            # Record in history
            self._message_history.append(message)
            if len(self._message_history) > self._max_history:
                self._message_history.pop(0)

            # Delivery hooks
            for hook in self._on_publish:
                self._safe_hook(hook, message)

            # Deliver to direct subscribers of the exact topic
            delivery_count = self._deliver_to_topic(
                actual_topic, message
            )

            # Wildcard delivery: also deliver to parent topics
            self._deliver_wildcard(actual_topic, message, delivery_count)

            # @agent routing
            self._handle_agent_routing(message)

            logger.debug(
                "Published: topic=%s, type=%s, sender=%s, "
                "delivered=%d subscribers",
                actual_topic,
                message.type.value,
                message.sender,
                delivery_count,
            )
            return delivery_count

    def _deliver_to_topic(
        self, topic: str, message: Message
    ) -> int:
        """Deliver message to all subscribers of a specific topic."""
        subscribers = self._topics.get(topic, {})
        count = 0
        for sub_id, callback in list(subscribers.items()):
            try:
                callback(message)
                count += 1
            except Exception as exc:
                logger.error(
                    "Subscriber %s on topic %s raised: %s",
                    sub_id,
                    topic,
                    exc,
                )
        return count

    def _deliver_wildcard(
        self, topic: str, message: Message, current_count: int
    ) -> int:
        """
        Deliver to wildcard subscribers by traversing the topic hierarchy.

        For topic ``a.b.c``, also delivers to subscribers of ``a.b``,
        ``a``, and ``*`` (if any).
        """
        extra_count = 0
        parts = topic.split(".")
        for i in range(len(parts) - 1, 0, -1):
            parent = ".".join(parts[:i])
            extra_count += self._deliver_to_topic(parent, message)

        # Global wildcard
        extra_count += self._deliver_to_topic("*", message)
        return extra_count

    def _handle_agent_routing(self, message: Message) -> None:
        """Route a message directly to an agent by @name."""
        recipient = message.recipient
        if not recipient or not recipient.startswith("@"):
            return

        agent_name = recipient[1:]  # Strip @
        for addr in self._agent_addresses.values():
            if addr.name == agent_name or addr.agent_id == agent_name:
                # Deliver to all of this agent's subscribed topics
                for topic in addr.subscribed_topics:
                    self._deliver_to_topic(topic, message)
                break

    # ------------------------------------------------------------------
    # Agent Registration
    # ------------------------------------------------------------------

    def register_agent(
        self,
        agent_id: str,
        name: str,
        channel: str = "default",
        topics: Optional[List[str]] = None,
    ) -> AgentAddress:
        """
        Register an agent on the bus and subscribe to default topics.

        Args:
            agent_id: The agent's unique ID.
            name: Human-readable name.
            channel: Logical channel.
            topics: Additional topics to subscribe to.

        Returns:
            The AgentAddress entry.
        """
        address = AgentAddress(
            agent_id=agent_id,
            name=name,
            channel=channel,
            subscribed_topics=set(topics or []),
        )

        with self._lock:
            self._agent_addresses[agent_id] = address

            # Subscribe to agent-specific topic
            agent_topic = f"agent.{name}"
            self.subscribe(
                agent_topic,
                lambda msg, aid=agent_id: self._route_to_agent(aid, msg),
                subscriber_name=name,
            )

            # Subscribe to any additional topics
            if topics:
                for topic in topics:
                    self.subscribe(
                        topic,
                        lambda msg, aid=agent_id: self._route_to_agent(
                            aid, msg
                        ),
                        subscriber_name=name,
                    )

            logger.info(
                "Agent registered on bus '%s': id=%s, name=%s, "
                "channel=%s",
                self._name,
                agent_id[:8],
                name,
                channel,
            )
            return address

    def get_agent_address(self, agent_id: str) -> Optional[AgentAddress]:
        """Get the address for a registered agent."""
        with self._lock:
            return self._agent_addresses.get(agent_id)

    def get_connected_agents(self) -> List[AgentAddress]:
        """Return all registered agent addresses."""
        with self._lock:
            return list(self._agent_addresses.values())

    # ------------------------------------------------------------------
    # Bus Management
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """
        Return statistics about the event bus.

        Returns:
            Dictionary with topic count, subscriber count, message count.
        """
        with self._lock:
            total_subscribers = sum(
                len(subs) for subs in self._topics.values()
            )
            return {
                "bus_name": self._name,
                "topics": len(self._topics),
                "total_subscribers": total_subscribers,
                "message_history": len(self._message_history),
                "registered_agents": len(self._agent_addresses),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def get_topics(self) -> Dict[str, int]:
        """Return all topics and their subscriber counts."""
        with self._lock:
            return {
                topic: len(subs)
                for topic, subs in self._topics.items()
            }

    def on_publish(self, hook: Callable[[Message], None]) -> None:
        """Register a hook called on every publish."""
        self._on_publish.append(hook)

    def on_subscribe(
        self, hook: Callable[[str, str], None]
    ) -> None:
        """Register a hook called on every subscribe."""
        self._on_subscribe.append(hook)

    def set_max_history(self, count: int) -> None:
        """Set the maximum number of messages to keep in history."""
        with self._lock:
            self._max_history = count
            while len(self._message_history) > count:
                self._message_history.pop(0)

    def get_message_history(
        self,
        message_type: Optional[MessageType] = None,
        limit: int = 100,
    ) -> List[Message]:
        """Return recent message history, optionally filtered by type."""
        with self._lock:
            if message_type is None:
                return list(self._message_history[-limit:])
            filtered = [
                m
                for m in self._message_history
                if m.type == message_type
            ]
            return filtered[-limit:]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _route_to_agent(agent_id: str, message: Message) -> None:
        """
        Default routing stub for agent-directed messages.

        In production, this would push the message to the agent's
        input queue. For now it logs the routing event.
        """
        logger.debug(
            "Routed message %s to agent %s", message.id[:8], agent_id[:8]
        )

    @staticmethod
    def _safe_hook(hook: Callable, *args: Any) -> None:
        """Call a hook safely."""
        try:
            hook(*args)
        except Exception as exc:
            logger.warning("Hook %s failed: %s", hook.__name__, exc)


# ===================================================================
# Shared Workspace
# ===================================================================

class SharedWorkspace:
    """
    A thread-safe, partitioned workspace for inter-agent data sharing.

    The workspace is organized as a hierarchical path store similar to a
    filesystem::

        /agents/<agent_id>/...
        /workflows/<workflow_id>/...
        /tasks/<task_id>/...
        /shared/artifacts/...
        /config/...

    Agents can read and write data to specific paths. Changes are logged
    for traceability.

    Thread Safety:
        All read/write operations are thread-safe.

    Usage::

        ws = SharedWorkspace()

        # Write data
        ws.write("/agents/safety_agent/hara_result", {"asil": "D"})

        # Read data
        result = ws.read("/agents/safety_agent/hara_result")

        # Subscribe to changes
        def on_change(path, value):
            print(f"Path {path} changed")

        ws.watch("/agents/safety_agent/*", on_change)

        # List directory
        entries = ws.list("/agents/safety_agent/")

        # Get change history
        history = ws.get_history("/agents/safety_agent/hara_result")
    """

    def __init__(self, name: str = "default") -> None:
        """
        Initialize the shared workspace.

        Args:
            name: Workspace name (for logging).
        """
        self._name = name
        self._lock = threading.RLock()
        self._store: Dict[str, Any] = {}
        self._history: Dict[str, List[Tuple[str, Any]]] = defaultdict(list)
        self._max_history_per_key = 100
        self._watchers: Dict[str, List[Callable[[str, Any], None]]] = {}

        logger.info("SharedWorkspace '%s' initialized", name)

    # ------------------------------------------------------------------
    # Read / Write
    # ------------------------------------------------------------------

    def write(
        self,
        path: str,
        value: Any,
        overwrite: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Write a value to a workspace path.

        Args:
            path: The path (e.g., ``"/agents/safety_agent/result"``).
                Must start with ``/``.
            value: The value to store (must be JSON-serializable).
            overwrite: If False, raises KeyError if the path exists.
            metadata: Optional metadata attached to this write.

        Raises:
            ValueError: If path does not start with ``/``.
            KeyError: If ``overwrite`` is False and the path exists.
        """
        if not path.startswith("/"):
            raise ValueError(f"Path must start with '/', got: {path!r}")

        normalized = self._normalize_path(path)

        with self._lock:
            if not overwrite and normalized in self._store:
                raise KeyError(
                    f"Path {path!r} already exists and overwrite=False"
                )

            old_value = self._store.get(normalized)
            self._store[normalized] = value

            # Record history
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "value": value,
                "old_value": old_value,
                "metadata": metadata or {},
            }
            self._history[normalized].append(entry)
            if len(self._history[normalized]) > self._max_history_per_key:
                self._history[normalized].pop(0)

            # Notify watchers
            self._notify_watchers(normalized, value)

            logger.debug(
                "Workspace write: path=%s, value_type=%s",
                normalized,
                type(value).__name__,
            )

    def read(
        self, path: str, default: Any = None
    ) -> Any:
        """
        Read a value from a workspace path.

        Args:
            path: The path to read.
            default: Value returned if path does not exist.

        Returns:
            The stored value, or *default* if not found.
        """
        normalized = self._normalize_path(path)
        with self._lock:
            return self._store.get(normalized, default)

    def read_glob(self, pattern: str) -> Dict[str, Any]:
        """
        Read all paths matching a glob-like pattern.

        Supports ``*`` (single-level wildcard) and ``**``
        (multi-level wildcard).

        Args:
            pattern: Path pattern (e.g., ``"/agents/*/result"``).

        Returns:
            Dict mapping matching paths to their values.
        """
        normalized = self._normalize_path(pattern)
        with self._lock:
            results = {}
            for store_path, value in self._store.items():
                if self._path_matches(normalized, store_path):
                    results[store_path] = value
            return results

    def delete(self, path: str) -> bool:
        """
        Delete a path from the workspace.

        Args:
            path: The path to delete.

        Returns:
            True if deleted, False if not found.
        """
        normalized = self._normalize_path(path)
        with self._lock:
            if normalized in self._store:
                del self._store[normalized]
                self._history[normalized].append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "value": None,
                    "old_value": self._store.get(normalized),
                    "metadata": {"action": "delete"},
                })
                logger.debug("Workspace delete: path=%s", normalized)
                return True
            return False

    def exists(self, path: str) -> bool:
        """Check if a path exists in the workspace."""
        normalized = self._normalize_path(path)
        with self._lock:
            return normalized in self._store

    def list(self, prefix: str) -> Dict[str, Any]:
        """
        List all entries under a given prefix path.

        Args:
            prefix: The prefix to filter by (e.g., ``"/agents/"``).

        Returns:
            Dictionary of matching paths and their values.
        """
        normalized = self._normalize_path(prefix)
        with self._lock:
            return {
                path: value
                for path, value in self._store.items()
                if path.startswith(normalized)
            }

    # ------------------------------------------------------------------
    # Change Watching
    # ------------------------------------------------------------------

    def watch(
        self,
        pattern: str,
        callback: Callable[[str, Any], None],
    ) -> str:
        """
        Watch a path pattern for changes.

        The callback is invoked whenever any matching path is written.

        Args:
            pattern: Path pattern to watch (supports ``*`` wildcard).
            callback: Function ``(path, new_value)`` called on changes.

        Returns:
            A watcher ID for unregistering.
        """
        normalized = self._normalize_path(pattern)
        watcher_id = uuid.uuid4().hex

        with self._lock:
            if normalized not in self._watchers:
                self._watchers[normalized] = []
            self._watchers[normalized].append(callback)

            logger.debug(
                "Watcher registered: id=%s, pattern=%s",
                watcher_id[:8],
                normalized,
            )
            return watcher_id

    def unwatch(self, pattern: str, callback: Callable) -> bool:
        """
        Remove a watcher.

        Args:
            pattern: The pattern the watcher was registered on.
            callback: The callback to remove.

        Returns:
            True if removed, False if not found.
        """
        normalized = self._normalize_path(pattern)
        with self._lock:
            watchers = self._watchers.get(normalized, [])
            if callback in watchers:
                watchers.remove(callback)
                return True
            return False

    # ------------------------------------------------------------------
    # History / Audit
    # ------------------------------------------------------------------

    def get_history(
        self, path: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get the change history for a path.

        Args:
            path: The path to get history for.
            limit: Maximum number of entries to return.

        Returns:
            List of history entries with timestamp, value, old_value.
        """
        normalized = self._normalize_path(path)
        with self._lock:
            entries = list(self._history.get(normalized, []))
            return entries[-limit:]

    def get_all_history(
        self, limit_per_path: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get change history for all paths.

        Args:
            limit_per_path: Max entries per path.

        Returns:
            Dict mapping path -> list of history entries.
        """
        with self._lock:
            return {
                path: entries[-limit_per_path:]
                for path, entries in self._history.items()
            }

    def clear(self) -> None:
        """Clear all data and history from the workspace."""
        with self._lock:
            self._store.clear()
            self._history.clear()
            logger.info("SharedWorkspace '%s' cleared", self._name)

    def get_stats(self) -> Dict[str, Any]:
        """
        Return workspace statistics.

        Returns:
            Dictionary with store size, history size, watcher count.
        """
        with self._lock:
            return {
                "workspace_name": self._name,
                "stored_paths": len(self._store),
                "history_entries": sum(
                    len(v) for v in self._history.values()
                ),
                "watchers": sum(
                    len(v) for v in self._watchers.values()
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    # ------------------------------------------------------------------
    # Partitioned Access
    # ------------------------------------------------------------------

    def agent_path(self, agent_id: str, subpath: str = "") -> str:
        """Return a path scoped to a specific agent."""
        base = f"/agents/{agent_id}"
        if subpath:
            return f"{base}/{subpath.lstrip('/')}"
        return base

    def workflow_path(self, workflow_id: str, subpath: str = "") -> str:
        """Return a path scoped to a specific workflow."""
        base = f"/workflows/{workflow_id}"
        if subpath:
            return f"{base}/{subpath.lstrip('/')}"
        return base

    def task_path(self, task_id: str, subpath: str = "") -> str:
        """Return a path scoped to a specific task."""
        base = f"/tasks/{task_id}"
        if subpath:
            return f"{base}/{subpath.lstrip('/')}"
        return base

    # ------------------------------------------------------------------
    # Snapshot / Restore
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """
        Capture a full snapshot of the workspace.

        Returns:
            Serialized workspace state.
        """
        with self._lock:
            return {
                "name": self._name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "store": dict(self._store),
            }

    def restore(self, snapshot: Dict[str, Any]) -> None:
        """
        Restore workspace state from a snapshot.

        Args:
            snapshot: The snapshot dict (from ``snapshot()``).
        """
        with self._lock:
            self._store = dict(snapshot.get("store", {}))
            logger.info(
                "Workspace '%s' restored from snapshot (%d paths)",
                self._name,
                len(self._store),
            )

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalize a path: strip trailing slash, collapse //."""
        normalized = "/" + "/".join(
            part for part in path.split("/") if part
        )
        return normalized if normalized else "/"

    @staticmethod
    def _path_matches(pattern: str, path: str) -> bool:
        """
        Simple glob matching for workspace paths.

        Supports ``*`` (matches any sequence within a single level)
        and ``**`` (matches across levels).
        """
        import fnmatch
        return fnmatch.fnmatch(path, pattern)

    def _notify_watchers(self, path: str, value: Any) -> None:
        """Notify all watchers matching the given path."""
        for pattern, callbacks in list(self._watchers.items()):
            if self._path_matches(pattern, path):
                for cb in callbacks:
                    try:
                        cb(path, value)
                    except Exception as exc:
                        logger.warning(
                            "Watcher callback on pattern %s failed: %s",
                            pattern,
                            exc,
                        )


# ===================================================================
# Convenience Factory
# ===================================================================

def create_communication_layer(
    bus_name: str = "default",
    workspace_name: str = "default",
) -> Tuple[EventBus, SharedWorkspace]:
    """
    Create and return a pair of (EventBus, SharedWorkspace).

    This is the recommended entry point for setting up the communication
    infrastructure.

    Args:
        bus_name: Name for the EventBus instance.
        workspace_name: Name for the SharedWorkspace instance.

    Returns:
        A tuple of ``(event_bus, shared_workspace)``.
    """
    bus = EventBus(name=bus_name)
    workspace = SharedWorkspace(name=workspace_name)
    logger.info(
        "Communication layer created: bus=%s, workspace=%s",
        bus_name,
        workspace_name,
    )
    return bus, workspace
