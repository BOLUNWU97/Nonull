"""
multimodel 单元测试 / Unit tests for the multi-model hybrid scheduler.

纯逻辑测试 (MockClient/MockLLM, $0, 无真实 LLM):
  - ModelRegistry: 注册/按档位/隐私/成本/速度筛选, from_config
  - KeyRotator: 多 Key 轮询 + 冷却跳过
  - TaskRouter: 简单/复杂/超复杂/隐私分类 + 策略选模型
  - ModelDispatcher: 调用 + 重试 + 多 Key 轮询 + 降级 + 日志 (MockClient)
  - MultiModelCollaborator: 拆解/并行/汇总 (MockClient)
"""
import asyncio
import time

import pytest

from multimodel import (
    ModelRegistry, ModelEntry, ModelTier, PrivacyLevel, KeyRotator,
    TaskRouter, RoutingStrategy, TaskComplexity,
    ModelDispatcher, CallLogger,
    MultiModelCollaborator, HybridScheduler,
)


# ── 测试夹具 / Fixtures ──────────────────────────────────────────

def _make_registry():
    reg = ModelRegistry()
    reg.register(ModelEntry(name="big", model_id="gpt-4o", tier=ModelTier.LARGE,
                            priority=90, cost_per_1k_in=0.0025, avg_latency_ms=2000,
                            api_keys=["k1", "k2"]))
    reg.register(ModelEntry(name="reasoner", model_id="deepseek-reasoner",
                            tier=ModelTier.LARGE, priority=100, cost_per_1k_in=0.0005,
                            avg_latency_ms=3000, api_keys=["k3"]))
    reg.register(ModelEntry(name="mini", model_id="gpt-4o-mini", tier=ModelTier.SMALL,
                            priority=50, cost_per_1k_in=0.0001, avg_latency_ms=600,
                            api_keys=["k1"]))
    reg.register(ModelEntry(name="local", model_id="llama3.1", tier=ModelTier.LOCAL,
                            is_local=True, priority=70, api_keys=["ollama"]))
    return reg


class _MockResp:
    def __init__(self, content):
        self.content = content
        self.prompt_tokens = 10
        self.completion_tokens = 20
        self.model = "mock"


class _MockClient:
    """模拟 LLMClient: chat 返回固定/脚本化内容。"""
    def __init__(self, content="mock answer", fail_times=0):
        self.content = content
        self.fail_times = fail_times
        self.calls = 0

    def chat(self, messages, json_mode=False, **kw):
        self.calls += 1
        if self.calls <= self.fail_times:
            from core.llm_client import LLMServerError
            raise LLMServerError("mock server error")
        return _MockResp(self.content)

    def close(self):
        pass


# ── ModelRegistry ────────────────────────────────────────────────

class TestModelRegistry:
    def test_register_and_get(self):
        reg = _make_registry()
        assert len(reg) == 4
        assert reg.get("big").model_id == "gpt-4o"

    def test_by_tier_sorted_by_priority(self):
        reg = _make_registry()
        large = reg.by_tier(ModelTier.LARGE)
        assert [e.name for e in large] == ["reasoner", "big"]  # priority 100 > 90

    def test_local_models(self):
        reg = _make_registry()
        locals_ = reg.local_models()
        assert len(locals_) == 1 and locals_[0].name == "local"

    def test_cheapest(self):
        reg = _make_registry()
        cheapest = reg.cheapest(reg.by_tier(ModelTier.LARGE))
        assert cheapest.name == "reasoner"  # 0.0005 < 0.0025

    def test_fastest(self):
        reg = _make_registry()
        fastest = reg.fastest(reg.by_tier(ModelTier.LARGE))
        assert fastest.name == "big"  # 2000 < 3000

    def test_local_forces_internal_privacy(self):
        e = ModelEntry(name="x", model_id="m", is_local=True)
        assert e.privacy == PrivacyLevel.INTERNAL  # __post_init__ 升级


# ── KeyRotator ───────────────────────────────────────────────────

class TestKeyRotator:
    def test_round_robin(self):
        r = KeyRotator(["a", "b", "c"])
        now = time.time()
        got = [r.next_key(now) for _ in range(6)]
        assert got == ["a", "b", "c", "a", "b", "c"]

    def test_skips_cooled_down(self):
        r = KeyRotator(["a", "b"])
        now = time.time()
        r.cooldown_key("a", now + 100)  # 冷却 a
        # 接下来应只返回 b
        got = [r.next_key(now) for _ in range(3)]
        assert all(k == "b" for k in got)

    def test_single_key(self):
        r = KeyRotator(["only"])
        assert r.next_key(time.time()) == "only"


# ── TaskRouter ───────────────────────────────────────────────────

class TestTaskRouter:
    def test_simple_task_routes_small(self):
        router = TaskRouter(_make_registry())
        d = router.route("翻译: hello world")
        assert d.complexity == TaskComplexity.SIMPLE
        assert d.model.tier in (ModelTier.SMALL, ModelTier.LOCAL)

    def test_complex_task_routes_large(self):
        router = TaskRouter(_make_registry())
        d = router.route("帮我设计并实现一个分布式限流算法, 分析其时间复杂度")
        assert d.complexity in (TaskComplexity.COMPLEX, TaskComplexity.SUPER_COMPLEX)
        assert d.model.tier == ModelTier.LARGE

    def test_code_task_is_complex(self):
        router = TaskRouter(_make_registry())
        d = router.route("```python\ndef foo(): pass\n``` 帮我调试")
        assert d.complexity != TaskComplexity.SIMPLE

    def test_privacy_forces_local(self):
        router = TaskRouter(_make_registry())
        d = router.route("处理这份内网机密数据, 不要外传")
        assert d.privacy == PrivacyLevel.INTERNAL
        assert d.model.is_local

    def test_super_complex_needs_collaboration(self):
        router = TaskRouter(_make_registry())
        big_task = "请全面设计一个端到端的完整系统方案, " + "需要分析架构设计实现推理优化部署运维监控。" * 100
        d = router.route(big_task)
        assert d.complexity == TaskComplexity.SUPER_COMPLEX
        assert d.needs_collaboration

    def test_cost_strategy_picks_cheapest(self):
        router = TaskRouter(_make_registry())
        d = router.route("设计一个复杂算法方案", strategy=RoutingStrategy.COST)
        assert d.model.name == "reasoner"  # 最便宜的 large

    def test_speed_strategy_picks_fastest(self):
        router = TaskRouter(_make_registry())
        d = router.route("设计一个复杂算法方案", strategy=RoutingStrategy.SPEED)
        assert d.model.name == "big"  # 最快的 large


# ── ModelDispatcher ──────────────────────────────────────────────

class TestModelDispatcher:
    def test_dispatch_success(self, monkeypatch):
        reg = _make_registry()
        disp = ModelDispatcher(reg)
        mock = _MockClient("hello from model")
        monkeypatch.setattr(disp, "_get_client", lambda e, k: mock)
        from core.llm_client import LLMMessage
        result = disp.dispatch(reg.get("big"), [LLMMessage(role="user", content="hi")])
        assert result.success
        assert result.content == "hello from model"
        assert result.log.attempts == 1

    def test_dispatch_retries_on_server_error(self, monkeypatch):
        reg = _make_registry()
        disp = ModelDispatcher(reg, max_retries=2, backoff_base=0.0)
        mock = _MockClient("recovered", fail_times=1)  # 第1次失败, 第2次成功
        monkeypatch.setattr(disp, "_get_client", lambda e, k: mock)
        from core.llm_client import LLMMessage
        result = disp.dispatch(reg.get("big"), [LLMMessage(role="user", content="hi")],
                               allow_fallback=False)
        assert result.success
        assert result.log.attempts == 2  # 重试了一次

    def test_dispatch_logs_call(self, monkeypatch):
        reg = _make_registry()
        disp = ModelDispatcher(reg)
        mock = _MockClient("ok")
        monkeypatch.setattr(disp, "_get_client", lambda e, k: mock)
        from core.llm_client import LLMMessage
        disp.dispatch(reg.get("mini"), [LLMMessage(role="user", content="hi")])
        summary = disp.call_logger.summary()
        assert summary["total_calls"] == 1
        assert summary["success"] == 1

    def test_dispatch_uses_multiple_keys(self, monkeypatch):
        """多 Key 模型: 连续调用应轮询不同 Key。"""
        reg = _make_registry()
        disp = ModelDispatcher(reg)
        used_keys = []
        def fake_get_client(entry, key):
            used_keys.append(key)
            return _MockClient("ok")
        monkeypatch.setattr(disp, "_get_client", fake_get_client)
        from core.llm_client import LLMMessage
        msgs = [LLMMessage(role="user", content="hi")]
        disp.dispatch(reg.get("big"), msgs)  # big 有 k1, k2
        disp.dispatch(reg.get("big"), msgs)
        assert used_keys[0] != used_keys[1]  # 轮询了不同 Key


# ── MultiModelCollaborator ───────────────────────────────────────

class TestCollaborator:
    async def test_decompose_and_synthesize(self, monkeypatch):
        reg = _make_registry()
        router = TaskRouter(reg)
        disp = ModelDispatcher(reg)

        # mock: decompose 返回 JSON, 子任务/汇总返回文本
        def fake_get_client(entry, key):
            return _MockClient('{"subtasks": [{"id": "s1", "description": "part A", "depends_on": []}, {"id": "s2", "description": "part B", "depends_on": []}]}')
        monkeypatch.setattr(disp, "_get_client", fake_get_client)

        collab = MultiModelCollaborator(reg, router, disp, enable_cross_check=False)
        subtasks = await collab.decompose("complex task")
        assert len(subtasks) == 2
        assert subtasks[0].id == "s1"

    async def test_full_collaboration(self, monkeypatch):
        reg = _make_registry()
        router = TaskRouter(reg)
        disp = ModelDispatcher(reg)

        call_count = [0]
        def fake_get_client(entry, key):
            call_count[0] += 1
            # 第一次调用是 decompose (需 JSON), 之后是子任务/汇总
            return _MockClient('{"subtasks": [{"id": "s1", "description": "A", "depends_on": []}]}')
        monkeypatch.setattr(disp, "_get_client", fake_get_client)

        collab = MultiModelCollaborator(reg, router, disp, enable_cross_check=False)
        result = await collab.collaborate("super complex task")
        assert result.final_output  # 有输出
        assert len(result.subtasks) >= 1


# ── HybridScheduler (门面) ───────────────────────────────────────

class TestHybridScheduler:
    async def test_simple_task_single_mode(self, monkeypatch):
        reg = _make_registry()
        sched = HybridScheduler(reg)
        mock = _MockClient("simple answer")
        monkeypatch.setattr(sched.dispatcher, "_get_client", lambda e, k: mock)
        result = await sched.aschedule("翻译: hi")
        assert result.mode == "single"
        assert result.success
        assert result.complexity == "simple"

    async def test_stats(self, monkeypatch):
        reg = _make_registry()
        sched = HybridScheduler(reg)
        mock = _MockClient("ok")
        monkeypatch.setattr(sched.dispatcher, "_get_client", lambda e, k: mock)
        await sched.aschedule("hello")
        stats = sched.stats()
        assert stats["models_registered"] == 4
        assert stats["call_log"]["total_calls"] >= 1


# ── 整改/优化回归 (审计发现的 P0/P1/P2 修复) ────────────────────

class TestHardeningFixes:
    def test_env_var_expansion(self, monkeypatch):
        """P0: from_config 展开 ${ENV_VAR}, 不传字面量当 Key。"""
        from multimodel.registry import _expand_env
        monkeypatch.setenv("MY_TEST_KEY", "sk-real-12345")
        assert _expand_env("${MY_TEST_KEY}") == "sk-real-12345"
        assert _expand_env(["${MY_TEST_KEY}", "plain"]) == ["sk-real-12345", "plain"]
        # 未定义变量 → 空串 (不泄漏字面量)
        assert _expand_env("${UNDEFINED_VAR_XYZ}") == ""

    def test_from_config_expands_keys(self, monkeypatch):
        """P0: from_config 的 api_keys 被展开。"""
        monkeypatch.setenv("TESTKEY1", "key-aaa")

        class _Cfg:
            def get_section(self, name):
                if name == "models":
                    return {"m1": {"model_id": "x", "api_keys": ["${TESTKEY1}"], "tier": "large"}}
                return {}
            def get(self, k, d=None):
                return d
        reg = ModelRegistry.from_config(_Cfg())
        assert reg.get("m1").api_keys == ["key-aaa"]  # 展开了, 非 "${TESTKEY1}"

    def test_dispatcher_close_idempotent(self):
        """P1: ModelDispatcher.close() 关闭缓存 client, 幂等。"""
        reg = _make_registry()
        disp = ModelDispatcher(reg)
        disp._client_cache["fake::k"] = _MockClient("x")
        disp.close()
        assert len(disp._client_cache) == 0
        disp.close()  # 第二次不崩

    def test_scheduler_close(self):
        """P1: HybridScheduler.close() 委托 dispatcher.close()。"""
        reg = _make_registry()
        sched = HybridScheduler(reg)
        sched.dispatcher._client_cache["fake::k"] = _MockClient("x")
        sched.close()
        assert len(sched.dispatcher._client_cache) == 0

    def test_fallback_no_double_record(self, monkeypatch):
        """P2: 降级路径不重复 record (CallLogger total_calls 不翻倍)。"""
        reg = _make_registry()
        disp = ModelDispatcher(reg, max_retries=0, backoff_base=0.0)

        # big 永远失败, 降级到其他模型成功
        def fake_get_client(entry, key):
            if entry.name == "big":
                return _MockClient("x", fail_times=99)  # 永远失败
            return _MockClient("alt ok")  # 降级目标成功
        monkeypatch.setattr(disp, "_get_client", fake_get_client)
        from core.llm_client import LLMMessage
        result = disp.dispatch(reg.get("big"), [LLMMessage(role="user", content="hi")],
                               allow_fallback=True)
        # 应成功 (降级), 且每次调用只 record 一次 —— total_calls == 实际尝试数
        summary = disp.call_logger.summary()
        # big 失败1次 + 降级目标成功1次 = 2 条 log (不是 3 条)
        assert summary["total_calls"] == 2
