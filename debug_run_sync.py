import time, asyncio

from core.llm_client import LLMConfig, LLMClient
cfg = LLMConfig.from_env()
print(f"Key set: {bool(cfg.api_key)}")
print(f"Model: {cfg.model}")

from core.agent_core import Nonull
agent = Nonull()
print(f"Agent created: {agent}")

t0 = time.time()
result = agent.run_sync("Say hi in 3 words")
t = time.time() - t0
print(f"run_sync took {t:.2f}s")
print(f"Status: {result.get('status')}")
out = result.get("output", "")
print(f"Output: {out[:100]}")

# Now test via asyncio.to_thread
async def test_async():
    t0 = time.time()
    result2 = await asyncio.to_thread(agent.run_sync, "Say hello in 3 words")
    t = time.time() - t0
    print(f"async to_thread took {t:.2f}s")
    out2 = result2.get("output", "")
    print(f"Async output: {out2[:100]}")

asyncio.run(test_async())
print("DONE")
