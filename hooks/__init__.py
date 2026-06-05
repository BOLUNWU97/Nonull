"""
Nonull — Hooks Package
===============================
钩子系统 | Lifecycle Hook System

A comprehensive hook system inspired by Claude Code's 38+ hook events,
providing lifecycle hooks for every major agent operation. Supports four
hook types: Shell commands, HTTP endpoints, LLM prompts, and Agent hooks.

受 Claude Code 38+ 钩子事件启发的全面钩子系统，为每个重要的智能体操作
提供生命周期钩子。支持四种钩子类型：Shell 命令、HTTP 端点、LLM 提示词和
智能体钩子。

Hook Types (钩子类型):
    - SHELL:    Execute shell commands
    - HTTP:     Call HTTP endpoints
    - LLM:      Inject LLM prompts
    - AGENT:    Run agent sub-tasks

Lifecycle Events (生命周期事件):
    PreAction / PostAction          — Action execution
    PreToolUse / PostToolUse        — Tool execution
    SessionStart / SessionEnd       — Session lifecycle
    PermissionRequest / Denied      — Permission events
    PreCompact / PostCompact        — Context compaction
    AgentStart / AgentStop          — Agent lifecycle
    Error / Recovery                — Error handling
    PreThink / PostThink            — Thinking phase
    PreRespond / PostRespond        — Response generation
    PreStream / PostStream          — Streaming output
    PreMemoryRead / PostMemoryRead  — Memory operations
    PreMemoryWrite / PostMemoryWrite
    PrePlan / PostPlan              — Planning phase
    PreEval / PostEval              — Evaluation phase

Exports:
    HookSystem       — Central hook registry and execution engine
    HookEvent        — All supported hook event names
    HookType         — Hook type enum (SHELL, HTTP, LLM, AGENT)
    HookPriority     — Execution priority enum
    HookResult       — Result of a hook execution
    HookContext      — Context passed to hooks
    HookRegistry     — Hook registration and management
"""

from hooks.hook_system import (
    HOOK_EVENTS,
    HookContext,
    HookError,
    HookPriority,
    HookRegistry,
    HookResult,
    HookSystem,
    HookType,
    RegisteredHook,
)

__version__ = "1.0.0"
__all__ = [
    "HookSystem",
    "HookType",
    "HookPriority",
    "HookResult",
    "HookContext",
    "HookRegistry",
    "RegisteredHook",
    "HookError",
    "HOOK_EVENTS",
]
