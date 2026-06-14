"""
记忆跨会话连续性 demo / Memory continuity across sessions.

验证本轮修复的 save/load (Neocortex 持久化) 真的让 agent "不再失忆":
  Agent A: review 代码 → 保存状态 (含完整记忆)
  Agent B: 加载 A 的记忆 → 不重新分析, 仅凭记忆回答 "上次发现了什么 bug"

如果 B 能说出 A 发现的 bug (如 divide-by-zero), 证明记忆系统真实可用——
不只是 "能存能取", 而是 "真能帮 agent 跨会话延续"。

Verifies the save/load fix gives the agent real cross-session memory:
A reviews code + saves; B loads A's memory and recalls the findings
WITHOUT re-analyzing — proving memory actually helps, not just round-trips.
"""
import asyncio
import os
import sys

from core import Nonull

SAMPLE_CODE = '''\
def divide(a, b):
    return a / b

class Cache:
    def get(self, key):
        return self._data[key]
'''


async def main() -> None:
    state_path = os.path.expanduser("~/.Nonull/demos/memory_continuity.json")
    os.makedirs(os.path.dirname(state_path), exist_ok=True)

    # ── Agent A: review + save / Agent A reviews then saves memory ──
    print("=" * 60)
    print("🤖 Agent A: review 代码并保存记忆")
    print("=" * 60)
    agent_a = Nonull(name="reviewer-A")
    if agent_a.llm_client is None:
        print("⚠️  未配置 LLM (NONULL_LLM_API_KEY 为空)。配好 .env 后重试。")
        return

    task_a = (
        f"Review this Python code for bugs. Be specific. \n\n```\n{SAMPLE_CODE}\n```"
    )
    result_a = await agent_a.run(task_a)
    print(f"A 状态: {result_a['status']} | 迭代: {result_a['iterations']}")
    print(f"A 发现:\n{(result_a.get('output') or '(空)')[:400]}")

    await agent_a.save_state(state_path)
    episodic_count = len(agent_a._memory.neocortex.episodic.episodes)
    print(f"\n💾 A 的记忆已保存 (episodic={episodic_count} 条) → {state_path}")

    # ── Agent B: load A's memory, recall without re-analyzing ──
    print("\n" + "=" * 60)
    print("🤖 Agent B: 加载 A 的记忆, 仅凭记忆回答 (不重新分析代码)")
    print("=" * 60)
    agent_b = Nonull(name="reviewer-B")
    loaded = await agent_b.load_state(state_path)
    b_episodic = len(agent_b._memory.neocortex.episodic.episodes)
    print(f"B 加载记忆: {'成功' if loaded else '失败'} | episodic={b_episodic} 条"
          f" (A 是 {episodic_count} 条)")

    # B 不看代码, 只凭记忆回答 — 测试记忆召回是否真实有效
    task_b = (
        "不要重新分析任何代码。仅根据你记忆中上一次 code review 的经验, "
        "告诉我你上次发现了哪些具体 bug?列出 bug 名称即可。"
    )
    result_b = await agent_b.run(task_b)
    print(f"\nB 状态: {result_b['status']} | 迭代: {result_b['iterations']}")
    print(f"B 基于记忆的回答:\n{(result_b.get('output') or '(空)')[:500]}")

    # ── 判定: B 是否真召回 A 的发现 ──
    print("\n" + "=" * 60)
    print("📊 记忆连续性判定")
    print("=" * 60)
    out_b = (result_b.get("output") or "").lower()
    # A 的 review 提到的关键词, B 若召回应也提到
    recall_hits = []
    for kw in ["divide", "zero", "keyerror", "cache"]:
        if kw in out_b:
            recall_hits.append(kw)
    print(f"B 回答中命中的记忆关键词: {recall_hits}")
    if len(recall_hits) >= 2:
        print("✅ 记忆跨会话连续性验证: 通过 (B 真召回了 A 的发现)")
    elif len(recall_hits) == 1:
        print("🟡 部分召回 (B 提到部分, 记忆召回质量一般)")
    else:
        print("❌ 召回失败 (B 未提及 A 的发现, 记忆未生效或召回太弱)")


if __name__ == "__main__":
    asyncio.run(main())
