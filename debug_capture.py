import asyncio, sys
from io import StringIO

# Capture console output
from channels.cli import CLIChannel
from channels.base import Message, MessageRole
from core.agent_core import Nonull

agent = Nonull()
ch = CLIChannel(name="test_cli", use_rich=False)  # FORCE plain output
ch.bind_agent(agent)
msg = Message(id="t1", channel="test_cli", role=MessageRole.USER,
              content="Say hi in 3 words", session_id="", user_id="test")

async def test():
    print("--- OUTPUT START ---")
    await ch._run_bound_agent(msg)
    print("--- OUTPUT END ---")

asyncio.run(test())
