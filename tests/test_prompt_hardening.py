"""
Prompt 工程硬化测试 / Tests pinning the P0 prompt-engineering hardening.

钉住 P0 重构引入的新行为, 防止回归:
- json_mode 传递 (response_format 强约束)
- dup_count 循环检测注入 reason
- _diagnose_failure 失败分类 (替代盲回 REASONING)
- _parse_llm_json 鲁棒性 (markdown 块 / prose 包裹 / fallback)
"""
import asyncio
import json

import pytest

from core.agent_core import Nonull
from core.llm_client import LLMResponse


class RecordingMockLLM:
    """记录所有 chat 调用 (messages + kwargs) 的 MockLLM / Records all calls."""

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.calls = []  # [(messages, kwargs)]

    def chat(self, messages, tools=None, **kwargs):
        self.calls.append((messages, kwargs))
        user = messages[-1].content
        if "Decompose into" in user:
            payload = {"subtasks": [{"id": "s1", "description": "do it",
                        "verify": "check", "tool": None}],
                       "strategy": "sequential", "estimated_steps": 1}
        elif "Choose the next action" in user:
            payload = {"next_action": "complete", "reasoning": "r", "confidence": 0.9}
        elif "Evaluate honestly" in user:
            payload = {"completed": True, "summary": "done", "score": 0.9}
        elif "FAILED" in user:  # RECOVERING 诊断
            payload = {"diagnosis": "permanent error", "should_retry": False,
                       "alternative_action": None, "adjustment": None}
        else:
            payload = {}
        return LLMResponse(content=json.dumps(payload), model=self.model,
                           usage={"prompt_tokens": 10, "completion_tokens": 5})


def _make_agent(monkeypatch, mock):
    monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
    a = Nonull()
    a._llm_client = mock
    return a


# ── json_mode 强约束传递 ────────────────────────────────────────

class TestJsonMode:
    def test_json_mode_passed_on_every_call(self, monkeypatch):
        """plan/reason/reflect 每次调用都应传 json_mode=True."""
        a = _make_agent(monkeypatch, RecordingMockLLM())
        asyncio.run(a.run("test"))
        assert len(a._llm_client.calls) >= 3  # plan + reason + reflect
        for messages, kwargs in a._llm_client.calls:
            assert kwargs.get("json_mode") is True, \
                f"json_mode 未传递 / not passed: {kwargs}"


# ── 循环检测 dup_count ──────────────────────────────────────────

class TestLoopDetection:
    def test_dup_count_zero_on_first_reason(self, monkeypatch):
        """首次 reason (action_history 为空) dup_count=0."""
        a = _make_agent(monkeypatch, RecordingMockLLM())
        asyncio.run(a.run("test"))
        reason_calls = [m for m, k in a._llm_client.calls
                        if "Choose the next action" in m[-1].content]
        assert len(reason_calls) >= 1
        # 首次 reason 在 act 之前, action_history 空 → dup_count 0
        assert "DUPLICATE ACTION COUNT: 0" in reason_calls[0][-1].content

    def test_dup_count_reflects_history(self, monkeypatch):
        """action_history 有连续相同动作时 dup_count 正确计算."""
        a = _make_agent(monkeypatch, RecordingMockLLM())
        a._current_task = "dup test"
        a._iteration = 1
        ctx = {
            "task": "dup test",
            "plan": None,
            "action_history": [
                {"iteration": 1, "action": "text:retry", "result": {}},
                {"iteration": 2, "action": "text:retry", "result": {}},
            ],
        }
        asyncio.run(a.reason(ctx))
        reason_calls = [m for m, k in a._llm_client.calls
                        if "Choose the next action" in m[-1].content]
        assert len(reason_calls) == 1
        # 2 条相同动作 → dup_count=2 → LOOPING 警告
        assert "DUPLICATE ACTION COUNT: 2" in reason_calls[0][-1].content
        assert "LOOPING" in reason_calls[0][-1].content


# ── RECOVERING 失败诊断 ─────────────────────────────────────────

class TestDiagnoseFailure:
    def test_returns_none_without_llm(self, monkeypatch):
        """无 LLM 时 _diagnose_failure 返回 None (不崩)."""
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        a._llm_client = None
        assert a._diagnose_failure(ValueError("test")) is None

    def test_returns_dict_with_llm(self, monkeypatch):
        """有 LLM 时返回含 should_retry 的诊断 dict."""
        a = _make_agent(monkeypatch, RecordingMockLLM())
        result = a._diagnose_failure(KeyError("missing tool"))
        assert isinstance(result, dict)
        assert "should_retry" in result
        # RecordingMockLLM 的 FAILED 分支返回 should_retry=False
        assert result.get("should_retry") is False

    def test_diagnosis_giveup_stops_recovery(self, monkeypatch):
        """诊断 should_retry=False → _attempt_recovery 返回 False (放弃)."""
        a = _make_agent(monkeypatch, RecordingMockLLM())
        a._error_count = 1  # 未超 recovery_attempts
        result = asyncio.run(a._attempt_recovery(KeyError("permanent")))
        assert result is False  # 诊断建议放弃


# ── _parse_llm_json 鲁棒性 (extract_json) ───────────────────────

class TestParseLLMJsonRobustness:
    def test_handles_markdown_code_block(self, monkeypatch):
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        result = a._parse_llm_json('```json\n{"key": "value"}\n```', fallback={})
        assert result == {"key": "value"}

    def test_handles_prose_around_json(self, monkeypatch):
        """LLM 在 JSON 前后加解释文字时仍能提取."""
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        result = a._parse_llm_json('Here is my response:\n{"action": "go"}\nDone.', fallback={})
        assert result == {"action": "go"}

    def test_fallback_on_total_garbage(self, monkeypatch):
        """完全非 JSON 时返回 fallback."""
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        fb = {"safe": "default"}
        assert a._parse_llm_json("this is not json at all", fallback=fb) == fb

    def test_empty_text_returns_fallback(self, monkeypatch):
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        fb = {"default": True}
        assert a._parse_llm_json("", fallback=fb) == fb


# ── text: 输出安全 (测评发现的 P1 修复) ──────────────────────────

class TestTextOutputSafety:
    """text: 是 agent 的文本输出 (非可执行动作), 不该按内容风险评分拦截。

    深度测评 Run2 发现: agent 的 code-review 文本 (text: action) 讨论
    'write'/'delete'/'http' 概念时, _evaluate_context_risk 误判为危险动作
    (0.8 > 0.7) 拦截, 浪费 2 迭代。修复: text: 直接放行。"""

    def test_text_output_not_blocked_by_write_keyword(self):
        """text: 含 'write' 不拦截 (是输出讨论, 非 write 动作)."""
        from core.safety import SafetyGuardian
        g = SafetyGuardian()
        safe, risk, reason = g.validate("text:The code has a write bug here")
        assert safe is True
        assert risk == 0.0

    def test_text_output_not_blocked_by_multiple_keywords(self):
        """text: 含 write/delete/http 多关键词仍放行."""
        from core.safety import SafetyGuardian
        g = SafetyGuardian()
        safe, risk, _ = g.validate(
            "text:Found write/delete issues and http network calls in code"
        )
        assert safe is True
        assert risk == 0.0

    def test_exec_still_blocked(self):
        """exec: 仍正常评分 (text: 放行不影响真实危险动作)."""
        from core.safety import SafetyGuardian
        g = SafetyGuardian()
        # exec:rm -rf 是真实危险动作, 应拦截
        safe, risk, _ = g.validate("exec:rm -rf /")
        assert safe is False

    def test_skill_action_still_evaluated(self):
        """skill: 仍正常评分 (text: 放行只针对 text:, 不影响其他 action)."""
        from core.safety import SafetyGuardian
        g = SafetyGuardian()
        # skill: deny-first 0.5, 正常评分 (非 text: 的 0.0 直接放行)
        safe, risk, _ = g.validate("skill:some_skill")
        assert risk > 0.0  # 仍评分 (text: 才是 0.0 放行)
