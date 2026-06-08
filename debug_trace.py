import asyncio, sys
from channels.base import Message, MessageRole

# Monkey-patch _output to see what's happening
from channels import cli
orig_output = cli.CLIChannel._output

async def debug_output(self, text, style="default"):
    print(f"  [_output] style={style} text_len={len(text) if text else 0} text={repr(text[:80]) if text else None}", file=sys.stderr)
    return await orig_output(self, text, style)

cli.CLIChannel._output = debug_output

from core.agent_core import Nonull
agent = Nonull()

ch = cli.CLIChannel(name="test", use_rich=False)
ch.bind_agent(agent)
msg = Message(id="t1", channel="test", role=MessageRole.USER,
              content="Say hi in 3 words", session_id="", user_id="test")

async def test():
    print("=== CALLING _run_bound_agent ===", file=sys.stderr)
    await ch._run_bound_agent(msg)
    print("=== DONE ===", file=sys.stderr)

asyncio.run(test())
