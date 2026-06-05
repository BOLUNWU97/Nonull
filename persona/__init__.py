"""
Nonull (智驾智能体) - Persona Orchestrator Package
====================================================

人格编排系统 — 将角色、场景、徽章与 Copilot 融为一体。
Persona Orchestration System — unifies persona, scenario, badges, and copilot.

@package: persona
@version: 0.1.0
@since:   2026-06-05
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .driving_persona import PersonaType
from .persona_orchestrator import (
    # Core enums
    DrivingArchetype,
    DrivingStyle,
    ExperienceLevel,
    ScenarioType,
    WeatherCondition,
    RoadCondition,
    BadgeCategory,
    BadgeRarity,
    CopilotInterventionStyle,
    CopilotPersona,

    # Data classes
    PersonaProfile,
    DrivingScenario,
    Badge,
    CopilotConfig,
    GrowthStats,
    SessionRecord,
    PersonaState,

    # Main orchestrator
    PersonaOrchestrator,
)
from .scenario_engine import ScenarioEngine
from .safety_badge import SafetyBadgeSystem

logger = logging.getLogger(__name__)

__version__ = "0.1.0"
__author__ = "Nonull Team"
__license__ = "MIT"
__description__ = "Persona Orchestration for Autonomous Driving AI (驾驶人格编排系统)"

__all__: List[str] = [
    # Enums
    "PersonaType",
    "DrivingArchetype",
    "DrivingStyle",
    "ExperienceLevel",
    "ScenarioType",
    "WeatherCondition",
    "RoadCondition",
    "BadgeCategory",
    "BadgeRarity",
    "CopilotInterventionStyle",
    "CopilotPersona",

    # Data classes
    "PersonaProfile",
    "DrivingScenario",
    "Badge",
    "CopilotConfig",
    "GrowthStats",
    "SessionRecord",
    "PersonaState",

    # Main orchestrator
    "PersonaOrchestrator",

    # Engines & systems
    "ScenarioEngine",
    "SafetyBadgeSystem",
]
