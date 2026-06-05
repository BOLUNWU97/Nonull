"""Unit tests for Orchestrator.run_with_skills glue layer.

These tests verify that the Orchestrator can dispatch subtasks to
skills via the SkillRegistry without requiring a custom executor_fn,
and that errors are isolated per subtask.
"""
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestration.orchestrator import (
    Orchestrator,
    OrchestrationPlan,
    Subtask,
)
from skills.base import (
    BaseSkill,
    SkillCategory,
    SkillMetadata,
)


# -----------------------------------------------------------------------------
# Test Doubles (fakes / fakes) — keep tests self-contained.
# -----------------------------------------------------------------------------

@dataclass
class FakeSkillResult:
    """Mimics skills.base.SkillResult without the full dataclass machinery."""
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    skill_name: str = ""


class FakeSkill(BaseSkill):
    """In-memory skill that records calls and returns a configurable result."""

    def __init__(self, name: str, tags=None, description: str = "",
                 return_value=None, raise_exc: bool = False):
        # Skip BaseSkill.__init__ chain noise — implement minimal state
        self._instance_id = "fake-" + name
        self._active = True
        self._metrics = MagicMock()
        self.logger = MagicMock()
        self._return_value = return_value
        self._raise = raise_exc
        self._calls: List[Dict[str, Any]] = []
        self._name = name
        self._tags = tags or []
        self._description = description

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self._name,
            category=SkillCategory.GENERAL,
            description=self._description,
            tags=self._tags,
        )

    def _execute_impl(self, context):
        self._calls.append({"context": dict(context)})
        if self._raise:
            raise RuntimeError(
                f"FakeSkill {self._name!r} intentionally failed"
            )
        return self._return_value

    def execute(self, context):  # override to return our FakeSkillResult
        self._calls.append({"context": dict(context)})
        if self._raise:
            return FakeSkillResult(
                success=False,
                error=f"FakeSkill {self._name!r} intentionally failed",
                skill_name=self._name,
            )
        return FakeSkillResult(
            success=True,
            data=self._return_value,
            skill_name=self._name,
        )

    @property
    def is_active(self) -> bool:
        return self._active

    def activate(self):
        self._active = True

    def deactivate(self):
        self._active = False

    def add_pre_hook(self, hook):
        pass

    def add_post_hook(self, hook):
        pass

    def add_safety_hook(self, hook):
        pass


class FakeSkillRegistry:
    """Lightweight stand-in for SkillRegistry."""

    def __init__(self, skills: List[FakeSkill] = None):
        self._skills: Dict[str, FakeSkill] = {}
        for s in skills or []:
            self._skills[s.metadata.name] = s

    def get_skill(self, name: str) -> Optional[FakeSkill]:
        return self._skills.get(name)

    def get_all_skills(self) -> List[FakeSkill]:
        return list(self._skills.values())


# -----------------------------------------------------------------------------
# Test helpers
# -----------------------------------------------------------------------------

def _make_plan(subtask_specs) -> OrchestrationPlan:
    """Build a tiny plan with the given subtask specs.

    Each spec is a dict: {name, description, deps (names), capabilities}.
    """
    plan = OrchestrationPlan(task="test task")
    name_to_id: Dict[str, str] = {}
    for spec in subtask_specs:
        st = Subtask(
            task_id=plan.id,
            name=spec["name"],
            description=spec.get("description", spec["name"]),
            agent_type=spec.get("agent_type", "tester"),
            required_capabilities=set(spec.get("capabilities", [])),
            dependencies=[
                name_to_id[d] for d in spec.get("deps", []) if d in name_to_id
            ],
        )
        plan.subtasks[st.id] = st
        name_to_id[spec["name"]] = st.id
    plan.root_subtask_ids = [
        st.id for st in plan.subtasks.values() if not st.dependencies
    ]
    return plan


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

def test_run_with_skills_dispatches_each_subtask():
    """Each subtask's mapped skill is called with the right context."""
    skill_a = FakeSkill("a", return_value={"result": "A"})
    skill_b = FakeSkill("b", return_value={"result": "B"})

    registry = FakeSkillRegistry([skill_a, skill_b])

    plan = _make_plan([
        {"name": "alpha", "description": "alpha step"},
        {"name": "beta", "description": "beta step"},
    ])

    orch = Orchestrator()
    result = orch.run_with_skills(
        plan=plan,
        registry=registry,
        name_to_skill={"alpha": "a", "beta": "b"},
        context={"code": "int x = 1;"},
    )

    assert result["status"] == "succeeded"
    assert result["outputs"]["alpha"] == {"result": "A"}
    assert result["outputs"]["beta"] == {"result": "B"}
    assert result["skill_used"]["alpha"] == "a"
    assert result["skill_used"]["beta"] == "b"
    assert len(skill_a._calls) == 1
    assert len(skill_b._calls) == 1
    # Context is passed through with the user-supplied keys
    a_call_ctx = skill_a._calls[0]["context"]
    assert a_call_ctx["code"] == "int x = 1;"
    assert a_call_ctx["subtask_name"] == "alpha"
    # subtask_id should be a valid id from the plan
    assert a_call_ctx["subtask_id"] in plan.subtasks


def test_run_with_skills_uses_each_subtask_own_subtask_name_in_context():
    """Verify the per-skill context carries the right subtask metadata."""
    skill_a = FakeSkill("a", return_value="A")
    skill_b = FakeSkill("b", return_value="B")
    registry = FakeSkillRegistry([skill_a, skill_b])
    plan = _make_plan([
        {"name": "first", "description": "first step"},
        {"name": "second", "description": "second step"},
    ])

    Orchestrator().run_with_skills(
        plan=plan,
        registry=registry,
        name_to_skill={"first": "a", "second": "b"},
        context={},
    )

    names = sorted(call["context"]["subtask_name"] for call in
                   skill_a._calls + skill_b._calls)
    assert names == ["first", "second"]


def test_run_with_skills_isolates_failing_skill():
    """A failing skill must not prevent other subtasks from running."""
    good_skill = FakeSkill("good", return_value={"ok": True})
    bad_skill = FakeSkill("bad", raise_exc=True)

    registry = FakeSkillRegistry([good_skill, bad_skill])
    plan = _make_plan([
        {"name": "do_good", "description": "good step"},
        {"name": "do_bad", "description": "bad step"},
    ])

    result = Orchestrator().run_with_skills(
        plan=plan,
        registry=registry,
        name_to_skill={"do_good": "good", "do_bad": "bad"},
        context={},
    )

    # Good subtask still succeeded
    assert result["outputs"]["do_good"] == {"ok": True}
    # Bad subtask recorded an error
    assert "do_bad" in result["errors"]
    # Overall status is partial
    assert result["status"] == "partial"
    # Summary reflects mixed outcome
    assert result["summary"]["succeeded"] == 1
    assert result["summary"]["failed"] == 1


def test_run_with_skills_auto_derives_mapping():
    """Without an explicit mapping, the orchestrator picks the best tag match."""
    static_skill = FakeSkill(
        "static_analysis",
        tags=["static", "analysis", "code"],
        description="Run static analysis on code",
        return_value={"findings": []},
    )
    summary_skill = FakeSkill(
        "summary_report",
        tags=["summary", "report"],
        description="Generate a summary report",
        return_value={"report": "ok"},
    )
    registry = FakeSkillRegistry([static_skill, summary_skill])

    plan = _make_plan([
        {"name": "static_analysis", "description": "static analysis step"},
        {"name": "summary_report", "description": "summary report step",
         "deps": ["static_analysis"]},
    ])

    result = Orchestrator().run_with_skills(
        plan=plan,
        registry=registry,
        # No name_to_skill — auto-derive
        context={},
    )

    assert result["dispatch_method"] == "auto"
    assert result["skill_used"]["static_analysis"] == "static_analysis"
    assert result["skill_used"]["summary_report"] == "summary_report"
    assert result["status"] == "succeeded"


def test_run_with_skills_skips_subtasks_with_failed_dependencies():
    """Subtasks downstream of a failed subtask should be skipped, not run."""
    skill_a = FakeSkill("a", raise_exc=True)  # always fails
    skill_b = FakeSkill("b", return_value={"ok": True})
    registry = FakeSkillRegistry([skill_a, skill_b])
    plan = _make_plan([
        {"name": "first", "description": "fails"},
        {"name": "second", "description": "depends on first", "deps": ["first"]},
    ])

    result = Orchestrator().run_with_skills(
        plan=plan,
        registry=registry,
        name_to_skill={"first": "a", "second": "b"},
        context={},
    )

    # Skill B should never be called
    assert len(skill_b._calls) == 0
    assert result["subtask_status"]["second"] == "skipped"
    assert result["summary"]["skipped"] == 1
    assert result["status"] == "failed"


def test_run_with_skills_missing_skill_in_registry():
    """A missing skill should produce a per-subtask error, not crash."""
    registry = FakeSkillRegistry([])  # empty
    plan = _make_plan([{"name": "missing", "description": "no skill"}])

    result = Orchestrator().run_with_skills(
        plan=plan,
        registry=registry,
        name_to_skill={"missing": "nonexistent_skill"},
        context={},
    )

    assert result["status"] == "failed"
    assert "missing" in result["errors"]
    assert "nonexistent_skill" in result["errors"]["missing"]


def test_run_with_skills_explicit_mapping_dispatches_method():
    """When name_to_skill is provided, dispatch_method should be 'explicit'."""
    skill = FakeSkill("x", return_value="ok")
    registry = FakeSkillRegistry([skill])
    plan = _make_plan([{"name": "step", "description": "s"}])

    result = Orchestrator().run_with_skills(
        plan=plan,
        registry=registry,
        name_to_skill={"step": "x"},
        context={},
    )
    assert result["dispatch_method"] == "explicit"


def test_run_workflow_classmethod_end_to_end(monkeypatch):
    """Orchestrator.run_workflow should instantiate a workflow and run it."""
    # Build a minimal plan-shaped workflow + skill to avoid
    # depending on the full default-workflows/skill catalogue.
    skill = FakeSkill("x", return_value="ok")
    registry = FakeSkillRegistry([skill])

    # Patch create_workflow_registry to return a controllable fake
    fake_workflow_registry = MagicMock()
    plan = _make_plan([{"name": "step", "description": "s"}])
    fake_workflow_registry.instantiate.return_value = plan
    fake_workflow_registry_mod = MagicMock()
    fake_workflow_registry_mod.create_workflow_registry.return_value = (
        fake_workflow_registry
    )

    # Inject the fake
    import orchestration.workflows as wf_mod
    monkeypatch.setattr(wf_mod, "create_workflow_registry",
                        fake_workflow_registry_mod.create_workflow_registry)

    # Also need to patch the import inside run_workflow — it imports
    # orchestration.workflows, so patching the module attribute above
    # is sufficient.
    result = Orchestrator.run_workflow(
        workflow_id="code_review",
        registry=registry,
        task="Review some code",
        context={"language": "cpp"},
    )

    fake_workflow_registry.instantiate.assert_called_once()
    assert result["status"] == "succeeded"
    assert result["outputs"]["step"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
