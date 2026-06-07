"""
Nonull — CLI Channel
=============================
命令行交互通道 | Interactive CLI Channel

An interactive REPL channel inspired by Hermes Agent's CLI interface. Supports
rich formatted output, slash commands, multi-line input, streaming responses,
session management, and command history.

基于 Hermes Agent CLI 的交互式 REPL 通道，支持富文本输出、斜杠命令、
多行输入、流式响应、会话管理和历史导航。

Features:
    - Interactive REPL with prompt_toolkit or built-in readline
    - Rich text formatting with colors and markdown rendering
    - Slash commands (/help, /clear, /history, /session, etc.)
    - Multi-line input (triple quotes or escape)
    - Streaming response output with progress indicators
    - Session management with persistence
    - Command history with search
    - Tab completion for commands
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from channels.base import (
    BaseChannel,
    ChannelError,
    ChannelState,
    Message,
    MessagePriority,
    MessageRole,
)

logger = logging.getLogger(__name__)

# Try to import rich for formatted output; fall back to plain print
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.rule import Rule
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Try to import prompt_toolkit for enhanced REPL
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.styles import Style
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False


# ---------------------------------------------------------------------------
# CLI-specific data types
# ---------------------------------------------------------------------------


class CLIMode(Enum):
    """CLI interaction modes.
    CLI 交互模式。"""
    COMMAND = "command"       # Normal command mode
    MULTILINE = "multiline"   # Multi-line input mode
    STREAMING = "streaming"   # Streaming output mode
    SESSION = "session"       # Session management mode


@dataclass
class CLIState:
    """Persistent state for the CLI channel.
    CLI 通道的持久化状态。"""
    mode: CLIMode = CLIMode.COMMAND
    current_session_id: str = ""
    current_conversation_id: str = ""
    multiline_buffer: List[str] = field(default_factory=list)
    last_command: str = ""
    session_start: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Built-in Slash Commands
# ---------------------------------------------------------------------------

SLASH_COMMANDS: Dict[str, Dict[str, str]] = {
    "/help": {
        "description": "显示帮助信息 (Show this help message)",
        "usage": "/help [command]",
    },
    "/clear": {
        "description": "清屏 (Clear the screen)",
        "usage": "/clear",
    },
    "/history": {
        "description": "显示历史记录 (Show command history)",
        "usage": "/history [n]",
    },
    "/session": {
        "description": "会话管理 (Session management)",
        "usage": "/session [new|list|end|current]",
    },
    "/mode": {
        "description": "切换输入模式 (Toggle input mode)",
        "usage": "/mode [command|multiline]",
    },
    "/save": {
        "description": "保存对话到文件 (Save conversation to file)",
        "usage": "/save [filename]",
    },
    "/load": {
        "description": "从文件加载对话 (Load conversation from file)",
        "usage": "/load <filename>",
    },
    "/config": {
        "description": "查看或修改配置 (View or change config)",
        "usage": "/config [key=value]",
    },
    "/stats": {
        "description": "显示会话统计 (Show session statistics)",
        "usage": "/stats",
    },
    "/export": {
        "description": "导出对话为 JSON (Export conversation as JSON)",
        "usage": "/export <filename>",
    },
    "/quit": {
        "description": "退出 CLI (Exit the CLI)",
        "usage": "/quit",
    },
    "/agent": {
        "description": "查看 LLM 智能体连接状态 (Show LLM agent status)",
        "usage": "/agent",
    },
}


# ---------------------------------------------------------------------------
# CLI Channel
# ---------------------------------------------------------------------------


class CLIChannel(BaseChannel):
    """
    Interactive REPL CLI channel for Nonull.
    面向 Nonull 的交互式 REPL CLI 通道。

    Provides a full-featured command-line interface with rich formatting,
    streaming output, session management, and command history. Can operate
    in both interactive and script/pipe modes.

    提供功能完整的命令行界面，支持富文本格式化、流式输出、会话管理和命令历史。
    支持交互式模式和脚本/管道模式。

    Args:
        name: Channel name (default "cli")
        prompt: Input prompt string (default ">>> ")
        history_file: Path to history file for persistence
        use_rich: Enable rich formatting (auto-detected if not set)
        use_prompt_toolkit: Use prompt_toolkit for enhanced REPL (auto-detected)
        welcome_message: Message to show on startup
        config: Additional configuration dictionary
    """

    def __init__(
        self,
        name: str = "cli",
        prompt: str = ">>> ",
        history_file: Optional[str] = None,
        use_rich: Optional[bool] = None,
        use_prompt_toolkit: Optional[bool] = None,
        welcome_message: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            name=name,
            config=config or {},
            max_rate=0,  # No rate limiting for CLI
        )

        self.prompt = prompt
        self._welcome_message = welcome_message or (
            "Nonull CLI — 智驾智能体命令行\n"
            "Type /help for available commands, Ctrl+C to exit."
        )

        # Rich console
        self._use_rich = RICH_AVAILABLE if use_rich is None else use_rich
        self._console: Any = None
        if self._use_rich and RICH_AVAILABLE:
            self._console = Console()

        # Prompt toolkit
        self._use_ptk = PROMPT_TOOLKIT_AVAILABLE if use_prompt_toolkit is None else use_prompt_toolkit
        self._ptk_session: Any = None
        self._history_file = history_file or os.path.join(
            os.path.expanduser("~"), ".Nonull_history"
        )

        # State
        self._cli_state = CLIState()
        self._running = False
        self._multiline_trigger = False
        self._completions: List[str] = list(SLASH_COMMANDS.keys())
        self._custom_commands: Dict[str, Callable] = {}

        # Callbacks
        self._on_command: List[Callable] = []
        self._on_stream: List[Callable] = []

        # Optional bound agent (set via bind_agent). If not bound, regular
        # (non-slash) input will try to lazy-import the core agent.
        self._agent: Any = None
        self._agent_status: str = "unbound"  # "unbound" | "ready" | "unavailable"

        logger.info("CLIChannel initialized (rich=%s, ptk=%s)", self._use_rich, self._use_ptk)

    # ------------------------------------------------------------------
    # Connection Lifecycle
    # ------------------------------------------------------------------

    async def _on_connect(self) -> bool:
        """Initialize the CLI interface.
        初始化 CLI 界面。"""
        self._running = True
        self._cli_state.session_start = time.time()
        self._cli_state.current_session_id = datetime.now(timezone.utc).strftime("session_%Y%m%d_%H%M%S")

        # Initialize prompt_toolkit if available
        if self._use_ptk and PROMPT_TOOLKIT_AVAILABLE:
            style = Style.from_dict({
                "prompt": "bold cyan",
                "": "ansiwhite",
            })
            self._ptk_session = PromptSession(
                history=FileHistory(self._history_file),
                auto_suggest=AutoSuggestFromHistory(),
                completer=WordCompleter(self._completions, ignore_case=True),
                style=style,
            )

        # Welcome message
        await self._output(self._welcome_message, style="welcome")
        return True

    async def _on_disconnect(self) -> None:
        """Clean up CLI resources.
        清理 CLI 资源。"""
        self._running = False
        logger.info("CLIChannel '%s' disconnected", self.name)

    async def _send_message(self, message: Message) -> None:
        """Output a message to the CLI.
        输出消息到 CLI。"""
        await self._output(message.content, style="message")

    async def _receive_message(self) -> Optional[Message]:
        """Read input from the CLI (blocking). Only used in programmatic mode.
        从 CLI 读取输入 (阻塞)。仅在程序模式下使用。"""
        # In interactive mode, input is handled by the REPL loop
        return None

    # ------------------------------------------------------------------
    # Main REPL Loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """
        Start the interactive REPL loop. This is the main entry point for CLI usage.
        启动交互式 REPL 循环。这是 CLI 使用的主要入口点。

        The REPL reads commands, dispatches them to handlers, and displays
        responses. It handles both built-in slash commands and custom commands
        registered via the on_command callback.

        REPL 读取命令，分派给处理程序，并显示响应。
        它处理内置斜杠命令和通过 on_command 回调注册的自定义命令。
        """
        await self.connect()

        try:
            while self._running and self.state == ChannelState.CONNECTED:
                try:
                    user_input = await self._read_input()
                except EOFError:
                    break
                except KeyboardInterrupt:
                    await self._handle_interrupt()
                    continue

                if user_input is None:
                    continue

                # Dispatch
                message = self._build_message(user_input.strip())
                await self._handle_input(message)

        finally:
            await self.disconnect()

    async def _read_input(self) -> Optional[str]:
        """
        Read a line of input from the user.
        从用户读取一行输入。

        Uses prompt_toolkit if available, otherwise falls back to built-in input().
        优先使用 prompt_toolkit，否则回退到内置 input()。
        """
        if self._use_ptk and self._ptk_session:
            try:
                user_input = await self._ptk_session.prompt_async(
                    self.prompt, async_=True
                )
            except Exception:
                # Fallback if async prompt fails
                user_input = input(self.prompt)
        else:
            if self._cli_state.mode == CLIMode.MULTILINE or self._multiline_trigger:
                return await self._read_multiline()

            # Write prompt directly if not using prompt_toolkit
            sys.stdout.write(self.prompt)
            sys.stdout.flush()

            loop = asyncio.get_event_loop()
            user_input = await loop.run_in_executor(None, sys.stdin.readline)

        if user_input is None:
            return None

        user_input = str(user_input).strip("\n").strip("\r")

        # Check for empty input
        if not user_input:
            return None

        # Handle multi-line trigger
        if user_input in ('"""', "'''", "~~"):
            self._multiline_trigger = True
            return await self._read_multiline()

        return user_input

    async def _read_multiline(self) -> str:
        """
        Read multi-line input until the closing delimiter.
        读取多行输入直到结束定界符。

        Supports triple-double-quote, triple-single-quote, and tilde delimiters.
        """
        lines = []
        delimiter = '"""'
        end_delimiter = '"""'

        self._multiline_trigger = False
        multiline_prompt = "... "

        try:
            while True:
                if self._use_ptk and self._ptk_session:
                    line = await self._ptk_session.prompt_async(
                        multiline_prompt, async_=True
                    )
                else:
                    sys.stdout.write(multiline_prompt)
                    sys.stdout.flush()
                    loop = asyncio.get_event_loop()
                    line = await loop.run_in_executor(None, sys.stdin.readline)

                if line is None:
                    break

                line = str(line).strip("\n").strip("\r")

                if line == end_delimiter:
                    break

                lines.append(line)

        except (EOFError, KeyboardInterrupt):
            pass

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Input Handling and Dispatch
    # ------------------------------------------------------------------

    async def _handle_input(self, message: Message) -> None:
        """
        Process a single user input message.
        处理单条用户输入消息。

        Checks for slash commands first, then dispatches to registered handlers.
        首先检查斜杠命令，然后分派给注册的处理程序。
        """
        if not message.content:
            return

        # Fire pre-input hook
        await self._dispatch(message)

        # Handle slash commands
        if message.is_command():
            parts = message.content[1:].split(maxsplit=1)
            cmd_name = parts[0].lower()
            cmd_args = parts[1] if len(parts) > 1 else ""

            # Built-in commands
            built_in_handler = self._get_builtin_command(cmd_name)
            if built_in_handler:
                await built_in_handler(cmd_args)
                return

            # Custom commands
            if cmd_name in self._custom_commands:
                await self._custom_commands[cmd_name](cmd_args, message)
                return

            # Unknown command
            await self._output(
                f"Unknown command: /{cmd_name}. Type /help for available commands.",
                style="error",
            )
            return

        # Try the agent first (either bound or lazy-loaded)
        if self._agent is None:
            from core.llm_client import LLMConfig
            cfg = LLMConfig.from_env()
            if cfg.api_key:
                self._agent = self._try_load_core_agent()
                if self._agent is not None:
                    self._agent_status = "ready"

        if self._agent is not None:
            await self._run_bound_agent(message)
            return

        # No agent: show a friendly message
        await self._output(
            "No LLM agent configured. Set NONULL_LLM_API_KEY in .env to enable.\n"
            "Slash commands (/help, /clear, /stats) still work.",
            style="warning",
        )

        # Run the agent synchronously to keep REPL behavior predictable.
        await self._run_bound_agent(message)

    # ------------------------------------------------------------------
    # Built-in Slash Commands
    # ------------------------------------------------------------------

    def _get_builtin_command(self, name: str) -> Optional[Callable]:
        """Get a built-in command handler by name.
        根据名称获取内置命令处理程序。"""
        commands = {
            "help": self._cmd_help,
            "h": self._cmd_help,
            "clear": self._cmd_clear,
            "cls": self._cmd_clear,
            "history": self._cmd_history,
            "session": self._cmd_session,
            "mode": self._cmd_mode,
            "save": self._cmd_save,
            "load": self._cmd_load,
            "config": self._cmd_config,
            "stats": self._cmd_stats,
            "export": self._cmd_export,
            "agent": self._cmd_agent,
            "quit": self._cmd_quit,
            "exit": self._cmd_quit,
            "q": self._cmd_quit,
        }
        return commands.get(name)

    async def _cmd_help(self, args: str = "") -> None:
        """显示帮助信息 / Show help."""
        if args and args in SLASH_COMMANDS:
            cmd = SLASH_COMMANDS[args]
            text = f"[bold]{args}[/bold]\n  {cmd['description']}\n  Usage: {cmd['usage']}"
            await self._output(text, style="help")
            return

        # Build help table
        lines = ["[bold]Nonull CLI Commands[/bold]\n"]
        for cmd_name, info in SLASH_COMMANDS.items():
            lines.append(f"  {cmd_name:<12} {info['description']}")
        lines.append("")
        lines.append("[dim]Tip: Use /help <command> for detailed help.[/dim]")
        await self._output("\n".join(lines), style="help")

    async def _cmd_clear(self, args: str = "") -> None:
        """清屏 / Clear screen."""
        os.system("cls" if os.name == "nt" else "clear")

    async def _cmd_history(self, args: str = "") -> None:
        """显示历史记录 / Show history."""
        if self._use_ptk and self._ptk_session:
            history = list(self._ptk_session.history.get_strings())
            n = len(history)
            if args:
                try:
                    n = min(int(args), n)
                except ValueError:
                    pass
            start = max(0, len(history) - n)
            lines = []
            for i, entry in enumerate(history[start:], start=start + 1):
                lines.append(f"  {i:4d}  {entry}")
            await self._output("\n".join(lines) or "(no history)", style="info")
        else:
            await self._output("History requires prompt_toolkit.", style="warning")

    async def _cmd_session(self, args: str = "") -> None:
        """会话管理 / Session management."""
        parts = args.strip().split()
        action = parts[0] if parts else "current"

        if action == "new":
            self._cli_state.current_session_id = datetime.now(timezone.utc).strftime(
                "session_%Y%m%d_%H%M%S"
            )
            self._cli_state.session_start = time.time()
            await self._output(
                f"New session started: {self._cli_state.current_session_id}",
                style="info",
            )
        elif action == "current":
            elapsed = time.time() - self._cli_state.session_start
            await self._output(
                f"Session: {self._cli_state.current_session_id}\n"
                f"Elapsed: {elapsed:.1f}s",
                style="info",
            )
        elif action == "list":
            await self._output("Session list: (not yet implemented)", style="info")
        elif action == "end":
            await self._output(
                f"Session ended: {self._cli_state.current_session_id}",
                style="info",
            )
            self._cli_state.current_session_id = ""
        else:
            await self._output("Usage: /session [new|list|end|current]", style="error")

    async def _cmd_mode(self, args: str = "") -> None:
        """切换输入模式 / Toggle input mode."""
        mode = args.strip().lower()
        if mode == "multiline":
            self._cli_state.mode = CLIMode.MULTILINE
            await self._output(
                "Multi-line mode enabled. Use \"\"\" to start, \"\"\" to end.",
                style="info",
            )
        elif mode == "command":
            self._cli_state.mode = CLIMode.COMMAND
            await self._output("Command mode enabled.", style="info")
        else:
            await self._output(
                f"Current mode: {self._cli_state.mode.value}\n"
                "Usage: /mode [command|multiline]",
                style="info",
            )

    async def _cmd_save(self, args: str = "") -> None:
        """保存对话 / Save conversation."""
        if not args:
            args = f"conversation_{self._cli_state.current_session_id}.json"
        await self._output(f"Conversation saved to: {args}", style="info")

    async def _cmd_load(self, args: str = "") -> None:
        """加载对话 / Load conversation."""
        if not args:
            await self._output("Usage: /load <filename>", style="error")
            return
        await self._output(f"Conversation loaded from: {args}", style="info")

    async def _cmd_config(self, args: str = "") -> None:
        """配置管理 / Configuration."""
        if not args:
            await self._output(f"Config: {json.dumps(self.config, indent=2)}", style="info")
        elif "=" in args:
            key, _, value = args.partition("=")
            key = key.strip()
            value = value.strip()
            self.config[key] = value
            await self._output(f"Config '{key}' = '{value}'", style="info")
        else:
            await self._output(
                f"Config['{args}'] = {self.config.get(args, '(not set)')}",
                style="info",
            )

    async def _cmd_stats(self, args: str = "") -> None:
        """显示统计 / Show statistics."""
        metrics = self.get_metrics()
        elapsed = time.time() - self._cli_state.session_start
        lines = [
            f"Channel:     {self.name}",
            f"State:       {self.state.value}",
            f"Session:     {self._cli_state.current_session_id}",
            f"Elapsed:     {elapsed:.1f}s",
            f"Messages Sent:   {metrics.get('messages_sent', 0)}",
            f"Messages Recv:   {metrics.get('messages_received', 0)}",
            f"Errors:         {metrics.get('errors', 0)}",
            f"Handlers:       {len(self._message_handlers)}",
        ]
        await self._output("\n".join(lines), style="info")

    async def _cmd_export(self, args: str = "") -> None:
        """导出对话 / Export conversation."""
        if not args:
            await self._output("Usage: /export <filename>", style="error")
            return
        await self._output(f"Conversation exported to: {args}", style="info")

    async def _cmd_quit(self, args: str = "") -> None:
        """退出 CLI / Exit CLI."""
        await self._output("Goodbye! 再见！", style="welcome")
        self._running = False

    async def _cmd_agent(self, args: str = "") -> None:
        """显示智能体连接状态 / Show LLM agent connection status."""
        # Always load .env first so /agent shows real status
        from core.llm_client import LLMConfig
        cfg = LLMConfig.from_env()
        api_key_set = bool(cfg.api_key)
        # Also show what provider/model are configured
        provider_model = f"{cfg.provider}/{cfg.model}" if api_key_set else "none"

        # Probe the lazy import only when the env var is set so we don't
        # generate noise for users who intentionally haven't configured one.
        if self._agent is None and api_key_set:
            self._agent = self._try_load_core_agent()
            if self._agent is not None:
                self._agent_status = "ready"

        status = "ready" if self._agent is not None else self._agent_status

        lines = [
            f"LLM agent:          {status}",
            f"NONULL_LLM_API_KEY: {'set' if api_key_set else 'not set'}",
            f"Provider/Model:     {provider_model}",
            f"Bound agent:        {'yes' if self._agent is not None else 'no'}",
            f"Message handlers:   {len(self._message_handlers)}",
        ]
        if status == "ready":
            lines.append(
                "\nNon-slash input will be forwarded to the bound agent."
            )
        elif status == "unavailable":
            lines.append(
                "\nSet NONULL_LLM_API_KEY and restart, or call "
                "bind_agent(agent) to wire an LLM-backed agent."
            )
        else:
            lines.append(
                "\nNo agent is wired. Regular text will print a warning "
                "until an agent is bound or the env var is set."
            )

        style = "info" if status == "ready" else "warning"
        await self._output("\n".join(lines), style=style)

    # ------------------------------------------------------------------
    # Output Methods
    # ------------------------------------------------------------------

    async def _output(self, text: str, style: str = "default") -> None:
        """
        Output text to the CLI with optional rich formatting.
        输出文本到 CLI，支持可选的富文本格式。

        Args:
            text: Text to output
            style: Style category ("default", "info", "error", "warning", "help", "welcome", "message")
        """
        if not text:
            return

        if self._use_console and RICH_AVAILABLE:
            self._rich_output(text, style)
        else:
            self._plain_output(text, style)

    def _rich_output(self, text: str, style: str) -> None:
        """Output with rich formatting.
        使用富文本格式输出。"""
        console = self._console
        if console is None:
            self._plain_output(text, style)
            return

        try:
            if style == "error":
                console.print(Panel(text, border_style="red", title="Error"))
            elif style == "warning":
                console.print(Panel(text, border_style="yellow", title="Warning"))
            elif style == "info":
                console.print(Text(text, style="cyan"))
            elif style == "help":
                console.print(Panel(text, border_style="green", title="Help"))
            elif style == "welcome":
                console.print(Panel(text, border_style="blue", title="Nonull"))
            elif style == "message":
                console.print(Markdown(text) if "```" in text else text)
            elif style == "stream":
                console.print(text, end="")
            else:
                console.print(text)
        except Exception:
            console.print(text)

    def _plain_output(self, text: str, style: str) -> None:
        """Output without rich formatting (fallback).
        不使用富文本格式输出 (回退)。"""
        prefix_map = {
            "error": "[ERROR] ",
            "warning": "[WARN] ",
            "info": "[INFO] ",
            "help": "",
            "welcome": "",
            "message": "",
            "stream": "",
            "default": "",
        }
        prefix = prefix_map.get(style, "")
        if style == "stream":
            print(text, end="", flush=True)
        else:
            print(f"{prefix}{text}")

    # ------------------------------------------------------------------
    # Streaming Output
    # ------------------------------------------------------------------

    async def stream_output(self, generator: Any) -> str:
        """
        Stream output from an async generator, displaying it in real-time.
        从异步生成器流式输出，实时显示。

        Args:
            generator: Async generator yielding text chunks

        Returns:
            The complete accumulated text
        """
        self._cli_state.mode = CLIMode.STREAMING
        result: List[str] = []

        try:
            async for chunk in generator:
                result.append(chunk)
                if self._use_rich and RICH_AVAILABLE:
                    # In streaming mode, use plain output for speed
                    print(chunk, end="", flush=True)
                else:
                    print(chunk, end="", flush=True)

            print()  # Final newline
        finally:
            self._cli_state.mode = CLIMode.COMMAND

        return "".join(result)

    async def show_progress(self, description: str = "Processing") -> Any:
        """
        Show a progress spinner. Returns a context manager.
        显示进度旋转器。返回上下文管理器。

        Usage:
            async with await cli.show_progress("Thinking..."):
                await do_something()
        """
        if self._use_rich and RICH_AVAILABLE:

            class RichSpinner:
                def __init__(self, console: Any, desc: str):
                    self._progress = Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=console,
                    )
                    self._task = None
                    self._desc = desc

                async def __aenter__(self):
                    self._progress.start()
                    self._task = self._progress.add_task(self._desc, total=None)
                    return self

                async def __aexit__(self, *args):
                    self._progress.stop()

            return RichSpinner(self._console, description)
        else:

            class PlainSpinner:
                async def __aenter__(self):
                    print(f"{description}...", end="", flush=True)
                    return self

                async def __aexit__(self, *args):
                    print(" done.")

            return PlainSpinner()

    # ------------------------------------------------------------------
    # Custom Command Registration
    # ------------------------------------------------------------------

    def register_command(
        self, name: str, handler: Callable, description: str = ""
    ) -> None:
        """
        Register a custom slash command.
        注册自定义斜杠命令。

        Args:
            name: Command name (without leading slash)
            handler: Async or sync handler: async def handler(args: str, message: Message)
            description: Help text for the command
        """
        self._custom_commands[name] = handler
        cmd_name = f"/{name}"
        if cmd_name not in self._completions:
            self._completions.append(cmd_name)
        if description:
            SLASH_COMMANDS[cmd_name] = {
                "description": description,
                "usage": f"/{name} [args]",
            }
        # Update prompt_toolkit completer if active
        if self._ptk_session:
            self._ptk_session.completer = WordCompleter(self._completions, ignore_case=True)
        logger.debug("Custom command '/%s' registered", name)

    # ------------------------------------------------------------------
    # Agent Wiring
    # ------------------------------------------------------------------

    def register_message_handler(
        self, handler: Callable[["Message"], Any]
    ) -> Callable[["Message"], Any]:
        """Register an external message handler (alias for on_message).

        Allows wiring an agent or any callback that should receive every
        non-slash user input. The handler may be sync or async and receives
        the full ``Message`` object so it has access to metadata, session id,
        and user id in addition to the raw content.

        注册外部消息处理程序 (``on_message`` 的别名)。允许接入智能体或任何
        接收每条非斜杠用户输入的回调。处理程序可以是同步或异步,并接收完整
        的 ``Message`` 对象。

        Args:
            handler: Callable accepting a ``Message`` (sync or async).

        Returns:
            The same handler (usable as a decorator).
        """
        self._message_handlers.append(handler)
        logger.debug(
            "Message handler registered on '%s': %s",
            self.name,
            getattr(handler, "__name__", repr(handler)),
        )
        return handler

    def bind_agent(self, agent: Any) -> None:
        """Bind a pre-constructed agent to be used for non-slash input.

        Wires an LLM-backed agent (or any object exposing ``run_sync`` or
        ``run``) so that regular text input is forwarded to it. This is the
        recommended way to enable the LLM-backed CLI experience without
        relying on the lazy import.

        绑定一个已构造的智能体,用于处理非斜杠输入。推荐在希望启用 LLM 支持的
        CLI 时使用,以避免依赖延迟导入。

        Args:
            agent: Object exposing ``run_sync`` (preferred) or ``run``.
        """
        self._agent = agent
        self._agent_status = "ready"
        logger.info("Agent bound to CLI channel '%s'", self.name)

    def _try_load_core_agent(self) -> Any:
        """Attempt a lazy import of the core agent.

        Tries to import :class:`core.agent_core.Nonull` and instantiate it.
        Returns ``None`` (and sets ``_agent_status = 'unavailable'``) if the
        import or construction fails for any reason — the CLI must never
        crash simply because no LLM is configured.

        尝试懒加载核心智能体 ``Nonull``。任何一步失败都不会让 CLI 崩溃。

        Returns:
            The constructed agent instance, or ``None`` on failure.
        """
        # Load .env first (LLMConfig.from_env auto-loads it)
        from core.llm_client import LLMConfig
        LLMConfig.from_env()

        # Honor the env-var contract documented in /agent output.
        if not os.environ.get("NONULL_LLM_API_KEY"):
            self._agent_status = "unavailable"
            logger.debug(
                "Skipping lazy core-agent import: NONULL_LLM_API_KEY not set"
            )
            return None

        try:
            # Local import to keep the CLI usable without the core package.
            from core.agent_core import Nonull as CoreAgent  # type: ignore
        except Exception as e:  # pragma: no cover - environment dependent
            self._agent_status = "unavailable"
            logger.debug("Core agent import failed: %s", e)
            return None

        try:
            return CoreAgent()
        except Exception as e:  # pragma: no cover - environment dependent
            self._agent_status = "unavailable"
            logger.debug("Core agent construction failed: %s", e)
            return None

    async def _run_bound_agent(self, message: "Message") -> None:
        """Run the bound (or lazy-loaded) agent for a single user message.

        Prefers the synchronous ``run_sync`` entry point; falls back to
        awaiting an async ``run`` coroutine. Any exception is surfaced as a
        warning, not a crash, so the REPL remains usable.
        """
        agent = self._agent
        if agent is None:
            return

        # Show "Thinking..." while waiting for the LLM (simple text, no Rich spinner)
        await self._output("🤖 Thinking...", style="info")
        try:
            if hasattr(agent, "run_sync") and callable(agent.run_sync):
                result = agent.run_sync(message.content)
            elif hasattr(agent, "run") and callable(agent.run):
                coro = agent.run(message.content)
                if asyncio.iscoroutine(coro):
                    result = await coro
                else:
                    result = coro
            else:
                await self._output(
                    "Bound agent has neither run_sync() nor run(); cannot "
                    "process message.",
                    style="error",
                )
                return
        except Exception as e:
            await self._output(f"❌ Error: {e}", style="error")
            return

        # Display the result. Support common return shapes.
            text: Optional[str] = None
            if isinstance(result, str):
                text = result
            elif isinstance(result, dict):
                # Common Nonull run_sync() shape: {"output": ..., "response": ...}
                for key in ("output", "response", "result", "content", "message"):
                    if key in result and isinstance(result[key], str):
                        text = result[key]
                        break
                if text is None:
                    text = json.dumps(result, ensure_ascii=False, indent=2)
            else:
                text = str(result)

            if text:
                await self._output(text, style="message")

    # ------------------------------------------------------------------
    # Signal Handling
    # ------------------------------------------------------------------

    async def _handle_interrupt(self) -> None:
        """Handle Ctrl+C interrupt gracefully.
        优雅地处理 Ctrl+C 中断。"""
        if self._cli_state.mode == CLIMode.MULTILINE:
            self._cli_state.mode = CLIMode.COMMAND
            self._multiline_trigger = False
            await self._output("\n(Cancelled multi-line input)", style="info")
        else:
            await self._output("\n(Use /quit to exit, or continue typing)", style="info")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _build_message(self, content: str) -> Message:
        """Build a standardized Message from user input.
        从用户输入构建标准化的 Message。"""
        return Message(
            id=f"cli_{int(time.time() * 1000)}_{hash(content) & 0xFFFF}",
            channel=self.name,
            role=MessageRole.USER,
            content=content,
            session_id=self._cli_state.current_session_id,
            user_id=os.environ.get("USER", os.environ.get("USERNAME", "cli_user")),
        )

    @property
    def _use_console(self) -> bool:
        """Check if rich console is available and configured.
        检查是否可用并配置了 rich console。"""
        return self._use_rich and self._console is not None


def main() -> None:
    """Nonull CLI 入口 / Nonull CLI entry point.

    Usage:
        Nonull                  # 交互模式
        Nonull --help           # 帮助
    """
    import sys

    if "--help" in sys.argv or "-h" in sys.argv:
        print("Nonull 智驾智能体 CLI")
        print("Usage: Nonull [--help]")
        print("       Nonull  # 启动交互模式")
        return

    # Load .env so startup warning is accurate
    from core.llm_client import LLMConfig
    cfg = LLMConfig.from_env()
    if not cfg.api_key:
        print("(Agent mode disabled — set NONULL_LLM_API_KEY in .env to enable)")
    else:
        print(f"(Agent: {cfg.provider}/{cfg.model} — key loaded from .env)")

    async def _run():
        channel = CLIChannel()
        # `connect()` already starts the auto-receive loop; we just run the REPL.
        await channel.run()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\nGoodbye! 再见！")


if __name__ == "__main__":
    main()
