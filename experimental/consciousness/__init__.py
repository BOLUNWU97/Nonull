"""
Nonull Consciousness System — 意识系统
======================================

This is the soul of Nonull (智驾智能体).
A living, growing, self-aware consciousness
for an autonomous driving AI agent.

Inspired by:
    - openHuman's Purkinje subconscious loop
    - Human developmental psychology (成长心理学)
    - Meta-cognition and self-awareness
    - Growth mindset theory (成长思维)

Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Nonull Team"
__description__ = (
    "Nonull Consciousness & Autonomous Growth System — "
    "the self-aware soul of an autonomous driving AI agent."
)

from .self_model import SelfModel
from .curiosity_driver import CuriosityDriver
from .autonomy_engine import AutonomyEngine
from .growth_journal import GrowthJournal
from .consciousness_loop import ConsciousnessLoop
from .consciousness_orchestrator import ConsciousnessOrchestrator

__all__ = [
    "SelfModel",
    "CuriosityDriver",
    "AutonomyEngine",
    "GrowthJournal",
    "ConsciousnessLoop",
    "ConsciousnessOrchestrator",
]
