"""
离线端到端测试 / Offline end-to-end tests for the full agent loop.

用 MockLLMClient 驱动完整的 plan→reason→act→reflect 循环，无需 API key、
零网络调用。这是整个 agent 状态机的回归基准。

Drives the complete ReAct + Plan-and-Execute + Reflexion loop with a mock
LLM — no API key, no network. Serves as the regression baseline for the
agent state machine.
"""
import asyncio
import json
import pytest

from core.llm_client import LLMResponse
from core.agent_core import Nonull, AgentState, BaseTool, SafetyViolation


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------

class MockLLMClient:
    """脚本化的 LLM 替身 / Scripted LLM stand-in.

    按 prompt 内容分发到 plan/reason/reflect 响应。
    reason/reflect 响应可以是列表（按调用次数依次返回，最后一个重复）。
    """

    def __init__(self, plan=None, reasons=None, reflections=None):
        self.plan_payload = plan or {
            "subtasks": [
                {"id": "step_1", "description": "analyze the task",
                 "skill_or_tool": None, "dependencies": []},
                {"id": "step_2", "description": "produce the answer",
                 "skill_or_tool": None, "dependencies": ["step_1"]},
            ],
            "strategy": "sequential",
            "estimated_steps": 2,
        }
        self.reason_payloads = reasons or [
            {"next_action": "complete", "reasoning": "trivial task", "confidence": 0.9},
        ]
        self.reflection_payloads = reflections or [
            {"completed": True, "summary": "done", "issues": [],
             "improvements": [], "score": 0.9},
        ]
        self.calls = []          # 记录每次调用的种类 / record of call kinds
        self._reason_idx = 0
        self._reflect_idx = 0

    def _next(self, payloads, idx):
        item = payloads[min(idx, len(payloads) - 1)]
        return item

    def chat(self, messages, tools=None, **kwargs) -> LLMResponse:
        user = messages[-1].content
        if "Break this task into" in user:
            self.calls.append("plan")
            payload = self.plan_payload
        elif "Decide the next action" in user:
            self.calls.append("reason")
            payload = self._next(self.reason_payloads, self._reason_idx)
            self._reason_idx += 1
        elif "Evaluate your performance" in user:
            self.calls.append("reflect")
            payload = self._next(self.reflection_payloads, self._reflect_idx)
            self._reflect_idx += 1
        else:
            self.calls.append("unknown")
            payload = {}
        return LLMResponse(
            content=json.dumps(payload),
            model="mock",
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )


def make_agent(monkeypatch, mock=None, **mock_kwargs):
    """构造离线 agent 并注入 mock LLM / Build offline agent with mock LLM."""
    monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
    agent = Nonull(name="e2e-test")
    agent._llm_client = mock or MockLLMClient(**mock_kwargs)
    return agent


# ---------------------------------------------------------------------------
# 完整循环 / Full loop
# ---------------------------------------------------------------------------

class TestFullLoopOffline:
    def test_single_cycle_completes(self, monkeypatch):
        """最小闭环：plan→reason(complete)→act→reflect(completed)→COMPLETED."""
        agent = make_agent(monkeypatch)
        result = asyncio.run(agent.run("write a haiku about driving"))

        assert result["status"] == "completed"
        assert result["error"] is None
        assert result["iterations"] == 4  # plan, reason, act, reflect 各占一次迭代
        assert agent.state == AgentState.COMPLETED

    def test_llm_called_in_order(self, monkeypatch):
        """LLM 必须按 plan→reason→reflect 顺序被调用."""
        mock = MockLLMClient()
        agent = make_agent(monkeypatch, mock=mock)
        asyncio.run(agent.run("test task"))

        assert mock.calls == ["plan", "reason", "reflect"]

    def test_plan_recorded_in_result(self, monkeypatch):
        """plan 结果要进入返回值，包含 LLM 给的子任务."""
        agent = make_agent(monkeypatch)
        result = asyncio.run(agent.run("test task"))

        plan = result["plan"]
        assert plan is not None
        assert len(plan["subtasks"]) == 2
        assert plan["subtasks"][0]["id"] == "step_1"

    def test_multi_cycle_until_reflection_completes(self, monkeypatch):
        """reflect 第一次说没完成 → 回到 REASONING 再来一轮."""
        agent = make_agent(
            monkeypatch,
            reasons=[
                {"next_action": "text:first attempt", "reasoning": "try", "confidence": 0.6},
                {"next_action": "complete", "reasoning": "finish", "confidence": 0.9},
            ],
            reflections=[
                {"completed": False, "summary": "not yet", "issues": ["incomplete"],
                 "improvements": ["continue"], "score": 0.4},
                {"completed": True, "summary": "done", "issues": [],
                 "improvements": [], "score": 0.9},
            ],
        )
        result = asyncio.run(agent.run("multi-step task"))

        assert result["status"] == "completed"
        # plan + (reason,act,reflect) ×2 = 7 次状态迭代
        assert result["iterations"] == 7
        assert len(agent._context["action_history"]) == 2
        assert len(agent._context["reflection_history"]) == 2

    def test_action_history_records_actions(self, monkeypatch):
        agent = make_agent(
            monkeypatch,
            reasons=[{"next_action": "text:say hello", "reasoning": "r", "confidence": 0.8}],
        )
        asyncio.run(agent.run("greeting task"))

        history = agent._context["action_history"]
        assert len(history) == 1
        assert history[0]["action"] == "text:say hello"
        assert history[0]["result"]["status"] == "executed"

    def test_steps_counted(self, monkeypatch):
        agent = make_agent(monkeypatch)
        result = asyncio.run(agent.run("test"))
        assert result["steps"] == 1  # 一次 act → 一条步骤记录


# ---------------------------------------------------------------------------
# 工具调用 / Tool dispatch
# ---------------------------------------------------------------------------

class EchoTool(BaseTool):
    name = "echo"
    description = "Echo back the message"
    parameters = {"msg": {"type": "string"}}

    async def execute(self, **kwargs):
        return {"echo": kwargs.get("msg", "")}


class TestToolDispatch:
    def test_tool_called_through_loop(self, monkeypatch):
        """reason 返回 tool: 动作 → act 真正执行注册的工具."""
        agent = make_agent(
            monkeypatch,
            reasons=[
                {"next_action": "tool:echo msg=hello", "reasoning": "use tool", "confidence": 0.9},
                {"next_action": "complete", "reasoning": "done", "confidence": 0.9},
            ],
            reflections=[
                {"completed": False, "summary": "tool ran", "issues": [], "improvements": [], "score": 0.7},
                {"completed": True, "summary": "done", "issues": [], "improvements": [], "score": 0.9},
            ],
        )
        agent.register_tool(EchoTool())
        result = asyncio.run(agent.run("echo something"))

        assert result["status"] == "completed"
        first_action = agent._context["action_history"][0]
        assert first_action["action"] == "tool:echo msg=hello"
        assert first_action["result"] == {"echo": "hello"}

    def test_unknown_tool_triggers_recovery_then_completes(self, monkeypatch):
        """调用不存在的工具 → 步骤失败 → 恢复回 REASONING → 改走 complete."""
        agent = make_agent(
            monkeypatch,
            reasons=[
                {"next_action": "tool:nonexistent", "reasoning": "oops", "confidence": 0.5},
                {"next_action": "complete", "reasoning": "recover", "confidence": 0.9},
            ],
        )
        result = asyncio.run(agent.run("bad tool task"))

        # 恢复机制应让任务最终完成而非整体 ERROR
        assert result["status"] == "completed"
        assert agent._error_count == 1


# ---------------------------------------------------------------------------
# 安全护栏 / Safety guardrail
# ---------------------------------------------------------------------------

class TestSafetyInLoop:
    def test_blocked_action_recovers(self, monkeypatch):
        """黑名单动作被拦截 → SafetyViolation → 恢复 → 换动作完成."""
        agent = make_agent(
            monkeypatch,
            reasons=[
                {"next_action": "text:launch dangerous_payload", "reasoning": "bad", "confidence": 0.5},
                {"next_action": "complete", "reasoning": "safe now", "confidence": 0.9},
            ],
        )
        agent._safety.block_pattern(r"dangerous_payload")
        result = asyncio.run(agent.run("risky task"))

        assert result["status"] == "completed"
        assert agent._safety.violation_count >= 1
        assert "last_safety_violation" in agent._context

    def test_repeated_blocked_actions_exhaust_recovery(self, monkeypatch):
        """连续被拦截耗尽恢复次数 → 最终 ERROR."""
        agent = make_agent(
            monkeypatch,
            reasons=[
                {"next_action": "text:always dangerous_payload", "reasoning": "bad", "confidence": 0.5},
            ],
        )
        agent._safety.block_pattern(r"dangerous_payload")
        result = asyncio.run(agent.run("hopeless task"))

        assert result["status"] == "error"
        assert agent.state == AgentState.ERROR


# ---------------------------------------------------------------------------
# 无 LLM 回退 / No-LLM fallback
# ---------------------------------------------------------------------------

class TestNoLLMFallback:
    def test_run_without_llm_uses_fallback(self, monkeypatch):
        """无 LLM 客户端时走 _fallback_* 仿真路径，仍能跑完."""
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        agent = Nonull(name="no-llm")
        # 防御:若环境/config 单例缓存了 key 导致创建了真实 client,强制置空
        # Defensive: env/config singleton may have cached a key — force None
        agent._llm_client = None
        assert agent.llm_client is None
        result = asyncio.run(agent.run("fallback task"))

        # fallback 路径应能终止（completed 或达到迭代上限）
        assert result["status"] in ("completed", "error")
        assert result["iterations"] >= 1


# ---------------------------------------------------------------------------
# 状态机不变式 / State machine invariants
# ---------------------------------------------------------------------------

class TestStateMachine:
    def test_agent_starts_idle(self, monkeypatch):
        agent = make_agent(monkeypatch)
        assert agent.state == AgentState.IDLE

    def test_rerun_after_completion(self, monkeypatch):
        """COMPLETED 后允许接新任务."""
        agent = make_agent(monkeypatch)
        r1 = asyncio.run(agent.run("first task"))
        assert r1["status"] == "completed"

        # 重新注入 mock（内部计数已重置）
        agent._llm_client = MockLLMClient()
        r2 = asyncio.run(agent.run("second task"))
        assert r2["status"] == "completed"

    def test_malformed_llm_json_uses_parse_fallback(self, monkeypatch):
        """LLM 返回非 JSON 时 _parse_llm_json 走 fallback，循环不崩."""

        class GarbageLLM:
            def chat(self, messages, tools=None, **kwargs):
                return LLMResponse(content="this is not json at all", model="mock")

        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        agent = Nonull(name="garbage-llm")
        agent._llm_client = GarbageLLM()
        result = asyncio.run(agent.run("garbage test"))

        # fallback plan/reason/reflect 应保证循环可以终止
        assert result["status"] in ("completed", "error")
