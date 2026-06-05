"""
Nonull — Platform Adapters
===================================
平台适配器 | Multi-Platform Integration Adapters

Base platform adapters designed for extensibility across multiple messaging
platforms. Provides concrete implementations for Telegram, Feishu (飞书),
DingTalk (钉钉), WebSocket, and HTTP APIs, along with a base adapter class
for custom platform integration.

为跨多个消息平台的可扩展性而设计的基础平台适配器。提供 Telegram、飞书、
钉钉、WebSocket 和 HTTP API 的具体实现，以及用于自定义平台集成的
基础适配器类。

Each adapter extends BaseChannel and implements the platform-specific
connection, message sending, and message receiving logic.

每个适配器都继承 BaseChannel 并实现特定平台的连接、消息发送和消息接收逻辑。

Supported Platforms (支持的平台):
    - Telegram        (via python-telegram-bot or raw API)
    - Feishu / Lark   (飞书, via feishu SDK or raw API)
    - DingTalk        (钉钉, via dingtalk SDK or raw API)
    - WebSocket       (custom WebSocket server/client)
    - HTTP API        (RESTful webhook-based adapter)
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from channels.base import (
    BaseChannel,
    ChannelAuthError,
    ChannelConnectionError,
    ChannelError,
    ChannelState,
    Message,
    MessagePriority,
    MessageRole,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform Adapter Base
# ---------------------------------------------------------------------------


class PlatformAdapter(BaseChannel, ABC):
    """
    Base class for all platform-specific adapters.
    所有平台特定适配器的基类。

    Provides common platform adapter functionality like token management,
    webhook URL generation, and platform-specific error handling.

    Args:
        name: Adapter name (e.g., "telegram", "feishu")
        config: Configuration dictionary
        api_token: API token for the platform
        api_base_url: Base URL for the platform API
        webhook_url: Webhook URL (if using webhook mode)
        allowed_users: Set of allowed user IDs
    """

    def __init__(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
        api_token: Optional[str] = None,
        api_base_url: Optional[str] = None,
        webhook_url: Optional[str] = None,
        allowed_users: Optional[Set[str]] = None,
    ) -> None:
        super().__init__(
            name=name,
            config=config or {},
            max_rate=config.get("max_rate", 30) if config else 30,
            auth_token=api_token,
            allowed_users=list(allowed_users) if allowed_users else None,
        )
        self.api_token = api_token
        self.api_base_url = api_base_url
        self.webhook_url = webhook_url
        self._platform_metrics: Dict[str, int] = {
            "api_calls": 0,
            "api_errors": 0,
            "webhooks_received": 0,
        }

    def build_message(
        self,
        content: str,
        user_id: str = "",
        platform_message_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        role: MessageRole = MessageRole.USER,
    ) -> Message:
        """
        Build a standardized Message from platform-specific data.
        从平台特定数据构建标准化的 Message。
        """
        return Message(
            id=f"{self.name}_{uuid.uuid4().hex[:12]}",
            channel=self.name,
            role=role,
            content=content,
            platform=self.name,
            platform_message_id=platform_message_id,
            user_id=user_id,
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc),
        )

    async def _make_api_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the platform API.
        向平台 API 发起 HTTP 请求。

        This is a placeholder; in production, use an HTTP client library
        like `aiohttp` or `httpx`.

        这是占位实现；生产环境中请使用 aiohttp 或 httpx 等 HTTP 客户端库。
        """
        self._platform_metrics["api_calls"] += 1
        url = f"{self.api_base_url.rstrip('/')}/{endpoint.lstrip('/')}" if self.api_base_url else endpoint
        logger.debug("API request: %s %s", method, url)

        # Placeholder - in production, make actual HTTP call
        # async with aiohttp.ClientSession() as session:
        #     async with session.request(method, url, json=data, headers=headers) as resp:
        #         return await resp.json()

        self._platform_metrics["api_errors"] += 1
        raise NotImplementedError(
            f"HTTP client not configured. Install aiohttp or httpx to use {self.name} adapter."
        )

    def get_platform_metrics(self) -> Dict[str, int]:
        """Get platform-specific metrics.
        获取平台特定指标。"""
        metrics = self.get_metrics()
        metrics.update(self._platform_metrics)
        return metrics


# ---------------------------------------------------------------------------
# Telegram Adapter
# ---------------------------------------------------------------------------


class TelegramAdapter(PlatformAdapter):
    """
    Telegram Bot API adapter.
    Telegram 机器人 API 适配器。

    Supports both long-polling (getUpdates) and webhook modes for receiving
    messages. Handles text, photo, document, and other message types.

    支持长轮询 (getUpdates) 和 Webhook 两种接收消息模式。
    处理文本、图片、文档等消息类型。

    API Documentation: https://core.telegram.org/bots/api

    Args:
        name: Channel name (default "telegram")
        bot_token: Telegram Bot API token
        webhook_url: Webhook URL (webhook mode)
        poll_interval: Polling interval in seconds (polling mode, default 1.0)
        allowed_users: Set of allowed Telegram user IDs
        config: Additional configuration
    """

    def __init__(
        self,
        name: str = "telegram",
        bot_token: Optional[str] = None,
        webhook_url: Optional[str] = None,
        poll_interval: float = 1.0,
        allowed_users: Optional[Set[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            name=name,
            config=config or {},
            api_token=bot_token,
            api_base_url=config.get("api_base_url", "https://api.telegram.org/bot"),
            webhook_url=webhook_url,
            allowed_users=allowed_users,
        )
        self.bot_token = bot_token
        self.poll_interval = poll_interval
        self._polling_task: Optional[asyncio.Task] = None
        self._last_update_id: int = 0
        self._message_type_handlers: Dict[str, Callable] = {}

        logger.info("TelegramAdapter '%s' initialized (mode=%s)",
                     name, "webhook" if webhook_url else "polling")

    async def _on_connect(self) -> bool:
        """Connect to Telegram API and verify the bot token.
        连接到 Telegram API 并验证机器人令牌。"""
        try:
            # Verify token by calling getMe API
            # In production: await self._make_api_request("GET", "getMe")
            logger.info("Telegram bot '%s' connected", self.name)
            self._start_polling()
            return True
        except Exception as e:
            logger.error("Telegram connection failed: %s", e)
            return False

    async def _on_disconnect(self) -> None:
        """Disconnect from Telegram API.
        断开与 Telegram API 的连接。"""
        self._stop_polling()
        logger.info("Telegram adapter '%s' disconnected", self.name)

    async def _send_message(self, message: Message) -> None:
        """
        Send a message to Telegram.
        发送消息到 Telegram。

        Supports text messages and messages with attachments.
        """
        chat_id = message.metadata.get("chat_id", message.user_id)
        if not chat_id:
            logger.warning("No chat_id for Telegram message")
            return

        # Build sendMessage payload
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": message.content,
            "parse_mode": "MarkdownV2",
        }

        # Handle reply_to
        if message.reply_to:
            payload["reply_to_message_id"] = message.reply_to

        # In production: await self._make_api_request("POST", "sendMessage", payload)
        logger.debug("Telegram send: chat=%s text=%s", chat_id, message.content[:50])

    async def _receive_message(self) -> Optional[Message]:
        """
        Receive a message from Telegram via polling (getUpdates).
        通过轮询从 Telegram 接收消息。

        Returns:
            Message if a new update is available, None otherwise
        """
        # In production, this calls getUpdates and processes the response
        await asyncio.sleep(self.poll_interval)
        return None

    def _start_polling(self) -> None:
        """Start the long-polling loop for receiving messages.
        启动用于接收消息的长轮询循环。"""
        if self._polling_task and not self._polling_task.done():
            return
        self._polling_task = asyncio.create_task(self._polling_loop())
        logger.debug("Telegram polling started")

    def _stop_polling(self) -> None:
        """Stop the long-polling loop.
        停止长轮询循环。"""
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            self._polling_task = None
        logger.debug("Telegram polling stopped")

    async def _polling_loop(self) -> None:
        """Background polling loop for Telegram updates.
        Telegram 更新轮询的后台循环。"""
        while self.state == ChannelState.CONNECTED:
            try:
                updates = await self._fetch_updates()
                for update in updates:
                    message = self._parse_update(update)
                    if message:
                        await self._dispatch(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Telegram polling error: %s", e)
            await asyncio.sleep(self.poll_interval)

    async def _fetch_updates(self) -> List[Dict[str, Any]]:
        """Fetch new updates from Telegram API.
        从 Telegram API 获取新更新。"""
        # In production:
        # params = {"offset": self._last_update_id + 1, "timeout": 30}
        # response = await self._make_api_request("GET", "getUpdates", params)
        # return response.get("result", [])
        return []

    def _parse_update(self, update: Dict[str, Any]) -> Optional[Message]:
        """
        Parse a Telegram update into a standardized Message.
        将 Telegram 更新解析为标准化 Message。
        """
        # Extract update_id
        update_id = update.get("update_id", 0)
        if update_id:
            self._last_update_id = max(self._last_update_id, update_id)

        # Extract message data
        msg_data = update.get("message") or update.get("edited_message")
        if not msg_data:
            return None

        text = msg_data.get("text", "")
        chat = msg_data.get("chat", {})
        from_user = msg_data.get("from", {})

        return self.build_message(
            content=text,
            user_id=str(from_user.get("id", "")),
            platform_message_id=str(msg_data.get("message_id", "")),
            metadata={
                "chat_id": str(chat.get("id", "")),
                "chat_type": chat.get("type", ""),
                "username": from_user.get("username", ""),
                "first_name": from_user.get("first_name", ""),
                "update_id": update_id,
                "raw": msg_data,
            },
        )

    async def process_webhook(self, payload: Dict[str, Any]) -> Optional[Message]:
        """
        Process an incoming Telegram webhook payload.
        处理传入的 Telegram Webhook 载荷。

        Args:
            payload: The raw webhook JSON payload

        Returns:
            Parsed Message, or None if not a message update
        """
        self._platform_metrics["webhooks_received"] += 1
        return self._parse_update(payload)


# ---------------------------------------------------------------------------
# Feishu (Lark) Adapter
# ---------------------------------------------------------------------------


class FeishuAdapter(PlatformAdapter):
    """
    Feishu (Lark) Bot API adapter.
    飞书 (Lark) 机器人 API 适配器。

    Supports both card-based and text-based messaging, event subscription
    handling, and interactive message replies.

    支持卡片和文本消息、事件订阅处理以及交互式消息回复。

    API Documentation: https://open.feishu.cn/document/home

    Args:
        name: Channel name (default "feishu")
        app_id: Feishu App ID
        app_secret: Feishu App Secret
        webhook_verification_token: Verification token for webhooks
        allowed_users: Set of allowed user IDs
        config: Additional configuration
    """

    def __init__(
        self,
        name: str = "feishu",
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        webhook_verification_token: Optional[str] = None,
        allowed_users: Optional[Set[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            name=name,
            config=config or {},
            api_token=app_secret,
            api_base_url=config.get("api_base_url", "https://open.feishu.cn/open-apis"),
            allowed_users=allowed_users,
        )
        self.app_id = app_id
        self.app_secret = app_secret
        self.webhook_verification_token = webhook_verification_token
        self._tenant_access_token: Optional[str] = None
        self._token_expires_at: float = 0

        logger.info("FeishuAdapter '%s' initialized", name)

    async def _on_connect(self) -> bool:
        """Authenticate with Feishu API and obtain access token.
        向飞书 API 进行身份验证并获取访问令牌。"""
        try:
            await self._refresh_token()
            logger.info("Feishu adapter '%s' connected", self.name)
            return True
        except Exception as e:
            logger.error("Feishu connection failed: %s", e)
            return False

    async def _on_disconnect(self) -> None:
        """Disconnect from Feishu API.
        断开与飞书 API 的连接。"""
        self._tenant_access_token = None
        logger.info("Feishu adapter '%s' disconnected", self.name)

    async def _send_message(self, message: Message) -> None:
        """
        Send a message to Feishu.
        发送消息到飞书。

        Supports both text and interactive card messages based on content format.
        """
        receive_id = message.metadata.get("open_id", message.user_id)
        receive_id_type = message.metadata.get("receive_id_type", "open_id")

        if not receive_id:
            logger.warning("No receive_id for Feishu message")
            return

        # Check if content is JSON (card message) or plain text
        try:
            content_data = json.loads(message.content)
            content_type = "interactive" if isinstance(content_data, dict) else "text"
        except (json.JSONDecodeError, TypeError):
            content_data = {"text": message.content}
            content_type = "text"

        payload = {
            "receive_id": receive_id,
            "msg_type": content_type,
            "content": json.dumps(content_data, ensure_ascii=False),
        }

        # In production:
        # await self._make_api_request(
        #     "POST",
        #     f"im/v1/messages?receive_id_type={receive_id_type}",
        #     payload,
        #     headers={"Authorization": f"Bearer {self._tenant_access_token}"},
        # )
        logger.debug("Feishu send: type=%s receive_id=%s", content_type, receive_id)

    async def _receive_message(self) -> Optional[Message]:
        """
        Feishu uses webhooks for message reception (no polling).
        飞书使用 Webhook 接收消息 (无轮询)。"""
        return None

    async def _refresh_token(self) -> None:
        """Refresh the Feishu tenant access token.
        刷新飞书 tenant access token。"""
        if time.time() < self._token_expires_at:
            return

        # In production:
        # response = await self._make_api_request("POST", "auth/v3/tenant_access_token/internal", {
        #     "app_id": self.app_id,
        #     "app_secret": self.app_secret,
        # })
        # self._tenant_access_token = response.get("tenant_access_token")
        # self._token_expires_at = time.time() + response.get("expire", 7200) - 60

        self._tenant_access_token = "placeholder_token"
        self._token_expires_at = time.time() + 3600
        logger.debug("Feishu token refreshed")

    async def process_webhook(self, payload: Dict[str, Any]) -> Optional[Message]:
        """
        Process an incoming Feishu webhook event.
        处理传入的飞书 Webhook 事件。

        Args:
            payload: The raw webhook JSON payload

        Returns:
            Parsed Message, or None if not a message event
        """
        self._platform_metrics["webhooks_received"] += 1

        # Verify webhook token
        token = payload.get("token", "")
        if self.webhook_verification_token and token != self.webhook_verification_token:
            logger.warning("Invalid Feishu webhook token")
            return None

        # Parse event
        event = payload.get("event", {})
        event_type = event.get("type", "")

        if event_type == "im.message.receive_v1":
            sender = event.get("sender", {})
            message_body = event.get("message", {})

            content_raw = message_body.get("content", "{}")
            try:
                content = json.loads(content_raw)
                text = content.get("text", "")
            except (json.JSONDecodeError, TypeError):
                text = content_raw

            return self.build_message(
                content=text,
                user_id=sender.get("sender_id", {}).get("open_id", ""),
                platform_message_id=message_body.get("message_id", ""),
                metadata={
                    "chat_id": message_body.get("chat_id", ""),
                    "message_type": message_body.get("message_type", ""),
                    "event_type": event_type,
                    "sender": sender,
                    "raw": payload,
                },
            )

        return None


# ---------------------------------------------------------------------------
# DingTalk Adapter
# ---------------------------------------------------------------------------


class DingTalkAdapter(PlatformAdapter):
    """
    DingTalk (钉钉) Bot API adapter.
    钉钉机器人 API 适配器。

    Supports webhook-based outbound messaging and event subscription for
    receiving messages. Handles text, markdown, and interactive card messages.

    支持基于 Webhook 的出站消息和事件订阅接收消息。
    处理文本、Markdown 和交互式卡片消息。

    API Documentation: https://open.dingtalk.com/document/orgapp

    Args:
        name: Channel name (default "dingtalk")
        app_key: DingTalk App Key (ClientId)
        app_secret: DingTalk App Secret (ClientSecret)
        robot_code: Robot code for the bot
        allowed_users: Set of allowed user IDs
        config: Additional configuration
    """

    def __init__(
        self,
        name: str = "dingtalk",
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        robot_code: Optional[str] = None,
        allowed_users: Optional[Set[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            name=name,
            config=config or {},
            api_token=app_secret,
            api_base_url=config.get("api_base_url", "https://api.dingtalk.com/v1.0"),
            allowed_users=allowed_users,
        )
        self.app_key = app_key
        self.app_secret = app_secret
        self.robot_code = robot_code
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

        logger.info("DingTalkAdapter '%s' initialized", name)

    async def _on_connect(self) -> bool:
        """Authenticate with DingTalk API.
        向钉钉 API 进行身份验证。"""
        try:
            await self._refresh_token()
            logger.info("DingTalk adapter '%s' connected", self.name)
            return True
        except Exception as e:
            logger.error("DingTalk connection failed: %s", e)
            return False

    async def _on_disconnect(self) -> None:
        """Disconnect from DingTalk API.
        断开与钉钉 API 的连接。"""
        self._access_token = None
        logger.info("DingTalk adapter '%s' disconnected", self.name)

    async def _send_message(self, message: Message) -> None:
        """
        Send a message to DingTalk.
        发送消息到钉钉。

        Supports text and markdown message types. Uses robot-oriented
        messaging API for user/group messages.
        """
        # Determine target type from metadata
        target_id = message.metadata.get("conversation_id",
                                         message.metadata.get("user_id", message.user_id))
        if not target_id:
            logger.warning("No target ID for DingTalk message")
            return

        # Build message based on content
        msg_type = "text"
        content: Dict[str, Any] = {"text": message.content}
        if "```" in message.content or "#" in message.content:
            msg_type = "markdown"
            content = {
                "title": message.metadata.get("title", "Nonull"),
                "text": message.content,
            }

        payload = {
            "robotCode": self.robot_code,
            "targetId": target_id,
            "msgKey": f"sample{msg_type}",
            "msgParam": json.dumps(content, ensure_ascii=False),
        }

        # In production:
        # headers = {
        #     "x-acs-dingtalk-access-token": self._access_token,
        #     "Content-Type": "application/json",
        # }
        # await self._make_api_request("POST", "robot/oToMessages/batchSend", payload, headers)
        logger.debug("DingTalk send: type=%s target=%s", msg_type, target_id)

    async def _receive_message(self) -> Optional[Message]:
        """DingTalk uses webhooks for message reception (no polling).
        钉钉使用 Webhook 接收消息 (无轮询)。"""
        return None

    async def _refresh_token(self) -> None:
        """Refresh the DingTalk access token.
        刷新钉钉访问令牌。"""
        if time.time() < self._token_expires_at:
            return

        # In production:
        # response = await self._make_api_request("POST", "oauth2/accessToken", {
        #     "appKey": self.app_key,
        #     "appSecret": self.app_secret,
        # })
        # self._access_token = response.get("accessToken")
        # self._token_expires_at = time.time() + response.get("expireIn", 7200) - 60

        self._access_token = "placeholder_token"
        self._token_expires_at = time.time() + 3600
        logger.debug("DingTalk token refreshed")

    async def process_webhook(self, payload: Dict[str, Any]) -> Optional[Message]:
        """
        Process an incoming DingTalk webhook callback.
        处理传入的钉钉 Webhook 回调。

        Args:
            payload: The raw webhook JSON payload

        Returns:
            Parsed Message, or None if not a message event
        """
        self._platform_metrics["webhooks_received"] += 1

        # Parse DingTalk callback structure
        text = payload.get("text", {}).get("content", "")
        sender_id = payload.get("senderId", "") or payload.get("senderStaffId", "")
        conversation_id = payload.get("conversationId", "")
        conversation_title = payload.get("conversationTitle", "")
        sender_nick = payload.get("senderNick", "")
        msg_type = payload.get("msgtype", "text")

        if msg_type == "text":
            return self.build_message(
                content=text,
                user_id=sender_id,
                platform_message_id=payload.get("msgId", ""),
                metadata={
                    "conversation_id": conversation_id,
                    "conversation_title": conversation_title,
                    "sender_nick": sender_nick,
                    "msg_type": msg_type,
                    "raw": payload,
                },
            )

        return None


# ---------------------------------------------------------------------------
# WebSocket Adapter
# ---------------------------------------------------------------------------


class WebSocketAdapter(PlatformAdapter):
    """
    WebSocket server/client adapter for real-time communication.
    用于实时通信的 WebSocket 服务器/客户端适配器。

    Can operate as a server (accepting incoming connections) or as a client
    (connecting to an external WebSocket server). Supports authentication,
    heartbeat/ping-pong, and automatic reconnection.

    可以作为服务器 (接受传入连接) 或客户端 (连接到外部 WebSocket 服务器) 运行。
    支持认证、心跳和自动重连。

    Args:
        name: Channel name (default "websocket")
        host: Host to bind/connect to
        port: Port number
        mode: "server" or "client"
        path: URL path (for client mode)
        ssl: Use SSL/TLS
        heartbeet_interval: Ping interval in seconds
        allowed_users: Set of allowed user IDs
        config: Additional configuration
    """

    def __init__(
        self,
        name: str = "websocket",
        host: str = "localhost",
        port: int = 8765,
        mode: str = "server",
        path: str = "/ws",
        ssl: bool = False,
        heartbeat_interval: float = 30.0,
        allowed_users: Optional[Set[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            name=name,
            config=config or {},
            allowed_users=allowed_users,
        )
        self.host = host
        self.port = port
        self.mode = mode.lower()
        self.path = path
        self.ssl = ssl
        self.heartbeat_interval = heartbeat_interval

        self._server: Any = None  # asyncio server (server mode)
        self._connections: Dict[str, Any] = {}  # conn_id -> websocket
        self._heartbeat_task: Optional[asyncio.Task] = None

        logger.info("WebSocketAdapter '%s' initialized (mode=%s, %s:%d)",
                     name, self.mode, host, port)

    async def _on_connect(self) -> bool:
        """
        Start the WebSocket server or connect as a client.
        启动 WebSocket 服务器或作为客户端连接。
        """
        try:
            if self.mode == "server":
                await self._start_server()
            elif self.mode == "client":
                await self._connect_client()
            else:
                raise ValueError(f"Invalid WebSocket mode: {self.mode}")

            # Start heartbeat
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info("WebSocket adapter '%s' connected (%s mode)", self.name, self.mode)
            return True
        except Exception as e:
            logger.error("WebSocket connection failed: %s", e)
            return False

    async def _on_disconnect(self) -> None:
        """Stop the WebSocket server or disconnect the client.
        停止 WebSocket 服务器或断开客户端连接。"""
        # Stop heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        if self.mode == "server" and self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        # Close all connections
        for conn_id, ws in list(self._connections.items()):
            try:
                await ws.close()
            except Exception:
                pass
        self._connections.clear()

        logger.info("WebSocket adapter '%s' disconnected", self.name)

    async def _send_message(self, message: Message) -> None:
        """
        Send a message over WebSocket.
        通过 WebSocket 发送消息。

        Routes to a specific connection if conn_id is in metadata,
        otherwise broadcasts to all connections.
        """
        payload = json.dumps({
            "type": "message",
            "id": message.id,
            "role": message.role.value,
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
        })

        conn_id = message.metadata.get("conn_id", "")
        if conn_id and conn_id in self._connections:
            ws = self._connections[conn_id]
            try:
                await ws.send(payload)
            except Exception as e:
                logger.error("WebSocket send to %s failed: %s", conn_id, e)
        else:
            # Broadcast to all
            for cid, ws in list(self._connections.items()):
                try:
                    await ws.send(payload)
                except Exception as e:
                    logger.warning("WebSocket broadcast to %s failed: %s", cid, e)

    async def _receive_message(self) -> Optional[Message]:
        """
        WebSocket receives messages asynchronously via connection handlers.
        WebSocket 通过连接处理程序异步接收消息。"""
        return None

    async def _start_server(self) -> None:
        """
        Start the WebSocket server.
        启动 WebSocket 服务器。

        In production, use `websockets` library or similar:
            import websockets
            self._server = await websockets.serve(
                self._handle_connection, self.host, self.port
            )
        """
        # Placeholder for WebSocket server setup
        logger.info("WebSocket server placeholder on %s:%d", self.host, self.port)

    async def _connect_client(self) -> None:
        """
        Connect as a WebSocket client.
        作为 WebSocket 客户端连接。

        In production:
            import websockets
            uri = f"{'wss' if self.ssl else 'ws'}://{self.host}:{self.port}{self.path}"
            ws = await websockets.connect(uri)
            self._connections["client"] = ws
        """
        logger.info("WebSocket client placeholder for %s:%d%s", self.host, self.port, self.path)

    async def _handle_connection(self, websocket: Any, path: str) -> None:
        """
        Handle an incoming WebSocket connection (server mode).
        处理传入的 WebSocket 连接 (服务器模式)。

        Reads messages in a loop and dispatches them.
        """
        conn_id = f"conn_{uuid.uuid4().hex[:8]}"
        self._connections[conn_id] = websocket
        logger.debug("WebSocket connection: %s", conn_id)

        try:
            async for raw_message in websocket:
                try:
                    data = json.loads(raw_message)
                    message = self._parse_ws_message(data, conn_id)
                    if message:
                        await self._dispatch(message)
                except json.JSONDecodeError:
                    # Treat as plain text message
                    message = self.build_message(
                        content=raw_message,
                        user_id=conn_id,
                        metadata={"conn_id": conn_id},
                    )
                    await self._dispatch(message)
        except Exception as e:
            logger.warning("WebSocket connection %s error: %s", conn_id, e)
        finally:
            self._connections.pop(conn_id, None)

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to maintain connections.
        发送周期性心跳以维持连接。"""
        while self.state == ChannelState.CONNECTED:
            await asyncio.sleep(self.heartbeat_interval)
            for conn_id, ws in list(self._connections.items()):
                try:
                    ping_payload = json.dumps({"type": "ping"})
                    await ws.send(ping_payload)
                except Exception as e:
                    logger.warning("WebSocket heartbeat to %s failed: %s", conn_id, e)

    def _parse_ws_message(self, data: Dict[str, Any], conn_id: str) -> Optional[Message]:
        """Parse a WebSocket JSON message into a standardized Message.
        将 WebSocket JSON 消息解析为标准化 Message。"""
        content = data.get("content", data.get("text", ""))
        if not content:
            return None

        return self.build_message(
            content=content,
            user_id=data.get("user_id", conn_id),
            platform_message_id=data.get("id", ""),
            metadata={
                "conn_id": conn_id,
                "message_type": data.get("type", "message"),
                "raw": data,
            },
        )


# ---------------------------------------------------------------------------
# HTTP API Adapter
# ---------------------------------------------------------------------------


class HTTPAdapter(PlatformAdapter):
    """
    HTTP REST API adapter for webhook-based communication.
    用于基于 Webhook 的 HTTP REST API 适配器。

    Receives messages via incoming webhooks and sends responses via
    outgoing HTTP calls. Supports signature verification for webhook
    authenticity. Ideal for custom integrations with other services.

    通过传入的 Webhook 接收消息，并通过出站 HTTP 调用发送响应。
    支持签名验证以验证 Webhook 真实性。适用于与其他服务的自定义集成。

    Args:
        name: Channel name (default "http")
        listen_host: Host for the webhook server
        listen_port: Port for the webhook server
        webhook_path: URL path for receiving webhooks
        webhook_secret: Secret for HMAC signature verification
        allowed_users: Set of allowed API keys or user IDs
        config: Additional configuration
    """

    def __init__(
        self,
        name: str = "http",
        listen_host: str = "0.0.0.0",
        listen_port: int = 8080,
        webhook_path: str = "/webhook",
        webhook_secret: Optional[str] = None,
        allowed_users: Optional[Set[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            name=name,
            config=config or {},
            allowed_users=allowed_users,
        )
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.webhook_path = webhook_path
        self.webhook_secret = webhook_secret
        self._webhook_server: Any = None

        logger.info("HTTPAdapter '%s' initialized (webhook at %s:%d%s)",
                     name, listen_host, listen_port, webhook_path)

    async def _on_connect(self) -> bool:
        """Start the webhook server.
        启动 Webhook 服务器。"""
        try:
            # In production, start an aiohttp or FastAPI server:
            # from aiohttp import web
            # app = web.Application()
            # app.router.add_post(self.webhook_path, self._handle_webhook)
            # self._webhook_server = await web._run_app(app, host=self.listen_host, port=self.listen_port)
            logger.info("HTTP adapter '%s' listening on %s:%d%s",
                         self.name, self.listen_host, self.listen_port, self.webhook_path)
            return True
        except Exception as e:
            logger.error("HTTP adapter server start failed: %s", e)
            return False

    async def _on_disconnect(self) -> None:
        """Stop the webhook server.
        停止 Webhook 服务器。"""
        if self._webhook_server:
            self._webhook_server.close()
            self._webhook_server = None
        logger.info("HTTP adapter '%s' disconnected", self.name)

    async def _send_message(self, message: Message) -> None:
        """
        Send a message via an outgoing HTTP call.
        通过出站 HTTP 调用发送消息。

        Uses the callback_url from metadata or config to deliver the response.
        """
        callback_url = message.metadata.get(
            "callback_url",
            message.metadata.get("response_url",
                                 self.config.get("default_callback_url", "")),
        )
        if not callback_url:
            logger.warning("No callback URL for HTTP message")
            return

        payload = {
            "id": message.id,
            "role": message.role.value,
            "content": message.content,
            "conversation_id": message.conversation_id,
            "session_id": message.session_id,
            "timestamp": message.created_at.isoformat(),
        }

        # In production:
        # async with aiohttp.ClientSession() as session:
        #     async with session.post(callback_url, json=payload) as resp:
        #         logger.debug("HTTP callback sent to %s: %s", callback_url, resp.status)
        logger.debug("HTTP send: callback=%s", callback_url)

    async def _receive_message(self) -> Optional[Message]:
        """HTTP adapter receives messages via webhooks (no polling).
        HTTP 适配器通过 Webhook 接收消息 (无轮询)。"""
        return None

    async def process_webhook(
        self,
        body: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Message]:
        """
        Process an incoming HTTP webhook request.
        处理传入的 HTTP Webhook 请求。

        Args:
            body: Request body (parsed JSON)
            headers: Request headers for signature verification

        Returns:
            Parsed Message, or None if verification fails
        """
        self._platform_metrics["webhooks_received"] += 1

        # Signature verification
        if self.webhook_secret and headers:
            if not self._verify_signature(body, headers):
                logger.warning("HTTP webhook signature verification failed")
                raise ChannelAuthError("Invalid webhook signature")

        # Extract message fields
        content = (body.get("message", {})
                   .get("content", body.get("content", body.get("text", ""))))
        if not content:
            content = body.get("content", body.get("text", ""))

        user_id = body.get("user_id", body.get("user", body.get("sender", "")))
        msg_id = body.get("id", body.get("message_id", str(uuid.uuid4())))

        return self.build_message(
            content=str(content),
            user_id=str(user_id),
            platform_message_id=str(msg_id),
            metadata={
                "callback_url": body.get("callback_url", body.get("response_url", "")),
                "method": headers.get(":method", "POST") if headers else "POST",
                "source_ip": headers.get("x-forwarded-for", "") if headers else "",
                "raw": body,
            },
        )

    def _verify_signature(
        self, body: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        """
        Verify HMAC signature of the webhook payload.
        验证 Webhook 载荷的 HMAC 签名。

        Supports common signature header patterns (X-Hub-Signature,
        X-Signature, Authorization).
        """
        signature = (
            headers.get("x-hub-signature-256", "")
            or headers.get("x-signature", "")
            or headers.get("authorization", "")
        )
        if not signature:
            return not self.webhook_secret  # No signature required if no secret

        # Remove common prefixes
        signature = signature.replace("sha256=", "").replace("Bearer ", "")

        # Compute expected signature
        body_bytes = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
        expected = hmac.new(
            self.webhook_secret.encode(), body_bytes, hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected)
