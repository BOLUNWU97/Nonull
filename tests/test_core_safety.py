"""
core.safety.SafetyGuardian 直接测试 / Direct tests for the SafetyGuardian
Nonull ACTUALLY uses (core.safety, not safety.guardian).

之前 test_safety_guardian.py 测的是 safety.guardian.SafetyGuardian (safety/ 包,
5 层 + ASIL 枚举), 但 Nonull.__init__ 实际用的是 core.safety.SafetyGuardian
(deny-first + risk scoring, 从 agent_core 拆出)。这是真实覆盖缺口 —— 测错了类。
本文件补这个缺口, 直接测 Nonull 用的那个。

Covers the SafetyGuardian class Nonull actually uses (core.safety), filling the
gap left by test_safety_guardian.py which tests a DIFFERENT class (safety.guardian).
"""
import pytest

from core.safety import SafetyGuardian


class TestCoreSafetyValidate:
    """core.safety.SafetyGuardian.validate() 全路径覆盖."""

    def test_returns_tuple_of_three(self):
        """validate 返回 (safe, risk, reason) 三元组."""
        g = SafetyGuardian()
        result = g.validate("complete")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_complete_action_passes(self):
        """complete 是安全动作."""
        g = SafetyGuardian()
        safe, _, _ = g.validate("complete")
        assert safe is True

    def test_disabled_allows_everything(self):
        """safety 禁用时全放行 (含危险动作)."""
        g = SafetyGuardian()
        g._enabled = False
        safe, _, _ = g.validate("exec:rm -rf /")
        assert safe is True


class TestCoreSafetyTextOutput:
    """text: 输出不按内容评分 (深度测评修复的 P1 bug)."""

    def test_text_with_write_keyword_passes(self):
        g = SafetyGuardian()
        safe, risk, _ = g.validate("text:code has a write bug")
        assert safe is True
        assert risk == 0.0

    def test_text_with_multiple_keywords_passes(self):
        g = SafetyGuardian()
        safe, risk, _ = g.validate("text:found write/delete issues with http calls")
        assert safe is True
        assert risk == 0.0


class TestCoreSafetyBlocklist:
    """正则黑名单 (在 text: 放行之前, 仍能拦截 text:dangerous)."""

    def test_block_pattern_intercepts_text(self):
        """block_pattern 仍能拦截 text:dangerous (黑名单在 text: 放行前)."""
        g = SafetyGuardian()
        g.block_pattern(r"dangerous_payload")
        safe, risk, _ = g.validate("text:launch dangerous_payload")
        assert safe is False
        assert risk == 1.0

    def test_block_pattern_not_triggered_by_safe_text(self):
        """安全文本不被黑名单误拦."""
        g = SafetyGuardian()
        g.block_pattern(r"dangerous_payload")
        safe, _, _ = g.validate("text:normal review content")
        assert safe is True


class TestCoreSafetyContextRisk:
    """上下文风险评估 (_evaluate_context_risk)."""

    def test_exec_rm_rf_blocked(self):
        """exec:rm -rf 高风险被拦."""
        g = SafetyGuardian()
        safe, risk, _ = g.validate("exec:rm -rf /")
        assert safe is False

    def test_write_keyword_adds_risk(self):
        """非 text: 的 action 含 write → +context_risk."""
        g = SafetyGuardian()
        _, risk, _ = g.validate("tool:write_file")
        # deny 0.5 + write context_risk 0.2 = 0.7
        assert risk >= 0.7

    def test_safe_tool_low_risk(self):
        """安全工具低风险."""
        g = SafetyGuardian()
        _, risk, _ = g.validate("tool:read_file")
        # deny 0.5, 无 context_risk (read 不触发 write/delete/http/exec)
        assert risk <= 0.7


class TestCoreSafetyAllowCommand:
    """白名单命令."""

    def test_allow_command_reduces_block(self):
        """allow_command 添加白名单."""
        g = SafetyGuardian()
        g.allow_command("mytool")
        # mytool 在白名单 → 不 +0.3
        safe, _, _ = g.validate("mytool:do_something")
        assert safe is True

    def test_violation_count_tracks(self):
        """violation_count 跟踪拦截次数."""
        g = SafetyGuardian()
        g.block_pattern(r"blocked")
        initial = g.violation_count
        g.validate("text:blocked content")
        assert g.violation_count > initial


class TestCoreSafetyConfig:
    """配置方法."""

    def test_set_max_risk(self):
        """set_max_risk 调整阈值."""
        g = SafetyGuardian()
        g.set_max_risk(0.4)  # 更严格
        # 0.5 deny-first > 0.4 → 拦截
        safe, _, _ = g.validate("complete")
        assert safe is False

    def test_set_max_risk_clamped(self):
        """set_max_risk 钳制到 [0, 1]."""
        g = SafetyGuardian()
        g.set_max_risk(5.0)
        assert g._max_risk_score == 1.0
        g.set_max_risk(-1.0)
        assert g._max_risk_score == 0.0

    def test_repr(self):
        """__repr__ 不崩."""
        g = SafetyGuardian()
        r = repr(g)
        assert "SafetyGuardian" in r
