"""Advisory-Template tests for the HARA / safety skills.

These tests pin the contract that the HARA skill is an ADVISORY TEMPLATE,
not a real HARA work product. The skill matches input keywords against
hardcoded hazard templates; the S/E/C values it produces are demo
defaults, not expert-elicited values per ISO 26262-3:2018.

If a future change starts producing "real" HARA outputs (e.g. by
calling an LLM, looking up a database, or running a calibrated
elicitation workflow), these tests will fail loudly — which is the
intended behavior. The skill's job is to make the template-ness
visible to every consumer.

What we assert:

1. The class docstring contains "ADVISORY TEMPLATE ONLY".
2. Every per-hazard output dict carries ``is_template=True``.
3. The wrapper output (the dict returned by ``_execute_impl``) carries
   a top-level ``is_template=True`` and a top-level ``warning`` string
   naming the limitation.
4. The per-hazard warning string names ISO 26262-3:2018 so consumers
   can grep for it.
5. The ``sec_overrides`` context field actually overrides the
   template's S/E/C values when supplied (configurability test).
6. The skill is registered under the corrected name ``hara_analysis``,
   and the old typo ``haras_analysis`` is preserved as a legacy alias.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict

import pytest

# Ensure project root is importable when running pytest from any CWD.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.registry import SkillRegistry
# P15: ADAS safety skills moved to domains/adas/skills/safety.py
from domains.adas.skills.safety import HazardAnalysisSkill


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def registry() -> SkillRegistry:
    """A single registry instance for this test module."""
    reg = SkillRegistry()
    reg.auto_discover()
    return reg


@pytest.fixture(scope="module")
def hara_skill(registry) -> HazardAnalysisSkill:
    """The HazardAnalysisSkill instance from the registry."""
    skill = registry.get_skill("hara_analysis")
    assert skill is not None, "hara_analysis not registered"
    return skill  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Class-level contract
# ---------------------------------------------------------------------------


class TestClassDocstringContract:
    """The class docstring must warn that this is a template, not a HARA."""

    def test_docstring_contains_advisory_template_only(self):
        assert "ADVISORY TEMPLATE ONLY" in HazardAnalysisSkill.__doc__, (
            "HazardAnalysisSkill.__doc__ must contain the literal string "
            "'ADVISORY TEMPLATE ONLY' so consumers see the warning in help()."
        )

    def test_docstring_names_iso_26262(self):
        # The warning should at least mention the standard it's not compliant with.
        assert "ISO 26262" in HazardAnalysisSkill.__doc__, (
            "Class docstring should name the standard (ISO 26262) that this "
            "template is not a certified implementation of."
        )

    def test_class_has_legacy_aliases_attribute(self):
        assert hasattr(HazardAnalysisSkill, "LEGACY_ALIASES"), (
            "HazardAnalysisSkill must declare LEGACY_ALIASES so the registry "
            "can register the old typo name as a backward-compat alias."
        )
        assert "haras_analysis" in HazardAnalysisSkill.LEGACY_ALIASES, (
            "The 'haras_analysis' typo must be listed in LEGACY_ALIASES."
        )


# ---------------------------------------------------------------------------
# Per-hazard output contract
# ---------------------------------------------------------------------------


class TestPerHazardOutputMarkers:
    """Every per-hazard dict must be self-marking as a template."""

    def test_per_hazard_dict_has_is_template_true(self, hara_skill):
        """The keyword '制动' triggers the brake-failure template, which has
        at least one hazard entry. That entry must carry is_template=True."""
        result = hara_skill._analyze_hazard(
            function="制动系统",
            scenario="高速公路",
        )
        assert result["hazards"], "Expected at least one hazard from brake template"
        for h in result["hazards"]:
            assert h.get("is_template") is True, (
                f"Hazard {h.get('hazard')!r} is missing is_template=True. "
                "All _analyze_hazard outputs must be self-marking."
            )

    def test_per_hazard_dict_has_template_id(self, hara_skill):
        result = hara_skill._analyze_hazard(
            function="制动系统",
            scenario="高速公路",
        )
        for h in result["hazards"]:
            assert h.get("template_id"), (
                f"Hazard {h.get('hazard')!r} must have a template_id so "
                "consumers can trace which keyword bucket produced it."
            )

    def test_wrapper_output_has_is_template_and_warning(self, hara_skill):
        """_execute_impl must return a top-level is_template=True + warning."""
        output = hara_skill._execute_impl({
            "system_description": "ADAS test",
            "functions": ["制动"],
        })
        assert output.get("is_template") is True, (
            "_execute_impl output must carry is_template=True at the top level."
        )
        warning = output.get("warning", "")
        assert warning, "Top-level warning string is empty"
        assert "ISO 26262" in warning, (
            f"Top-level warning should name ISO 26262-3:2018 so consumers can "
            f"grep for it. Got: {warning!r}"
        )
        assert "ADVISORY TEMPLATE ONLY" in warning, (
            f"Top-level warning should literally contain 'ADVISORY TEMPLATE "
            f"ONLY'. Got: {warning!r}"
        )

    def test_per_hazard_wrapper_has_is_template_and_warning(self, hara_skill):
        """_analyze_hazard return value must also be self-marking."""
        result = hara_skill._analyze_hazard(
            function="制动系统",
            scenario="高速公路",
        )
        assert result.get("is_template") is True
        assert "ISO 26262" in result.get("warning", "")
        assert "template" in result.get("warning", "").lower()


# ---------------------------------------------------------------------------
# Configurability of S/E/C
# ---------------------------------------------------------------------------


class TestSECOverrides:
    """The sec_overrides context field must actually override template values."""

    def test_sec_overrides_change_severity(self, hara_skill):
        """Pass an override for 制动失效 -> severity 1, and confirm the
        output reflects the override (not the template's 3)."""
        overrides = {"制动失效": {"S": 1, "E": 1, "C": 1}}
        result = hara_skill._execute_impl({
            "system_description": "ADAS",
            "functions": ["制动"],
            "sec_overrides": overrides,
        })
        # Find 制动失效 in the flattened hazards.
        for entry in result["hazards"]:
            for h in entry["hazards"]:
                if h["hazard"] == "制动失效":
                    assert h["severity_S"] == 1, (
                        f"sec_overrides did not override severity_S for "
                        f"制动失效. Got: {h['severity_S']!r}"
                    )
                    assert h["exposure_E"] == 1
                    assert h["controllability_C"] == 1
                    return
        pytest.fail("制动失效 not present in output to test override on")

    def test_no_overrides_uses_template(self, hara_skill):
        """Without sec_overrides, the template's hardcoded S/E/C must apply."""
        result = hara_skill._execute_impl({
            "system_description": "ADAS",
            "functions": ["制动"],
        })
        for entry in result["hazards"]:
            for h in entry["hazards"]:
                if h["hazard"] == "制动失效":
                    # 制动失效 has template S=3, E=3, C=3.
                    assert h["severity_S"] == 3
                    assert h["exposure_E"] == 3
                    assert h["controllability_C"] == 3
                    return
        pytest.fail("制动失效 not present in output to test template default on")

    def test_partial_override_only_overrides_given_keys(self, hara_skill):
        """sec_overrides missing E or C must NOT clobber the template values."""
        overrides = {"制动失效": {"S": 1}}  # only S
        result = hara_skill._execute_impl({
            "system_description": "ADAS",
            "functions": ["制动"],
            "sec_overrides": overrides,
        })
        for entry in result["hazards"]:
            for h in entry["hazards"]:
                if h["hazard"] == "制动失效":
                    assert h["severity_S"] == 1, "S override should apply"
                    assert h["exposure_E"] == 3, (
                        "E should fall back to template default (3) when not "
                        f"in overrides. Got: {h['exposure_E']!r}"
                    )
                    assert h["controllability_C"] == 3
                    return
        pytest.fail("制动失效 not present in output to test partial override on")

    def test_is_template_still_true_when_overrides_supplied(self, hara_skill):
        """Even when the caller injects S/E/C, is_template must remain True —
        it marks "this came from the keyword-templating skill", not "this is
        a default value". Consumers can use sec_overrides to feed real
        expert-elicited values, but the output lineage is still the template."""
        result = hara_skill._execute_impl({
            "system_description": "ADAS",
            "functions": ["制动"],
            "sec_overrides": {"制动失效": {"S": 1, "E": 1, "C": 1}},
        })
        assert result["is_template"] is True
        for entry in result["hazards"]:
            for h in entry["hazards"]:
                assert h["is_template"] is True


# ---------------------------------------------------------------------------
# Skill registration contract
# ---------------------------------------------------------------------------


class TestSkillRegistration:
    """The skill must be registered under the corrected name."""

    def test_canonical_name_registered(self, registry):
        assert "hara_analysis" in registry, (
            "hara_analysis (corrected name) should be registered."
        )
        assert "haras_analysis" not in [
            s.metadata.name for s in registry.get_all_skills()
        ], "Legacy alias must not appear in canonical skill list."

    def test_legacy_alias_resolves(self, registry):
        skill = registry.get_skill("haras_analysis")
        assert skill is not None
        assert skill.metadata.name == "hara_analysis"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
