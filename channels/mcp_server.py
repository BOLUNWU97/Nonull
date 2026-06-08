"""
Nonull MCP Server — exposes Nonull as an MCP tool for any MCP client.

MCP (Model Context Protocol) allows any MCP-compatible client (Claude Desktop,
Cursor, VS Code extensions, etc.) to use Nonull's skills as tools.

Usage:
    python -m channels.mcp_server
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Nonull.MCP")

try:
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    import mcp.server.stdio
    import mcp.types as types
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


def create_server(agent=None, skill_registry=None) -> Optional[Any]:
    """Create the MCP server instance."""
    if not MCP_AVAILABLE:
        raise ImportError("MCP not installed: pip install mcp")

    server = Server("nonull")

    @server.list_tools()
    async def list_tools() -> List[types.Tool]:
        """List all available Nonull skills as MCP tools."""
        tools = []

        # Core agent chat tool
        tools.append(types.Tool(
            name="agent_chat",
            description="Chat with the Nonull AI agent. Send any question or task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Your message or task for the agent"},
                    "max_tokens": {"type": "integer", "description": "Max tokens in response", "default": 2048},
                },
                "required": ["message"],
            },
        ))

        # Code review tool
        tools.append(types.Tool(
            name="code_review",
            description="Review code for bugs, style issues, and security problems.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Source code to review"},
                    "language": {"type": "string", "description": "Programming language", "default": "python"},
                },
                "required": ["code"],
            },
        ))

        # Scenario analysis tool
        tools.append(types.Tool(
            name="scenario_analysis",
            description="Analyze test coverage against 36 ADAS driving scenarios.",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_cases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of test case names or descriptions",
                    },
                },
                "required": ["test_cases"],
            },
        ))

        # File system tools
        tools.append(types.Tool(
            name="file_read",
            description="Read a text file with optional line limit.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "limit": {"type": "integer", "description": "Max lines to read", "default": 100},
                },
                "required": ["path"],
            },
        ))

        # Execute code tool
        tools.append(types.Tool(
            name="run_code",
            description="Execute Python code in a sandboxed environment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                    "backend": {"type": "string", "description": "Execution backend (inline/subprocess)", "default": "inline"},
                },
                "required": ["code"],
            },
        ))

        # Brainstorm tool
        tools.append(types.Tool(
            name="brainstorm",
            description="Generate creative ideas using brainstorming techniques.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic to brainstorm about"},
                    "count": {"type": "integer", "description": "Number of ideas", "default": 5},
                },
                "required": ["topic"],
            },
        ))

        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
        """Execute a Nonull skill via MCP."""
        try:
            if name == "agent_chat":
                if agent is not None and hasattr(agent, "run_sync"):
                    result = agent.run_sync(arguments.get("message", ""))
                    return [types.TextContent(type="text", text=result.get("output", str(result)))]
                return [types.TextContent(type="text", text="Agent not available. Set NONULL_LLM_API_KEY.")]

            elif name == "code_review":
                from skills.registry import SkillRegistry
                reg = SkillRegistry()
                reg.auto_discover()
                skill = reg.get_skill("code_review")
                if skill:
                    skill.activate()
                    result = skill.execute({
                        "code": arguments.get("code", ""),
                        "language": arguments.get("language", "python"),
                    })
                    return [types.TextContent(type="text", text=json.dumps(result.data, indent=2))]

            elif name == "scenario_analysis":
                try:
                    from domains.adas.scenarios import ScenarioEngine
                    engine = ScenarioEngine()
                    report = engine.analyze_scenario_coverage(arguments.get("test_cases", []))
                    return [types.TextContent(type="text", text=json.dumps(report, indent=2))]
                except ImportError:
                    return [types.TextContent(type="text", text="ADAS domain not loaded.")]

            elif name in ("file_read", "file_write", "file_edit", "glob", "grep"):
                from skills.filesystem.fs_skills import ReadFileSkill
                skill = ReadFileSkill()
                skill.activate()
                result = skill.execute(arguments)
                return [types.TextContent(type="text", text=str(result.data))]

            elif name == "run_code":
                from skills.execution.executable_skill import CodeRunnerSkill
                skill = CodeRunnerSkill()
                skill.activate()
                result = skill.execute(arguments)
                return [types.TextContent(type="text", text=json.dumps(result.data, indent=2))]

            elif name == "brainstorm":
                from skills.creative.idea_skills import BrainstormSkill
                skill = BrainstormSkill()
                skill.activate()
                result = skill.execute(arguments)
                return [types.TextContent(type="text", text=json.dumps(result.data, indent=2))]

            else:
                return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

        except Exception as e:
            return [types.TextContent(type="text", text=f"Error: {type(e).__name__}: {e}")]

    return server


async def run_server(agent=None, skill_registry=None):
    """Run the MCP server over stdio transport."""
    server = create_server(agent, skill_registry)
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="nonull",
                server_version="0.2.3",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main():
    """Entry point: run the MCP server."""
    if not MCP_AVAILABLE:
        print("MCP not installed. Run: pip install mcp")
        return

    # Pre-load the agent if possible
    agent = None
    try:
        from core.llm_client import LLMConfig
        cfg = LLMConfig.from_env()
        if cfg.api_key:
            from core.agent_core import Nonull
            agent = Nonull()
            logger.info("Agent loaded: %s/%s", cfg.provider, cfg.model)
    except Exception as e:
        logger.warning("Agent not loaded: %s", e)

    print("Nonull MCP Server starting on stdio...", flush=True)
    asyncio.run(run_server(agent))


if __name__ == "__main__":
    main()
