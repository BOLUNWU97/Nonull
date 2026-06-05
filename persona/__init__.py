"""
Nonull (智驾智能体) - Persona Orchestrator Package
====================================================

人格编排系统 — 将角色、场景、安全指标与 Copilot 融为一体。
Persona Orchestration System — unifies persona, scenario, safety metrics, and copilot.

@package: persona
@version: 0.1.0
@since:   2026-06-05
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Driving persona (角色 / character)
# ---------------------------------------------------------------------------
from .driving_persona import (
    PersonaType,
    AnalysisFocus,
    DrivingPersona,
    ConservativePersona,
    SportyPersona,
    VeteranPersona,
    get_persona,
)

# ---------------------------------------------------------------------------
# Scenario engine (场景思维 / scenario thinking)
# ---------------------------------------------------------------------------
from .scenario_engine import (
    OperationalDomain,
    DOMAIN_LABELS,
    DifficultyLevel,
    ADASScenario,
    ScenarioEngine,
    get_engine,
)

# ---------------------------------------------------------------------------
# Safety metrics (安全指标 / advisory safety metrics)
# ---------------------------------------------------------------------------
from .safety_badge import (
    BadgeCategory,
    CATEGORY_META,
    BadgeLevel,
    LEVEL_META,
    BadgeScore,
    SafetyBadgeSystem,
    get_badge_system,
)

# ---------------------------------------------------------------------------
# Co-pilot (副驾提醒 / proactive alert system)
# ---------------------------------------------------------------------------
from .co_pilot import (
    AlertSeverity,
    Alert,
    TelemetryContext,
    AlertRule,
    CoPilot,
)

# ---------------------------------------------------------------------------
# Orchestrator (人格编排器 / persona orchestrator — top-level entry point)
# ---------------------------------------------------------------------------
from .persona_orchestrator import PersonaOrchestrator

logger = logging.getLogger(__name__)

__version__ = "0.1.0"
__author__ = "Nonull Team"
__license__ = "MIT"
__description__ = "Persona Orchestration for Autonomous Driving AI (驾驶人格编排系统)"

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
