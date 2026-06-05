"""
Nonull 记忆系统 / Memory System for Nonull (智驾智能体)

记忆架构 / Memory Architecture:
    - WorkingMemory:    短期工作记忆 / Short-term task context
    - EpisodicMemory:   情景记忆 / Past driving scenarios & debugging sessions
    - SemanticMemory:   语义记忆 / Domain knowledge (safety, tech stack, best practices)
    - ProceduralMemory: 程序记忆 / Skills, tools, workflow patterns
    - Neocortex:        新皮层管理器 / Unified coordinator over all memory types
    - SubconsciousLoop: 潜意识循环 / Background insight & connection discovery

设计灵感 / Design Inspirations:
    - openHuman Neocortex (1B token capacity)
    - OpenClaw's 4-layer memory architecture
    - Claude Code's file-based persistent memory
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Nonull Team"

from .working_memory import WorkingMemory, ContextWindow, TokenBudget
from .episodic import EpisodicMemory, Episode
from .semantic import SemanticMemory, KnowledgeNode
from .procedural import ProceduralMemory, Skill, ExecutionTrace
from .neocortex import Neocortex, MemoryQuery, MemoryResult, RelevanceScore
from .subconscious_loop import SubconsciousLoop, Insight

__all__ = [
    # Version
    "__version__",

    # Working Memory
    "WorkingMemory",
    "ContextWindow",
    "TokenBudget",

    # Episodic Memory
    "EpisodicMemory",
    "Episode",

    # Semantic Memory
    "SemanticMemory",
    "KnowledgeNode",

    # Procedural Memory
    "ProceduralMemory",
    "Skill",
    "ExecutionTrace",

    # Neocortex (Central Hub)
    "Neocortex",
    "MemoryQuery",
    "MemoryResult",
    "RelevanceScore",

    # Subconscious Loop
    "SubconsciousLoop",
    "Insight",
]
