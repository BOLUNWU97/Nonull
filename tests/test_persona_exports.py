"""Verify persona/ exports the symbols examples/quickstart.py depends on."""
from persona import (
    PersonaOrchestrator,
    PersonaType,
    ScenarioEngine,
    SafetyBadgeSystem,
)


def test_scenario_engine_importable():
    assert ScenarioEngine is not None


def test_safety_badge_system_importable():
    assert SafetyBadgeSystem is not None


def test_persona_orchestrator_importable():
    assert PersonaOrchestrator is not None


def test_persona_type_importable():
    assert PersonaType is not None


def test_quickstart_dependencies():
    """The exact imports examples/quickstart.py relies on."""
    import persona
    needed = ["PersonaOrchestrator", "PersonaType", "ScenarioEngine"]
    for name in needed:
        assert name in persona.__all__, f"{name} missing from persona.__all__"
