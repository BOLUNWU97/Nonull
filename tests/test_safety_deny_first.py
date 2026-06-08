"""Tests for safety/deny_first.py — Deny-First Rule Engine."""
from safety.deny_first import DenyFirstEngine
from safety import SafetyRule, Verdict, RuleCategory


class TestDenyFirstEngine:
    def test_default_rules_can_be_loaded(self):
        engine = DenyFirstEngine()
        count = engine.load_default_rules()
        rules = engine.get_rules()
        assert count > 0
        assert len(rules) > 0

    def test_default_rules_include_vehicle_safety(self):
        engine = DenyFirstEngine()
        engine.load_default_rules()
        vehicle_rules = [r for r in engine.get_rules() if r.category == RuleCategory.VEHICLE_SAFETY]
        assert len(vehicle_rules) > 0

    def test_add_rule_increases_count(self):
        engine = DenyFirstEngine()
        count_before = len(engine.get_rules())
        rule = SafetyRule(
            rule_id="temp_deny",
            rule_type="deny",
            pattern=r"temp:.*",
            category=RuleCategory.CODE_SAFETY,
            priority=100,
            reason="Temporary rule for testing",
        )
        engine.add_rule(rule)
        assert len(engine.get_rules()) == count_before + 1
        engine.remove_rule("temp_deny")
        assert len(engine.get_rules()) == count_before

    def test_remove_nonexistent_rule_returns_false(self):
        engine = DenyFirstEngine()
        result = engine.remove_rule("nonexistent_id")
        assert result is False

    def test_add_rule_with_dict(self):
        engine = DenyFirstEngine()
        rule_id = engine.add_rule({
            "rule_id": "dict_rule",
            "rule_type": "deny",
            "pattern": r"danger:.*",
            "category": RuleCategory.CODE_SAFETY,
            "priority": 100,
            "reason": "Test dict rule",
        })
        assert rule_id == "dict_rule"
        assert "dict_rule" in [r.rule_id for r in engine.get_rules()]
        engine.remove_rule("dict_rule")
