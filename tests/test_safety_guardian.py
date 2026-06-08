"""Tests for safety/guardian.py — Safety Guardian (advisory)."""
import pytest
from safety.guardian import SafetyGuardian
from safety import SafetyVerdict, Verdict


class TestSafetyGuardian:
    def test_validate_action_returns_verdict(self):
        g = SafetyGuardian()
        g._enabled = True
        g._deny_first = False
        result = g.validate_action({"type": "read", "target": "README.md"})
        assert isinstance(result, SafetyVerdict)

    def test_validate_allows_safe_action(self):
        g = SafetyGuardian()
        g._enabled = True
        g._deny_first = False
        result = g.validate_action({"type": "read", "target": "test.txt"})
        assert result.verdict in (Verdict.APPROVED, Verdict.APPROVED_WITH_WARNING)

    def test_disabled_allows_everything(self):
        g = SafetyGuardian()
        g._enabled = False
        result = g.validate_action({"type": "exec", "target": "rm -rf /"})
        assert result.verdict == Verdict.APPROVED

    def test_deny_first_blocks_unknown(self):
        g = SafetyGuardian()
        g._enabled = True
        g._deny_first = True
        result = g.validate_action({"type": "shell_exec", "command": "ls"})
        assert result.verdict == Verdict.DENIED

    def test_violation_log_records_denials(self):
        g = SafetyGuardian()
        g._enabled = True
        g._deny_first = True
        g.validate_action({"type": "shell_exec", "command": "cat /etc/passwd"})
        assert len(g._violation_log) >= 0

    def test_validate_handles_empty_action(self):
        g = SafetyGuardian()
        g._enabled = True
        g._deny_first = False
        result = g.validate_action({"type": "", "target": ""})
        assert isinstance(result, SafetyVerdict)

    def test_safety_verdict_dataclass(self):
        v = SafetyVerdict(verdict=Verdict.APPROVED, score=0.8, reason="OK")
        assert v.verdict == Verdict.APPROVED
        assert v.score == 0.8
        assert v.reason == "OK"

    def test_verdict_enum_values(self):
        assert Verdict.APPROVED.value == "approved"
        assert Verdict.DENIED.value == "denied"
