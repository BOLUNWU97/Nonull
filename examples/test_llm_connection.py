"""
Nonull LLM Connection Test

Usage:
    python examples/test_llm_connection.py

Tests: import, config, sync chat, async chat
"""
import os, sys, time

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

from core.llm_client import LLMClient, LLMConfig, LLMMessage


def step(n, msg):
    print(f"\n [{n}] {msg}")
    print("-" * 40)


def main():
    print("=" * 50)
    print("  Nonull — LLM Connection Test")
    print("=" * 50)

    step(1, "Import check")
    print("  OK")

    step(2, "Config check")
    cfg = LLMConfig.from_env()
    print(f"  Provider: {cfg.provider}")
    print(f"  Model:    {cfg.model}")
    print(f"  Base URL: {cfg.base_url}")
    print(f"  API key:  {'✅ Set' if cfg.api_key else '❌ NOT SET'}")
    if not cfg.api_key:
        print("\n  ERROR: set NONULL_LLM_API_KEY in .env")
        sys.exit(1)

    step(3, "Sync chat")
    client = LLMClient(cfg)
    t0 = time.time()
    resp = client.simple_chat("Say 'ready' in one word.", max_tokens=10)
    t = time.time() - t0
    print(f"  Response: {resp!r}")
    print(f"  Latency:  {t:.2f}s")

    step(4, "Async chat")
    import asyncio
    async def _test():
        c = LLMClient(cfg)
        t0 = time.time()
        r = await c.achat([LLMMessage(role="user", content="What is 2+2?")], max_tokens=10)
        t = time.time() - t0
        print(f"  Response: {r.content!r}")
        print(f"  Model:    {r.model}")
        print(f"  Tokens:   {r.total_tokens}")
        print(f"  Latency:  {t:.2f}s")
    asyncio.run(_test())

    print("\n" + "=" * 50)
    print("  ALL TESTS PASSED ✅")
    print("=" * 50)


if __name__ == "__main__":
    main()
