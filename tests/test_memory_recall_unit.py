"""
记忆召回链路单元测试 / Unit tests for the memory-recall chain helpers.

覆盖 _extract_memory_finding / _best_memory_findings —— 这两个是跨会话记忆
召回链路的关键纯函数 (呈现层 + 选择层), 之前只靠手动 demo 验证, 无回归保护。
demo ✅ 后补单元测试, 防止任何人改坏它们时只有跑真实 LLM 才发现。

Covers the two pure functions in the memory-recall chain (presentation +
selection layers). Previously only validated by the manual cross-session
demo; these unit tests give them regression protection without needing LLM.
"""
import pytest

from core.agent_core import _extract_memory_finding, _best_memory_findings


# ── _extract_memory_finding: 从 dict-as-string 提取发现 ─────────

class TestExtractMemoryFinding:
    def test_extracts_result_from_dict_string(self):
        """dict-as-string → 提取 result 字段 (跳过 task preamble)."""
        content = "{'task': 'review code', 'action': 'text:report', 'result': 'ZeroDivisionError on divide'}"
        out = _extract_memory_finding(content)
        assert "ZeroDivisionError" in out
        # 不应以 task preamble 开头
        assert not out.startswith("{'task'")

    def test_strips_type_prefix(self):
        """neocortex 发的 [learning] 前缀应被剥离, 否则 literal_eval 失败."""
        content = "[learning] {'task': 'r', 'action': 'a', 'result': 'found the bug'}"
        out = _extract_memory_finding(content)
        assert "found the bug" in out

    def test_strips_other_type_prefix(self):
        """[other] 前缀也应剥离."""
        content = "[other] {'result': 'cache KeyError present'}"
        out = _extract_memory_finding(content)
        assert "cache KeyError" in out

    def test_plain_string_passthrough(self):
        """纯字符串 (非 dict) 直通截断."""
        assert _extract_memory_finding("just plain text") == "just plain text"

    def test_truncates_to_limit(self):
        """超 limit 截断."""
        long = "x" * 1000
        assert len(_extract_memory_finding(long, limit=50)) <= 50

    def test_nested_dict_recursion(self):
        """result 本身是 dict-as-string 时递归取 output/content."""
        content = "{'result': \"{'status': 'ok', 'output': 'deep finding text'}\"}"
        out = _extract_memory_finding(content)
        assert "deep finding text" in out

    def test_unparseable_does_not_crash(self):
        """非合法 literal 不崩, 返回截断原文."""
        out = _extract_memory_finding("not a dict {incomplete")
        assert isinstance(out, str)

    def test_empty_string(self):
        assert _extract_memory_finding("") == ""

    def test_falls_back_to_action_if_no_result(self):
        """无 result 时取 action."""
        content = "{'task': 'r', 'action': 'the action finding', 'result': None}"
        out = _extract_memory_finding(content)
        # result 是 None, 应取 action
        assert "the action finding" in out


# ── _best_memory_findings: 选择 finding-rich 条目 ───────────────

class TestBestMemoryFindings:
    def test_empty_input(self):
        assert _best_memory_findings([], 2) == []

    def test_returns_at_most_n(self):
        findings = ["a", "b", "c", "d"]
        assert len(_best_memory_findings(findings, 2)) <= 2

    def test_finding_rich_ranks_before_short(self):
        """长 (finding-rich, >200 字符) 应排在短 metadata 前."""
        short_meta = "task_start event"
        long_finding = "Discovered ZeroDivisionError in divide function when b is zero, " \
                       "plus KeyError in cache.get and style issues. " * 5  # >200 chars
        assert len(long_finding) > 200
        best = _best_memory_findings([short_meta, long_finding], 2)
        # 长 finding 应排第一 (LLM 首位锚定)
        assert best[0] == long_finding

    def test_metadata_preamble_demoted(self):
        """[other] / {'event': metadata preamble 应降级 (排在真实发现后)."""
        preamble = "[other] " + "x" * 250  # 长但只是 metadata
        real_finding = "Real review: found divide-by-zero bug. " * 10  # >200, finding
        assert len(real_finding) > 200
        best = _best_memory_findings([preamble, real_finding], 2)
        # 真实发现应排第一
        assert best[0] == real_finding

    def test_event_dict_preamble_demoted(self):
        """{'event': 'task_start'...} preamble 应降级."""
        preamble = "{'event': 'task_start', 'task': 'review', 'data': '" + "x" * 250 + "'}"
        real_finding = "Found KeyError and ZeroDivisionError bugs. " * 10
        best = _best_memory_findings([preamble, real_finding], 2)
        assert best[0] == real_finding

    def test_dedup_same_prefix(self):
        """相同前 80 字符视为重复, 去重."""
        base = "x" * 100 + "tail1"
        dup = "x" * 100 + "tail2"  # 前 80 字符相同
        best = _best_memory_findings([base, dup], 2)
        # 去重后应只剩 1 条 (前 80 字符都是 x*80)
        assert len(best) == 1

    def test_all_short_returns_some(self):
        """全部短 (<200) 时不崩, 返回 <= n."""
        findings = ["short1", "short2", "short3"]
        best = _best_memory_findings(findings, 2)
        assert len(best) <= 2
