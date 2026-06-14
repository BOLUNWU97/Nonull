"""
Agent Loop 真实 demo / Standard agentic loop with a real LLM.

演示 Agent Loop 模式: 真实 LLM 在 while 循环里, 自主选工具 → 执行 → observe
结果 → 重复, 直到给出最终答案。与 Nonull.run() 的五阶段循环不同, 这里 LLM
完全控制流程 (ReAct: Reason → Act → Observe)。

Demonstrates the agentic-loop pattern with a real LLM: the model autonomously
picks tools, executes them, observes results, and loops until it gives a final
answer — the LLM fully owns control flow.
"""
import asyncio
import ast
import operator

from core import AgentLoop
from core.llm_client import LLMClient, LLMConfig


# ── 工具 (agent 可调用) ──────────────────────────────────────────

def calculator(expression: str = "", **kw) -> str:
    """Calculate a math expression. Parameter: expression (str), e.g. '15 * 23'.
    计算 (string) 表达式，可以。Parameter expression=..."""
    expr = expression or kw.get("expr") or kw.get("input") or ""
    allowed = {ast.Add: operator.add, ast.Sub: operator.sub,
               ast.Mult: operator.mul, ast.Div: operator.truediv}
    try:
        node = ast.parse(expr, mode="eval").body
        def ev(n):
            if isinstance(n, ast.BinOp):
                return allowed[type(n.op)](ev(n.left), ev(n.right))
            if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
                return -ev(n.operand)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
                return n.value
            raise ValueError("unsupported expression")
        return str(ev(node))
    except Exception as e:
        return f"error: {e}"


def word_count(text: str = "", **kw) -> str:
    """Count words in text. Parameter: text (str).
    返回词数。Parameter text=..."""
    t = text or kw.get("input") or kw.get("string") or ""
    return str(len(str(t).split()))


async def main() -> None:
    cfg = LLMConfig.from_env()
    if not cfg.api_key:
        print("⚠️  未配置 LLM (NONULL_LLM_API_KEY 为空)。配好 .env 后重试。")
        return

    llm = LLMClient(cfg)
    loop = AgentLoop(
        llm,
        tools=[calculator, word_count],
        max_steps=6,
    )

    task = (
        "Do two things using tools: (1) count the words in "
        "'the quick brown fox jumps over'; (2) compute 15 * 23. "
        "Then give a one-sentence final summary."
    )
    print(f"📋 任务: {task}\n")
    print(f"🔧 可用工具: calculator, word_count | max_steps=6\n")
    print("━" * 60)

    result = await loop.run(task)

    print("━" * 60)
    print(f"✅ 完成: {result.completed} | 步数: {result.total_steps} | "
          f"工具调用: {result.tool_calls}")
    if result.error:
        print(f"❌ 错误: {result.error}")
    print(f"\n📝 最终答案:\n{result.output[:500]}")

    print("\n🔄 循环步骤:")
    for s in result.steps:
        tag = "🔧" if s.action.startswith("tool:") else "🏁"
        print(f"  {tag} [step {s.step}] {s.action}")
        print(f"      thought: {s.thought[:120]}")
        print(f"      observe: {s.observation[:120]}")


if __name__ == "__main__":
    asyncio.run(main())
