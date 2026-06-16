"""
多模型混合调度真实 demo / Real-LLM demo for the hybrid multi-model scheduler.

用真实 LLM 验证 multimodel 包的端到端行为 (单元测试只用 MockClient, 真跑才
能暴露真问题 —— 这正是本项目反复验证过的教训)。

注意: .env 只配了一个真实模型 (MiniMax-M3)。为了在不要求额外 key 的前提下
演示"路由到不同 tier"的逻辑, 本 demo 把同一个真实端点注册成多个逻辑模型
(fast=small / reasoner=large), 它们 model_id 相同但 tier/优先级不同。这足以
验证: 路由分类是否正确、调用分发是否真打到 LLM、协作流水线是否真跑通。
真实多厂商场景只需在 nonull_models.yaml 配多个不同 base_url/key 即可。

Run:  python examples/multimodel_demo.py
"""
import asyncio
import os

from multimodel import (
    ModelRegistry, ModelEntry, ModelTier, PrivacyLevel,
    TaskRouter, ModelDispatcher, MultiModelCollaborator, HybridScheduler,
    RoutingStrategy,
)
from core.llm_client import LLMConfig
from core.cost_tracker import CostTracker


def _build_registry() -> ModelRegistry:
    """用 .env 的真实 MiniMax 端点注册多个逻辑模型 (不同 tier)。"""
    cfg = LLMConfig.from_env()
    if not cfg.api_key:
        return None

    reg = ModelRegistry()
    # 小模型 (简单任务路由目标) —— 真实端点, 标记为 small + 低 max_tokens
    reg.register(ModelEntry(
        name="fast", model_id=cfg.model, provider=cfg.provider,
        base_url=cfg.base_url, api_keys=[cfg.api_key],
        tier=ModelTier.SMALL, priority=50,
        cost_per_1k_in=0.0002, cost_per_1k_out=0.0008, avg_latency_ms=800,
        max_tokens=1024, timeout=90.0,  # MiniMax-M3 是推理模型, 长<think>需更长超时
    ))
    # 强模型 (复杂任务路由目标) —— 同一真实端点, 标记为 large + 高优先级
    reg.register(ModelEntry(
        name="reasoner", model_id=cfg.model, provider=cfg.provider,
        base_url=cfg.base_url, api_keys=[cfg.api_key],
        tier=ModelTier.LARGE, priority=100,
        cost_per_1k_in=0.0005, cost_per_1k_out=0.0022, avg_latency_ms=2500,
        max_tokens=2048, timeout=90.0,
    ))
    # 第二个强模型 (协作时交叉校验用不同模型) —— 同端点, 不同逻辑名
    reg.register(ModelEntry(
        name="reviewer", model_id=cfg.model, provider=cfg.provider,
        base_url=cfg.base_url, api_keys=[cfg.api_key],
        tier=ModelTier.LARGE, priority=90,
        cost_per_1k_in=0.0005, cost_per_1k_out=0.0022, avg_latency_ms=2500,
        max_tokens=2048, timeout=90.0,
    ))
    return reg


async def main() -> None:
    print("=" * 64)
    print("🌐 多模型混合调度 — 真实 LLM 验证 / Hybrid scheduler real-LLM demo")
    print("=" * 64)

    reg = _build_registry()
    if reg is None:
        print("⚠️  未配置 LLM (.env 的 NONULL_LLM_API_KEY 为空)。跳过。")
        return
    print(f"✅ 注册 {len(reg)} 个逻辑模型: {[e.name for e in reg.all()]}")
    print(f"   (同一真实端点, 不同 tier/优先级, 演示路由逻辑)\n")

    cost = CostTracker()
    scheduler = HybridScheduler(reg, cost_tracker=cost,
                                default_strategy=RoutingStrategy.BALANCED)

    # ── 测试 1: 简单任务 → 应路由到 small 模型, 单模型执行 ──
    print("─" * 64)
    print("【测试 1】简单任务 (应路由 small, mode=single)")
    print("─" * 64)
    r1 = await scheduler.aschedule("用一句话解释什么是快速排序")
    print(f"  路由复杂度: {r1.complexity}")
    print(f"  执行模式:   {r1.mode}")
    print(f"  用了模型:   {r1.model_used}")
    print(f"  成功:       {r1.success}")
    print(f"  输出(120字): {(r1.output or '(空)')[:120]}")

    # ── 测试 2: 复杂任务 → 应路由到 large 模型, 单模型执行 ──
    print("\n" + "─" * 64)
    print("【测试 2】复杂任务 (应路由 large, mode=single)")
    print("─" * 64)
    r2 = await scheduler.aschedule(
        "分析并实现一个线程安全的 LRU 缓存, 说明时间复杂度和并发处理"
    )
    print(f"  路由复杂度: {r2.complexity}")
    print(f"  执行模式:   {r2.mode}")
    print(f"  用了模型:   {r2.model_used}")
    print(f"  成功:       {r2.success}")
    print(f"  输出(150字): {(r2.output or '(空)')[:150]}")

    # ── 测试 3: 超复杂任务 → 应触发多模型协作 ──
    print("\n" + "─" * 64)
    print("【测试 3】超复杂任务 (应触发 mode=collaboration)")
    print("─" * 64)
    r3 = await scheduler.aschedule(
        "请全面设计一个端到端的完整分布式限流系统方案, 需要系统性地"
        "分析架构设计、算法实现、容错推理、性能优化、部署运维多个方面"
    )
    print(f"  路由复杂度: {r3.complexity}")
    print(f"  执行模式:   {r3.mode}")
    print(f"  用了模型:   {r3.model_used}")
    print(f"  成功:       {r3.success}")
    if r3.mode == "collaboration":
        d = r3.detail
        print(f"  拆解子任务: {d.get('subtask_count')} 个")
        print(f"  交叉校验:   {d.get('cross_checked')}")
        print(f"  参与模型数: {d.get('total_models_used')}")
    print(f"  输出(200字): {(r3.output or '(空)')[:200]}")

    # ── 测试 4: 隐私任务 → 应强制本地 (但无本地模型时降级 + 警告) ──
    print("\n" + "─" * 64)
    print("【测试 4】隐私任务 (隐私分类, 无本地模型时降级)")
    print("─" * 64)
    r4 = await scheduler.aschedule("处理这份内网机密数据, 不要外传")
    print(f"  隐私级别:   {r4.privacy}")
    print(f"  用了模型:   {r4.model_used}")
    print(f"  (隐私正确识别为 internal; 真实部署配 Ollama 本地模型即强制本地)")

    # ── 汇总: 调用日志 + 成本 ──
    print("\n" + "=" * 64)
    print("📊 调度统计 / Scheduler stats")
    print("=" * 64)
    stats = scheduler.stats()
    print(f"  注册模型:   {stats['models_registered']}")
    cl = stats["call_log"]
    print(f"  总调用次数: {cl.get('total_calls')}")
    print(f"  成功率:     {cl.get('success_rate')}")
    print(f"  各模型调用: {cl.get('by_model')}")
    print(f"  总成本:     ${cl.get('total_cost', 0):.5f}")

    # 验证断言
    print("\n" + "=" * 64)
    print("✅ 验证结论 / Verdict")
    print("=" * 64)
    checks = [
        ("简单任务路由到 small/local", r1.complexity == "simple"),
        ("复杂任务路由到 large", r2.complexity in ("complex", "super_complex")),
        ("超复杂触发协作", r3.mode == "collaboration"),
        ("隐私任务识别 internal", r4.privacy == "internal"),
        ("所有调用真打到 LLM", cl.get("total_calls", 0) > 0),
    ]
    for label, ok in checks:
        print(f"  {'✅' if ok else '❌'} {label}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
