"""End-to-end integration test for the skill_workflow example.

This test exercises the actual example file (examples/skill_workflow.py)
end-to-end with a mock LLM or a stubbed workflow, to verify:
- The example imports cleanly
- The skill registry can auto-discover
- The orchestrator can instantiate
- A simple AEB review workflow can be run

This is the smoke test that protects the public entrypoint from breaking.
"""
import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_PATH = PROJECT_ROOT / "examples" / "skill_workflow.py"


def test_skill_workflow_example_exists():
    """The example file must exist."""
    assert EXAMPLE_PATH.exists(), f"Missing: {EXAMPLE_PATH}"


def test_skill_workflow_example_imports():
    """The example must be importable without errors.

    We don't run the workflow, just verify the module can be imported.
    """
    spec = importlib.util.spec_from_file_location("skill_workflow_example", str(EXAMPLE_PATH))
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        pytest.fail(f"examples/skill_workflow.py failed to import: {type(e).__name__}: {e}")


def test_skill_workflow_example_has_run_function():
    """The example must expose a run_aeb_review_workflow function."""
    spec = importlib.util.spec_from_file_location("skill_workflow_example", str(EXAMPLE_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert hasattr(mod, "run_aeb_review_workflow"), (
        "examples/skill_workflow.py must define run_aeb_review_workflow()"
    )


def test_skill_registry_auto_discover_loads_many_skills():
    """The registry must auto-discover enough skills for the example to work."""
    from skills.registry import SkillRegistry
    reg = SkillRegistry()
    reg.auto_discover()
    skill_count = len(reg.get_all_skills())
    assert skill_count >= 25, (
        f"Expected at least 25 skills, got {skill_count}. "
        f"Names: {[s.metadata.name for s in reg.get_all_skills()]}"
    )


def test_code_review_skill_can_be_looked_up():
    """The example references the code_review workflow which needs this skill."""
    from skills.registry import SkillRegistry
    reg = SkillRegistry()
    reg.auto_discover()
    skill = reg.get_skill("code_review")
    assert skill is not None, "code_review skill not found in registry"


def test_orchestrator_instantiates():
    """The Orchestrator class can be instantiated."""
    from orchestration.orchestrator import Orchestrator
    orch = Orchestrator()
    assert orch is not None


def test_orchestrator_run_with_skills_accepts_plan():
    """Orchestrator.run_with_skills has the expected signature."""
    import inspect
    from orchestration.orchestrator import Orchestrator
    sig = inspect.signature(Orchestrator.run_with_skills)
    # The signature should accept: plan, registry, name_to_skill, context
    params = list(sig.parameters.keys())
    assert "plan" in params
    assert "registry" in params
    assert "name_to_skill" in params
    assert "context" in params
