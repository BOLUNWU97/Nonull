"""
Nonull 真实 code-review demo / Real LLM-powered code review.

配好 NONULL_LLM_API_KEY 后运行:
    python examples/code_review_demo.py            # review 内置示例代码
    python examples/code_review_demo.py somefile.py   # review 指定文件

不带 key 时友好退出。带 key 时跑完整认知循环 (plan→reason→act→reflect),
并展示本轮新增的能力: 成本追踪、记忆状态、状态持久化。

Real LLM code review driving the full cognition loop, showcasing cost
tracking, memory state, and state persistence.
"""
import asyncio
import os
import sys

from core import Nonull

# 内置示例: 故意有 bug 的代码 / sample code with intentional issues
SAMPLE_CODE = '''\
def divide(a, b):
    return a / b

def process_items(items):
    result = []
    for i in range(len(items)):
        result.append(items[i] * 2)
    return result

class Cache:
    def __init__(self):
        self._data = {}
    def get(self, key):
        return self._data[key]  # KeyError if missing
'''


async def main() -> None:
    # 读代码: 命令行文件 or 内置示例 / read code from argv or sample
    code = SAMPLE_CODE
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], encoding="utf-8") as f:
                code = f.read()
        except OSError as e:
            print(f"❌ 无法读取文件 {sys.argv[1]}: {e}")
            return

    agent = Nonull(name="code-reviewer")

    # 无 key 友好退出 / graceful exit without an API key
    if agent.llm_client is None:
        print("⚠️  未配置 LLM (NONULL_LLM_API_KEY 为空).")
        print("   配置步骤:")
        print("     1. cp .env.example .env")
        print("     2. 在 .env 填入你的 OpenAI 兼容 API key")
        print("     3. 重新运行: python examples/code_review_demo.py")
        print("\n   支持的 provider: OpenAI / DeepSeek / MiniMax / Ollama / vLLM / 任何兼容端点")
        return

    task = (
        "Review this Python code for bugs, safety risks, and style issues. "
        "Produce a structured report with: (1) bugs found, (2) safety risks, "
        "(3) style suggestions. Be specific with line references.\n\n"
        f"```\n{code[:3000]}\n```"
    )
    print(f"📋 任务: review {len(code)} 字符代码\n")

    # 完整认知循环 / full cognition loop
    result = await agent.run(task)

    print("\n" + "=" * 60)
    print(f"状态: {result['status']}    迭代: {result['iterations']}    耗时: {result['duration']:.1f}s")
    if result.get("error"):
        print(f"错误: {result['error']}")
    print("=" * 60)
    print("\n📝 输出:")
    print(result.get("output") or "(agent 未产出文本输出)")

    # 展示新能力 / showcase new capabilities
    status = agent.get_status()
    cost = status.get("cost", {})
    print("\n" + "-" * 60)
    print("📊 运行指标 / run metrics:")
    print(f"  💰 成本: ${cost.get('total_cost', 0):.4f} "
          f"({cost.get('call_count', 0)} 次 LLM 调用)")
    by_model = cost.get("by_model", {})
    for model, stats in by_model.items():
        print(f"     └─ {model}: {stats.get('calls', 0)} calls, "
              f"{stats.get('prompt_tokens', 0)}+{stats.get('completion_tokens', 0)} tokens")
    mem = status.get("memory_sizes", {})
    print(f"  🧠 记忆: working={mem.get('working', 0)} episodic={mem.get('episodic', 0)} "
          f"semantic={mem.get('semantic', 0)}")
    print(f"  🛡️  安全拦截: {status.get('safety_violations', 0)}")

    # 持久化: 记忆现在真能存了 (本轮修复) / persistence: memory now actually saves
    state_path = os.path.expanduser("~/.Nonull/demos/code_review_state.json")
    try:
        saved = await agent.save_state(state_path)
        print(f"\n💾 状态已存: {saved}")
        print("   (下次 Nonull().load_state(path) 可恢复记忆, 不再失忆)")
    except Exception as e:
        print(f"\n💾 状态保存失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
