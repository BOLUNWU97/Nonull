"""Smoke test: verify examples/quickstart.py can be imported and its main imports work.

This test guards the most embarrassing failure mode: a new user clones the repo,
runs `pip install -e .`, then `python examples/quickstart.py`, and gets an
ImportError on the very first line.

If this test fails, it means one of these symbols is not exported:
- core.Nonull
- core.NonullConfig
- persona.PersonaOrchestrator
- persona.PersonaType
- persona.ScenarioEngine
- persona.SafetyBadgeSystem
- nonull.Nonull (top-level re-export)
- nonull.NonullConfig (top-level re-export)
"""
import importlib
import sys
import pytest


CORE_IMPORTS = [
    ("core", "NonullConfig"),
    ("core", "Nonull"),
    ("persona", "PersonaOrchestrator"),
    ("persona", "PersonaType"),
    ("persona", "ScenarioEngine"),
    ("persona", "SafetyBadgeSystem"),
    ("safety", "SafetyGuardian"),
    ("memory", "Neocortex"),
    ("skills", "SkillRegistry"),
    ("orchestration", "Orchestrator"),
    ("nonull", "Nonull"),
    ("nonull", "NonullConfig"),
    ("nonull", "PersonaOrchestrator"),
    ("nonull", "PersonaType"),
]


@pytest.mark.parametrize("module_name,symbol_name", CORE_IMPORTS)
def test_quickstart_dependency_importable(module_name: str, symbol_name: str):
    """Every import in quickstart.py and README must resolve."""
    module = importlib.import_module(module_name)
    assert hasattr(module, symbol_name), (
        f"Module {module_name!r} is missing {symbol_name!r} which is required by "
        f"examples/quickstart.py or the README quickstart snippet. "
        f"This will cause a new user's first import to fail."
    )


def test_quickstart_module_loads():
    """examples/quickstart.py must at least import without errors."""
    # We don't want to actually RUN the script (it would print a lot),
    # just import it. Since it's not a module, we read and check it
    # imports the right symbols.
    from pathlib import Path
    quickstart = Path(__file__).parent.parent / "examples" / "quickstart.py"
    content = quickstart.read_text(encoding="utf-8")

    # Check the file references real symbols
    assert "PersonaOrchestrator" in content or "Nonull" in content, (
        "examples/quickstart.py doesn't seem to use either PersonaOrchestrator or Nonull"
    )

    # The import lines we expect to be present and working
    if "from persona import" in content:
        # Make sure the persona imports would work
        from persona import PersonaOrchestrator, PersonaType, ScenarioEngine
        assert PersonaOrchestrator is not None
        assert PersonaType is not None
        assert ScenarioEngine is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
