"""
Cost Tracker 测试 / Tests for core.cost_tracker.

验证成本计算、聚合、预算、模糊匹配、持久化。无需 API key。
"""
import pytest

from core.cost_tracker import (
    CostTracker, BudgetExceeded, UsageRecord, DEFAULT_PRICE_TABLE,
)


# ── 成本计算 / Cost calculation ─────────────────────────────────

class TestCostCalculation:
    def test_known_model_cost(self):
        t = CostTracker()
        cost = t.record("gpt-4o", prompt_tokens=1000, completion_tokens=500)
        # 1000/1000 * 0.0025 + 500/1000 * 0.010 = 0.0025 + 0.005 = 0.0075
        assert abs(cost - 0.0075) < 1e-6

    def test_local_model_zero_cost(self):
        t = CostTracker()
        cost = t.record("llama3", prompt_tokens=1000, completion_tokens=500)
        assert cost == 0.0

    def test_ollama_local_zero(self):
        t = CostTracker()
        assert t.record("ollama", 9999, 9999) == 0.0

    def test_fuzzy_prefix_match(self):
        """带版本后缀的模型名应前缀匹配到基准模型."""
        t = CostTracker()
        # gpt-4o-2024-08-06 → 匹配 gpt-4o
        cost = t.record("gpt-4o-2024-08-06", 1000, 0)
        assert abs(cost - 0.0025) < 1e-6

    def test_case_insensitive(self):
        t = CostTracker()
        cost = t.record("GPT-4O", 1000, 0)
        assert abs(cost - 0.0025) < 1e-6

    def test_unknown_model_uses_conservative_default(self):
        t = CostTracker()
        # 未知模型 → gpt-4o-mini (0.00015 input)
        cost = t.record("some-future-model", 1000, 0)
        assert abs(cost - 0.00015) < 1e-6


# ── 聚合 / Aggregation ──────────────────────────────────────────

class TestAggregation:
    def test_total_cost_and_tokens(self):
        t = CostTracker()
        t.record("gpt-4o", 1000, 500)
        t.record("gpt-4o-mini", 2000, 100)
        assert t.total_cost() > 0
        tokens = t.total_tokens()
        assert tokens["prompt"] == 3000
        assert tokens["completion"] == 600
        assert tokens["total"] == 3600

    def test_by_model_groups_calls(self):
        t = CostTracker()
        t.record("gpt-4o", 1000, 0)
        t.record("gpt-4o", 500, 0)
        t.record("gpt-4o-mini", 1000, 0)
        agg = t.by_model()
        assert agg["gpt-4o"]["calls"] == 2
        assert agg["gpt-4o"]["prompt_tokens"] == 1500
        assert agg["gpt-4o-mini"]["calls"] == 1

    def test_summary_structure(self):
        t = CostTracker(budget=1.0)
        t.record("gpt-4o", 1000, 0)
        s = t.summary()
        assert s["total_cost"] > 0
        assert s["budget"] == 1.0
        assert s["budget_remaining"] is not None
        assert s["budget_remaining"] < 1.0
        assert "by_model" in s
        assert s["call_count"] == 1

    def test_summary_no_budget(self):
        t = CostTracker()
        s = t.summary()
        assert s["budget"] is None
        assert s["budget_remaining"] is None


# ── 预算 / Budget ───────────────────────────────────────────────

class TestBudget:
    def test_budget_exceeded_raises(self):
        t = CostTracker(budget=0.001)
        with pytest.raises(BudgetExceeded):
            t.record("gpt-4o", 10000, 10000)

    def test_check_budget_within(self):
        t = CostTracker(budget=10.0)
        t.record("gpt-4o-mini", 1000, 0)
        assert t.check_budget() is True

    def test_no_budget_never_raises(self):
        t = CostTracker()  # budget=None → 无限
        t.record("gpt-4o", 10 ** 9, 10 ** 9)
        # 不 raise 即通过

    def test_zero_tokens_zero_cost(self):
        t = CostTracker(budget=0.0)
        t.record("gpt-4o", 0, 0)  # 0 token, $0 cost, 不超 $0 预算
        assert t.total_cost() == 0.0


# ── 自定义价格 / Custom pricing ─────────────────────────────────

class TestCustomPrice:
    def test_register_price(self):
        t = CostTracker()
        t.register_price("custom-llm", 0.001, 0.002)
        cost = t.record("custom-llm", 1000, 1000)
        # 1000/1000*0.001 + 1000/1000*0.002 = 0.003
        assert abs(cost - 0.003) < 1e-6

    def test_default_price_table_not_mutated(self):
        before = dict(DEFAULT_PRICE_TABLE["gpt-4o"])
        t = CostTracker()
        t.register_price("gpt-4o", 99, 99)  # 改实例的, 不改模块常量
        assert DEFAULT_PRICE_TABLE["gpt-4o"] == before


# ── 持久化 / Persistence ────────────────────────────────────────

class TestPersistence:
    def test_roundtrip(self, tmp_path):
        t = CostTracker(budget=5.0)
        t.record("gpt-4o", 1000, 500)
        t.record("deepseek-chat", 2000, 300)
        path = str(tmp_path / "cost.json")
        t.save(path)
        loaded = CostTracker.load(path)
        assert loaded.total_cost() == t.total_cost()
        assert len(loaded) == 2
        assert loaded.summary()["budget"] == 5.0

    def test_by_model_after_reload(self, tmp_path):
        t = CostTracker()
        t.record("gpt-4o", 1000, 0)
        t.record("gpt-4o", 500, 0)
        path = str(tmp_path / "c.json")
        t.save(path)
        loaded = CostTracker.load(path)
        assert loaded.by_model()["gpt-4o"]["calls"] == 2

    def test_reset(self):
        t = CostTracker()
        t.record("gpt-4o", 1000, 0)
        assert len(t) == 1
        t.reset()
        assert len(t) == 0
        assert t.total_cost() == 0.0


# ── UsageRecord 序列化 / Record serialization ───────────────────

class TestUsageRecord:
    def test_roundtrip(self):
        r = UsageRecord(model="gpt-4o", prompt_tokens=100, completion_tokens=50,
                        cost=0.001, timestamp=1234567.0)
        d = r.to_dict()
        r2 = UsageRecord.from_dict(d)
        assert r2.model == r.model
        assert r2.prompt_tokens == r.prompt_tokens
        assert r2.cost == r.cost
        assert r2.timestamp == r.timestamp
