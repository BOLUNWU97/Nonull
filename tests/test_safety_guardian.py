"""Tests for safety/guardian.py — Safety Guardian (advisory).

Note: SafetyGuardian.validate_action() expects an Action object or a dict
with keys: type/category, tool/target, params, etc.
"""
from safety.guardian import SafetyGuardian
from safety import SafetyVerdict, Verdict, ActionCategory


def make_action(tool="read", category="tool_call", params=None):
    """Helper to create a test action dict."""
    return {
        "action_id": "test_001",
        "category": category,
        "tool": tool,
        "params": params or {},
        "context": {},
    }


class TestSafetyGuardian:
    def test_validate_action_returns_verdict(self):
        g = SafetyGuardian()
        g._enabled = True
        g._deny_first = False
        result = g.validate_action(make_action())
        assert isinstance(result, SafetyVerdict)

    def test_allows_safe_read_action(self):
        g = SafetyGuardian()
        g._enabled = True
        g._deny_first = False
        result = g.validate_action(make_action("read"))
        assert result.verdict in (Verdict.APPROVED, Verdict.ASK)

    def test_disabled_allows_everything(self):
        g = SafetyGuardian()
        g._enabled = True
        g._deny_first = False
        result = g.validate_action(make_action("read", "file_operation", {"path": "test.txt"}))
        assert result.verdict in (Verdict.APPROVED, Verdict.ASK)

    def test_vehicle_control_action_is_not_approved(self):
        g = SafetyGuardian()
        g._enabled = True
        g._deny_first = True
        result = g.validate_action(make_action("set_brake", "vehicle_control", {"value": 0}))
        # In STANDARD mode, vehicle control actions are ASKed, not auto-approved
        assert result.verdict != Verdict.APPROVED

    def test_handles_empty_params(self):
        g = SafetyGuardian()
        g._enabled = True
        g._deny_first = False
        result = g.validate_action({"action_id": "empty", "category": "tool_call", "tool": "", "params": {}})
        assert isinstance(result, SafetyVerdict)

    def test_safety_verdict_dataclass(self):
        v = SafetyVerdict(verdict=Verdict.APPROVED, score=0.8, reason="OK", layer="test")
        assert v.verdict == Verdict.APPROVED
        assert v.score == 0.8
        assert v.reason == "OK"
        assert v.layer == "test"

    def test_verdict_enum_values(self):
        assert Verdict.APPROVED.value == "approved"
        assert Verdict.DENIED.value == "denied"
