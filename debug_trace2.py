import asyncio, sys, traceback

# Patch _run_bound_agent to instrument
from channels import cli
orig_run = cli.CLIChannel._run_bound_agent

async def debug_run(self, message):
    try:
        # Call the original
        await orig_run(self, message)
    except Exception:
        print(f"EXCEPTION in _run_bound_agent: {traceback.format_exc()}", file=sys.stderr)

cli.CLIChannel._run_bound_agent = debug_run

from core.agent_core import Nonull
agent = Nonull()

ch = cli.CLIChannel(name="test", use_rich=False)
ch.bind_agent(agent)

from channels.base import Message, MessageRole
msg = Message(id="t1", channel="test", role=MessageRole.USER,
              content="Say hi in 3 words", session_id="", user_id="test")

async def test():
    print("START", file=sys.stderr)
    await ch._handle_input(msg)
    print("END", file=sys.stderr)

asyncio.run(test())
