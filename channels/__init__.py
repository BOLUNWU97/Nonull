"""
Nonull — Channels Package
===================================
智能体多通道通信网关 | Multi-Channel Communication Gateway

A multi-channel gateway system inspired by OpenClaw's gateway architecture,
Hermes Agent's platform adapters, and Claude Code's hook lifecycle.

Channels provide unified message routing across multiple platforms including
CLI, Telegram, Feishu (飞书), DingTalk (钉钉), WebSocket, HTTP API, and
the Model Context Protocol (MCP). Each channel implements a common abstract
interface for connection lifecycle, authentication, rate limiting, and
error handling.

典型工作流 (Typical Workflow):
    GatewayChannel receives a message
        → routes to the correct platform adapter
        → adapter normalizes into standard Message format
        → message passes through hooks (pre/post)
        → agent processes and responds
        → response flows back through the gateway

Exports:
    BaseChannel          — Abstract base class for all channels
    CLIChannel           — Interactive REPL with rich formatting
    GatewayChannel       — Unified message routing gateway
    MCPAdapter           — Model Context Protocol integration
    TelegramAdapter      — Telegram Bot API adapter
    FeishuAdapter        — Feishu (飞书) adapter
    DingTalkAdapter      — DingTalk (钉钉) adapter
    WebSocketAdapter     — WebSocket server adapter
    HTTPAdapter          — HTTP REST API adapter
    Message              — Standardized message dataclass
    ChannelMessage       — Alias for Message (backward compat)
    ChannelError         — Base exception for channel errors
    ChannelAuthError     — Authentication failure exception
    ChannelRateLimitError— Rate limit exceeded exception
"""

from channels.base import (
    BaseChannel,
    ChannelState,
    Message,
    MessageRole,
    MessagePriority,
    ChannelError,
    ChannelAuthError,
    ChannelConnectionError,
    ChannelRateLimitError,
    ChannelTimeoutError,
)
from channels.cli import CLIChannel
from channels.gateway import GatewayChannel
from channels.mcp_adapter import MCPAdapter, MCPServerConnection
from channels.platform_adapters import (
    TelegramAdapter,
    FeishuAdapter,
    DingTalkAdapter,
    WebSocketAdapter,
    HTTPAdapter,
    PlatformAdapter,
)

__version__ = "1.0.0"
__all__ = [
    # Base
    "BaseChannel",
    "ChannelState",
    "Message",
    "MessageRole",
    "MessagePriority",
    "ChannelError",
    "ChannelAuthError",
    "ChannelConnectionError",
    "ChannelRateLimitError",
    "ChannelTimeoutError",
    # CLI
    "CLIChannel",
    # Gateway
    "GatewayChannel",
    # MCP
    "MCPAdapter",
    "MCPServerConnection",
    # Platform Adapters
    "PlatformAdapter",
    "TelegramAdapter",
    "FeishuAdapter",
    "DingTalkAdapter",
    "WebSocketAdapter",
    "HTTPAdapter",
]
