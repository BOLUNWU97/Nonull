"""
ADVISORY NOTE — The hook system supports the project's deny-first safety
pipeline (PreAction / PostAction, PreToolUse / PostToolUse, PermissionRequest
/ PermissionDenied). These hooks are ADVISORY observability and gating
points, not certified ISO 26262 safety mechanisms. Hooks do NOT implement
freedom from interference, MC/DC, or any certified safety element. See
README §Disclaimer and `safety.disclaimer: advisory_only` in config.

Nonull — Hook System
==============================
钩子系统 | Lifecycle Hook System

A comprehensive hook system inspired by Claude Code's 38+ hook events,
providing lifecycle hooks for every major agent operation.

受 Claude Code 38+ 钩子事件启发的全面钩子系统。

DESIGN PHILOSOPHY (设计理念):
    Every significant lifecycle event in the agent has a pre-hook and a
    post-hook. Hooks can be Shell commands, HTTP calls, LLM prompts, or
    Agent sub-tasks. This enables observability, security, customization,
    and extension without modifying core agent code.

    智能体中的每个重要生命周期事件都有 pre-hook 和 post-hook。
    钩子可以是 Shell 命令、HTTP 调用、LLM 提示词或智能体子任务。

Hook Events (38+ lifecycle events):
    PreAction / PostAction          动作执行前后
    PreToolUse / PostToolUse        工具使用前后
    SessionStart / SessionEnd       会话开始/结束
    PermissionRequest / PermissionDenied  权限请求/拒绝
    PreCompact / PostCompact        上下文压缩前后
    AgentStart / AgentStop          智能体启动/停止
    PreThink / PostThink            思考前后
    PreRespond / PostRespond        响应生成前后
    PreStream / PostStream          流式输出前后
    PreMemoryRead / PostMemoryRead  内存读取前后
    PreMemoryWrite / PostMemoryWrite 内存写入前后
    PrePlan / PostPlan              规划阶段前后
    PreEval / PostEval              评估阶段前后
    Error / Recovery                错误与恢复
    PreCompact / PostCompact        上下文压缩前后
    HookError                       钩子自身异常

Hook Types (4 types):
    SHELL  - Execute shell/system commands
    HTTP   - Make HTTP requests to external services
    LLM    - Inject additional prompts into the LLM context
    AGENT  - Run agent sub-tasks with their own lifecycle

Key features:
    - 38+ hook events for complete lifecycle coverage
    - 4 hook types: SHELL, HTTP, LLM, AGENT
    - Priority-based execution ordering
    - Hook chaining with pipeline pattern (output feeds next input)
    - Graduated context cost model (lightweight to heavyweight hooks)
    - Pre/Post pairs for every major lifecycle event
    - Async-first design
    - Comprehensive error handling with timeout control
    - Metrics and observability for all hook executions
"""

from __future__ import annotations

import asyncio
import enum
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


# ===================================================================
# Enums and Constants
# ===================================================================

# Define ALL 38+ hook event names
HOOK_EVENTS: List[str] = [
    # Action lifecycle
    "PreAction",
    "PostAction",
    # Tool lifecycle
    "PreToolUse",
    "PostToolUse",
    # Session lifecycle
    "SessionStart",
    "SessionEnd",
    # Permission events
    "PermissionRequest",
    "PermissionDenied",
    # Context compaction
    "PreCompact",
    "PostCompact",
    # Agent lifecycle
    "AgentStart",
    "AgentStop",
    # Thinking phase
    "PreThink",
    "PostThink",
    # Response generation
    "PreRespond",
    "PostRespond",
    # Streaming
    "PreStream",
    "PostStream",
    # Memory operations
    "PreMemoryRead",
    "PostMemoryRead",
    "PreMemoryWrite",
    "PostMemoryWrite",
    # Planning
    "PrePlan",
    "PostPlan",
    # Evaluation
    "PreEval",
    "PostEval",
    # Error handling
    "Error",
    "Recovery",
    # Hook system events
    "HookError",
    "PreHookChain",
    "PostHookChain",
    # Configuration events
    "PreConfigChange",
    "PostConfigChange",
    # File operations
    "PreFileRead",
    "PostFileRead",
    "PreFileWrite",
    "PostFileWrite",
    # External communication
    "PreExternalCall",
    "PostExternalCall",
    # Shutdown
    "PreShutdown",
]

# Additional aliases for convenience
HOOK_EVENT_ALIASES: Dict[str, str] = {
    "BeforeAction": "PreAction",
    "AfterAction": "PostAction",
    "BeforeTool": "PreToolUse",
    "AfterTool": "PostToolUse",
    "BeforeCompact": "PreCompact",
    "AfterCompact": "PostCompact",
    "BeforeThink": "PreThink",
    "AfterThink": "PostThink",
    "BeforeRespond": "PreRespond",
    "AfterRespond": "PostRespond",
    "BeforeStream": "PreStream",
    "AfterStream": "PostStream",
    "BeforePlan": "PrePlan",
    "AfterPlan": "PostPlan",
    "BeforeEval": "PreEval",
    "AfterEval": "PostEval",
    "BeforeSessionStart": "SessionStart",
    "AfterSessionEnd": "SessionEnd",
}


class HookType(Enum):
    """Type of hook execution strategy.
    钩子执行策略类型。"""
    SHELL = "shell"       # Execute shell/system command
    HTTP = "http"         # Make HTTP request
    LLM = "llm"           # Inject prompt into LLM context
    AGENT = "agent"       # Run agent sub-task


class HookPriority(Enum):
    """Execution priority for hooks. Higher priority runs first.
    钩子执行优先级。优先级越高越先执行。"""
    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100
    CRITICAL = 1000


# ===================================================================
# Data Classes
# ===================================================================


@dataclass
class HookContext:
    """
    Context data passed to every hook execution.
    传递给每个钩子执行的上下文数据。

    Attributes:
        event: The hook event name (e.g., "PreAction")
        hook_id: Unique ID of the hook being executed
        timestamp: When the hook was triggered
        session_id: Current agent session ID
        conversation_id: Current conversation ID
        data: Arbitrary data payload relevant to the event
        previous_results: Results from previous hooks in the chain
        metadata: Additional context metadata
        agent_state: Snapshot of agent state at hook time
    """
    event: str
    hook_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str = ""
    conversation_id: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    previous_results: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    agent_state: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event,
            "hook_id": self.hook_id,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "data": self.data,
            "previous_results": self.previous_results,
            "metadata": self.metadata,
        }


@dataclass
class HookResult:
    """
    Result of a single hook execution.
    单个钩子执行的结果。

    Attributes:
        hook_id: ID of the hook that ran
        event: The hook event
        success: Whether execution succeeded
        output: Output data from the hook
        error: Error message if failed
        duration_ms: Execution duration in milliseconds
        timestamp: When execution completed
        transformed_data: Modified data for pipeline chaining
    """
    hook_id: str
    event: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    transformed_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook_id": self.hook_id,
            "event": self.event,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class RegisteredHook:
    """
    A registered hook with its configuration and execution logic.
    已注册的钩子及其配置和执行逻辑。

    Attributes:
        hook_id: Unique identifier for this hook
        event: The lifecycle event to hook into
        hook_type: Type of hook (SHELL, HTTP, LLM, AGENT)
        name: Human-readable name
        priority: Execution priority
        config: Type-specific configuration
        enabled: Whether this hook is active
        timeout: Max execution time in seconds
        description: Description of what this hook does
        created_at: When this hook was registered
        run_count: How many times this hook has run
        max_retries: Max retry attempts on failure
        chain: If True, output passes to next hook as input
    """
    hook_id: str
    event: str
    hook_type: HookType
    name: str
    priority: HookPriority = HookPriority.NORMAL
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    timeout: float = 30.0
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    run_count: int = 0
    max_retries: int = 0
    chain: bool = False
    tags: List[str] = field(default_factory=list)
    _handler: Optional[Callable] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook_id": self.hook_id,
            "event": self.event,
            "hook_type": self.hook_type.value,
            "name": self.name,
            "priority": self.priority.value,
            "enabled": self.enabled,
            "timeout": self.timeout,
            "description": self.description,
            "run_count": self.run_count,
            "chain": self.chain,
            "tags": self.tags,
        }


class HookError(Exception):
    """Exception raised when a hook execution fails.
    钩子执行失败时引发的异常。"""


# ===================================================================
# Graduated Context Cost Model
# ===================================================================

# Context cost multipliers per hook type
# These represent the relative "weight" of each hook type on the context window
HOOK_CONTEXT_COST: Dict[HookType, float] = {
    HookType.SHELL: 0.1,   # Lightweight - result only
    HookType.HTTP: 0.3,    # Medium - request + response headers
    HookType.LLM: 0.6,     # Heavy - full prompt injection
    HookType.AGENT: 0.8,   # Heaviest - sub-agent lifecycle
}

# Graduated context budget for hooks (percentage of total context)
# Lower-priority hooks get less budget
HOOK_BUDGET_TIER: Dict[HookPriority, float] = {
    HookPriority.LOWEST: 0.05,
    HookPriority.LOW: 0.10,
    HookPriority.NORMAL: 0.15,
    HookPriority.HIGH: 0.25,
    HookPriority.HIGHEST: 0.35,
    HookPriority.CRITICAL: 0.50,
}


# ===================================================================
# Hook Registry
# ===================================================================


class HookRegistry:
    """
    Registry for managing hook registration, lookup, and lifecycle.
    用于管理钩子注册、查找和生命周期的注册表。

    Maintains an ordered mapping of events to hooks and provides
    query methods for filtering by type, priority, tags, etc.
    """

    def __init__(self) -> None:
        # event_name -> list of RegisteredHook (sorted by priority desc)
        self._hooks: Dict[str, List[RegisteredHook]] = {}
        # hook_id -> RegisteredHook (flat lookup)
        self._hook_map: Dict[str, RegisteredHook] = {}

    def register(
        self,
        event: str,
        hook_type: HookType,
        name: str,
        priority: HookPriority = HookPriority.NORMAL,
        config: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
        description: str = "",
        enabled: bool = True,
        chain: bool = False,
        tags: Optional[List[str]] = None,
        handler: Optional[Callable] = None,
    ) -> RegisteredHook:
        """
        Register a new hook for a lifecycle event.
        为生命周期事件注册一个新钩子。

        Args:
            event: Hook event name (e.g., "PreAction", "PostToolUse")
            hook_type: Type of hook execution
            name: Human-readable name for this hook
            priority: Execution priority (higher runs first)
            config: Type-specific configuration
            timeout: Max execution time in seconds
            description: Description of the hook's purpose
            enabled: Whether the hook starts enabled
            chain: If True, output feeds into next hook's input
            tags: Optional tags for filtering/grouping
            handler: Optional callable handler (for AGENT type)

        Returns:
            The registered RegisteredHook instance

        Raises:
            ValueError: If the event name is invalid
        """
        # Resolve event alias
        event = self._resolve_event(event)

        hook = RegisteredHook(
            hook_id=f"hook_{uuid.uuid4().hex[:12]}",
            event=event,
            hook_type=hook_type,
            name=name,
            priority=priority,
            config=config or {},
            timeout=timeout,
            description=description,
            enabled=enabled,
            chain=chain,
            tags=tags or [],
            _handler=handler,
        )

        # Add to event list, sorted by priority
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(hook)
        self._hooks[event].sort(key=lambda h: h.priority.value, reverse=True)

        # Flat map
        self._hook_map[hook.hook_id] = hook

        logger.debug(
            "Hook registered: '%s' on '%s' (type=%s, priority=%s)",
            name, event, hook_type.value, priority.name,
        )
        return hook

    def unregister(self, hook_id: str) -> Optional[RegisteredHook]:
        """
        Unregister a hook by its ID.
        根据 ID 注销钩子。

        Args:
            hook_id: The hook's unique identifier

        Returns:
            The removed hook, or None if not found
        """
        hook = self._hook_map.pop(hook_id, None)
        if hook:
            event_list = self._hooks.get(hook.event, [])
            if hook in event_list:
                event_list.remove(hook)
            logger.debug("Hook unregistered: '%s' (%s)", hook.name, hook_id)
        return hook

    def get_hook(self, hook_id: str) -> Optional[RegisteredHook]:
        """Get a registered hook by ID.
        根据 ID 获取已注册的钩子。"""
        return self._hook_map.get(hook_id)

    def get_hooks(
        self,
        event: Optional[str] = None,
        hook_type: Optional[HookType] = None,
        enabled_only: bool = True,
        tags: Optional[List[str]] = None,
    ) -> List[RegisteredHook]:
        """
        Get hooks matching the given filters.
        获取符合给定过滤条件的钩子。

        Args:
            event: Filter by event name
            hook_type: Filter by hook type
            enabled_only: Only return enabled hooks
            tags: Filter by tags (matches any tag)

        Returns:
            List of matching hooks, sorted by priority
        """
        if event:
            event = self._resolve_event(event)
            hooks = list(self._hooks.get(event, []))
        else:
            # Flatten all hooks
            hooks = []
            for evt_list in self._hooks.values():
                hooks.extend(evt_list)

        # Apply filters
        if enabled_only:
            hooks = [h for h in hooks if h.enabled]
        if hook_type:
            hooks = [h for h in hooks if h.hook_type == hook_type]
        if tags:
            hooks = [h for h in hooks if any(t in h.tags for t in tags)]

        return sorted(hooks, key=lambda h: h.priority.value, reverse=True)

    def get_events(self) -> List[str]:
        """Get all event names that have at least one hook registered.
        获取所有已注册钩子的事件名称列表。"""
        return list(self._hooks.keys())

    def get_all_events(self) -> List[str]:
        """Get all known event names (including those without hooks).
        获取所有已知的事件名称 (包括没有钩子的)。"""
        return list(HOOK_EVENTS)

    def enable(self, hook_id: str) -> bool:
        """Enable a hook by ID.
        启用指定 ID 的钩子。"""
        hook = self._hook_map.get(hook_id)
        if hook:
            hook.enabled = True
            return True
        return False

    def disable(self, hook_id: str) -> bool:
        """Disable a hook by ID.
        禁用指定 ID 的钩子。"""
        hook = self._hook_map.get(hook_id)
        if hook:
            hook.enabled = False
            return True
        return False

    def count(self, event: Optional[str] = None) -> int:
        """Count registered hooks, optionally filtered by event.
        统计已注册的钩子数量，可选择按事件过滤。"""
        if event:
            event = self._resolve_event(event)
            return len(self._hooks.get(event, []))
        return len(self._hook_map)

    def clear(self) -> None:
        """Unregister all hooks.
        注销所有钩子。"""
        self._hooks.clear()
        self._hook_map.clear()
        logger.debug("All hooks cleared from registry")

    @staticmethod
    def _resolve_event(event: str) -> str:
        """Resolve event alias to canonical name.
        将事件别名解析为规范名称。"""
        return HOOK_EVENT_ALIASES.get(event, event)

    def __repr__(self) -> str:
        return f"<HookRegistry events={len(self._hooks)} hooks={len(self._hook_map)}>"


# ===================================================================
# Hook Executors (per type)
# ===================================================================


class ShellHookExecutor:
    """Execute SHELL-type hooks by running shell commands.
    执行 SHELL 类型钩子：运行 shell 命令。"""

    @staticmethod
    async def execute(hook: RegisteredHook, context: HookContext) -> HookResult:
        """
        Execute a shell command hook.
        执行 shell 命令钩子。

        Config fields:
            command: Shell command to run (supports {data} and {context} placeholders)
            shell: Shell to use (default "bash" on Linux/Mac, "powershell" on Windows)
            cwd: Working directory
            capture_output: Whether to capture stdout/stderr (default True)
        """
        start_time = time.monotonic()
        command = hook.config.get("command", "")
        shell = hook.config.get("shell", "")
        cwd = hook.config.get("cwd", None)
        capture = hook.config.get("capture_output", True)

        if not command:
            return HookResult(
                hook_id=hook.hook_id,
                event=hook.event,
                success=False,
                error="No command configured",
                duration_ms=0.0,
            )

        # Format command with context data
        try:
            formatted_command = command.format(
                data=json.dumps(context.data),
                event=context.event,
                session_id=context.session_id,
                **{k: str(v) for k, v in context.data.items()},
            )
        except KeyError as e:
            return HookResult(
                hook_id=hook.hook_id,
                event=hook.event,
                success=False,
                error=f"Command formatting error: {e}",
                duration_ms=0.0,
            )

        try:
            # Execute command
            process = await asyncio.create_subprocess_shell(
                formatted_command,
                stdout=asyncio.subprocess.PIPE if capture else None,
                stderr=asyncio.subprocess.PIPE if capture else None,
                cwd=cwd,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=hook.timeout
            )

            duration = (time.monotonic() - start_time) * 1000
            success = process.returncode == 0

            output = {}
            if capture:
                output["stdout"] = stdout.decode("utf-8", errors="replace") if stdout else ""
                output["stderr"] = stderr.decode("utf-8", errors="replace") if stderr else ""
            output["returncode"] = process.returncode

            # Try to parse stdout as JSON for chaining
            transformed = None
            if hook.chain and capture and output.get("stdout"):
                try:
                    transformed = json.loads(output["stdout"])
                except (json.JSONDecodeError, TypeError):
                    transformed = {"text": output["stdout"]}

            return HookResult(
                hook_id=hook.hook_id,
                event=hook.event,
                success=success,
                output=output,
                error=output.get("stderr") if not success else None,
                duration_ms=duration,
                transformed_data=transformed,
            )

        except asyncio.TimeoutError:
            duration = (time.monotonic() - start_time) * 1000
            logger.warning("Shell hook '%s' timed out after %ss", hook.name, hook.timeout)
            return HookResult(
                hook_id=hook.hook_id,
                event=hook.event,
                success=False,
                error=f"Timed out after {hook.timeout}s",
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.monotonic() - start_time) * 1000
            return HookResult(
                hook_id=hook.hook_id,
                event=hook.event,
                success=False,
                error=str(e),
                duration_ms=duration,
            )


class HTTPHookExecutor:
    """Execute HTTP-type hooks by making web requests.
    执行 HTTP 类型钩子：发起 Web 请求。"""

    @staticmethod
    async def execute(hook: RegisteredHook, context: HookContext) -> HookResult:
        """
        Execute an HTTP request hook.
        执行 HTTP 请求钩子。

        Config fields:
            url: Request URL (supports {data} placeholders)
            method: HTTP method (default "POST")
            headers: Optional request headers
            body: Request body template
            auth: Optional auth configuration
        """
        start_time = time.monotonic()
        url = hook.config.get("url", "")
        method = hook.config.get("method", "POST").upper()
        headers = hook.config.get("headers", {})
        body_template = hook.config.get("body", {})

        if not url:
            return HookResult(
                hook_id=hook.hook_id,
                event=hook.event,
                success=False,
                error="No URL configured",
                duration_ms=0.0,
            )

        # Format URL and body with context data
        try:
            formatted_url = url.format(
                data=json.dumps(context.data),
                event=context.event,
                session_id=context.session_id,
                **{k: str(v) for k, v in context.data.items()},
            )
        except KeyError as e:
            return HookResult(
                hook_id=hook.hook_id,
                event=hook.event,
                success=False,
                error=f"URL formatting error: {e}",
                duration_ms=0.0,
            )

        # Placeholder for actual HTTP call
        # In production, use aiohttp or httpx:
        #   async with aiohttp.ClientSession() as session:
        #       async with session.request(method, url, json=body, headers=headers) as resp:
        #           response_data = await resp.json()

        duration = (time.monotonic() - start_time) * 1000
        logger.debug(
            "HTTP hook '%s': %s %s (stub - install aiohttp for real execution)",
            hook.name, method, formatted_url,
        )

        return HookResult(
            hook_id=hook.hook_id,
            event=hook.event,
            success=True,
            output={
                "url": formatted_url,
                "method": method,
                "note": "HTTP client not configured. Install aiohttp or httpx.",
            },
            duration_ms=duration,
        )


class LLMHookExecutor:
    """Execute LLM-type hooks by injecting prompts into the LLM context.
    执行 LLM 类型钩子：将提示词注入 LLM 上下文。"""

    @staticmethod
    async def execute(hook: RegisteredHook, context: HookContext) -> HookResult:
        """
        Execute an LLM prompt injection hook.
        执行 LLM 提示词注入钩子。

        Config fields:
            prompt: The prompt text to inject (supports {data} placeholders)
            role: Message role ("system", "user", "assistant")
            position: Injection position ("before_main", "after_main", "replace")
            template: Jinja2-like template for the prompt
        """
        start_time = time.monotonic()
        prompt_template = hook.config.get("prompt", "")
        role = hook.config.get("role", "system")
        position = hook.config.get("position", "before_main")

        if not prompt_template:
            return HookResult(
                hook_id=hook.hook_id,
                event=hook.event,
                success=False,
                error="No prompt configured",
                duration_ms=0.0,
            )

        # Format prompt with context data
        try:
            formatted_prompt = prompt_template.format(
                data=json.dumps(context.data, indent=2),
                event=context.event,
                session_id=context.session_id,
                conversation_id=context.conversation_id,
                **{k: str(v) for k, v in context.data.items()},
            )
        except KeyError as e:
            return HookResult(
                hook_id=hook.hook_id,
                event=hook.event,
                success=False,
                error=f"Prompt formatting error: {e}",
                duration_ms=0.0,
            )

        duration = (time.monotonic() - start_time) * 1000

        result = HookResult(
            hook_id=hook.hook_id,
            event=hook.event,
            success=True,
            output={
                "prompt": formatted_prompt,
                "role": role,
                "position": position,
            },
            duration_ms=duration,
        )

        # Set transformed_data for chaining if enabled
        if hook.chain:
            result.transformed_data = {
                "injected_prompt": formatted_prompt,
                "role": role,
                "position": position,
            }

        logger.debug(
            "LLM hook '%s': %s prompt (%d chars, position=%s)",
            hook.name, role, len(formatted_prompt), position,
        )
        return result


class AgentHookExecutor:
    """Execute AGENT-type hooks by running agent sub-tasks.
    执行 AGENT 类型钩子：运行智能体子任务。"""

    @staticmethod
    async def execute(hook: RegisteredHook, context: HookContext) -> HookResult:
        """
        Execute an agent sub-task hook.
        执行智能体子任务钩子。

        Config fields:
            task: Task description for the sub-agent
            model: Model to use for the sub-agent
            max_tokens: Max tokens for sub-agent response
            tools: Tools available to the sub-agent
        """
        start_time = time.monotonic()

        # If a callable handler is provided, use it
        if hook._handler:
            try:
                result = await hook._handler(context)
                duration = (time.monotonic() - start_time) * 1000
                return HookResult(
                    hook_id=hook.hook_id,
                    event=hook.event,
                    success=True,
                    output=result,
                    duration_ms=duration,
                    transformed_data=result if hook.chain else None,
                )
            except Exception as e:
                duration = (time.monotonic() - start_time) * 1000
                return HookResult(
                    hook_id=hook.hook_id,
                    event=hook.event,
                    success=False,
                    error=str(e),
                    duration_ms=duration,
                )

        # Otherwise, use config-defined task
        task = hook.config.get("task", "")
        if not task:
            return HookResult(
                hook_id=hook.hook_id,
                event=hook.event,
                success=False,
                error="No task or handler configured",
                duration_ms=0.0,
            )

        duration = (time.monotonic() - start_time) * 1000
        logger.debug("Agent hook '%s': task='%s' (stub)", hook.name, task)

        return HookResult(
            hook_id=hook.hook_id,
            event=hook.event,
            success=True,
            output={
                "task": task,
                "status": "dispatched",
                "note": "Agent sub-task execution stub",
            },
            duration_ms=duration,
        )


# ===================================================================
# Hook System (Main)
# ===================================================================


class HookSystem:
    """
    Central hook system for Nonull.
    Nonull 的中央钩子系统。

    Manages hook registration, execution, chaining, and lifecycle.
    Provides the primary API for triggering hooks at every major
    lifecycle event in the agent.

    管理钩子的注册、执行、链式调用和生命周期。
    提供在智能体每个主要生命周期事件触发钩子的主要 API。

    Usage:
        hooks = HookSystem()

        # Register a shell hook
        hooks.register(
            event="PostToolUse",
            hook_type=HookType.SHELL,
            name="log-tool-use",
            config={"command": "echo '{data}' >> tool_usage.log"},
        )

        # Trigger hooks
        results = await hooks.trigger("PreAction", data={"action": "think"})

    Args:
        max_concurrent: Maximum concurrent hook executions
        default_timeout: Default timeout for hooks without explicit timeout
        collect_metrics: Whether to collect execution metrics
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        default_timeout: float = 30.0,
        collect_metrics: bool = True,
    ) -> None:
        self.registry = HookRegistry()
        self._max_concurrent = max_concurrent
        self._default_timeout = default_timeout
        self._collect_metrics = collect_metrics

        # Executors
        self._executors: Dict[HookType, Any] = {
            HookType.SHELL: ShellHookExecutor(),
            HookType.HTTP: HTTPHookExecutor(),
            HookType.LLM: LLMHookExecutor(),
            HookType.AGENT: AgentHookExecutor(),
        }

        # Metrics
        self._metrics: Dict[str, Any] = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_duration_ms": 0.0,
            "executions_by_event": {},
            "executions_by_type": {},
        }

        # Semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)

        logger.info(
            "HookSystem initialized (%d events, max_concurrent=%d)",
            len(HOOK_EVENTS), max_concurrent,
        )

    # ------------------------------------------------------------------
    # Registration API
    # ------------------------------------------------------------------

    def register(
        self,
        event: str,
        hook_type: HookType,
        name: str,
        priority: HookPriority = HookPriority.NORMAL,
        config: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
        description: str = "",
        enabled: bool = True,
        chain: bool = False,
        tags: Optional[List[str]] = None,
        handler: Optional[Callable] = None,
    ) -> RegisteredHook:
        """
        Register a new hook.
        注册一个新钩子。

        Args:
            event: Lifecycle event name (see HOOK_EVENTS)
            hook_type: Type of hook (SHELL, HTTP, LLM, AGENT)
            name: Human-readable name
            priority: Execution priority
            config: Type-specific configuration
            timeout: Max execution time in seconds
            description: Description of the hook's purpose
            enabled: Whether the hook should start enabled
            chain: If True, output is passed to the next hook as input
            tags: Tags for filtering/grouping
            handler: Callable handler (for AGENT hooks)

        Returns:
            The registered hook instance
        """
        return self.registry.register(
            event=event,
            hook_type=hook_type,
            name=name,
            priority=priority,
            config=config,
            timeout=timeout or self._default_timeout,
            description=description,
            enabled=enabled,
            chain=chain,
            tags=tags,
            handler=handler,
        )

    def unregister(self, hook_id: str) -> Optional[RegisteredHook]:
        """Unregister a hook by ID.
        根据 ID 注销钩子。"""
        return self.registry.unregister(hook_id)

    def get_hook(self, hook_id: str) -> Optional[RegisteredHook]:
        """Get a hook by ID.
        根据 ID 获取钩子。"""
        return self.registry.get_hook(hook_id)

    # ------------------------------------------------------------------
    # Hook Triggering (Main Execution API)
    # ------------------------------------------------------------------

    async def trigger(
        self,
        event: str,
        data: Optional[Dict[str, Any]] = None,
        session_id: str = "",
        conversation_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        agent_state: Optional[Dict[str, Any]] = None,
    ) -> List[HookResult]:
        """
        Trigger all hooks registered for a lifecycle event.
        触发为某个生命周期事件注册的所有钩子。

        This is the primary API for executing hooks. It:
            1. Resolves the event name
            2. Gathers all matching hooks sorted by priority
            3. Executes them with concurrency control
            4. Supports pipeline chaining (output -> next input)
            5. Collects execution metrics

        这是执行钩子的主要 API。它：
            1. 解析事件名称
            2. 收集所有匹配的钩子并按优先级排序
            3. 使用并发控制执行钩子
            4. 支持管道链式调用 (输出 -> 下一个输入)
            5. 收集执行指标

        Args:
            event: The lifecycle event name
            data: Event-specific data payload
            session_id: Current session identifier
            conversation_id: Current conversation identifier
            metadata: Additional context metadata
            agent_state: Current agent state snapshot

        Returns:
            List of HookResult objects, one per executed hook
        """
        # Resolve event alias
        event = self._resolve_event(event)

        # Get matching hooks
        hooks = self.registry.get_hooks(event=event, enabled_only=True)
        if not hooks:
            return []

        # Build base context
        base_context = HookContext(
            event=event,
            hook_id="",
            session_id=session_id,
            conversation_id=conversation_id,
            data=data or {},
            metadata=metadata or {},
            agent_state=agent_state,
        )

        # Track chaining: previous_results feeds into next hook
        previous_results: List[HookResult] = []
        all_results: List[HookResult] = []

        logger.debug(
            "Triggering %d hook(s) for event '%s'",
            len(hooks), event,
        )

        # Execute hooks with chaining
        for hook in hooks:
            context = HookContext(
                event=event,
                hook_id=hook.hook_id,
                session_id=session_id,
                conversation_id=conversation_id,
                data=data or {},
                previous_results=[r.to_dict() for r in previous_results],
                metadata=metadata or {},
                agent_state=agent_state,
            )

            # If chain mode and there was a previous result, pass transformed data
            if hook.chain and previous_results:
                last = previous_results[-1]
                if last.transformed_data:
                    context.data.update(last.transformed_data)

            # Execute with concurrency control
            async with self._semaphore:
                result = await self._execute_single(hook, context)

            previous_results.append(result)
            all_results.append(result)

            # Update metrics
            self._update_metrics(event, hook, result)

        logger.debug(
            "Event '%s': %d hooks executed (%d success, %d fail)",
            event, len(all_results),
            sum(1 for r in all_results if r.success),
            sum(1 for r in all_results if not r.success),
        )

        return all_results

    async def trigger_pre_post(
        self,
        event_base: str,
        data: Optional[Dict[str, Any]] = None,
        session_id: str = "",
        conversation_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        agent_state: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[HookResult], List[HookResult]]:
        """
        Trigger both Pre- and Post- hooks for a base event.
        触发某个基础事件的 Pre- 和 Post- 钩子。

        For example, trigger_pre_post("Action") triggers "PreAction"
        and "PostAction" in sequence.

        例如, trigger_pre_post("Action") 会依次触发 "PreAction" 和 "PostAction"。

        Args:
            event_base: Base event name (without Pre/Post prefix)
            data: Event data payload
            session_id: Current session ID
            conversation_id: Current conversation ID
            metadata: Additional metadata
            agent_state: Current agent state

        Returns:
            Tuple of (pre_results, post_results)
        """
        pre_results = await self.trigger(
            event=f"Pre{event_base}",
            data=data,
            session_id=session_id,
            conversation_id=conversation_id,
            metadata=metadata,
            agent_state=agent_state,
        )

        post_results = await self.trigger(
            event=f"Post{event_base}",
            data=data,
            session_id=session_id,
            conversation_id=conversation_id,
            metadata=metadata,
            agent_state=agent_state,
        )

        return pre_results, post_results

    async def _execute_single(
        self, hook: RegisteredHook, context: HookContext
    ) -> HookResult:
        """
        Execute a single hook with timeout and retry.
        执行单个钩子，带超时和重试。

        Args:
            hook: The hook to execute
            context: Execution context

        Returns:
            HookResult with execution outcome
        """
        executor = self._executors.get(hook.hook_type)
        if not executor:
            return HookResult(
                hook_id=hook.hook_id,
                event=hook.event,
                success=False,
                error=f"No executor for hook type: {hook.hook_type}",
            )

        last_result: Optional[HookResult] = None
        max_attempts = hook.max_retries + 1

        for attempt in range(1, max_attempts + 1):
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    executor.execute(hook, context),
                    timeout=hook.timeout,
                )

                # Update hook run count
                hook.run_count += 1

                # If failed and retries remain, try again
                if not result.success and attempt < max_attempts:
                    logger.warning(
                        "Hook '%s' failed (attempt %d/%d), retrying...",
                        hook.name, attempt, max_attempts,
                    )
                    last_result = result
                    continue

                return result

            except asyncio.TimeoutError:
                hook.run_count += 1
                return HookResult(
                    hook_id=hook.hook_id,
                    event=hook.event,
                    success=False,
                    error=f"Timed out after {hook.timeout}s",
                    duration_ms=hook.timeout * 1000,
                )
            except Exception as e:
                if attempt < max_attempts:
                    logger.warning(
                        "Hook '%s' error (attempt %d/%d): %s",
                        hook.name, attempt, max_attempts, e,
                    )
                    last_result = HookResult(
                        hook_id=hook.hook_id,
                        event=hook.event,
                        success=False,
                        error=str(e),
                    )
                    continue
                hook.run_count += 1
                return HookResult(
                    hook_id=hook.hook_id,
                    event=hook.event,
                    success=False,
                    error=str(e),
                )

        # All retries exhausted
        if last_result:
            return last_result
        return HookResult(
            hook_id=hook.hook_id,
            event=hook.event,
            success=False,
            error="Max retries exhausted",
        )

    # ------------------------------------------------------------------
    # Convenience Methods for Common Events
    # ------------------------------------------------------------------

    async def on_action(self, action: str, data: Dict[str, Any]) -> List[HookResult]:
        """Trigger PreAction and PostAction hooks.
        触发 PreAction 和 PostAction 钩子。"""
        results = await self.trigger("PreAction", data={"action": action, **data})
        results += await self.trigger("PostAction", data={"action": action, **data})
        return results

    async def on_tool_use(
        self, tool_name: str, arguments: Dict[str, Any], result: Any = None
    ) -> List[HookResult]:
        """Trigger PreToolUse and PostToolUse hooks.
        触发 PreToolUse 和 PostToolUse 钩子。"""
        data = {"tool": tool_name, "arguments": arguments, "result": result}
        pre = await self.trigger("PreToolUse", data=data)
        post = await self.trigger("PostToolUse", data=data)
        return pre + post

    async def on_session_start(
        self, session_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> List[HookResult]:
        """Trigger SessionStart hooks.
        触发 SessionStart 钩子。"""
        return await self.trigger(
            "SessionStart",
            data={"session_id": session_id, **(metadata or {})},
            session_id=session_id,
        )

    async def on_session_end(
        self, session_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> List[HookResult]:
        """Trigger SessionEnd hooks.
        触发 SessionEnd 钩子。"""
        return await self.trigger(
            "SessionEnd",
            data={"session_id": session_id, **(metadata or {})},
            session_id=session_id,
        )

    async def on_error(
        self, error: Exception, context_data: Optional[Dict[str, Any]] = None
    ) -> List[HookResult]:
        """Trigger Error hook with exception info.
        触发 Error 钩子，包含异常信息。"""
        return await self.trigger(
            "Error",
            data={
                "error_type": type(error).__name__,
                "error_message": str(error),
                **(context_data or {}),
            },
        )

    async def on_recovery(
        self, error: Exception, recovery_action: str
    ) -> List[HookResult]:
        """Trigger Recovery hook after error recovery.
        在错误恢复后触发 Recovery 钩子。"""
        return await self.trigger(
            "Recovery",
            data={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "recovery_action": recovery_action,
            },
        )

    async def on_think(self, thought: str) -> List[HookResult]:
        """Trigger PreThink and PostThink hooks.
        触发 PreThink 和 PostThink 钩子。"""
        data = {"thought": thought}
        pre = await self.trigger("PreThink", data=data)
        post = await self.trigger("PostThink", data=data)
        return pre + post

    async def on_respond(self, response: str) -> List[HookResult]:
        """Trigger PreRespond and PostRespond hooks.
        触发 PreRespond 和 PostRespond 钩子。"""
        data = {"response": response}
        pre = await self.trigger("PreRespond", data=data)
        post = await self.trigger("PostRespond", data=data)
        return pre + post

    async def on_permission_request(
        self, permission: str, user: str
    ) -> List[HookResult]:
        """Trigger PermissionRequest hook.
        触发 PermissionRequest 钩子。"""
        return await self.trigger(
            "PermissionRequest",
            data={"permission": permission, "user": user},
        )

    async def on_permission_denied(
        self, permission: str, reason: str
    ) -> List[HookResult]:
        """Trigger PermissionDenied hook.
        触发 PermissionDenied 钩子。"""
        return await self.trigger(
            "PermissionDenied",
            data={"permission": permission, "reason": reason},
        )

    # ------------------------------------------------------------------
    # Hook Enable/Disable
    # ------------------------------------------------------------------

    def enable(self, hook_id: str) -> bool:
        """Enable a hook by ID.
        启用指定 ID 的钩子。"""
        return self.registry.enable(hook_id)

    def disable(self, hook_id: str) -> bool:
        """Disable a hook by ID.
        禁用指定 ID 的钩子。"""
        return self.registry.disable(hook_id)

    def enable_event(self, event: str) -> int:
        """Enable all hooks for an event.
        启用某个事件的所有钩子。"""
        count = 0
        for hook in self.registry.get_hooks(event=event, enabled_only=False):
            hook.enabled = True
            count += 1
        return count

    def disable_event(self, event: str) -> int:
        """Disable all hooks for an event.
        禁用某个事件的所有钩子。"""
        count = 0
        for hook in self.registry.get_hooks(event=event, enabled_only=False):
            hook.enabled = False
            count += 1
        return count

    # ------------------------------------------------------------------
    # Context Cost Management
    # ------------------------------------------------------------------

    def estimate_context_cost(self, event: Optional[str] = None) -> float:
        """
        Estimate the total context cost of hooks.
        估算钩子的总上下文成本。

        Uses the graduated context cost model: different hook types
        and priorities have different context weights.

        使用渐进式上下文成本模型：不同的钩子类型和优先级具有不同的上下文权重。

        Returns:
            Estimated context cost (0.0 to 1.0 scale)
        """
        hooks = self.registry.get_hooks(event=event, enabled_only=True)
        if not hooks:
            return 0.0

        total_cost = 0.0
        for hook in hooks:
            base_cost = HOOK_CONTEXT_COST.get(hook.hook_type, 0.1)
            budget_tier = HOOK_BUDGET_TIER.get(hook.priority, 0.15)
            total_cost += base_cost * budget_tier

        return min(total_cost, 1.0)

    def optimize_context(self, target_budget: float = 0.3) -> int:
        """
        Optimize hook context usage by disabling low-priority hooks
        when the budget is exceeded.
        当预算超出时，通过禁用低优先级钩子来优化上下文使用。

        Args:
            target_budget: Target context budget (0.0 to 1.0)

        Returns:
            Number of hooks disabled
        """
        current_cost = self.estimate_context_cost()
        if current_cost <= target_budget:
            return 0

        # Get all hooks sorted by priority ascending (lowest first)
        all_hooks = sorted(
            self.registry.get_hooks(enabled_only=True),
            key=lambda h: (h.priority.value, HOOK_CONTEXT_COST.get(h.hook_type, 0.1)),
        )

        disabled = 0
        for hook in all_hooks:
            if current_cost <= target_budget:
                break
            hook.enabled = False
            disabled += 1
            hook_cost = HOOK_CONTEXT_COST.get(hook.hook_type, 0.1)
            budget_tier = HOOK_BUDGET_TIER.get(hook.priority, 0.15)
            current_cost -= hook_cost * budget_tier

        logger.info(
            "Context optimization: disabled %d hooks (cost %.2f -> %.2f)",
            disabled,
            self.estimate_context_cost() + (current_cost if disabled > 0 else 0),
            self.estimate_context_cost(),
        )
        return disabled

    # ------------------------------------------------------------------
    # Metrics & Health
    # ------------------------------------------------------------------

    def _update_metrics(self, event: str, hook: RegisteredHook, result: HookResult) -> None:
        """Update execution metrics.
        更新执行指标。"""
        if not self._collect_metrics:
            return

        self._metrics["total_executions"] += 1
        if result.success:
            self._metrics["successful_executions"] += 1
        else:
            self._metrics["failed_executions"] += 1
        self._metrics["total_duration_ms"] += result.duration_ms

        # By event
        if event not in self._metrics["executions_by_event"]:
            self._metrics["executions_by_event"][event] = {
                "count": 0, "success": 0, "fail": 0, "duration_ms": 0.0,
            }
        ev_metrics = self._metrics["executions_by_event"][event]
        ev_metrics["count"] += 1
        ev_metrics["success"] += 1 if result.success else 0
        ev_metrics["fail"] += 0 if result.success else 1
        ev_metrics["duration_ms"] += result.duration_ms

        # By type
        type_key = hook.hook_type.value
        if type_key not in self._metrics["executions_by_type"]:
            self._metrics["executions_by_type"][type_key] = {
                "count": 0, "success": 0, "fail": 0,
            }
        type_metrics = self._metrics["executions_by_type"][type_key]
        type_metrics["count"] += 1
        type_metrics["success"] += 1 if result.success else 0
        type_metrics["fail"] += 0 if result.success else 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get hook system metrics.
        获取钩子系统指标。"""
        return dict(self._metrics)

    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the hook system.
        执行钩子系统健康检查。"""
        return {
            "total_hooks": self.registry.count(),
            "total_events_with_hooks": len(self.registry.get_events()),
            "available_events": len(HOOK_EVENTS),
            "total_executions": self._metrics.get("total_executions", 0),
            "success_rate": (
                (self._metrics["successful_executions"] / self._metrics["total_executions"] * 100)
                if self._metrics.get("total_executions", 0) > 0 else 100.0
            ),
            "estimated_context_cost": self.estimate_context_cost(),
            "healthy": True,
        }

    def get_event_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        Get a summary of all events and their registered hooks.
        获取所有事件及其已注册钩子的摘要。"""
        summary = {}
        for event in HOOK_EVENTS:
            hooks = self.registry.get_hooks(event=event, enabled_only=False)
            enabled = [h for h in hooks if h.enabled]
            summary[event] = {
                "total": len(hooks),
                "enabled": len(enabled),
                "types": list(set(h.hook_type.value for h in hooks)),
            }
        return summary

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all registered hooks and reset metrics.
        清除所有已注册的钩子并重置指标。"""
        self.registry.clear()
        self._metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_duration_ms": 0.0,
            "executions_by_event": {},
            "executions_by_type": {},
        }
        logger.info("HookSystem cleared")

    @staticmethod
    def _resolve_event(event: str) -> str:
        """Resolve event alias to canonical name.
        将事件别名解析为规范名称。"""
        return HOOK_EVENT_ALIASES.get(event, event)

    @staticmethod
    def list_available_events() -> List[str]:
        """Get the full list of available hook events.
        获取所有可用的钩子事件列表。"""
        return list(HOOK_EVENTS)

    def __repr__(self) -> str:
        return (
            f"<HookSystem events={self.registry.count()} "
            f"executions={self._metrics['total_executions']}>"
        )
