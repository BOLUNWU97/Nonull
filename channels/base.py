"""
Nonull — Base Channel
==============================
通道基类与消息标准化 | Channel Base Class and Message Standardization

Defines the abstract interface that every channel must implement, along with
standardized message formats, connection lifecycle management, authentication
& authorization, rate limiting, and retry/error handling.

所有通道的抽象基类，统一消息格式、连接生命周期、认证授权、限流与错误重试。

Usage:
    class MyChannel(BaseChannel):
        async def _on_connect(self) -> bool:
            # platform-specific connection logic
            return True

        async def _on_disconnect(self) -> None:
            # cleanup

        async def _send_message(self, message: Message) -> None:
            # deliver message to platform

        async def _receive_message(self) -> Message | None:
            # poll or read incoming messages
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ChannelError(Exception):
    """Base exception for all channel-related errors.
    所有通道相关异常的基类。"""


class ChannelAuthError(ChannelError):
    """Authentication or authorization failure.
    认证或授权失败。"""


class ChannelConnectionError(ChannelError):
    """Connection-level failure (timeout, reset, etc.).
    连接级别的失败 (超时、重置等)。"""


class ChannelRateLimitError(ChannelError):
    """Rate limit exceeded.
    超出速率限制。"""


class ChannelTimeoutError(ChannelError):
    """Operation timed out.
    操作超时。"""


# ---------------------------------------------------------------------------
# Enums & Data Classes
# ---------------------------------------------------------------------------


class ChannelState(enum.Enum):
    """Channel connection lifecycle states.
    通道连接生命周期状态。"""
    INITIALIZED = "initialized"        # Created but not connected
    CONNECTING = "connecting"          # Attempting to connect
    CONNECTED = "connected"            # Successfully connected
    DISCONNECTING = "disconnecting"    # Shutting down
    DISCONNECTED = "disconnected"      # Fully disconnected
    ERROR = "error"                    # Unrecoverable error state
    CLOSED = "closed"                  # Permanently closed


class MessageRole(enum.Enum):
    """Role of the message sender.
    消息发送者角色。"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    AGENT = "agent"


class MessagePriority(enum.Enum):
    """Message priority levels for queuing.
    消息优先级 (用于消息排队)。"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Message:
    """
    Standardized message format used across all channels.
    所有通道统一的标准化消息格式。

    Attributes:
        id: Unique message identifier (UUID string)
        channel: Source channel name (e.g., "cli", "telegram")
        role: Sender role
        content: Message text content
        metadata: Arbitrary platform-specific metadata
        platform: Platform name (e.g., "telegram", "feishu")
        platform_message_id: Original message ID on the platform
        user_id: Platform-specific user identifier
        session_id: Group messages into sessions
        conversation_id: Thread/conversation identifier
        priority: Message priority for queuing
        created_at: Timestamp when message was created
        reply_to: Optional ID of message being replied to
        attachments: List of attachment URIs or file paths
        tool_calls: Tool calls if this is a tool-use message
        tool_results: Tool results if this is a tool-response message
    """
    id: str
    channel: str
    role: MessageRole
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    platform: str = ""
    platform_message_id: str = ""
    user_id: str = ""
    session_id: str = ""
    conversation_id: str = ""
    priority: MessagePriority = MessagePriority.NORMAL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reply_to: Optional[str] = None
    attachments: List[str] = field(default_factory=list)
    tool_calls: Optional[Dict[str, Any]] = None
    tool_results: Optional[Dict[str, Any]] = None

    def is_command(self) -> bool:
        """Check if message content starts with '/' (slash command).
        检查消息内容是否以 '/' 开头 (斜杠命令)。"""
        return self.content.startswith("/") if self.content else False

    def is_mention(self, bot_name: str) -> bool:
        """Check if the message mentions the bot.
        检查消息是否提到了机器人。"""
        return bot_name.lower() in self.content.lower() if self.content else False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary.
        序列化为 JSON 兼容的字典。"""
        return {
            "id": self.id,
            "channel": self.channel,
            "role": self.role.value,
            "content": self.content,
            "metadata": self.metadata,
            "platform": self.platform,
            "platform_message_id": self.platform_message_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "reply_to": self.reply_to,
            "attachments": self.attachments,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Deserialize from a dictionary.
        从字典反序列化。"""
        data = data.copy()
        data["role"] = MessageRole(data["role"])
        data["priority"] = MessagePriority(data.get("priority", 1))
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)

    def __str__(self) -> str:
        return f"[{self.channel}:{self.role.value}] {self.content[:80]}"


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """
    Token-bucket rate limiter for channel message throttling.
    基于令牌桶的通道消息限流器。

    Args:
        max_rate: Maximum number of messages per interval
        interval: Time window in seconds (default 1.0)
    """

    def __init__(self, max_rate: int, interval: float = 1.0) -> None:
        self.max_rate = max_rate
        self.interval = interval
        self._tokens: float = float(max_rate)
        self._last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens from the bucket. Blocks until tokens are available.
        从桶中获取令牌，阻塞直到令牌可用。

        Returns:
            Wait time in seconds (0 if no waiting needed)
        """
        async with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0
            # Not enough tokens; calculate wait time
            deficit = tokens - self._tokens
            wait_time = (deficit / self.max_rate) * self.interval
            self._tokens = 0.0
            return wait_time

    def _refill(self) -> None:
        """Refill tokens based on elapsed time.
        根据经过的时间补充令牌。"""
        elapsed = time.monotonic() - self._last_refill
        self._tokens = min(float(self.max_rate), self._tokens + elapsed * self.max_rate / self.interval)
        self._last_refill = time.monotonic()

    @property
    def is_throttled(self) -> bool:
        """Check if the rate limiter is currently throttling.
        检查限流器当前是否在节流。"""
        return self._tokens < 1.0


# ---------------------------------------------------------------------------
# Retry Handler
# ---------------------------------------------------------------------------


class RetryHandler:
    """
    Configurable retry logic with exponential backoff and jitter.
    带指数退避和抖动的可配置重试逻辑。

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Random jitter factor (0 = no jitter, 1 = full jitter)
        retryable_exceptions: Tuple of exception types that trigger retry
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: float = 0.1,
        retryable_exceptions: Tuple[type[Exception], ...] = (
            ChannelConnectionError,
            ChannelTimeoutError,
            ConnectionError,
            TimeoutError,
        ),
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
        self._attempt: int = 0

    async def execute(
        self,
        coro_factory: Callable[[], Any],
        context: str = "",
    ) -> Any:
        """
        Execute a coroutine with retry logic.
        使用重试逻辑执行协程。

        Args:
            coro_factory: Async callable that returns the operation result
            context: Human-readable description for logging

        Returns:
            The result of the successful coroutine call

        Raises:
            The last exception if all retries are exhausted
        """
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self._attempt = attempt
                return await coro_factory()
            except self.retryable_exceptions as e:
                last_exc = e
                if attempt < self.max_retries:
                    delay = self._compute_delay(attempt)
                    logger.warning(
                        "Retry %s/%s for %s after %.2fs: %s",
                        attempt, self.max_retries, context or "operation",
                        delay, e,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "All %s retries exhausted for %s: %s",
                        self.max_retries, context or "operation", e,
                    )
        raise last_exc  # type: ignore[misc]

    def _compute_delay(self, attempt: int) -> float:
        """Compute exponential backoff delay with optional jitter.
        计算带可选抖动的指数退避延迟。"""
        import random
        delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
        if self.jitter > 0:
            delay += random.uniform(0, self.jitter * delay)
        return delay


# ---------------------------------------------------------------------------
# Base Channel (Abstract)
# ---------------------------------------------------------------------------


class BaseChannel(ABC):
    """
    Abstract base class for all Nonull channels.
    所有 Nonull 通道的抽象基类。

    Provides standardized lifecycle management, authentication, rate limiting,
    and error handling. Each platform-specific channel must implement the
    abstract methods: _on_connect, _on_disconnect, _send_message, and
    _receive_message.

    提供标准化的生命周期管理、认证、限流和错误处理。
    每个特定平台的通道必须实现抽象方法。

    Args:
        name: Unique channel name (e.g., "telegram", "cli")
        config: Optional configuration dictionary
        max_rate: Maximum outbound messages per second (0 = unlimited)
        auth_token: Optional authentication token
        allowed_users: Optional list of allowed user IDs (empty = allow all)
    """

    def __init__(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
        max_rate: int = 30,
        auth_token: Optional[str] = None,
        allowed_users: Optional[List[str]] = None,
    ) -> None:
        self.name = name
        self.config = config or {}
        self.state: ChannelState = ChannelState.INITIALIZED
        self._auth_token = auth_token
        self._allowed_users = set(allowed_users or [])
        self._rate_limiter = RateLimiter(max_rate=max_rate) if max_rate > 0 else None
        self._retry_handler = RetryHandler(
            max_retries=self.config.get("max_retries", 3),
            base_delay=self.config.get("retry_base_delay", 1.0),
            max_delay=self.config.get("retry_max_delay", 60.0),
        )
        self._message_handlers: List[Callable[[Message], Any]] = []
        self._connection_lock = asyncio.Lock()
        self._receive_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._metrics: Dict[str, int] = {
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0,
            "retries": 0,
        }
        logger.info("Channel '%s' initialized (state=%s)", self.name, self.state.value)

    # ------------------------------------------------------------------
    # Public Lifecycle API
    # ------------------------------------------------------------------

    async def connect(self, timeout: float = 30.0) -> bool:
        """
        Connect to the channel. Thread-safe with lock protection.
        连接到通道。使用锁保护，线程安全。

        Args:
            timeout: Maximum seconds to wait for connection

        Returns:
            True if connected successfully, False otherwise

        Raises:
            ChannelTimeoutError: If connection times out
            ChannelConnectionError: If connection fails
        """
        async with self._connection_lock:
            if self.state in (ChannelState.CONNECTED, ChannelState.CONNECTING):
                logger.debug("Channel '%s' already %s", self.name, self.state.value)
                return self.state == ChannelState.CONNECTED

            self.state = ChannelState.CONNECTING
            logger.info("Channel '%s' connecting...", self.name)

            try:
                success = await asyncio.wait_for(
                    self._on_connect(), timeout=timeout
                )
            except asyncio.TimeoutError:
                self.state = ChannelState.ERROR
                raise ChannelTimeoutError(
                    f"Channel '{self.name}' connection timed out after {timeout}s"
                ) from None
            except Exception as e:
                self.state = ChannelState.ERROR
                raise ChannelConnectionError(
                    f"Channel '{self.name}' connection failed: {e}"
                ) from e

            if success:
                self.state = ChannelState.CONNECTED
                logger.info("Channel '%s' connected successfully", self.name)
                # Start background receive loop
                if self.config.get("auto_receive", True):
                    self._start_receive_loop()
            else:
                self.state = ChannelState.ERROR
                logger.error("Channel '%s' connection returned False", self.name)

            return success

    async def disconnect(self, timeout: float = 10.0) -> None:
        """
        Disconnect from the channel gracefully.
        优雅地断开通道连接。

        Args:
            timeout: Maximum seconds to wait for disconnection
        """
        async with self._connection_lock:
            if self.state in (ChannelState.DISCONNECTED, ChannelState.CLOSED):
                return

            self.state = ChannelState.DISCONNECTING
            logger.info("Channel '%s' disconnecting...", self.name)

            # Stop receive loop
            self._stop_receive_loop()

            try:
                await asyncio.wait_for(self._on_disconnect(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Channel '%s' disconnect timed out", self.name)
            except Exception as e:
                logger.error("Channel '%s' disconnect error: %s", self.name, e)

            self.state = ChannelState.DISCONNECTED
            logger.info("Channel '%s' disconnected", self.name)

    async def send(self, message: Message) -> None:
        """
        Send a message through the channel with rate limiting and retry.
        通过通道发送消息，带限流和重试。

        Args:
            message: Standardized message to send

        Raises:
            ChannelError: If the channel is not connected
            ChannelRateLimitError: If rate limited after waiting
        """
        if self.state != ChannelState.CONNECTED:
            raise ChannelError(
                f"Cannot send on channel '{self.name}': state={self.state.value}"
            )

        # Rate limiting
        if self._rate_limiter:
            wait_time = await self._rate_limiter.acquire()
            if wait_time > 0:
                logger.debug("Rate limited on '%s', waiting %.2fs", self.name, wait_time)
                await asyncio.sleep(wait_time)

        # Send with retry
        try:
            await self._retry_handler.execute(
                lambda: self._send_message(message),
                context=f"send on '{self.name}'",
            )
            self._metrics["messages_sent"] += 1
        except Exception as e:
            self._metrics["errors"] += 1
            raise ChannelError(f"Failed to send on '{self.name}': {e}") from e

    async def receive(self, timeout: float = 30.0) -> Optional[Message]:
        """
        Receive a single message from the channel (blocking).
        从通道接收单条消息 (阻塞)。

        Args:
            timeout: Maximum seconds to wait for a message

        Returns:
            Message if received, None if timed out

        Raises:
            ChannelConnectionError: If receive fails
        """
        if self.state != ChannelState.CONNECTED:
            raise ChannelError(
                f"Cannot receive on channel '{self.name}': state={self.state.value}"
            )

        try:
            message = await asyncio.wait_for(self._receive_message(), timeout=timeout)
            if message:
                self._metrics["messages_received"] += 1
            return message
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            self._metrics["errors"] += 1
            raise ChannelConnectionError(
                f"Receive failed on '{self.name}': {e}"
            ) from e

    # ------------------------------------------------------------------
    # Lifecycle Helpers
    # ------------------------------------------------------------------

    def _start_receive_loop(self) -> None:
        """Start the background message receive loop.
        启动后台消息接收循环。"""
        if self._receive_task and not self._receive_task.done():
            return
        self._stop_event.clear()
        self._receive_task = asyncio.create_task(self._receive_loop())
        logger.debug("Receive loop started for '%s'", self.name)

    def _stop_receive_loop(self) -> None:
        """Stop the background message receive loop.
        停止后台消息接收循环。"""
        self._stop_event.set()
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            self._receive_task = None
        logger.debug("Receive loop stopped for '%s'", self.name)

    async def _receive_loop(self) -> None:
        """Background loop: continuously receives and dispatches messages.
        后台循环：持续接收并分派消息。"""
        logger.info("Receive loop started for channel '%s'", self.name)
        while not self._stop_event.is_set():
            try:
                message = await self._receive_message()
                if message:
                    self._metrics["messages_received"] += 1
                    await self._dispatch(message)
            except asyncio.CancelledError:
                break
 except ChannelError:
                # Channel-level error (recoverable)
                self._metrics["errors"] += 1
                continue
            except Exception as e:
                self._metrics["errors"] += 1
                logger.error("Unexpected error in receive loop for '%s': %s", self.name, e)
                await asyncio.sleep(1)
        logger.info("Receive loop ended for channel '%s'", self.name)

    async def _dispatch(self, message: Message) -> None:
        """Dispatch a received message to all registered handlers.
        将收到的消息分派给所有注册的处理程序。"""
        for handler in self._message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error("Handler error on '%s': %s", self.name, e)

    # ------------------------------------------------------------------
    # Handler Registration
    # ------------------------------------------------------------------

    def on_message(self, handler: Callable[[Message], Any]) -> Callable:
        """
        Register a message handler. Can be used as a decorator.
        注册消息处理程序。可以用作装饰器。

        Usage:
            @channel.on_message
            async def handle(msg: Message):
                print(msg.content)
        """
        self._message_handlers.append(handler)
        logger.debug("Handler registered on '%s': %s", self.name, handler.__name__)
        return handler

    def remove_handler(self, handler: Callable) -> None:
        """Remove a previously registered message handler.
        移除之前注册的消息处理程序。"""
        if handler in self._message_handlers:
            self._message_handlers.remove(handler)

    # ------------------------------------------------------------------
    # Authentication & Authorization
    # ------------------------------------------------------------------

    def authenticate(self, token: str) -> bool:
        """
        Authenticate using a bearer token.
        使用 Bearer Token 进行身份验证。

        Returns:
            True if token matches the configured auth token
        """
        if not self._auth_token:
            return True  # No auth configured
        return token == self._auth_token

    def authorize_user(self, user_id: str) -> bool:
        """
        Check if a user is authorized (allowlist check).
        检查用户是否在授权列表中。

        Returns:
            True if user is authorized
        """
        if not self._allowed_users:
            return True  # Allow all if no allowlist
        return user_id in self._allowed_users

    def add_allowed_user(self, user_id: str) -> None:
        """Add a user to the authorization allowlist.
        将用户添加到授权白名单。"""
        self._allowed_users.add(user_id)

    def remove_allowed_user(self, user_id: str) -> None:
        """Remove a user from the authorization allowlist.
        从授权白名单中移除用户。"""
        self._allowed_users.discard(user_id)

    # ------------------------------------------------------------------
    # Metrics & Health
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, int]:
        """Get channel metrics (sent, received, errors, retries).
        获取通道指标 (发送、接收、错误、重试次数)。"""
        return dict(self._metrics)

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the channel.
        执行通道健康检查。

        Returns:
            Dictionary with status information
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "connected": self.state == ChannelState.CONNECTED,
            "metrics": self.get_metrics(),
            "handlers": len(self._message_handlers),
        }

    # ------------------------------------------------------------------
    # Abstract Methods (must be implemented by subclasses)
    # ------------------------------------------------------------------

    @abstractmethod
    async def _on_connect(self) -> bool:
        """
        Platform-specific connection logic.
        平台特定的连接逻辑。

        Returns:
            True if connection succeeded, False otherwise
        """
        ...

    @abstractmethod
    async def _on_disconnect(self) -> None:
        """
        Platform-specific disconnection/cleanup logic.
        平台特定的断开/清理逻辑。"""
        ...

    @abstractmethod
    async def _send_message(self, message: Message) -> None:
        """
        Platform-specific message delivery.
        平台特定的消息发送实现。

        Args:
            message: The standardized message to deliver
        """
        ...

    @abstractmethod
    async def _receive_message(self) -> Optional[Message]:
        """
        Platform-specific message reception.
        平台特定的消息接收实现。

        Returns:
            A Message if one is available, None otherwise
        """
        ...

    # ------------------------------------------------------------------
    # Context Manager Support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "BaseChannel":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Any,
    ) -> None:
        await self.disconnect()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}' state={self.state.value}>"
