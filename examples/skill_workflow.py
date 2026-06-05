"""
Example: Run a workflow using actual skills.
"""
import asyncio
from orchestration.orchestrator import Orchestrator
from orchestration.workflows import create_workflow_registry
from skills.registry import SkillRegistry


async def run_aeb_review_workflow(code: str):
    """Review an AEB C++ function using the code_review workflow + skills."""

    # 1. Auto-discover all 31 skills
    skill_registry = SkillRegistry()
    skill_registry.auto_discover()

    # 2. Get the code_review workflow
    workflow_registry = create_workflow_registry()
    plan = workflow_registry.instantiate(
        workflow_id="code_review",
        task=f"Review AEB C++ code",
        context={"language": "cpp", "code": code},
    )

    # 3. Run with auto-dispatched skills
    orchestrator = Orchestrator()
    result = orchestrator.run_with_skills(
        plan=plan,
        registry=skill_registry,
        context={"code": code, "language": "cpp"},
    )

    return result


if __name__ == "__main__":
    sample = """
    void calculateAEBBraking(float distance, float speed) {
        if (distance < 5.0) return 1.0;
        if (distance < 10.0) return 0.7;
        return 0.0;
    }
    """
    result = asyncio.run(run_aeb_review_workflow(sample))
    print(result)
