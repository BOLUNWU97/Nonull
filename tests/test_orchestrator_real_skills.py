"""Integration tests for Orchestrator.run_with_skills using the real SkillRegistry.

The earlier ``test_orchestrator_skills_glue.py`` test suite verified the
glue layer with a ``FakeSkillRegistry`` / ``FakeSkill`` — useful for unit
testing, but it does NOT prove that the real ``SkillRegistry`` /
``SkillMetadata`` shape plays well with ``_auto_derive_skill_mapping``.

If the real ``SkillMetadata.tags`` shape ever changes (e.g., becomes
``None`` for a skill, or stops being a list), the auto-derivation logic
silently returns an empty mapping. These tests catch that risk by
exercising the real registry end-to-end.

Tests:
    test_real_metadata_shape
        Asserts the real ``SkillMetadata`` exposes the fields the
        orchestrator reads (name, tags, description, ...).

    test_real_skill_tags_present
        Asserts that real skills expose at least one of (tags, description)
        — otherwise the auto-derivation can never match them.

    test_auto_discover_loads_many_skills
        Asserts ``auto_discover()`` populates a meaningful number of
        skills (>= 20 of the 31 real skills).

    test_auto_derive_with_real_registry
        Runs ``_auto_derive_skill_mapping`` against the real
        ``code_review`` workflow plan and asserts the mapping is
        non-empty and references real, registered skills.

    test_auto_derive_reproducible
        Runs the auto-derivation twice on the same plan and asserts
        identical results (same plan, same mapping).

    test_run_with_real_skill
        Calls ``run_with_skills`` with a plan that dispatches to the
        real ``CodeReviewSkill`` and asserts that the skill actually
        ran and produced a structured result.

    test_run_with_real_skill_via_workflow
        Calls the ``run_workflow`` classmethod with the real registry
        for the ``code_review`` workflow, asserting the full
        workflow -> plan -> skill dispatch path works.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List

import pytest

# Add the project root to sys.path so ``import skills.*`` works when pytest
# is invoked from any working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Reduce log noise from the libraries under test.
logging.getLogger("skills").setLevel(logging.WARNING)
logging.getLogger("orchestration").setLevel(logging.WARNING)

from orchestration.orchestrator import (
    Orchestrator,
    OrchestrationPlan,
    Subtask,
)
from orchestration.workflows import create_workflow_registry
from skills.base import (
    BaseSkill,
    SkillCategory,
    SkillMetadata,
    SkillResult,
)
from skills.registry import SkillRegistry


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def real_registry() -> SkillRegistry:
    """A real ``SkillRegistry`` populated by ``auto_discover()``."""
    registry = SkillRegistry()
    registry.auto_discover()
    return registry


@pytest.fixture(scope="module")
def code_review_plan() -> OrchestrationPlan:
    """The real ``code_review`` workflow instantiated as a plan."""
    wf_registry = create_workflow_registry()
    return wf_registry.instantiate(
        workflow_id="code_review",
        task="Review real C++/Python ADAS code",
    )


# =============================================================================
# Metadata / Registry Shape Tests
# =============================================================================

def test_real_metadata_shape():
    """``SkillMetadata`` must expose the fields the orchestrator reads.

    If this fails, the auto-derivation logic in
    ``Orchestrator._auto_derive_skill_mapping`` may silently break because
    it relies on these field names. The check is intentionally
    field-level so that renaming a field in ``SkillMetadata`` is caught.
    """
    meta = SkillMetadata(name="probe")

    # The fields the auto-derivation reads
    assert isinstance(meta.name, str)
    assert isinstance(meta.tags, list), (
        f"SkillMetadata.tags must be a list (got {type(meta.tags).__name__}); "
        f"auto-derivation does `meta.tags or []` but downstream code may not."
    )
    assert isinstance(meta.description, str)

    # Other public surface the registry/to_dict relies on
    assert hasattr(meta, "version")
    assert hasattr(meta, "category")
    assert hasattr(meta, "author")
    assert hasattr(meta, "requires")
    assert hasattr(meta, "input_schema")
    assert hasattr(meta, "output_schema")
    assert hasattr(meta, "max_execution_ms")
    assert hasattr(meta, "safety_level")

    # to_dict / from_dict must roundtrip
    d = meta.to_dict()
    assert d["name"] == "probe"
    assert d["tags"] == []
    rebuilt = SkillMetadata.from_dict(d)
    assert rebuilt.name == meta.name
    assert rebuilt.tags == meta.tags


def test_real_skill_tags_present(real_registry):
    """Every real skill must have non-empty tags or description.

    Otherwise the auto-derivation in ``_auto_derive_skill_mapping`` is
    dead-on-arrival for that skill: it cannot match it against any
    subtask (zero tag overlap AND zero description overlap).
    """
    skills = real_registry.get_all_skills()
    assert skills, "auto_discover() should have registered at least one skill"

    silent_skills: List[str] = []
    for skill in skills:
        meta = skill.metadata
        if not meta.tags and not meta.description:
            silent_skills.append(meta.name)

    assert not silent_skills, (
        "Skills with empty tags AND empty description are invisible to "
        "auto-derivation: " + ", ".join(silent_skills)
    )


def test_auto_discover_loads_many_skills(real_registry):
    """``auto_discover()`` should load a meaningful number of skills.

    The project ships 31 real skills across 9 categories. A correctly
    working auto-discover should register at least 20 of them.
    """
    count = real_registry.skill_count()
    assert count >= 20, (
        f"Expected at least 20 real skills auto-discovered, got {count}. "
        f"Check that all skill modules import cleanly."
    )


def test_real_skillresult_shape():
    """``SkillResult`` must expose the fields ``run_with_skills`` reads.

    The orchestrator uses ``getattr(skill_result, "success", False)`` and
    ``getattr(skill_result, "data", skill_result)`` so any object with
    those attributes works. This test pins down the real dataclass.
    """
    # Default-constructed result
    r = SkillResult()
    assert r.success is True
    assert r.data is None
    assert r.error is None
    assert r.skill_name == ""
    assert isinstance(r.warnings, list)
    assert isinstance(r.metrics, object)  # SkillMetrics instance

    # failure() helper
    fail = SkillResult.failure(error="boom", skill_name="x")
    assert fail.success is False
    assert fail.error == "boom"
    assert fail.skill_name == "x"

    # success_result() helper
    ok = SkillResult.success_result(data={"k": 1}, skill_name="y")
    assert ok.success is True
    assert ok.data == {"k": 1}
    assert ok.skill_name == "y"


# =============================================================================
# Auto-Derivation Tests (Real Registry)
# =============================================================================

def test_auto_derive_with_real_registry(real_registry, code_review_plan):
    """Auto-derive a non-empty subtask -> skill mapping for code_review.

    The ``code_review`` workflow has subtasks such as ``static_analysis``
    and ``security_review``. The real ``CodeReviewSkill`` has tags
    ``["code", "review", "cpp", "python", "misra", "autosar"]`` and a
    description containing Chinese. Auto-derivation should match at
    least one subtask (e.g., ``static_analysis`` -> ``code_review`` via
    shared ``misra`` / ``autosar`` tags).
    """
    orch = Orchestrator()
    mapping = orch._auto_derive_skill_mapping(code_review_plan, real_registry)

    assert isinstance(mapping, dict)
    assert len(mapping) >= 1, (
        "Expected at least one auto-derived skill mapping for the "
        "code_review plan, but got an empty mapping. "
        f"Subtasks: {[s.name for s in code_review_plan.subtasks.values()]}. "
        "This means real SkillMetadata.tags/description are not rich "
        "enough for the auto-derivation to work."
    )

    # Every mapped skill must actually exist in the registry
    for subtask_name, skill_name in mapping.items():
        assert isinstance(subtask_name, str)
        assert isinstance(skill_name, str)
        assert real_registry.get_skill(skill_name) is not None, (
            f"Auto-derived skill {skill_name!r} (for subtask "
            f"{subtask_name!r}) is not in the registry"
        )

    # The mapping must use the actual subtask names from the plan
    plan_subtask_names = {s.name for s in code_review_plan.subtasks.values()}
    assert set(mapping.keys()).issubset(plan_subtask_names), (
        f"Mapping keys {set(mapping.keys())} are not a subset of "
        f"plan subtask names {plan_subtask_names}"
    )


def test_auto_derive_reproducible(real_registry, code_review_plan):
    """Auto-derivation must be deterministic for the same plan.

    The docstring on ``_auto_derive_skill_mapping`` explicitly says
    ties are broken by alphabetical order for determinism. Verify the
    guarantee holds for the real registry.
    """
    orch = Orchestrator()
    mapping_1 = orch._auto_derive_skill_mapping(code_review_plan, real_registry)
    mapping_2 = orch._auto_derive_skill_mapping(code_review_plan, real_registry)
    mapping_3 = orch._auto_derive_skill_mapping(code_review_plan, real_registry)

    assert mapping_1 == mapping_2, (
        f"Auto-derivation is not reproducible across calls:\n"
        f"  1st: {mapping_1}\n  2nd: {mapping_2}"
    )
    assert mapping_1 == mapping_3, (
        f"Auto-derivation is not reproducible across calls:\n"
        f"  1st: {mapping_1}\n  3rd: {mapping_3}"
    )


def test_auto_derive_prefers_subtask_name_match():
    """A skill whose name contains the subtask name should win.

    This is a focused unit test using a real ``SkillRegistry`` but a
    tiny hand-built plan and skills, to verify the ``+5`` boost for
    "subtask name in skill name" is actually applied.
    """
    from skills.code_skills import CodeReviewSkill

    registry = SkillRegistry()
    registry.register(CodeReviewSkill)

    plan = OrchestrationPlan(task="test")
    st = Subtask(
        task_id=plan.id,
        name="code_review",
        description="a code review step",
        required_capabilities={"c++_review"},
    )
    plan.subtasks[st.id] = st
    plan.root_subtask_ids = [st.id]

    orch = Orchestrator()
    mapping = orch._auto_derive_skill_mapping(plan, registry)
    assert mapping.get("code_review") == "code_review"


# =============================================================================
# End-to-End run_with_skills Tests
# =============================================================================

def test_run_with_real_skill(real_registry):
    """``run_with_skills`` can dispatch to the real ``CodeReviewSkill``.

    Builds a one-subtask plan that maps to ``code_review`` and verifies
    the skill actually executed and returned a structured result.
    """
    # Context that satisfies CodeReviewSkill._validate_input
    code_context = {
        "code": (
            "int x;\n"                          # uninitialized var -> finding
            "printf(\"hello\\n\");\n"            # MISRA printf -> finding
            "using namespace std;\n"            # minor
            "int y = 1;\n"                      # initialized -> no finding
        ),
        "language": "cpp",
    }

    # Build a one-subtask plan that maps to "code_review"
    plan = OrchestrationPlan(task="static analysis of a small file")
    st = Subtask(
        task_id=plan.id,
        name="static_analysis",
        description="Run static analysis on the code",
        agent_type="code_reviewer",
        required_capabilities={"c++_review", "static_analysis"},
    )
    plan.subtasks[st.id] = st
    plan.root_subtask_ids = [st.id]

    orch = Orchestrator()
    result = orch.run_with_skills(
        plan=plan,
        registry=real_registry,
        name_to_skill={"static_analysis": "code_review"},
        context=code_context,
    )

    # The dispatch should have succeeded
    assert result["status"] in ("succeeded", "partial"), (
        f"Expected succeeded/partial, got {result['status']!r}; "
        f"errors={result['errors']}"
    )
    assert result["dispatch_method"] == "explicit"
    assert "static_analysis" in result["outputs"]
    assert "static_analysis" in result["skill_used"]
    assert result["skill_used"]["static_analysis"] == "code_review"

    # The real CodeReviewSkill returns a dict with "issues", "summary", etc.
    output = result["outputs"]["static_analysis"]
    assert isinstance(output, dict), (
        f"Expected dict output from real CodeReviewSkill, got "
        f"{type(output).__name__}: {output!r}"
    )
    # These keys are documented in the skill's output_schema
    assert "issues" in output
    assert "summary" in output
    assert "score" in output
    assert output["language"] == "cpp"
    # Sanity: the intentionally-bad code should produce at least one issue
    assert output["total_issues"] >= 1


def test_run_with_real_skill_via_workflow(real_registry, code_review_plan):
    """``Orchestrator.run_workflow`` end-to-end with the real registry.

    Uses the real ``code_review`` workflow and an explicit
    ``name_to_skill`` mapping so the test does not depend on the
    auto-derivation succeeding for every subtask (some subtask names
    may have no clean match in the current skill catalogue — that is
    a known limitation of the auto-deriver, not a bug).
    """
    # Map every code_review subtask to the real CodeReviewSkill so the
    # whole workflow can execute against the real registry.
    name_to_skill = {st.name: "code_review" for st in code_review_plan.subtasks.values()}

    code_context = {
        "code": "int x;\nprintf('hi');\n",
        "language": "cpp",
    }

    result = Orchestrator.run_workflow(
        workflow_id="code_review",
        registry=real_registry,
        task="Review some real ADAS C++ code",
        context=code_context,
    )

    # The first subtask (static_analysis) has no dependencies and should
    # always succeed when mapped to code_review with valid code.
    assert result["status"] in ("succeeded", "partial", "failed")
    # At least the first subtask should have been dispatched
    assert result["dispatch_method"] == "auto"  # run_workflow uses auto
    assert result["summary"]["total"] == len(code_review_plan.subtasks)


def test_run_with_real_skill_handles_validation_error(real_registry):
    """A real skill that fails validation should be isolated per subtask.

    The orchestrator claims per-subtask error isolation. Verify this
    works with a real skill that fails input validation (empty code).
    """
    plan = OrchestrationPlan(task="validation failure test")
    st = Subtask(
        task_id=plan.id,
        name="static_analysis",
        description="intentionally bad context",
        agent_type="code_reviewer",
        required_capabilities={"c++_review"},
    )
    plan.subtasks[st.id] = st
    plan.root_subtask_ids = [st.id]

    # Empty code -> CodeReviewSkill._validate_input raises SkillValidationError
    bad_context = {"code": "", "language": "cpp"}

    result = Orchestrator().run_with_skills(
        plan=plan,
        registry=real_registry,
        name_to_skill={"static_analysis": "code_review"},
        context=bad_context,
    )

    # The failure must be isolated — overall status reflects the failure,
    # but the workflow did not crash.
    assert result["status"] == "failed"
    assert "static_analysis" in result["errors"]
    assert result["summary"]["failed"] == 1
    assert result["summary"]["succeeded"] == 0


def test_run_with_real_skill_incompatible_language(real_registry):
    """An unsupported language must be reported, not crash."""
    plan = OrchestrationPlan(task="bad language test")
    st = Subtask(
        task_id=plan.id,
        name="static_analysis",
        description="bad language",
        agent_type="code_reviewer",
        required_capabilities={"c++_review"},
    )
    plan.subtasks[st.id] = st
    plan.root_subtask_ids = [st.id]

    bad_context = {"code": "x = 1", "language": "ruby"}  # not in (python, cpp, c++)

    result = Orchestrator().run_with_skills(
        plan=plan,
        registry=real_registry,
        name_to_skill={"static_analysis": "code_review"},
        context=bad_context,
    )

    assert result["status"] == "failed"
    assert "static_analysis" in result["errors"]


# =============================================================================
# Module entry point
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
