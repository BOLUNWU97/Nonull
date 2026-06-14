"""
成本集成测试 / Cost-tracking integration tests for Nonull.

钉住 CostTracker 与 Nonull LLM 调用的集成行为: 每次 plan/reason/reflect
调用都应记账、按 response.model 正确归因、get_status 暴露 cost, 且记账
失败绝不破坏主循环。这是上一轮 model-归因 bug 溜进来时的测试真空。

Pins the CostTracker↔Nonull integration: every plan/reason/reflect call
records cost, attributes to response.model (not "unknown"), get_status
exposes cost, and tracking failure never breaks the loop.
"""
import asyncio
import json

import pytest

from core.agent_core import Nonull
from core.llm_client import LLMResponse


class CostAwareMockLLM:
    """MockLLM that returns realistic usage for cost attribution tests."""

    def __init__(self, model: str = "gpt-4o"):
        self.model = model

    def chat(self, messages, tools=None, **kwargs) -> LLMResponse:
        user = messages[-1].content
        if "Decompose into" in user:
            payload = {"subtasks": [{"id": "s1", "description": "d",
                        "skill_or_tool": None, "dependencies": []}],
                       "strategy": "sequential", "estimated_steps": 1}
        elif "Choose the next action" in user:
            payload = {"next_action": "complete", "reasoning": "r", "confidence": 0.9}
        elif "Evaluate honestly" in user:
            payload = {"completed": True, "summary": "done", "issues": [],
                       "improvements": [], "score": 0.9}
        else:
            payload = {}
        return LLMResponse(
            content=json.dumps(payload),
            model=self.model,
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )


def _make_agent(monkeypatch, mock):
    monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
    a = Nonull()
    a._llm_client = mock
    return a


class TestCostRecordingPerCall:
    def test_three_calls_recorded(self, monkeypatch):
        """plan + reason + reflect = 3 LLM calls → 3 cost records."""
        a = _make_agent(monkeypatch, CostAwareMockLLM())
        asyncio.run(a.run("test"))
        assert len(a.cost_tracker) == 3

    def test_zero_calls_without_llm(self, monkeypatch):
        """无 LLM 客户端时不应有任何成本记录."""
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        a._llm_client = None
        asyncio.run(a.run("no-llm task"))
        assert len(a.cost_tracker) == 0


class TestModelAttribution:
    def test_attributed_to_response_model_not_unknown(self, monkeypatch):
        """钉住 model-归因 bug: 记账必须用 response.model, 不能 fallback 'unknown'."""
        a = _make_agent(monkeypatch, CostAwareMockLLM(model="deepseek-chat"))
        asyncio.run(a.run("test"))
        by_model = a.cost_tracker.by_model()
        assert "deepseek-chat" in by_model
        assert "unknown" not in by_model

    def test_different_models_tracked_separately(self, monkeypatch):
        """多模型调用应分开归因."""
        a = _make_agent(monkeypatch, CostAwareMockLLM(model="gpt-4o-mini"))
        asyncio.run(a.run("test"))
        # 再用不同模型记一笔
        a.cost_tracker.record("deepseek-chat", 200, 100)
        by_model = a.cost_tracker.by_model()
        assert "gpt-4o-mini" in by_model
        assert "deepseek-chat" in by_model


class TestCostCalculation:
    def test_total_matches_gpt4o_pricing(self, monkeypatch):
        """3 × (100 prompt + 50 completion) at gpt-4o = 3 × 0.00075 = 0.00225."""
        a = _make_agent(monkeypatch, CostAwareMockLLM(model="gpt-4o"))
        asyncio.run(a.run("test"))
        # gpt-4o: input 0.0025, output 0.010 per 1K
        # per call: 100/1000*0.0025 + 50/1000*0.010 = 0.00025 + 0.0005 = 0.00075
        assert abs(a.cost_tracker.total_cost() - 0.00225) < 1e-6

    def test_local_model_zero_cost(self, monkeypatch):
        """本地模型 (llama3) 不计成本."""
        a = _make_agent(monkeypatch, CostAwareMockLLM(model="llama3"))
        asyncio.run(a.run("test"))
        assert a.cost_tracker.total_cost() == 0.0


class TestGetStatusExposesCost:
    def test_status_has_cost_field(self, monkeypatch):
        a = _make_agent(monkeypatch, CostAwareMockLLM())
        asyncio.run(a.run("test"))
        st = a.get_status()
        assert "cost" in st

    def test_status_cost_call_count(self, monkeypatch):
        a = _make_agent(monkeypatch, CostAwareMockLLM())
        asyncio.run(a.run("test"))
        assert a.get_status()["cost"]["call_count"] == 3

    def test_status_cost_includes_by_model(self, monkeypatch):
        a = _make_agent(monkeypatch, CostAwareMockLLM(model="gpt-4o"))
        asyncio.run(a.run("test"))
        cost = a.get_status()["cost"]
        assert "by_model" in cost
        assert "gpt-4o" in cost["by_model"]


class TestRobustness:
    def test_record_cost_with_no_usage_is_noop(self, monkeypatch):
        """response 无 usage → _record_llm_cost 不崩, 不记账."""
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        # 构造一个无 usage 的 response-like 对象
        fake_resp = type("R", (), {
            "usage": None, "model": "gpt-4o",
            "prompt_tokens": 0, "completion_tokens": 0,
        })()
        a._record_llm_cost(fake_resp)  # 不应抛异常
        assert len(a.cost_tracker) == 0

    def test_cost_tracking_never_breaks_loop(self, monkeypatch):
        """即使 _record_llm_cost 内部出问题, 主循环仍应完成."""

        class BrokenTracker:
            def record(self, *a, **kw):
                raise RuntimeError("tracker exploded")
            def summary(self):
                return {"call_count": 0, "total_cost": 0, "by_model": {}}
            def __len__(self):
                return 0

        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        a._llm_client = CostAwareMockLLM()
        a._cost_tracker = BrokenTracker()  # 注入会爆炸的 tracker
        result = asyncio.run(a.run("robustness test"))
        # 记账爆炸不应影响 agent 完成
        assert result["status"] in ("completed", "error")

    def test_budget_exceeded_warns_not_crashes(self, monkeypatch, caplog):
        """预算超限只告警不崩."""
        from core.cost_tracker import CostTracker
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        a._llm_client = CostAwareMockLLM()
        a._cost_tracker = CostTracker(budget=0.0)  # 零预算, 第一次记录就超
        with caplog.at_level("WARNING"):
            result = asyncio.run(a.run("budget test"))
        # agent 仍应跑完 (告警不中断)
        assert result["status"] in ("completed", "error")
