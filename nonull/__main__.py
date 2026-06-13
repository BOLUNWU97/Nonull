"""Allow `python -m nonull` to launch the interactive CLI."""
from __future__ import annotations

import asyncio
import os
import sys

from channels.cli import CLIChannel
from core.llm_client import LLMConfig


def _show_startup(console) -> None:
    """Bilingual startup banner and LLM-warn message."""
    banner = (
        "[bold cyan]Nonull AI Agent Framework[/bold cyan]  --  领域无关的AI智能体框架\n"
        "[dim]四架构融合: OpenClaw | Hermes Agent | openHuman | Claude Code[/dim]\n"
    )
    console.print(banner)

    # Check LLM configuration
    cfg = LLMConfig.from_env()
    if not cfg.api_key:
        console.print(
            "[yellow]提示: NONULL_LLM_API_KEY 未设置 / LLM API key not set[/yellow]\n"
            "[dim]设置环境变量以启用智能体模式 | Set env var to enable agent mode:\n"
            "  export NONULL_LLM_API_KEY=sk-your-key\n"
            "  或创建 .env 文件 | or create a .env file[/dim]\n"
        )
    else:
        console.print(
            f"[green]智能体就绪 | Agent ready[/green]  "
            f"[{cfg.provider}/{cfg.model}]"
        )

    console.print(
        "\n[cyan]可用命令 | Available commands:[/cyan]\n"
        "  [bold]/status[/bold]  查看状态    [bold]/memory[/bold]  查看记忆\n"
        "  [bold]/skills[/bold]  列出技能    [bold]/plan[/bold]     查看当前计划\n"
        "  [bold]/quit[/bold]    退出        [bold]/help[/bold]     帮助\n"
        "  输入任何文本发送任务给智能体 | Type text to send a task\n"
    )


def _show_status(console, agent) -> None:
    """Show agent status from agent.get_status()."""
    if hasattr(agent, "get_status") and callable(agent.get_status):
        try:
            status = agent.get_status()
            console.print(
                "[bold blue]Agent Status | 智能体状态[/bold blue]\n"
                + ("[dim]" + str(status) + "[/dim]")
            )
        except Exception as exc:
            console.print(f"[red]Error getting status: {exc}[/red]")
    else:
        console.print("[dim]No status() available on agent[/dim]")


def _show_memory(console, agent) -> None:
    """Show memory stats."""
    if hasattr(agent, "memory") and agent.memory is not None:
        mem = agent.memory
        stats = {}
        try:
            if hasattr(mem, "get_stats"):
                stats = mem.get_stats()
            else:
                for attr in ("working", "episodic", "semantic", "procedural"):
                    if hasattr(mem, attr):
                        layer = getattr(mem, attr)
                        if layer is not None and hasattr(layer, "__len__"):
                            stats[attr] = len(layer)
        except Exception as exc:
            console.print(f"[red]Error reading memory: {exc}[/red]")
            return
        lines = [f"[bold blue]Memory Stats | 记忆统计[/bold blue]"]
        for key, value in stats.items():
            lines.append(f"  {key}: {value}")
        console.print("\n".join(lines))
    else:
        console.print("[dim]Memory not initialized | 记忆未初始化[/dim]")


def _show_skills(console, agent) -> None:
    """List available skills."""
    if hasattr(agent, "skills"):
        skills = agent.skills
        if hasattr(skills, "list_all"):
            skill_list = skills.list_all()
        elif hasattr(skills, "all_skills"):
            skill_list = skills.all_skills
        elif isinstance(skills, (list, tuple)):
            skill_list = skills
        else:
            skill_list = []

        if skill_list:
            console.print("[bold blue]Available Skills | 可用技能[/bold blue]")
            for sk in skill_list:
                name = getattr(sk, "name", str(sk))
                desc = getattr(sk, "description", "")
                console.print(f"  [bold]{name}[/bold]  —  {desc}")
        else:
            console.print("[dim]No skills found | 未找到技能[/dim]")
    else:
        console.print("[dim]No skill registry found | 未找到技能注册表[/dim]")


def _show_plan(console, agent) -> None:
    """Show current plan from context."""
    if hasattr(agent, "context") and agent.context is not None:
        ctx = agent.context
        plan = None
        if hasattr(ctx, "plan"):
            plan = ctx.plan
        elif hasattr(ctx, "get_plan"):
            plan = ctx.get_plan()
        if plan:
            console.print(f"[bold blue]Current Plan | 当前计划[/bold blue]\n{plan}")
        else:
            console.print("[dim]No active plan | 无活跃计划[/dim]")
    else:
        console.print("[dim]No context or plan available | 无上下文或计划[/dim]")


async def _main() -> None:
    import signal

    console = None
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        console = Console()
    except ImportError:
        pass  # no rich — use plain CLIChannel fallback

    channel = CLIChannel(use_rich=True)

    # Print startup banner before channel.connect() so it shows immediately
    if console:
        _show_startup(console)

    # Override welcome so the channel's own banner doesn't duplicate
    channel._welcome_message = ""

    # Bind agent if LLM is configured
    cfg = LLMConfig.from_env()
    agent = None
    if cfg.api_key:
        try:
            from core.agent_core import Nonull as CoreAgent

            agent = CoreAgent()
            channel.bind_agent(agent)
        except Exception as e:
            import logging
            logging.getLogger("nonull").warning("Agent init failed: %s", e)

    # Register custom slash commands
    async def _cmd_status(_args: str, _msg) -> None:
        if agent is not None:
            _show_status(console, agent)
        else:
            if console:
                console.print("[yellow]Agent not bound | 智能体未绑定[/yellow]")

    async def _cmd_memory(_args: str, _msg) -> None:
        if agent is not None:
            _show_memory(console, agent)
        else:
            if console:
                console.print("[yellow]Agent not bound | 智能体未绑定[/yellow]")

    async def _cmd_skills(_args: str, _msg) -> None:
        if agent is not None:
            _show_skills(console, agent)
        else:
            if console:
                console.print("[yellow]Agent not bound | 智能体未绑定[/yellow]")

    async def _cmd_plan(_args: str, _msg) -> None:
        if agent is not None:
            _show_plan(console, agent)
        else:
            if console:
                console.print("[yellow]Agent not bound | 智能体未绑定[/yellow]")

    channel.register_command("status", _cmd_status, "显示智能体状态 | Show agent status")
    channel.register_command("memory", _cmd_memory, "显示记忆统计 | Show memory stats")
    channel.register_command("skills", _cmd_skills, "列出可用技能 | List available skills")
    channel.register_command("plan", _cmd_plan, "显示当前计划 | Show current plan")

    await channel.run()


def main() -> None:
    """Nonull CLI entry point / Nonull CLI 入口."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Nonull AI Agent Framework CLI")
        print("Usage:")
        print("  python -m nonull              # interactive mode")
        print("  python -m nonull --plain      # plain text (no Rich)")
        print("  python -m nonull --help       # this help")
        return

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\n再见! / Goodbye!")


if __name__ == "__main__":
    main()
