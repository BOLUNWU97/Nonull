"""
Nonull — Gateway Channel
=================================
统一消息路由网关 | Unified Message Routing Gateway

A multi-channel gateway inspired by OpenClaw's gateway architecture. Provides
unified message routing, session key management, user authorization,
message queuing, and a platform adapter interface for extensibility.

受 OpenClaw 网关架构启发的多通道网关，提供统一消息路由、会话密钥管理、
用户授权、消息队列和可扩展的平台适配器接口。

The GatewayChannel sits between platform adapters and the agent core:
    [Platform Adapters] → GatewayChannel → [Agent Core]
    [Agent Core] → GatewayChannel → [Platform Adapters]

Key features:
    - Unified message routing across all connected channels
    - Session key generation and management
    - User allowlist/blocklist authorization
    - Message queuing with priority support
    - Platform adapter registration and discovery
    - Message broadcasting to multiple channels
    - Metrics and monitoring for all routes
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from channels.base import (
    BaseChannel,
    ChannelAuthError,
    ChannelError,
    ChannelRateLimitError,
    ChannelState,
    Message,
    MessagePriority,
    MessageRole,
    RetryHandler,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gateway-specific Data Types
# ---------------------------------------------------------------------------


@dataclass
class Session:
    """
    Represents an active user session across the gateway.
    表示跨网关的活跃用户会话。

    Attributes:
        session_id: Unique session identifier
        user_id: Platform-specific user identifier
        platform: Platform name (e.g., "telegram", "feishu")
        channel_name: Name of the channel handling this session
        created_at: Session creation timestamp
        last_active_at: Last activity timestamp
        metadata: Arbitrary session metadata
        conversation_id: Current conversation ID
        is_active: Whether the session is still active
    """
    session_id: str
    user_id: str
    platform: str
    channel_name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    conversation_id: str = ""
    is_active: bool = True

    def touch(self) -> None:
        """Update the last active timestamp.
        更新最后活跃时间戳。"""
        self.last_active_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "platform": self.platform,
            "channel_name": self.channel_name,
            "created_at": self.created_at.isoformat(),
            "last_active_at": self.last_active_at.isoformat(),
            "conversation_id": self.conversation_id,
            "is_active": self.is_active,
            "metadata": self.metadata,
        }


@dataclass
class QueuedMessage:
    """
    A message waiting in the gateway's outbound queue.
    等待在网关出站队列中的消息。

    Attributes:
        message: The standardized message
        priority: Delivery priority
        enqueued_at: When the message was queued
        retry_count: Number of delivery attempts
        max_retries: Maximum delivery attempts before dropping
    """
    message: Message
    priority: MessagePriority
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = 0
    max_retries: int = 3


class RoutingStrategy(Enum):
    """Message routing strategies for the gateway.
    网关的消息路由策略。"""
    DIRECT = "direct"              # Route to a specific channel
    BROADCAST = "broadcast"        # Route to all channels
    ROUND_ROBIN = "round_robin"    # Rotate through available channels
    LEAST_BUSY = "least_busy"      # Route to the least busy channel
    PRIORITY = "priority"          # Route based on channel priority


class GatewayState(Enum):
    """Gateway lifecycle states.
    网关生命周期状态。"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Message Queue
# ---------------------------------------------------------------------------


class MessageQueue:
    """
    Priority-based message queue for outbound gateway messages.
    基于优先级的网关出站消息队列。

    Supports multiple priority levels (LOW, NORMAL, HIGH, CRITICAL).
    Messages are dequeued highest-priority-first.
    """

    def __init__(self) -> None:
        self._queues: Dict[MessagePriority, asyncio.Queue] = {
            p: asyncio.Queue() for p in MessagePriority
        }
        self._total: int = 0

    async def put(self, message: QueuedMessage) -> None:
        """Enqueue a message at its priority level.
        将消息按其优先级入队。"""
        await self._queues[message.priority].put(message)
        self._total += 1

    async def get(self) -> Optional[QueuedMessage]:
        """
        Dequeue the highest-priority available message.
        出队最高优先级的可用消息。

        Iterates from CRITICAL down to LOW, returning the first available message.
        """
        for priority in (MessagePriority.CRITICAL, MessagePriority.HIGH,
                         MessagePriority.NORMAL, MessagePriority.LOW):
            queue = self._queues[priority]
            if not queue.empty():
                msg = queue.get_nowait()
                self._total -= 1
                return msg
        return None

    async def get_with_wait(self, timeout: float = 1.0) -> Optional[QueuedMessage]:
        """
        Wait for a message from any priority level.
        等待任何优先级的消息。

        Periodically polls all priority queues. Returns None if timeout expires.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            msg = await self.get()
            if msg:
                return msg
            await asyncio.sleep(0.05)
        return None

    @property
    def size(self) -> int:
        """Total messages across all priority levels.
        所有优先级级别的消息总数。"""
        return sum(q.qsize() for q in self._queues.values())

    @property
    def is_empty(self) -> bool:
        """Check if all queues are empty.
        检查所有队列是否为空。"""
        return all(q.empty() for q in self._queues.values())


# ---------------------------------------------------------------------------
# Gateway Channel
# ---------------------------------------------------------------------------


class GatewayChannel(BaseChannel):
    """
    Unified message routing gateway for Nonull.
    面向 Nonull 的统一消息路由网关。

    The GatewayChannel manages connections to multiple platform adapters,
    handles session key management, user authorization, priority-based
    message queuing, and provides a unified interface for the agent core
    to send and receive messages across all platforms.

    GatewayChannel 管理多个平台适配器的连接、会话密钥管理、用户授权、
    基于优先级的消息队列，为智能体核心提供跨所有平台的统一收发接口。

    Args:
        name: Gateway name (default "gateway")
        config: Configuration dictionary
        allowlist: Optional set of allowed user IDs
        blocklist: Optional set of blocked user IDs
        queue_max_retries: Max delivery attempts for queued messages
        session_timeout: Session idle timeout in seconds (0 = no timeout)
    """

    def __init__(
        self,
        name: str = "gateway",
        config: Optional[Dict[str, Any]] = None,
        allowlist: Optional[Set[str]] = None,
        blocklist: Optional[Set[str]] = None,
        queue_max_retries: int = 3,
        session_timeout: int = 3600,
    ) -> None:
        super().__init__(
            name=name,
            config=config or {},
            max_rate=0,  # Gateway manages rate per-channel
        )
        self._gateway_state: GatewayState = GatewayState.STOPPED
        self._channels: Dict[str, BaseChannel] = {}
        self._sessions: Dict[str, Session] = {}
        self._session_by_user: Dict[str, str] = {}  # user_id -> session_id
        self._allowlist: Set[str] = set(allowlist or [])
        self._blocklist: Set[str] = set(blocklist or [])
        self._queue = MessageQueue()
        self._queue_max_retries = queue_max_retries
        self._session_timeout = session_timeout
        self._queue_worker_task: Optional[asyncio.Task] = None
        self._session_cleanup_task: Optional[asyncio.Task] = None
        self._route_table: Dict[str, str] = {}  # channel_name -> platform
        self._platform_to_channel: Dict[str, str] = {}  # platform -> channel_name
        self._inbound_handlers: List[Callable[[Message], Any]] = []
        self._gateway_metrics: Dict[str, Any] = {
            "messages_routed": 0,
            "messages_queued": 0,
            "messages_dropped": 0,
            "sessions_created": 0,
            "sessions_expired": 0,
            "auth_failures": 0,
        }

        logger.info("GatewayChannel '%s' initialized", self.name)

    # ------------------------------------------------------------------
    # Connection Lifecycle
    # ------------------------------------------------------------------

    async def _on_connect(self) -> bool:
        """
        Start the gateway: register channels, start workers.
        启动网关：注册通道、启动工作线程。
        """
        self._gateway_state = GatewayState.STARTING

        # Connect all registered channels
        connect_tasks = []
        for ch_name, channel in self._channels.items():
            if channel.state not in (ChannelState.CONNECTED, ChannelState.CONNECTING):
                connect_tasks.append(self._connect_channel(ch_name))

        if connect_tasks:
            results = await asyncio.gather(*connect_tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error("Channel connect error: %s", result)

        # Start background workers
        self._queue_worker_task = asyncio.create_task(self._queue_worker())
        self._session_cleanup_task = asyncio.create_task(self._session_cleanup_loop())

        self._gateway_state = GatewayState.RUNNING
        logger.info("GatewayChannel '%s' started with %d channel(s)", self.name, len(self._channels))
        return True

    async def _on_disconnect(self) -> None:
        """
        Stop the gateway: drain queues, disconnect channels.
        停止网关：排空队列、断开通道。
        """
        self._gateway_state = GatewayState.STOPPING

        # Stop background workers
        if self._queue_worker_task:
            self._queue_worker_task.cancel()
            self._queue_worker_task = None
        if self._session_cleanup_task:
            self._session_cleanup_task.cancel()
            self._session_cleanup_task = None

        # Disconnect all channels
        disconnect_tasks = []
        for ch_name, channel in self._channels.items():
            if channel.state == ChannelState.CONNECTED:
                disconnect_tasks.append(channel.disconnect())

        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)

        self._channels.clear()
        self._sessions.clear()
        self._session_by_user.clear()
        self._gateway_state = GatewayState.STOPPED
        logger.info("GatewayChannel '%s' stopped", self.name)

    async def _send_message(self, message: Message) -> None:
        """
        Route a message through the gateway to the appropriate channel(s).
        通过网关将消息路由到适当的通道。

        Determines the target channel based on the message's channel field
        or metadata. Falls back to the platform mapping.
        """
        target_channel = self._resolve_target_channel(message)
        if target_channel:
            await target_channel.send(message)
            self._gateway_metrics["messages_routed"] += 1
        else:
            logger.warning("No channel found for message: %s", message)

    async def _receive_message(self) -> Optional[Message]:
        """
        Receive is not directly used by the gateway; it uses channel adapters.
        网关不直接使用接收方法；而是通过通道适配器接收消息。

        Returns None (inbound messages come through channel message handlers).
        """
        return None

    # ------------------------------------------------------------------
    # Channel Registration
    # ------------------------------------------------------------------

    def register_channel(self, name: str, channel: BaseChannel) -> None:
        """
        Register a channel with the gateway.
        向网关注册一个通道。

        Args:
            name: Unique name for the channel
            channel: Channel instance

        Raises:
            ValueError: If a channel with the same name is already registered
        """
        if name in self._channels:
            raise ValueError(f"Channel '{name}' is already registered")

        self._channels[name] = channel
        self._route_table[name] = channel.name

        # Register an inbound message handler on the channel
        channel.on_message(self._on_channel_message)

        logger.info("Channel '%s' registered with gateway '%s'", name, self.name)

        # Auto-connect if gateway is already running
        if self._gateway_state == GatewayState.RUNNING:
            asyncio.create_task(self._connect_channel(name))

    def unregister_channel(self, name: str) -> None:
        """
        Unregister a channel from the gateway.
        从网关注销一个通道。

        Args:
            name: Name of the channel to unregister
        """
        channel = self._channels.pop(name, None)
        if channel:
            self._route_table.pop(name, None)
            # Remove reverse mapping
            for platform, ch_name in list(self._platform_to_channel.items()):
                if ch_name == name:
                    self._platform_to_channel.pop(platform, None)
            asyncio.create_task(channel.disconnect())
            logger.info("Channel '%s' unregistered from gateway '%s'", name, self.name)

    def get_channel(self, name: str) -> Optional[BaseChannel]:
        """Get a registered channel by name.
        根据名称获取已注册的通道。"""
        return self._channels.get(name)

    def list_channels(self) -> Dict[str, str]:
        """List all registered channels and their states.
        列出所有已注册的通道及其状态。"""
        return {
            name: ch.state.value
            for name, ch in self._channels.items()
        }

    async def _connect_channel(self, name: str) -> None:
        """Connect a registered channel.
        连接一个已注册的通道。"""
        channel = self._channels.get(name)
        if channel and channel.state != ChannelState.CONNECTED:
            try:
                await channel.connect()
                logger.info("Channel '%s' connected via gateway", name)
            except Exception as e:
                logger.error("Failed to connect channel '%s': %s", name, e)

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------

    def create_session(
        self,
        user_id: str,
        platform: str,
        channel_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Session:
        """
        Create a new session for a user.
        为用户创建新会话。

        Args:
            user_id: Platform-specific user identifier
            platform: Platform name
            channel_name: Channel handling the session
            metadata: Optional session metadata

        Returns:
            The newly created Session
        """
        session_id = self._generate_session_id(user_id, platform)
        session = Session(
            session_id=session_id,
            user_id=user_id,
            platform=platform,
            channel_name=channel_name,
            metadata=metadata or {},
        )
        self._sessions[session_id] = session
        self._session_by_user[user_id] = session_id
        self._gateway_metrics["sessions_created"] += 1
        logger.debug("Session created: %s (user=%s, platform=%s)", session_id, user_id, platform)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by its ID.
        根据 ID 获取会话。"""
        return self._sessions.get(session_id)

    def get_session_by_user(self, user_id: str) -> Optional[Session]:
        """Get the active session for a user.
        获取用户的活跃会话。"""
        session_id = self._session_by_user.get(user_id)
        if session_id:
            return self._sessions.get(session_id)
        return None

    def end_session(self, session_id: str) -> None:
        """
        End a session and clean up resources.
        结束会话并清理资源。
        """
        session = self._sessions.pop(session_id, None)
        if session:
            session.is_active = False
            self._session_by_user.pop(session.user_id, None)
            logger.debug("Session ended: %s", session_id)

    async def _session_cleanup_loop(self) -> None:
        """Background task: periodically clean up expired sessions.
        后台任务：定期清理过期的会话。"""
        if self._session_timeout <= 0:
            return

        while self._gateway_state == GatewayState.RUNNING:
            try:
                now = datetime.now(timezone.utc)
                expired = []
                for sid, session in self._sessions.items():
                    elapsed = (now - session.last_active_at).total_seconds()
                    if elapsed > self._session_timeout:
                        expired.append(sid)

                for sid in expired:
                    self.end_session(sid)
                    self._gateway_metrics["sessions_expired"] += 1

                if expired:
                    logger.info("Cleaned up %d expired session(s)", len(expired))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Session cleanup error: %s", e)

            await asyncio.sleep(60)  # Check every 60 seconds

    def _generate_session_id(self, user_id: str, platform: str) -> str:
        """Generate a unique session ID.
        生成唯一的会话 ID。"""
        raw = f"{user_id}:{platform}:{time.time_ns()}:{uuid.uuid4()}"
        return f"session_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

    # ------------------------------------------------------------------
    # Message Routing
    # ------------------------------------------------------------------

    async def route_message(self, message: Message) -> None:
        """
        Route an inbound or outbound message to the appropriate target(s).
        将入站或出站消息路由到适当的目标。

        This is the primary API used by the agent core to send messages.
        This is also called by channel adapters when they receive inbound messages.

        这是智能体核心发送消息的主要 API。
        通道适配器收到入站消息时也会调用此方法。

        Args:
            message: The standardized message to route
        """
        # Authorization check
        if message.user_id:
            if not self._is_user_authorized(message.user_id):
                self._gateway_metrics["auth_failures"] += 1
                raise ChannelAuthError(f"User '{message.user_id}' is not authorized")

        # Session management
        session = self.get_session_by_user(message.user_id) if message.user_id else None
        if not session and message.user_id:
            session = self.create_session(
                user_id=message.user_id,
                platform=message.platform or message.channel,
                channel_name=message.channel,
            )
        if session:
            session.touch()

        # Route based on target
        if message.channel and message.channel in self._channels:
            # Direct routing to a specific channel
            await self._channels[message.channel].send(message)
            self._gateway_metrics["messages_routed"] += 1
        else:
            # Queue for delivery (background worker handles routing)
            queued = QueuedMessage(
                message=message,
                priority=message.priority,
                max_retries=self._queue_max_retries,
            )
            await self._queue.put(queued)
            self._gateway_metrics["messages_queued"] += 1

    async def broadcast(self, message: Message) -> int:
        """
        Broadcast a message to all connected channels.
        向所有已连接的通道广播消息。

        Args:
            message: Message to broadcast

        Returns:
            Number of channels the message was sent to
        """
        count = 0
        for ch_name, channel in self._channels.items():
            if channel.state == ChannelState.CONNECTED:
                try:
                    msg = Message(
                        id=f"broadcast_{uuid.uuid4().hex[:8]}",
                        channel=ch_name,
                        role=message.role,
                        content=message.content,
                        metadata=message.metadata,
                    )
                    await channel.send(msg)
                    count += 1
                except Exception as e:
                    logger.error("Broadcast to '%s' failed: %s", ch_name, e)
        self._gateway_metrics["messages_routed"] += count
        return count

    async def _queue_worker(self) -> None:
        """Background worker: dequeue and deliver messages.
        后台工作者：从队列取出并投递消息。"""
        logger.info("Queue worker started for gateway '%s'", self.name)

        while self._gateway_state == GatewayState.RUNNING:
            try:
                queued = await self._queue.get_with_wait(timeout=1.0)
                if queued is None:
                    continue

                target_channel = self._resolve_target_channel(queued.message)
                if target_channel and target_channel.state == ChannelState.CONNECTED:
                    try:
                        await target_channel.send(queued.message)
                    except Exception as e:
                        logger.warning("Delivery failed (attempt %d/%d): %s",
                                       queued.retry_count + 1, queued.max_retries, e)
                        if queued.retry_count < queued.max_retries:
                            queued.retry_count += 1
                            await self._queue.put(queued)
                        else:
                            self._gateway_metrics["messages_dropped"] += 1
                            logger.error("Message dropped after %d retries", queued.max_retries)
                else:
                    logger.warning("Target channel not available for message, dropping")
                    self._gateway_metrics["messages_dropped"] += 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Queue worker error: %s", e)

        logger.info("Queue worker stopped for gateway '%s'", self.name)

    def _resolve_target_channel(self, message: Message) -> Optional[BaseChannel]:
        """
        Determine which channel should deliver this message.
        确定哪个通道应投递此消息。

        Resolution order:
            1. Direct channel name match
            2. Platform-to-channel mapping
            3. First available connected channel
        """
        # Direct match
        if message.channel in self._channels:
            return self._channels[message.channel]

        # Platform mapping
        if message.platform:
            ch_name = self._platform_to_channel.get(message.platform)
            if ch_name and ch_name in self._channels:
                return self._channels[ch_name]

        # Fallback: first connected channel
        for channel in self._channels.values():
            if channel.state == ChannelState.CONNECTED:
                return channel

        return None

    # ------------------------------------------------------------------
    # Inbound Message Handling
    # ------------------------------------------------------------------

    async def _on_channel_message(self, message: Message) -> None:
        """
        Handle an inbound message from a channel adapter.
        处理来自通道适配器的入站消息。

        Performs authorization, session management, and dispatches
        to registered inbound handlers (typically the agent core).
        """
        # Authorization
        if message.user_id and not self._is_user_authorized(message.user_id):
            self._gateway_metrics["auth_failures"] += 1
            logger.warning("Unauthorized user '%s' on channel '%s'", message.user_id, message.channel)
            return

        # Session management
        session = self.get_session_by_user(message.user_id) if message.user_id else None
        if not session and message.user_id:
            session = self.create_session(
                user_id=message.user_id,
                platform=message.platform or message.channel,
                channel_name=message.channel,
            )
        if session:
            session.touch()
            message.session_id = session.session_id

        # Dispatch to handlers
        for handler in self._inbound_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error("Inbound handler error: %s", e)

    def on_inbound_message(self, handler: Callable[[Message], Any]) -> Callable:
        """
        Register a handler for all inbound messages.
        注册入站消息处理程序。

        This is the primary way for the agent core to receive messages.
        Can be used as a decorator.

        这是智能体核心接收消息的主要方式。可以用作装饰器。

        Usage:
            @gateway.on_inbound_message
            async def handle(msg: Message):
                await agent.process(msg)
        """
        self._inbound_handlers.append(handler)
        return handler

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    def set_allowlist(self, user_ids: Set[str]) -> None:
        """Set the user allowlist (replaces existing).
        设置用户白名单 (替换现有)。"""
        self._allowlist = set(user_ids)
        logger.info("Allowlist updated: %d user(s)", len(self._allowlist))

    def set_blocklist(self, user_ids: Set[str]) -> None:
        """Set the user blocklist (replaces existing).
        设置用户黑名单 (替换现有)。"""
        self._blocklist = set(user_ids)
        logger.info("Blocklist updated: %d user(s)", len(self._blocklist))

    def _is_user_authorized(self, user_id: str) -> bool:
        """
        Check if a user is authorized to use the gateway.
        检查用户是否有权使用网关。

        Blocklist takes precedence over allowlist.
        If allowlist is empty, all users except blocked are allowed.
        """
        if user_id in self._blocklist:
            return False
        if self._allowlist:
            return user_id in self._allowlist
        return True

    # ------------------------------------------------------------------
    # Platform-to-Channel Mapping
    # ------------------------------------------------------------------

    def map_platform(self, platform: str, channel_name: str) -> None:
        """
        Map a platform name to a registered channel.
        将平台名称映射到已注册的通道。

        This allows routing by platform name (e.g., "telegram", "feishu").
        """
        if channel_name not in self._channels:
            raise ValueError(f"Channel '{channel_name}' is not registered")
        self._platform_to_channel[platform] = channel_name
        logger.info("Platform '%s' mapped to channel '%s'", platform, channel_name)

    def get_platform_channel(self, platform: str) -> Optional[BaseChannel]:
        """Get the channel mapped to a platform.
        获取映射到平台的通道。"""
        ch_name = self._platform_to_channel.get(platform)
        if ch_name:
            return self._channels.get(ch_name)
        return None

    # ------------------------------------------------------------------
    # Queue Management
    # ------------------------------------------------------------------

    @property
    def queue_size(self) -> int:
        """Current number of messages in the outbound queue.
        出站队列中的当前消息数。"""
        return self._queue.size

    async def drain_queue(self) -> int:
        """
        Force-drain all pending messages from the queue.
        强制排空队列中所有待处理的消息。

        Returns:
            Number of messages drained
        """
        count = 0
        while not self._queue.is_empty:
            queued = await self._queue.get()
            if queued:
                target = self._resolve_target_channel(queued.message)
                if target and target.state == ChannelState.CONNECTED:
                    try:
                        await target.send(queued.message)
                        count += 1
                    except Exception:
                        pass
        return count

    # ------------------------------------------------------------------
    # Metrics & Health
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        """Get gateway metrics.
        获取网关指标。"""
        metrics = dict(self._gateway_metrics)
        metrics["channels"] = len(self._channels)
        metrics["active_sessions"] = len(self._sessions)
        metrics["queue_size"] = self.queue_size
        metrics["gateway_state"] = self._gateway_state.value
        metrics["channel_states"] = {
            name: ch.state.value for name, ch in self._channels.items()
        }
        return metrics

    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the gateway.
        执行网关健康检查。"""
        connected = sum(
            1 for ch in self._channels.values()
            if ch.state == ChannelState.CONNECTED
        )
        return {
            "name": self.name,
            "gateway_state": self._gateway_state.value,
            "channels_total": len(self._channels),
            "channels_connected": connected,
            "active_sessions": len(self._sessions),
            "queue_size": self.queue_size,
            "healthy": (self._gateway_state == GatewayState.RUNNING
                        and connected > 0),
        }

    def __repr__(self) -> str:
        return (
            f"<GatewayChannel name='{self.name}' "
            f"state={self._gateway_state.value} "
            f"channels={len(self._channels)}>"
        )
