"""
Nonull 记忆系统 / Memory System for Nonull (智驾智能体)

记忆架构 / Memory Architecture:
    - WorkingMemory:    短期工作记忆 / Short-term task context
    - EpisodicMemory:   情景记忆 / Past driving scenarios & debugging sessions
    - SemanticMemory:   语义记忆 / Domain knowledge (safety, tech stack, best practices)
    - ProceduralMemory: 程序记忆 / Skills, tools, workflow patterns
    - Neocortex:        新皮层管理器 / Unified coordinator over all memory types
    - SubconsciousLoop: 潜意识循环 / Background insight & connection discovery

默认特性 / Default feature set (honest):
    ✓ In-memory storage          内存存储
    ✓ Ebbinghaus decay           Ebbinghaus 遗忘衰减
    ✓ Cross-memory search        跨记忆检索
    ✓ Hybrid keyword + vector    关键词 + 向量混合检索
    ✓ Plugin architecture        可插拔后端（实现 MemoryBackend 即可接入 FAISS /
                                 Milvus / pgvector / Qdrant / Chroma，详见
                                 docs/architecture.md §5.4）

NOT enabled by default (won't be there after `pip install -r requirements.txt`):
    ✗ Vector embeddings (高维 / 语义级)  --  use a backend plugin
    ✗ FAISS / Milvus / pgvector          --  use a backend plugin
    ✗ Cross-process persistence          --  use a backend plugin

The previous "1B token capacity" claim and "sentence-transformers / FAISS
default" documentation were aspirational and have been removed. This module
ships a dependency-free n-gram EmbeddingProvider and an in-memory index
good for ~10K entries per process. To upgrade, see docs/architecture.md.

设计灵感 / Design Inspirations:
    - openHuman Neocortex (concept)
    - OpenClaw's 4-layer memory architecture
    - Claude Code's file-based persistent memory
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Nonull Team"

from .working_memory import WorkingMemory, ContextWindow, TokenBudget
from .episodic import EpisodicMemory, Episode, EpisodeType
from .semantic import SemanticMemory, KnowledgeNode
from .procedural import ProceduralMemory, Skill, ExecutionTrace
from .neocortex import Neocortex, MemoryQuery, MemoryResult, RelevanceScore
from .subconscious_loop import SubconsciousLoop, Insight
from .local_embedder import LocalSemanticEmbedder
from .semantic_index import SemanticIndex, SearchHit

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
    "EpisodeType",

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

    # Local semantic retrieval (native, zero-dependency)
    "LocalSemanticEmbedder",
    "SemanticIndex",
    "SearchHit",
]
