"""
Nonull - Persona Orchestrator Package (backward-compat shim)
============================================================

P15 NOTE — Domain Abstraction Refactor
--------------------------------------
The contents of this package have been **moved** to the new
``domains/adas/`` and ``core/`` packages. The classes that used to live
in ``persona/`` are now importable from their new canonical locations:

    persona/driving_persona.py  ->  domains/adas/personas.py
    persona/scenario_engine.py  ->  domains/adas/scenarios.py
    persona/co_pilot.py         ->  domains/adas/copilot.py
    persona/safety_badge.py     ->  core/safety_metrics.py
    persona/persona_orchestrator.py -> core/persona_orchestrator.py

This module remains so that older code (and the existing test
``tests/test_persona_exports.py``) keeps working. All public symbols are
re-exported **lazily** via ``__getattr__`` so that the import of one
symbol doesn't drag in the entire ADAS scenario library.

What's still here
-----------------
* ``__version__``, ``__author__``, ``__license__``, ``__description__``
* The ``__all__`` list (so ``from persona import *`` keeps working)
* Lazy re-exports of the moved symbols
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__version__ = "0.1.0"
__author__ = "Nonull Team"
__license__ = "MIT"
__description__ = (
    "Persona Orchestration for Autonomous Driving AI (驾驶人格编排系统) — "
    "P15: this package is a backward-compat shim; canonical location is "
    "domains/adas/ and core/."
)

# ---------------------------------------------------------------------------
# Lazy re-exports — map public symbol -> (module, attribute)
# ---------------------------------------------------------------------------

_PERSONA_TO_CANONICAL: Dict[str, tuple] = {
    # Driving persona
    "PersonaType":         ("domains.adas.personas",      "PersonaType"),
    "AnalysisFocus":       ("domains.adas.personas",      "AnalysisFocus"),
    "DrivingPersona":      ("domains.adas.personas",      "DrivingPersona"),
    "ConservativePersona": ("domains.adas.personas",      "ConservativePersona"),
    "SportyPersona":       ("domains.adas.personas",      "SportyPersona"),
    "VeteranPersona":      ("domains.adas.personas",      "VeteranPersona"),
    "get_persona":         ("domains.adas.personas",      "get_persona"),

    # Scenario engine
    "OperationalDomain":   ("domains.adas.scenarios",     "OperationalDomain"),
    "DOMAIN_LABELS":       ("domains.adas.scenarios",     "DOMAIN_LABELS"),
    "DifficultyLevel":     ("domains.adas.scenarios",     "DifficultyLevel"),
    "ADASScenario":        ("domains.adas.scenarios",     "ADASScenario"),
    "ScenarioEngine":      ("domains.adas.scenarios",     "ScenarioEngine"),
    "get_engine":          ("domains.adas.scenarios",     "get_engine"),

    # Safety metrics (now in core, since they are domain-agnostic)
    "BadgeCategory":       ("core.safety_metrics",        "BadgeCategory"),
    "CATEGORY_META":       ("core.safety_metrics",        "CATEGORY_META"),
    "BadgeLevel":          ("core.safety_metrics",        "BadgeLevel"),
    "LEVEL_META":          ("core.safety_metrics",        "LEVEL_META"),
    "BadgeScore":          ("core.safety_metrics",        "BadgeScore"),
    "SafetyBadgeSystem":   ("core.safety_metrics",        "SafetyBadgeSystem"),
    "get_badge_system":    ("core.safety_metrics",        "get_badge_system"),

    # Co-pilot
    "AlertSeverity":       ("domains.adas.copilot",       "AlertSeverity"),
    "Alert":               ("domains.adas.copilot",       "Alert"),
    "TelemetryContext":    ("domains.adas.copilot",       "TelemetryContext"),
    "AlertRule":           ("domains.adas.copilot",       "AlertRule"),
    "CoPilot":             ("domains.adas.copilot",       "CoPilot"),

    # Orchestrator (top-level entry point)
    "PersonaOrchestrator": ("core.persona_orchestrator",  "PersonaOrchestrator"),
}


def __getattr__(name: str) -> Any:
    """PEP 562 lazy attribute access.

    For any name in ``_PERSONA_TO_CANONICAL`` we import the canonical
    module and return the requested attribute. This is what keeps
    ``from persona import ScenarioEngine`` working without forcing the
    full persona/AD import chain at module load time.
    """
    if name in _PERSONA_TO_CANONICAL:
        module_name, attr = _PERSONA_TO_CANONICAL[name]
        import importlib
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            raise ImportError(
                f"persona.{name} could not be loaded from {module_name!r}: {e}. "
                f"The new canonical home is {module_name!r}."
            ) from e
        value = getattr(module, attr)
        globals()[name] = value  # cache for subsequent lookups
        return value

    raise AttributeError(f"module 'persona' has no attribute {name!r}")


def __dir__() -> List[str]:
    return sorted(list(globals().keys()) + list(_PERSONA_TO_CANONICAL.keys()))


__all__: List[str] = [
    # Driving persona
    "PersonaType",
    "AnalysisFocus",
    "DrivingPersona",
    "ConservativePersona",
    "SportyPersona",
    "VeteranPersona",
    "get_persona",

    # Scenario engine
    "OperationalDomain",
    "DOMAIN_LABELS",
    "DifficultyLevel",
    "ADASScenario",
    "ScenarioEngine",
    "get_engine",

    # Safety metrics
    "BadgeCategory",
    "CATEGORY_META",
    "BadgeLevel",
    "LEVEL_META",
    "BadgeScore",
    "SafetyBadgeSystem",
    "get_badge_system",

    # Co-pilot
    "AlertSeverity",
    "Alert",
    "TelemetryContext",
    "AlertRule",
    "CoPilot",

    # Orchestrator (top-level entry point)
    "PersonaOrchestrator",
]
