"""
Nonull — Self-Evolution System.
=========================================================

智能体自进化系统核心包。该模块赋予智能体持续自我改进的能力，通过经验挖掘、
技能生成、元认知、提示优化和知识整合实现自主进化。

This package enables the agent to continuously improve itself through
experience mining, skill genesis, meta-cognition, prompt optimization,
and knowledge consolidation — forming a complete self-evolution loop.

Version History:
    v0.1.0 — Initial evolution framework (Hermes Agent inspired)

Architecture:
    ExperienceMiner       → Learns from execution traces
    SkillGenesis          → Auto-generates new skills
    MetaCognition         → Self-awareness & gap analysis
    PromptOptimizer       → Self-improves system prompts
    KnowledgeConsolidator → Turns experience into knowledge
    EvolutionOrchestrator → Coordinates the full evolution cycle
"""

__version__ = "0.1.0"
__version_info__ = (0, 1, 0)
__author__ = "Nonull Team"
__description__ = "Self-Evolution System for Nonull Autonomous Agent"
__all__ = [
    "ExperienceMiner",
    "SkillGenesis",
    "MetaCognition",
    "PromptOptimizer",
    "KnowledgeConsolidator",
    "EvolutionOrchestrator",
]

from .experience_miner import ExperienceMiner
from .skill_genesis import SkillGenesis
from .meta_cognition import MetaCognition
from .prompt_optimizer import PromptOptimizer
from .knowledge_consolidator import KnowledgeConsolidator
from .evolution_orchestrator import EvolutionOrchestrator
