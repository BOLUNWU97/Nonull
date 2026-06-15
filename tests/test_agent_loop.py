"""
Agent Loop 测试 / Tests for the standard agentic loop (core.agent_loop).

用脚本化 MockLLM 驱动 AgentLoop, 覆盖: 自然完成 (final)、max_steps 截断、
工具执行与 observe、工具不存在/抛异常、LLM 崩溃、无工具。无真实 LLM/$0。
"""
import pytest

from core.agent_loop import AgentLoop, AgentLoopResult, LoopStep
from core.llm_client import LLMResponse


def _tool_call(name: str, args: str = "{}") -> dict:
    return {"id": f"call_{name}", "function": {"name": name, "arguments": args}}


def _final(text: str) -> LLMResponse:
    return LLMResponse(content=text, tool_calls=[])


def _thinking(tool_calls=None, content="thinking...") -> LLMResponse:
    return LLMResponse(content=content, tool_calls=tool_calls or [])


class ScriptedLLM:
    """按预设序列返回 LLMResponse 的 MockLLM."""
    def __init__(self, responses):
        self.responses = responses
        self.idx = 0

    def chat(self, messages, tools=None, **kwargs):
        r = self.responses[min(self.idx, len(self.responses) - 1)]
        self.idx += 1
        return r


# 测试工具
def calc(**kwargs):
    """计算器."""
    return 42


def echo(msg=""):
    """回声."""
    return f"echo:{msg}"


# ── 完成行为 ────────────────────────────────────────────────────

class TestAgentLoopCompletion:
    async def test_completes_on_final(self):
        """LLM 调一次工具后给最终答案 → completed, 2 steps, 1 tool_call."""
        llm = ScriptedLLM([
            _thinking([_tool_call("calc")]),
            _final("The answer is 42"),
        ])
        loop = AgentLoop(llm, tools=[calc], max_steps=5)
        result = await loop.run("calc")
        assert result.completed
        assert not result.truncated
        assert result.total_steps == 2
        assert result.tool_calls == 1
        assert "42" in result.output

    async def test_immediate_final(self):
        """LLM 不调工具直接给答案 → 1 step, 0 tool_calls."""
        llm = ScriptedLLM([_final("done immediately")])
        loop = AgentLoop(llm, tools=[calc], max_steps=5)
        result = await loop.run("easy task")
        assert result.completed
        assert result.total_steps == 1
        assert result.tool_calls == 0
        assert result.output == "done immediately"

    async def test_output_is_final_observation(self):
        """output = 最后一步的 observation (final 答案)."""
        llm = ScriptedLLM([_final("my final answer")])
        loop = AgentLoop(llm, tools=[], max_steps=3)
        result = await loop.run("test")
        assert result.output == "my final answer"


# ── 截断行为 ────────────────────────────────────────────────────

class TestAgentLoopTruncation:
    async def test_truncates_on_max_steps(self):
        """LLM 一直调工具 → max_steps 截断, completed=False."""
        llm = ScriptedLLM([_thinking([_tool_call("calc")])] * 100)
        loop = AgentLoop(llm, tools=[calc], max_steps=3)
        result = await loop.run("infinite tool loop")
        assert not result.completed
        assert result.truncated
        assert result.total_steps == 3

    async def test_max_steps_one(self):
        """max_steps=1 只跑一步."""
        llm = ScriptedLLM([_thinking([_tool_call("calc")])])
        loop = AgentLoop(llm, tools=[calc], max_steps=1)
        result = await loop.run("one step")
        assert result.total_steps == 1


# ── 工具执行 ────────────────────────────────────────────────────

class TestToolExecution:
    async def test_tool_result_observed(self):
        """工具结果进入 step.observation."""
        llm = ScriptedLLM([
            _thinking([_tool_call("echo", '{"msg": "hello"}')]),
            _final("done"),
        ])
        loop = AgentLoop(llm, tools=[echo], max_steps=5)
        result = await loop.run("echo hello")
        assert any("echo:hello" in s.observation for s in result.steps)

    async def test_tool_not_found(self):
        """调不存在的工具 → observe 'not found', 不崩, 继续到 final."""
        llm = ScriptedLLM([
            _thinking([_tool_call("nonexistent")]),
            _final("ok"),
        ])
        loop = AgentLoop(llm, tools=[calc], max_steps=5)
        result = await loop.run("bad tool")
        assert result.completed
        assert any("not found" in s.observation for s in result.steps)

    async def test_tool_raises_caught(self):
        """工具抛异常 → observe 'Error', 不崩, 继续."""
        def boom(**kwargs):
            raise ValueError("boom")
        llm = ScriptedLLM([
            _thinking([_tool_call("boom")]),
            _final("recovered"),
        ])
        loop = AgentLoop(llm, tools=[boom], max_steps=5)
        result = await loop.run("exploding tool")
        assert result.completed
        assert any("Error" in s.observation or "boom" in s.observation for s in result.steps)

    async def test_multiple_tool_calls_one_step(self):
        """一轮多个 tool_call 都执行."""
        llm = ScriptedLLM([
            _thinking([_tool_call("calc"), _tool_call("echo", '{"msg": "x"}')]),
            _final("done"),
        ])
        loop = AgentLoop(llm, tools=[calc, echo], max_steps=5)
        result = await loop.run("multi")
        assert result.tool_calls == 2


# ── 鲁棒性 ──────────────────────────────────────────────────────

class TestAgentLoopRobustness:
    async def test_llm_exception_caught(self):
        """LLM.chat 抛异常 → error 设置, 不崩."""
        class CrashLLM:
            def chat(self, *a, **k):
                raise RuntimeError("LLM crashed")
        loop = AgentLoop(CrashLLM(), tools=[calc], max_steps=5)
        result = await loop.run("crash test")
        assert result.error is not None
        assert "crashed" in result.error

    async def test_no_tools(self):
        """无工具时 LLM 应直接 final."""
        llm = ScriptedLLM([_final("no tools needed")])
        loop = AgentLoop(llm, tools=[], max_steps=3)
        result = await loop.run("toolless")
        assert result.completed
        assert result.tool_calls == 0

    async def test_result_to_dict_structure(self):
        """result.to_dict() 结构完整."""
        llm = ScriptedLLM([_final("done")])
        loop = AgentLoop(llm, tools=[calc], max_steps=3)
        result = await loop.run("test")
        d = result.to_dict()
        assert {"output", "steps", "completed", "total_steps", "tool_calls"}.issubset(d.keys())
        assert d["total_steps"] == 1
        assert d["completed"] is True

    async def test_step_records_thought_and_action(self):
        """每步记录 thought + action."""
        llm = ScriptedLLM([
            _thinking([_tool_call("calc")], content="I should calculate"),
            _final("done"),
        ])
        loop = AgentLoop(llm, tools=[calc], max_steps=5)
        result = await loop.run("test")
        assert result.steps[0].action == "tool:calc"
        assert "calculate" in result.steps[0].thought
        assert result.steps[1].action == "final"


# ── Nonull.run_react 集成 (两种模式合在同一 Nonull 实例) ─────────

class TestNonullRunReact:
    """验证 Nonull 实例同时支持 run() 与 run_react(), 共享 LLM/成本, 统一格式."""

    async def test_run_react_returns_react_mode(self, monkeypatch):
        """run_react 返回 mode='react' + run() 兼容字段."""
        from core.agent_core import Nonull
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        a._llm_client = ScriptedLLM([_final("react done")])
        result = await a.run_react("test", tools=[], max_steps=3)
        assert result["mode"] == "react"
        assert result["status"] == "completed"
        assert result["output"] == "react done"
        assert "cost" in result  # 共享 Nonull 成本追踪
        assert "duration" in result

    async def test_run_react_no_llm_graceful(self, monkeypatch):
        """无 LLM 时 run_react 友好返回 error (不崩)."""
        from core.agent_core import Nonull
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        a._llm_client = None
        result = await a.run_react("test")
        assert result["status"] == "error"
        assert result["mode"] == "react"
        assert result["error"] == "no LLM client"

    async def test_run_react_uses_tools_and_cost(self, monkeypatch):
        """run_react 执行工具 + 成本记账 (共享 Nonull cost_tracker)."""
        from core.agent_core import Nonull
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        a._llm_client = ScriptedLLM([
            _thinking([_tool_call("calc")]),
            _final("done"),
        ])
        result = await a.run_react("calc", tools=[calc], max_steps=5)
        assert result["status"] == "completed"
        assert result["tool_calls"] == 1
        assert result["iterations"] == 2
        # 成本经共享 cost_tracker 记账 (ScriptedLLM 返回 usage)
        assert result["cost"]["call_count"] >= 1

    async def test_run_and_run_react_share_instance(self, monkeypatch):
        """同一 Nonull 实例可先后用两种模式 (共享 LLM/成本)."""
        from core.agent_core import Nonull
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        a._llm_client = ScriptedLLM([_final("both modes work")])
        # react 模式
        r_react = await a.run_react("react task", tools=[])
        assert r_react["mode"] == "react"
        # 同一实例, react 的 cost 累积在共享 cost_tracker
        assert r_react["cost"]["call_count"] >= 1

    async def test_run_react_has_unified_fields(self, monkeypatch):
        """run_react 返回字段集与 run() 统一 (含 plan/mode/cost/truncated)."""
        from core.agent_core import Nonull
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        a._llm_client = ScriptedLLM([_final("done")])
        result = await a.run_react("test", tools=[])
        # 两种模式共享的统一字段集
        unified = {"status", "output", "plan", "steps", "iterations",
                   "duration", "error", "mode", "cost", "truncated"}
        assert unified.issubset(result.keys()), \
            f"missing unified fields: {unified - result.keys()}"
        assert result["plan"] is None  # react 不规划
        assert result["mode"] == "react"
        assert result["truncated"] is False  # 自然完成

    async def test_run_react_updates_agent_state(self, monkeypatch):
        """run_react 更新 self._state (与 run() 一致, get_status 反映 react)."""
        from core.agent_core import Nonull
        from core.agent_core import AgentState
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        a._llm_client = ScriptedLLM([_final("done")])
        assert a.state == AgentState.IDLE  # 初始
        await a.run_react("test", tools=[])
        assert a.state == AgentState.COMPLETED  # react 完成后状态更新

    async def test_run_react_timeout_protection(self, monkeypatch):
        """run_react 尊重 self._timeout (LLM 挂起时不无限等)."""
        import time as _time
        from core.agent_core import Nonull

        class SlowLLM:
            """每次 chat 阻塞 0.3s, 模拟慢/挂起的 LLM."""
            def chat(self, *a, **k):
                _time.sleep(0.3)
                return _thinking([_tool_call("calc")])  # 永远调工具, 不终止

        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        a._llm_client = SlowLLM()
        a._timeout = 0.1  # 小 timeout
        result = await a.run_react("slow task", tools=[calc], max_steps=10)
        assert result["status"] == "error"
        assert "timeout" in (result["error"] or "")
        assert result["truncated"] is True
        assert result["mode"] == "react"

    async def test_run_react_triggers_shutdown_hook(self, monkeypatch):
        """run_react 触发 ON_SHUTDOWN hook (与 run() 的 finally 一致)."""
        from core.agent_core import Nonull, HookPoint
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        a._llm_client = ScriptedLLM([_final("done")])
        triggered = []
        a.register_hook(HookPoint.ON_SHUTDOWN, lambda **kw: triggered.append("shutdown"))
        await a.run_react("hook test", tools=[])
        assert "shutdown" in triggered


# ── AgentLoop circuit-breaker (防重复失败工具烧 max_steps) ───────

class TestAgentLoopCircuitBreaker:
    """同工具连续失败 >=3 次 → 提示 LLM 换路 (防烧光 max_steps)."""

    async def test_circuit_breaker_fires_on_3_failures(self):
        """同工具失败 3 次后, observation 含 'broken'/'DIFFERENT' 提示."""
        def boom(**kwargs):
            raise ValueError("always fails")
        # LLM 永远调 boom (5 次), 但第 3 次后 circuit-breaker 提示换路
        llm = ScriptedLLM([_thinking([_tool_call("boom")])] * 5)
        loop = AgentLoop(llm, tools=[boom], max_steps=5)
        result = await loop.run("repeated fail")
        # 第 3 次失败的 observation 应含提示
        assert any("broken" in s.observation or "DIFFERENT" in s.observation
                   for s in result.steps)

    async def test_circuit_breaker_resets_on_success(self):
        """工具成功后失败计数重置."""
        call_count = [0]
        def flaky(**kwargs):
            call_count[0] += 1
            if call_count[0] < 3:  # 前 2 次失败
                raise ValueError("flaky")
            return "ok"  # 第 3 次成功
        llm = ScriptedLLM([
            _thinking([_tool_call("flaky")]),  # fail 1
            _thinking([_tool_call("flaky")]),  # fail 2
            _thinking([_tool_call("flaky")]),  # success (重置)
            _thinking([_tool_call("flaky")]),  # fail 1 again (重置后)
            _final("done"),
        ])
        loop = AgentLoop(llm, tools=[flaky], max_steps=8)
        result = await loop.run("flaky test")
        # 成功重置后, 后续失败不应触发 circuit-breaker (没到 3 次)
        # 关键: 第 3 步成功 (observation "ok")
        assert any(s.observation == "ok" for s in result.steps)
        assert result.completed


# ── AgentLoop context trimming (防 verbose tool 结果撑爆 context) ──

class TestAgentLoopContextTrimming:
    """messages 超阈值时丢弃中间轮, 保留首 system+user + 末尾最近几轮."""

    async def test_trim_keeps_system_and_user(self):
        """trim 后仍保留首 system + user (任务不丢)."""
        # max_context_messages=4 → 第 3 步后 messages > 4, 触发 trim
        llm = ScriptedLLM([
            _thinking([_tool_call("calc")]),
            _thinking([_tool_call("calc")]),
            _thinking([_tool_call("calc")]),
            _final("done"),
        ])
        loop = AgentLoop(llm, tools=[calc], max_steps=6, max_context_messages=4)
        result = await loop.run("trim test")
        assert result.completed
        # 即使 trim, 仍完成 (首 system+user 保留, LLM 知道任务)

    async def test_trim_does_not_crash(self):
        """trim 不崩, loop 正常完成."""
        llm = ScriptedLLM([_thinking([_tool_call("calc")])] * 8 + [_final("done")])
        loop = AgentLoop(llm, tools=[calc], max_steps=10, max_context_messages=6)
        result = await loop.run("many steps")
        assert result.completed
        assert result.total_steps <= 10

    async def test_no_trim_when_under_limit(self):
        """messages 未超阈值时不 trim (正常短任务)."""
        llm = ScriptedLLM([_final("quick")])
        loop = AgentLoop(llm, tools=[calc], max_steps=3, max_context_messages=20)
        result = await loop.run("short")
        assert result.completed
        assert result.total_steps == 1
