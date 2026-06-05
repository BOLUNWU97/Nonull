"""
Nonull — MCP Adapter (Model Context Protocol)
======================================================
模型上下文协议适配器 | Model Context Protocol Integration

Provides dynamic integration of MCP (Model Context Protocol) tools into the
Nonull system. Supports schema-based tool definition, MCP server
connection management, tool namespace isolation, and security validation.

提供 MCP (模型上下文协议) 工具的动态集成，支持基于 Schema 的工具定义、
MCP 服务器连接管理、工具命名空间隔离和安全验证。

MCP tools are automatically namespaced as: mcp__<server>__<tool>
This prevents naming conflicts between tools from different MCP servers.

MCP 工具自动命名空间隔离为：mcp__<server>__<tool>
防止来自不同 MCP 服务器的工具之间出现命名冲突。

Key features:
    - Dynamic tool discovery via MCP protocol
    - Schema-based tool definition and validation
    - MCP server lifecycle management (connect/disconnect/reconnect)
    - Tool namespace isolation with mcp__server__tool pattern
    - Security validation and allowlisting for MCP tools
    - Tool result caching and error handling
    - Support for multiple concurrent MCP server connections
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from channels.base import (
    BaseChannel,
    ChannelConnectionError,
    ChannelError,
    ChannelState,
    Message,
    MessageRole,
    RetryHandler,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MCP-specific Data Types
# ---------------------------------------------------------------------------


class MCPServerState(Enum):
    """MCP server connection states.
    MCP 服务器连接状态。"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MCPTool:
    """
    Represents a tool discovered from an MCP server.
    表示从 MCP 服务器发现的工具。

    Attributes:
        name: Tool name (within the server's namespace)
        full_name: Fully qualified name (mcp__<server>__<tool>)
        server_name: Source MCP server name
        description: Tool description provided by the MCP server
        input_schema: JSON Schema for tool parameters
        allowed: Whether this tool is allowed to be called
    """
    name: str
    full_name: str
    server_name: str
    description: str
    input_schema: Dict[str, Any]
    allowed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "full_name": self.full_name,
            "server_name": self.server_name,
            "description": self.description,
            "input_schema": self.input_schema,
            "allowed": self.allowed,
        }

    def to_openai_tool_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI-compatible tool schema format.
        转换为 OpenAI 兼容的工具 Schema 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.full_name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    def to_anthropic_tool_schema(self) -> Dict[str, Any]:
        """Convert to Anthropic-compatible tool schema format.
        转换为 Anthropic 兼容的工具 Schema 格式。"""
        return {
            "name": self.full_name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class MCPServerConnection:
    """
    Represents a connection to an MCP server.
    表示与 MCP 服务器的连接。

    Attributes:
        name: Server name identifier
        command: Command to start the MCP server process
        args: Command-line arguments
        env: Environment variables
        transport: Transport type ("stdio" or "sse")
        url: Server URL (for SSE transport)
        state: Current connection state
        tools: Dict of discovered tools (name -> MCPTool)
        config: Additional server configuration
    """
    name: str
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    transport: str = "stdio"
    url: Optional[str] = None
    state: MCPServerState = MCPServerState.DISCONNECTED
    tools: Dict[str, MCPTool] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    connected_at: Optional[datetime] = None
    _process: Any = None
    _stdin: Any = None
    _stdout: Any = None
    _session: Any = None

    @property
    def is_connected(self) -> bool:
        return self.state == MCPServerState.CONNECTED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "args": self.args,
            "transport": self.transport,
            "url": self.url,
            "state": self.state.value,
            "tool_count": len(self.tools),
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
        }


# ---------------------------------------------------------------------------
# MCP Adapter
# ---------------------------------------------------------------------------


class MCPAdapter(BaseChannel):
    """
    MCP (Model Context Protocol) adapter for Nonull.
    面向 Nonull 的 MCP (模型上下文协议) 适配器。

    Manages connections to MCP servers, discovers available tools,
    and provides a unified interface for tool execution with proper
    namespace isolation and security validation.

    管理到 MCP 服务器的连接，发现可用工具，并提供统一的工具执行接口，
    具有适当的命名空间隔离和安全验证。

    Args:
        name: Adapter name (default "mcp")
        config: Configuration dictionary
        tool_allowlist: Set of allowed tool full_names (empty = allow all)
        tool_blocklist: Set of blocked tool full_names
        enable_namespace: Enable mcp__server__tool namespace isolation
        auto_discover: Automatically discover tools on connect
    """

    def __init__(
        self,
        name: str = "mcp",
        config: Optional[Dict[str, Any]] = None,
        tool_allowlist: Optional[Set[str]] = None,
        tool_blocklist: Optional[Set[str]] = None,
        enable_namespace: bool = True,
        auto_discover: bool = True,
    ) -> None:
        super().__init__(
            name=name,
            config=config or {},
            max_rate=0,
        )
        self._servers: Dict[str, MCPServerConnection] = {}
        self._tool_allowlist: Set[str] = set(tool_allowlist or [])
        self._tool_blocklist: Set[str] = set(tool_blocklist or [])
        self._enable_namespace = enable_namespace
        self._auto_discover = auto_discover
        self._tools_cache: Dict[str, MCPTool] = {}  # full_name -> tool
        self._tool_executors: Dict[str, Callable] = {}
        self._reconnect_tasks: Dict[str, asyncio.Task] = {}

        self._mcp_metrics: Dict[str, int] = {
            "tools_discovered": 0,
            "tools_executed": 0,
            "tools_failed": 0,
            "servers_connected": 0,
            "servers_disconnected": 0,
            "security_blocks": 0,
        }

        logger.info("MCPAdapter '%s' initialized", self.name)

    # ------------------------------------------------------------------
    # Connection Lifecycle
    # ------------------------------------------------------------------

    async def _on_connect(self) -> bool:
        """
        Connect to all registered MCP servers and discover tools.
        连接到所有已注册的 MCP 服务器并发现工具。
        """
        if not self._servers:
            logger.warning("MCPAdapter '%s': no servers registered", self.name)
            return True

        connect_tasks = []
        for server_name in self._servers:
            connect_tasks.append(self._connect_server(server_name))

        results = await asyncio.gather(*connect_tasks, return_exceptions=True)
        success = True
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("MCP server connect error: %s", result)
                success = False

        # Discover tools from connected servers
        if self._auto_discover:
            await self.discover_tools()

        connected = sum(1 for s in self._servers.values() if s.is_connected)
        logger.info(
            "MCPAdapter '%s': %d/%d servers connected, %d tools discovered",
            self.name, connected, len(self._servers), len(self._tools_cache),
        )
        return success

    async def _on_disconnect(self) -> None:
        """
        Disconnect all MCP servers and clean up.
        断开所有 MCP 服务器并清理。
        """
        # Cancel reconnection tasks
        for task in self._reconnect_tasks.values():
            task.cancel()
        self._reconnect_tasks.clear()

        # Disconnect servers
        disconnect_tasks = []
        for server_name in list(self._servers.keys()):
            disconnect_tasks.append(self._disconnect_server(server_name))

        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)

        self._tools_cache.clear()
        self._tool_executors.clear()
        logger.info("MCPAdapter '%s' disconnected", self.name)

    async def _send_message(self, message: Message) -> None:
        """
        MCP adapter doesn't directly send messages; it executes tools.
        MCP 适配器不直接发送消息；它执行工具。

        Override this to interpret outbound messages as tool calls
        if desired. Default is a no-op.
        """
        pass  # MCP adapter is tool-execution oriented

    async def _receive_message(self) -> None:
        """
        MCP adapter doesn't poll for messages.
        MCP 适配器不轮询消息。"""
        return None

    # ------------------------------------------------------------------
    # Server Management
    # ------------------------------------------------------------------

    def register_server(
        self,
        name: str,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        transport: str = "stdio",
        url: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> MCPServerConnection:
        """
        Register an MCP server for connection.
        注册一个 MCP 服务器用于连接。

        Args:
            name: Unique server name
            command: Command to start the server process (stdio transport)
            args: Command-line arguments
            env: Environment variables
            transport: "stdio" or "sse"
            url: Server URL (for SSE transport)
            config: Additional configuration

        Returns:
            The created MCPServerConnection object

        Raises:
            ValueError: If a server with the same name is already registered
        """
        if name in self._servers:
            raise ValueError(f"MCP server '{name}' is already registered")

        if transport not in ("stdio", "sse"):
            raise ValueError(f"Unsupported transport '{transport}'. Use 'stdio' or 'sse'")

        server = MCPServerConnection(
            name=name,
            command=command,
            args=args or [],
            env=env or {},
            transport=transport,
            url=url,
            config=config or {},
        )
        self._servers[name] = server

        logger.info("MCP server '%s' registered (transport=%s)", name, transport)

        # Auto-connect if adapter is already connected
        if self.state == ChannelState.CONNECTED:
            asyncio.create_task(self._connect_server(name))

        return server

    def unregister_server(self, name: str) -> None:
        """
        Unregister an MCP server and disconnect it.
        注销 MCP 服务器并断开连接。
        """
        if name in self._reconnect_tasks:
            self._reconnect_tasks[name].cancel()
            self._reconnect_tasks.pop(name, None)

        asyncio.create_task(self._disconnect_server(name))
        server = self._servers.pop(name, None)

        if server:
            # Remove tools from this server
            tools_to_remove = [
                fqn for fqn, tool in self._tools_cache.items()
                if tool.server_name == name
            ]
            for fqn in tools_to_remove:
                self._tools_cache.pop(fqn, None)
                self._tool_executors.pop(fqn, None)
            self._mcp_metrics["tools_discovered"] -= len(tools_to_remove)

            logger.info("MCP server '%s' unregistered, %d tools removed", name, len(tools_to_remove))

    def get_server(self, name: str) -> Optional[MCPServerConnection]:
        """Get a registered server by name.
        根据名称获取已注册的服务器。"""
        return self._servers.get(name)

    def list_servers(self) -> Dict[str, Dict[str, Any]]:
        """List all registered servers with status.
        列出所有已注册的服务器及其状态。"""
        return {
            name: {
                "state": s.state.value,
                "transport": s.transport,
                "tool_count": len(s.tools),
            }
            for name, s in self._servers.items()
        }

    async def _connect_server(self, name: str) -> bool:
        """
        Connect to a specific MCP server.
        连接到特定的 MCP 服务器。

        Args:
            name: Server name

        Returns:
            True if connected successfully
        """
        server = self._servers.get(name)
        if not server:
            logger.warning("MCP server '%s' not found", name)
            return False

        if server.is_connected:
            return True

        server.state = MCPServerState.CONNECTING
        logger.info("Connecting to MCP server '%s' (%s transport)...", name, server.transport)

        try:
            # Attempt connection based on transport type
            if server.transport == "stdio":
                await self._connect_stdio(server)
            elif server.transport == "sse":
                await self._connect_sse(server)
            else:
                raise ChannelError(f"Unsupported transport: {server.transport}")

            server.state = MCPServerState.CONNECTED
            server.connected_at = datetime.now(timezone.utc)
            self._mcp_metrics["servers_connected"] += 1
            logger.info("MCP server '%s' connected successfully", name)
            return True

        except Exception as e:
            server.state = MCPServerState.ERROR
            logger.error("Failed to connect MCP server '%s': %s", name, e)
            return False

    async def _connect_stdio(self, server: MCPServerConnection) -> None:
        """
        Connect to an MCP server via stdio transport.
        通过 stdio 传输连接到 MCP 服务器。

        Starts the server process and sets up stdin/stdout communication.
        """
        if not server.command:
            raise ChannelError(f"Server '{server.name}' has no command configured for stdio transport")

        # Build env with inheritance
        proc_env = dict(server.env)

        # Start subprocess
        process = await asyncio.create_subprocess_exec(
            server.command,
            *server.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=proc_env if proc_env else None,
        )

        # Initialize MCP session (simplified; real MCP requires the full handshake)
        # In a full implementation, this would use the mcp Python package
        server._process = process
        server._stdin = process.stdin
        server._stdout = process.stdout

        logger.debug("MCP server '%s' process started (pid=%s)", server.name, process.pid)

    async def _connect_sse(self, server: MCPServerConnection) -> None:
        """
        Connect to an MCP server via SSE (Server-Sent Events) transport.
        通过 SSE 传输连接到 MCP 服务器。

        Args:
            server: The server connection configuration
        """
        if not server.url:
            raise ChannelError(f"Server '{server.name}' has no URL configured for SSE transport")

        # Placeholder for SSE connection logic
        # In a full implementation, this would use aiohttp or similar
        logger.debug("MCP server '%s' SSE connection to %s (stub)", server.name, server.url)

    async def _disconnect_server(self, name: str) -> None:
        """
        Disconnect from a specific MCP server.
        断开与特定 MCP 服务器的连接。
        """
        server = self._servers.get(name)
        if not server or server.state == MCPServerState.DISCONNECTED:
            return

        logger.info("Disconnecting MCP server '%s'...", name)

        if server._process:
            try:
                server._process.terminate()
                await asyncio.wait_for(server._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                server._process.kill()
            except Exception as e:
                logger.warning("Error terminating MCP server '%s': %s", name, e)

        server.state = MCPServerState.DISCONNECTED
        server._process = None
        server._stdin = None
        server._stdout = None
        self._mcp_metrics["servers_disconnected"] += 1
        logger.info("MCP server '%s' disconnected", name)

    # ------------------------------------------------------------------
    # Tool Discovery
    # ------------------------------------------------------------------

    async def discover_tools(self, server_name: Optional[str] = None) -> int:
        """
        Discover available tools from MCP servers.
        从 MCP 服务器发现可用工具。

        Args:
            server_name: Optional server to discover from (discover all if None)

        Returns:
            Number of tools discovered
        """
        targets = [server_name] if server_name else list(self._servers.keys())
        total_discovered = 0

        for name in targets:
            server = self._servers.get(name)
            if not server or not server.is_connected:
                continue

            try:
                # Simulate tool discovery; real MCP would use list_tools()
                # In production, this calls the MCP protocol's tools/list
                discovered = await self._fetch_server_tools(server)
                server.tools = {}

                for tool_def in discovered:
                    tool = self._build_tool(tool_def, server)
                    server.tools[tool.name] = tool
                    self._tools_cache[tool.full_name] = tool
                    self._setup_tool_executor(tool)

                total_discovered += len(discovered)
                logger.info(
                    "Discovered %d tools from MCP server '%s'",
                    len(discovered), name,
                )

            except Exception as e:
                logger.error("Failed to discover tools from '%s': %s", name, e)

        self._mcp_metrics["tools_discovered"] = len(self._tools_cache)
        return total_discovered

    async def _fetch_server_tools(self, server: MCPServerConnection) -> List[Dict[str, Any]]:
        """
        Fetch tool definitions from an MCP server.
        从 MCP 服务器获取工具定义。

        In production, this sends a tools/list request via the MCP protocol.
        For now, returns an empty list (tools must be provided via config).

        生产环境中通过 MCP 协议发送 tools/list 请求。
        当前返回空列表 (工具需通过配置提供)。
        """
        # In a real implementation, this would use the MCP protocol:
        #   request = {"jsonrpc": "2.0", "method": "tools/list", ...}
        #   response = await self._send_mcp_request(server, request)
        #
        # For now, check if tools are defined in config
        configured_tools = server.config.get("tools", [])
        return configured_tools

    def _build_tool(self, tool_def: Dict[str, Any], server: MCPServerConnection) -> MCPTool:
        """
        Build an MCPTool from a raw tool definition.
        从原始工具定义构建 MCPTool。

        Applies namespace isolation (mcp__server__tool) and security validation.
        """
        name = tool_def.get("name", "unknown")
        description = tool_def.get("description", "")
        input_schema = tool_def.get("input_schema", tool_def.get("parameters", {}))

        # Apply namespace isolation
        if self._enable_namespace:
            full_name = f"mcp__{server.name}__{name}"
        else:
            full_name = name

        # Security check
        allowed = self._is_tool_allowed(full_name)

        return MCPTool(
            name=name,
            full_name=full_name,
            server_name=server.name,
            description=description,
            input_schema=input_schema,
            allowed=allowed,
        )

    def _setup_tool_executor(self, tool: MCPTool) -> None:
        """
        Set up the execution function for a tool.
        为工具设置执行函数。

        In production, this wraps an MCP tools/call request.
        Currently stores metadata for external execution.
        """
        async def execute(**kwargs: Any) -> Dict[str, Any]:
            return await self._execute_tool_internal(tool, kwargs)

        self._tool_executors[tool.full_name] = execute

    async def _execute_tool_internal(
        self, tool: MCPTool, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Internal tool execution via MCP protocol.
        通过 MCP 协议内部执行工具。

        Args:
            tool: The tool to execute
            arguments: Tool arguments

        Returns:
            Tool execution result

        Raises:
            ChannelError: If execution fails or security check fails
        """
        # Security check
        if not tool.allowed:
            self._mcp_metrics["security_blocks"] += 1
            raise ChannelError(f"Tool '{tool.full_name}' is not allowed")

        if tool.full_name not in self._tools_cache:
            raise ChannelError(f"Tool '{tool.full_name}' not found")

        server = self._servers.get(tool.server_name)
        if not server or not server.is_connected:
            raise ChannelConnectionError(f"MCP server '{tool.server_name}' is not connected")

        # Validate arguments against schema
        self._validate_arguments(tool.input_schema, arguments)

        # Execute via MCP protocol
        # In production: send tools/call request to the MCP server
        try:
            self._mcp_metrics["tools_executed"] += 1
            result = await self._send_tool_call(server, tool, arguments)
            return result
        except Exception as e:
            self._mcp_metrics["tools_failed"] += 1
            logger.error("Tool '%s' execution failed: %s", tool.full_name, e)
            raise

    async def _send_tool_call(
        self, server: MCPServerConnection, tool: MCPTool, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send a tools/call request to the MCP server.
        向 MCP 服务器发送 tools/call 请求。

        In production, this implements the full MCP JSON-RPC call.
        For now, returns a placeholder result.
        """
        # Placeholder for MCP protocol call:
        # request = {
        #     "jsonrpc": "2.0",
        #     "method": "tools/call",
        #     "params": {"name": tool.name, "arguments": arguments},
        #     "id": str(uuid.uuid4()),
        # }
        # response = await self._send_mcp_request(server, request)
        #
        # For now, simulate a response
        logger.debug("Tool call: %s(%s)", tool.full_name, arguments)
        return {
            "content": [{"type": "text", "text": f"Executed {tool.full_name}"}],
            "is_error": False,
        }

    def _validate_arguments(self, schema: Dict[str, Any], arguments: Dict[str, Any]) -> None:
        """
        Validate tool arguments against JSON Schema.
        根据 JSON Schema 验证工具参数。

        Performs basic type checking and required field validation.
        In production, use a JSON Schema validation library like `jsonschema`.
        """
        if not schema:
            return

        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # Check required fields
        for field_name in required:
            if field_name not in arguments:
                raise ValueError(f"Missing required argument: '{field_name}'")

        # Basic type checking
        for field_name, value in arguments.items():
            if field_name in properties:
                expected_type = properties[field_name].get("type", "")
                if expected_type == "string" and not isinstance(value, str):
                    raise ValueError(
                        f"Argument '{field_name}' should be string, got {type(value).__name__}"
                    )
                elif expected_type == "integer" and not isinstance(value, int):
                    raise ValueError(
                        f"Argument '{field_name}' should be integer, got {type(value).__name__}"
                    )
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    raise ValueError(
                        f"Argument '{field_name}' should be number, got {type(value).__name__}"
                    )
                elif expected_type == "boolean" and not isinstance(value, bool):
                    raise ValueError(
                        f"Argument '{field_name}' should be boolean, got {type(value).__name__}"
                    )

    # ------------------------------------------------------------------
    # Tool Access
    # ------------------------------------------------------------------

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get a tool by its full name.
        根据完整名称获取工具。"""
        return self._tools_cache.get(name)

    def get_tools(self, server_name: Optional[str] = None) -> List[MCPTool]:
        """
        Get all discovered tools, optionally filtered by server.
        获取所有已发现的工具，可选地按服务器过滤。

        Args:
            server_name: Optional server name filter

        Returns:
            List of MCPTool objects
        """
        if server_name:
            return [
                t for t in self._tools_cache.values()
                if t.server_name == server_name
            ]
        return list(self._tools_cache.values())

    def list_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get all tool schemas in OpenAI-compatible format.
        获取所有工具的 OpenAI 兼容格式 Schema。

        Useful for passing to LLM APIs that support function calling.
        """
        return [
            tool.to_openai_tool_schema()
            for tool in self._tools_cache.values()
            if tool.allowed
        ]

    async def execute_tool(
        self, full_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool by its fully qualified name.
        根据完全限定名称执行工具。

        Args:
            full_name: Tool's fully qualified name (mcp__server__tool)
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        executor = self._tool_executors.get(full_name)
        if not executor:
            raise ChannelError(f"No executor found for tool '{full_name}'")

        return await executor(**arguments)

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------

    def set_tool_allowlist(self, tool_names: Set[str]) -> None:
        """Set the tool allowlist (replaces existing).
        设置工具白名单 (替换现有)。"""
        self._tool_allowlist = set(tool_names)
        # Re-evaluate all tools
        for tool in self._tools_cache.values():
            tool.allowed = self._is_tool_allowed(tool.full_name)

    def set_tool_blocklist(self, tool_names: Set[str]) -> None:
        """Set the tool blocklist (replaces existing).
        设置工具黑名单 (替换现有)。"""
        self._tool_blocklist = set(tool_names)
        # Re-evaluate all tools
        for tool in self._tools_cache.values():
            tool.allowed = self._is_tool_allowed(tool.full_name)

    def allow_tool(self, full_name: str) -> None:
        """Explicitly allow a tool.
        显式允许一个工具。"""
        tool = self._tools_cache.get(full_name)
        if tool:
            tool.allowed = True
        if full_name in self._tool_blocklist:
            self._tool_blocklist.remove(full_name)

    def block_tool(self, full_name: str) -> None:
        """Explicitly block a tool.
        显式阻止一个工具。"""
        tool = self._tools_cache.get(full_name)
        if tool:
            tool.allowed = False
        self._tool_blocklist.add(full_name)

    def _is_tool_allowed(self, full_name: str) -> bool:
        """
        Check if a tool is allowed by the security policy.
        根据安全策略检查工具是否允许。

        Blocklist takes precedence. If allowlist is set, the tool
        must be in it to be allowed.
        """
        if full_name in self._tool_blocklist:
            return False
        if self._tool_allowlist:
            return full_name in self._tool_allowlist
        return True

    # ------------------------------------------------------------------
    # Namespace Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_full_name(full_name: str) -> Tuple[str, str]:
        """
        Parse a fully qualified tool name into server and tool parts.
        将完全限定的工具名称解析为服务器和工具部分。

        Args:
            full_name: e.g., "mcp__filesystem__read_file"

        Returns:
            Tuple of (server_name, tool_name)
        """
        parts = full_name.split("__")
        if len(parts) >= 3 and parts[0] == "mcp":
            return parts[1], "__".join(parts[2:])
        return "", full_name

    @staticmethod
    def build_full_name(server_name: str, tool_name: str) -> str:
        """Build a fully qualified tool name.
        构建完全限定的工具名称。"""
        return f"mcp__{server_name}__{tool_name}"

    # ------------------------------------------------------------------
    # Metrics & Health
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        """Get MCP adapter metrics.
        获取 MCP 适配器指标。"""
        metrics = dict(self._mcp_metrics)
        metrics["servers"] = len(self._servers)
        metrics["connected_servers"] = sum(
            1 for s in self._servers.values() if s.is_connected
        )
        metrics["tools_total"] = len(self._tools_cache)
        metrics["tools_allowed"] = sum(1 for t in self._tools_cache.values() if t.allowed)
        return metrics

    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the MCP adapter.
        执行 MCP 适配器健康检查。"""
        connected = sum(1 for s in self._servers.values() if s.is_connected)
        return {
            "name": self.name,
            "state": self.state.value,
            "servers_connected": connected,
            "servers_total": len(self._servers),
            "tools_discovered": len(self._tools_cache),
            "healthy": self.state == ChannelState.CONNECTED,
        }

    def __repr__(self) -> str:
        return (
            f"<MCPAdapter name='{self.name}' "
            f"servers={len(self._servers)} "
            f"tools={len(self._tools_cache)}>"
        )
