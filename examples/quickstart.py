"""
Nonull 快速入门示例 — 简单到不能再简单
"""

# ═══════════════════════════════════════
# 1️⃣ 最简模式：3行代码
# ═══════════════════════════════════════

from core import Nonull

agent = Nonull()
result = agent.run_sync("分析这个AEB模块有什么安全问题")
print(result["output"])

# ═══════════════════════════════════════
# 2️⃣ 异步模式：适合复杂任务
# ═══════════════════════════════════════

import asyncio


async def example_async():
    agent = Nonull()
    result = await agent.run("审查这段感知代码的性能瓶颈")
    print(f"耗时: {result['duration']}s")
    print(f"结果: {result['output']}")


asyncio.run(example_async())

# ═══════════════════════════════════════
# 3️⃣ 切换人格（Nonull 独有）
# ═══════════════════════════════════════

from persona import PersonaOrchestrator, PersonaType

# 三种人格，同一个代码三种看法
for p in [PersonaType.CONSERVATIVE, PersonaType.SPORTY, PersonaType.VETERAN]:
    ai = PersonaOrchestrator(p)
    info = ai.get_current_persona()
    print(f"[{info['name']}] {info['phrase']}")

# ═══════════════════════════════════════
# 4️⃣ 查看安全成绩单
# ═══════════════════════════════════════

orchestrator = PersonaOrchestrator()
scorecard = orchestrator.get_scorecard()
print(f"安全评分: {scorecard.get('average_score', 'N/A')}")

# ═══════════════════════════════════════
# 5️⃣ 场景覆盖分析
# ═══════════════════════════════════════

from persona import ScenarioEngine

engine = ScenarioEngine()
report = engine.analyze_scenario_coverage(["高速巡航", "前车切入"])
print(f"场景覆盖率: {report['coverage_pct']}%  — 缺失: {report['missing_scenarios']}")
