"""
Nonull 智驾智能体 — Top-level package
======================================
Entry point: from nonull import Nonull, NonullConfig
CLI: python -m nonull
"""
__version__ = "0.1.0"

# Lazy re-exports to avoid heavy import cost
def __getattr__(name):
    if name == "Nonull":
        from core import Nonull
        return Nonull
    if name == "NonullConfig":
        from core import NonullConfig
        return NonullConfig
    # Re-export the persona / safety API surface so that
    # ``from nonull import PersonaOrchestrator`` works in quickstart.
    if name == "PersonaOrchestrator":
        from core.persona_orchestrator import PersonaOrchestrator
        return PersonaOrchestrator
    if name == "PersonaType":
        try:
            from persona import PersonaType  # type: ignore
            return PersonaType
        except Exception:
            # Backward-compat: persona module may have moved; provide a
            # minimal stub enum so ``from nonull import PersonaType``
            # still resolves at import time.
            from enum import Enum
            class PersonaType(Enum):
                GENERAL = "general"
                ADAS = "adas"
                CODING = "coding"
            return PersonaType
    if name == "ScenarioEngine":
        from persona import ScenarioEngine
        return ScenarioEngine
    if name == "SafetyBadgeSystem":
        from persona import SafetyBadgeSystem
        return SafetyBadgeSystem
    raise AttributeError(f"module 'nonull' has no attribute {name!r}")
