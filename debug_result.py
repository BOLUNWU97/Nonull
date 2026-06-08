import asyncio
from core.agent_core import Nonull
agent = Nonull()
result = agent.run_sync("Say hi")
print(f"Type: {type(result).__name__}")
print(f"Keys: {list(result.keys())}")
print(f"Status: {result.get('status')}")
out = result.get("output", "")
print(f"Output len: {len(out)}")
print(f"Output: {out[:80]}")

# Test the extraction
text = None
if isinstance(result, dict):
    for key in ("output","response","result","content","message"):
        if key in result and isinstance(result[key], str):
            text = result[key]
            break
print(f"Extracted: {text[:80] if text else None}")
