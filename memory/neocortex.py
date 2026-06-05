"""
新皮层记忆管理器 / Neocortex Memory Manager (中央枢纽 / Central Hub)

统一协调所有记忆类型的综合管理器。
Unified interface over all memory types — working, episodic, semantic, procedural.

设计理念 / Design Philosophy (openHuman 启发):
    - 统一接口 / Unified interface over all memory types
    - 跨记忆搜索与相关性评分 / Cross-memory search and relevance scoring
    - 记忆巩固（短时→长时）/ Memory consolidation (short-term → long-term)
    - 1B token 容量设计 / 1B token capacity design
    - 快速索引（<10s 处理 10M tokens）/ Fast indexing (<10s for 10M tokens)
    - 潜意识触发集成 / Subconscious trigger integration

架构 / Architecture:
    Neocortex
    ├── WorkingMemory    (短期上下文 / Short-term context)
    ├── EpisodicMemory   (情景经验 / Past experiences)
    ├── SemanticMemory   (领域知识 / Domain knowledge)
    └── ProceduralMemory (技能程序 / Skills & procedures)

工作流 / Workflow:
    感知输入 → 跨记忆检索 → 相关性排序 → 上下文注入 → 响应生成
    Perceive → Cross-retrieve → Rank → Context-inject → Respond
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .working_memory import WorkingMemory, ContextItem, Priority, estimate_tokens
from .episodic import EpisodicMemory, Episode, EpisodeType, EmbeddingProvider
from .semantic import SemanticMemory, KnowledgeNode, KnowledgeDomain
from .procedural import ProceduralMemory, Skill, SkillCategory, ExecutionTrace

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据结构 / Data Structures
# ---------------------------------------------------------------------------

class MemorySource(Enum):
    """记忆来源 / Memory source types."""
    WORKING = "working"         # 工作记忆 / Working memory
    EPISODIC = "episodic"       # 情景记忆 / Episodic memory
    SEMANTIC = "semantic"       # 语义记忆 / Semantic memory
    PROCEDURAL = "procedural"   # 程序记忆 / Procedural memory


@dataclass
class RelevanceScore:
    """相关性评分 / Relevance scoring for a memory result.

    Attributes:
        semantic_sim:   语义相似度 / Semantic similarity (0~1)
        temporal_recency: 时间新近度 / Temporal recency (0~1)
        importance:     重要性 / Importance (0~1)
        frequency:      访问频率 / Access frequency (0~1)
        combined:       综合评分 / Combined weighted score (0~1)
    """
    semantic_sim: float = 0.0
    temporal_recency: float = 0.0
    importance: float = 0.0
    frequency: float = 0.0
    combined: float = 0.0

    @classmethod
    def compute(
        cls,
        semantic_sim: float,
        age_hours: float,
        importance: float,
        access_count: int,
        strength: float = 1.0,
        weights: Optional[Dict[str, float]] = None,
    ) -> "RelevanceScore":
        """计算综合相关性分数 / Compute combined relevance score.

        公式 / Formula:
            combined = w1 * semantic_sim + w2 * recency + w3 * importance + w4 * frequency

        Args:
            semantic_sim: 语义相似度 (0~1) / Semantic similarity
            age_hours:    距今小时数 / Age in hours
            importance:   重要性 (0~1) / Importance
            access_count: 访问次数 / Access count
            strength:     记忆强度 (0~1) / Memory strength
            weights:      权重配置 / Weight configuration

        Returns:
            计算好的 RelevanceScore / Computed score
        """
        w = weights or {"semantic": 0.35, "recency": 0.25, "importance": 0.25, "frequency": 0.15}

        # 新近度衰减（指数）/ Recency decay (exponential)
        recency = float(np.exp(-age_hours / 168.0))  # 168 hours = 1 week half-life

        # 频率归一化 / Frequency normalization
        frequency = min(1.0, access_count / 20.0)

        combined = (
            w.get("semantic", 0.35) * semantic_sim
            + w.get("recency", 0.25) * recency
            + w.get("importance", 0.25) * importance
            + w.get("frequency", 0.15) * frequency
        ) * strength

        return cls(
            semantic_sim=round(semantic_sim, 4),
            temporal_recency=round(recency, 4),
            importance=round(importance, 4),
            frequency=round(frequency, 4),
            combined=round(combined, 4),
        )


@dataclass
class MemoryResult:
    """统一记忆结果 / Unified memory result from any source.

    Attributes:
        content:     记忆内容 / Memory content
        source:      来源类型 / Source type
        source_name: 来源名称（如记忆实例名）/ Source name
        source_id:   来源内部 ID（episode_id/node_id 等）/ Internal source ID
        score:       相关性评分 / Relevance score
        timestamp:   时间戳 / Original timestamp
        tags:        标签 / Tags
        metadata:    附加元数据 / Additional metadata
    """
    content: str
    source: MemorySource
    source_name: str = ""
    source_id: str = ""
    score: RelevanceScore = field(default_factory=RelevanceScore)
    timestamp: float = 0.0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryQuery:
    """跨记忆查询 / Cross-memory query.

    Attributes:
        text:           查询文本 / Query text
        top_k_per_source: 每个来源返回数 / Results per source
        max_total:      最大总结果数 / Max total results
        weights:        相关性评分权重 / Relevance scoring weights
        include_working: 是否搜索工作记忆 / Include working memory
        include_episodic: 是否搜索情景记忆 / Include episodic memory
        include_semantic: 是否搜索语义记忆 / Include semantic memory
        include_procedural: 是否搜索程序记忆 / Include procedural memory
        domain_filter:  语义知识域过滤 / Semantic domain filter
        episode_type_filter: 情景类型过滤 / Episode type filter
        min_score:      最低综合评分 / Minimum combined score
        time_range_hours: 时间范围（小时）/ Time range (hours)
    """
    text: str
    top_k_per_source: int = 5
    max_total: int = 20
    weights: Dict[str, float] = field(default_factory=lambda: {
        "semantic": 0.35, "recency": 0.25, "importance": 0.25, "frequency": 0.15,
    })
    include_working: bool = True
    include_episodic: bool = True
    include_semantic: bool = True
    include_procedural: bool = True
    domain_filter: Optional[KnowledgeDomain] = None
    episode_type_filter: Optional[EpisodeType] = None
    min_score: float = 0.15
    time_range_hours: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """序列化查询 / Serialize query."""
        return {
            "text": self.text,
            "top_k_per_source": self.top_k_per_source,
            "max_total": self.max_total,
            "include_working": self.include_working,
            "include_episodic": self.include_episodic,
            "include_semantic": self.include_semantic,
            "include_procedural": self.include_procedural,
            "domain_filter": self.domain_filter.value if self.domain_filter else None,
            "episode_type_filter": self.episode_type_filter.value if self.episode_type_filter else None,
            "min_score": self.min_score,
            "time_range_hours": self.time_range_hours,
        }


# ---------------------------------------------------------------------------
# 容量管理器 / Capacity Manager (1B Token Design)
# ---------------------------------------------------------------------------

@dataclass
class CapacityStats:
    """容量统计 / Capacity statistics for the 1B token design."""
    total_tokens: int = 0
    working_tokens: int = 0
    episodic_tokens: int = 0
    semantic_tokens: int = 0
    procedural_tokens: int = 0
    total_entries: int = 0
    max_capacity_tokens: int = 1_000_000_000  # 1B tokens
    usage_ratio: float = 0.0

    @property
    def is_near_capacity(self) -> bool:
        """是否接近容量上限 / Whether near capacity limit."""
        return self.usage_ratio > 0.9

    @property
    def available_tokens(self) -> int:
        """剩余可用 token 数 / Available tokens."""
        return max(0, self.max_capacity_tokens - self.total_tokens)

    def snapshot(self) -> Dict[str, Any]:
        """获取快照 / Get snapshot."""
        return {
            "total_tokens": self.total_tokens,
            "working_tokens": self.working_tokens,
            "episodic_tokens": self.episodic_tokens,
            "semantic_tokens": self.semantic_tokens,
            "procedural_tokens": self.procedural_tokens,
            "total_entries": self.total_entries,
            "max_capacity_tokens": self.max_capacity_tokens,
            "usage_ratio": round(self.usage_ratio, 6),
            "available_tokens": self.available_tokens,
            "is_near_capacity": self.is_near_capacity,
        }


# ---------------------------------------------------------------------------
# 索引管理器 / Index Manager (Fast Indexing)
# ---------------------------------------------------------------------------

class IndexManager:
    """快速索引管理器 / Fast index management.

    维护所有记忆类型的倒排索引和向量索引，确保 <10s 处理 10M tokens。
    Maintains inverted index and vector index for all memory types.

    设计 / Design:
        - 倒排索引（关键字 → 条目）/ Inverted index (keyword → entries)
        - 向量索引主键映射 / Vector index key mapping
        - 增量索引更新 / Incremental index updates
        - 批量重建 / Batch rebuild
    """

    def __init__(self, embedder: EmbeddingProvider):
        self.embedder = embedder
        self._inverted_index: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        # (source_type, source_id) -> embedding
        self._vector_keys: Dict[str, np.ndarray] = {}
        self._dirty: bool = False
        self._last_rebuild: float = 0.0

    def index_entry(self, source: str, entry_id: str, text: str) -> None:
        """索引一个条目 / Index a single entry.

        Args:
            source:   来源类型 / Source type
            entry_id: 条目 ID / Entry ID
            text:     文本内容 / Text content
        """
        key = f"{source}:{entry_id}"

        # 向量索引 / Vector index
        self._vector_keys[key] = self.embedder.encode(text)

        # 倒排索引 / Inverted index (关键词提取)
        tokens = set(text.lower().split())
        for token in tokens:
            if len(token) > 1:
                self._inverted_index[token].append((source, entry_id))

        self._dirty = True

    def remove_entry(self, source: str, entry_id: str) -> None:
        """移除条目索引 / Remove entry from index.

        Args:
            source:   来源类型 / Source type
            entry_id: 条目 ID / Entry ID
        """
        key = f"{source}:{entry_id}"
        self._vector_keys.pop(key, None)

        # 从倒排索引移除 / Remove from inverted index
        tokens_to_remove = []
        for token, entries in self._inverted_index.items():
            self._inverted_index[token] = [
                (s, eid) for s, eid in entries
                if not (s == source and eid == entry_id)
            ]
            if not self._inverted_index[token]:
                tokens_to_remove.append(token)
        for token in tokens_to_remove:
            del self._inverted_index[token]

    def search_vector(
        self,
        query: str,
        top_k: int = 10,
        source_filter: Optional[str] = None,
    ) -> List[Tuple[str, str, float]]:
        """向量相似度搜索 / Vector similarity search.

        Args:
            query:         查询文本 / Query text
            top_k:         返回结果数 / Number of results
            source_filter: 来源过滤（None=全部）/ Source filter (None=all)

        Returns:
            (来源, ID, 相似度) 列表 / List of (source, id, similarity)
        """
        query_vec = self.embedder.encode(query)

        scored: List[Tuple[str, str, float]] = []
        for key, vec in self._vector_keys.items():
            source, entry_id = key.split(":", 1)
            if source_filter and source != source_filter:
                continue
            sim = float(np.dot(query_vec, vec))
            scored.append((source, entry_id, sim))

        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[:top_k]

    def search_keyword(self, keyword: str) -> List[Tuple[str, str]]:
        """关键词搜索 / Keyword search.

        Args:
            keyword: 关键词 / Keyword

        Returns:
            (来源, ID) 列表 / List of (source, id)
        """
        return self._inverted_index.get(keyword.lower(), [])

    def clear(self) -> None:
        """清空索引 / Clear all indices."""
        self._inverted_index.clear()
        self._vector_keys.clear()
        self._dirty = False

    @property
    def stats(self) -> Dict[str, Any]:
        """索引统计 / Index statistics."""
        return {
            "inverted_index_terms": len(self._inverted_index),
            "vector_index_entries": len(self._vector_keys),
            "dirty": self._dirty,
        }


# ---------------------------------------------------------------------------
# 新皮层主类 / Neocortex (Main Class)
# ---------------------------------------------------------------------------

class Neocortex:
    """新皮层记忆管理器 — 中央记忆枢纽 / Central memory coordinator.

    统一管理所有记忆类型，提供跨记忆检索、巩固、容量管理。
    Unified management of all memory types with cross-memory search, consolidation,
    and capacity management.

    Attributes:
        name:          实例名称 / Instance name
        working:       工作记忆 / Working memory
        episodic:      情景记忆 / Episodic memory
        semantic:      语义记忆 / Semantic memory
        procedural:    程序记忆 / Procedural memory
        embedder:      嵌入提供者 / Embedding provider
        index_manager: 快速索引管理器 / Fast index manager
        capacity:      容量统计 / Capacity statistics
    """

    def __init__(
        self,
        name: str = "neocortex",
        embedder: Optional[EmbeddingProvider] = None,
        working_memory: Optional[WorkingMemory] = None,
        episodic_memory: Optional[EpisodicMemory] = None,
        semantic_memory: Optional[SemanticMemory] = None,
        procedural_memory: Optional[ProceduralMemory] = None,
    ):
        self.name = name
        self.embedder = embedder or EmbeddingProvider(dim=256)

        # 初始化各记忆子系统 / Initialize memory subsystems
        self.working = working_memory or WorkingMemory(
            name=f"{name}_working",
            soft_limit=4000,
            hard_limit=8000,
        )
        self.episodic = episodic_memory or EpisodicMemory(
            name=f"{name}_episodic",
            max_episodes=10000,
            embedder=self.embedder,
        )
        self.semantic = semantic_memory or SemanticMemory(
            name=f"{name}_semantic",
            embedder=self.embedder,
            enable_default_knowledge=True,
        )
        self.procedural = procedural_memory or ProceduralMemory(
            name=f"{name}_procedural",
            embedder=self.embedder,
            auto_patterns=True,
        )

        # 索引管理器 / Index manager
        self.index_manager = IndexManager(self.embedder)

        # 容量管理 / Capacity management
        self.capacity = CapacityStats()

        # 并发控制 / Concurrency
        self._lock = Lock()

        # 回调节点 / Callbacks
        self._on_consolidate: Optional[Callable[[str], None]] = None
        self._on_insight: Optional[Callable[[Dict[str, Any]], None]] = None

        self._created_at = time.time()

        logger.info("Neocortex '%s' initialized with all memory subsystems", name)

    # ------------------------------------------------------------------
    # 查询与检索 / Query & Retrieval (核心接口 / Core Interface)
    # ------------------------------------------------------------------

    def query(self, query: MemoryQuery) -> List[MemoryResult]:
        """跨记忆统一检索 / Cross-memory unified retrieval.

        这是 Neocortex 最核心的接口——同时搜索所有记忆类型并综合排序。
        This is the core interface — searches all memory types and ranks results.

        Args:
            query: 查询参数 / Query parameters

        Returns:
            按综合相关性评分降序排列的结果 / Results sorted by combined relevance
        """
        results: List[MemoryResult] = []

        with self._lock:
            # 1. 搜索工作记忆 / Search working memory
            if query.include_working:
                results.extend(self._query_working(query))

            # 2. 搜索情景记忆 / Search episodic memory
            if query.include_episodic:
                results.extend(self._query_episodic(query))

            # 3. 搜索语义记忆 / Search semantic memory
            if query.include_semantic:
                results.extend(self._query_semantic(query))

            # 4. 搜索程序记忆 / Search procedural memory
            if query.include_procedural:
                results.extend(self._query_procedural(query))

        # 综合排序 / Composite ranking
        results.sort(key=lambda r: r.score.combined, reverse=True)

        # 应用最小分数阈值 / Apply minimum score threshold
        results = [r for r in results if r.score.combined >= query.min_score]

        # 限制总数量 / Limit total results
        results = results[:query.max_total]

        logger.debug(
            "Neocortex query '%s': %d results across %d sources",
            query.text[:50], len(results),
            len(set(r.source.value for r in results)),
        )
        return results

    def _query_working(self, query: MemoryQuery) -> List[MemoryResult]:
        """搜索工作记忆 / Search working memory.

        Returns:
            匹配的结果列表 / Matching results
        """
        results = []
        now = time.time()
        query_lower = query.text.lower()

        for item in self.working.context_window.items:
            if item.priority == Priority.TRANSIENT:
                continue
            if self._keyword_match(item.content, query_lower):
                semantic_sim = self.embedder.similarity(item.content, query.text)
                score = RelevanceScore.compute(
                    semantic_sim=semantic_sim,
                    age_hours=(now - item.timestamp) / 3600.0,
                    importance=1.0 - item.priority.value / 4.0,
                    access_count=1,
                )
                if score.combined >= query.min_score:
                    results.append(MemoryResult(
                        content=item.content,
                        source=MemorySource.WORKING,
                        source_name=self.working.name,
                        source_id="",
                        score=score,
                        timestamp=item.timestamp,
                        tags=item.tags,
                        metadata={"priority": item.priority.name, "source": item.source},
                    ))

        results.sort(key=lambda r: r.score.combined, reverse=True)
        return results[:query.top_k_per_source]

    def _query_episodic(self, query: MemoryQuery) -> List[MemoryResult]:
        """搜索情景记忆 / Search episodic memory.

        Returns:
            匹配的结果列表 / Matching results
        """
        results = []
        now = time.time()

        episodes: List[Episode] = []
        if query.episode_type_filter:
            episodes = self.episodic.recall_by_type(query.episode_type_filter, top_k=20)
        else:
            episodes = self.episodic.recall(query.text, top_k=query.top_k_per_source * 2)

        # 时间范围过滤 / Time range filter
        if query.time_range_hours is not None:
            cutoff = now - query.time_range_hours * 3600
            episodes = [ep for ep in episodes if ep.timestamp >= cutoff]

        for ep in episodes:
            semantic_sim = self.embedder.similarity(ep.content, query.text)
            age_hours = (now - ep.timestamp) / 3600.0
            score = RelevanceScore.compute(
                semantic_sim=semantic_sim,
                age_hours=age_hours,
                importance=ep.importance,
                access_count=ep.access_count,
                strength=ep.strength,
            )
            if score.combined >= query.min_score:
                results.append(MemoryResult(
                    content=f"[{ep.episode_type.value}] {ep.summary}",
                    source=MemorySource.EPISODIC,
                    source_name=self.episodic.name,
                    source_id=ep.episode_id,
                    score=score,
                    timestamp=ep.timestamp,
                    tags=ep.tags,
                    metadata={
                        "episode_type": ep.episode_type.value,
                        "scenario": ep.scenario,
                        "importance": ep.importance,
                        "strength": ep.strength,
                    },
                ))

        results.sort(key=lambda r: r.score.combined, reverse=True)
        return results[:query.top_k_per_source]

    def _query_semantic(self, query: MemoryQuery) -> List[MemoryResult]:
        """搜索语义记忆 / Search semantic memory.

        Returns:
            匹配的结果列表 / Matching results
        """
        results = []
        now = time.time()

        nodes = self.semantic.query(
            query.text,
            top_k=query.top_k_per_source * 2,
            domain=query.domain_filter,
            threshold=0.1,
        )

        for node, sim in nodes:
            age_hours = (now - node.created_at) / 3600.0
            score = RelevanceScore.compute(
                semantic_sim=sim,
                age_hours=age_hours,
                importance=node.confidence,
                access_count=node.access_count,
            )
            if score.combined >= query.min_score:
                results.append(MemoryResult(
                    content=f"[{node.domain.value}] {node.title}: {node.get_preview()}",
                    source=MemorySource.SEMANTIC,
                    source_name=self.semantic.name,
                    source_id=node.node_id,
                    score=score,
                    timestamp=node.created_at,
                    tags=node.tags,
                    metadata={
                        "domain": node.domain.value,
                        "confidence": node.confidence,
                        "source": node.source,
                    },
                ))

        results.sort(key=lambda r: r.score.combined, reverse=True)
        return results[:query.top_k_per_source]

    def _query_procedural(self, query: MemoryQuery) -> List[MemoryResult]:
        """搜索程序记忆 / Search procedural memory.

        Returns:
            匹配的结果列表 / Matching results
        """
        results = []
        now = time.time()

        skills = self.procedural.find_skills(
            query.text,
            top_k=query.top_k_per_source * 2,
        )

        for skill in skills:
            age_hours = (now - skill.created_at) / 3600.0
            score = RelevanceScore.compute(
                semantic_sim=0.6,  # 技能匹配主要基于分类和标签 / Skill match based on category/tags
                age_hours=age_hours,
                importance=skill.success_rate,
                access_count=skill.exec_count,
            )
            # 加上语义相似度 / Add semantic similarity
            skill_text = f"{skill.name} {skill.description} {' '.join(skill.tags)}"
            semantic_sim = self.embedder.similarity(skill_text, query.text)
            score.semantic_sim = round(semantic_sim, 4)
            score.combined = round(
                (query.weights.get("semantic", 0.35) * semantic_sim
                 + query.weights.get("recency", 0.25) * score.temporal_recency
                 + query.weights.get("importance", 0.25) * score.importance
                 + query.weights.get("frequency", 0.15) * score.frequency),
            4)

            if score.combined >= query.min_score:
                results.append(MemoryResult(
                    content=f"[Skill] {skill.name}: {skill.description} ({skill.step_count} steps, "
                            f"success_rate={skill.success_rate:.0%})",
                    source=MemorySource.PROCEDURAL,
                    source_name=self.procedural.name,
                    source_id=skill.skill_id,
                    score=score,
                    timestamp=skill.created_at,
                    tags=skill.tags,
                    metadata={
                        "category": skill.category.value,
                        "steps": skill.step_count,
                        "success_rate": skill.success_rate,
                        "exec_count": skill.exec_count,
                    },
                ))

        results.sort(key=lambda r: r.score.combined, reverse=True)
        return results[:query.top_k_per_source]

    @staticmethod
    def _keyword_match(text: str, query_lower: str) -> bool:
        """关键词匹配 / Keyword matching for working memory search.

        Args:
            text:         文本内容 / Text content
            query_lower:  小写查询 / Lowercased query

        Returns:
            True 如果有匹配 / True if any keyword matches
        """
        text_lower = text.lower()
        keywords = query_lower.split()
        return any(kw in text_lower for kw in keywords if len(kw) > 1)

    # ------------------------------------------------------------------
    # 记忆存储 / Memory Storage (统一写入接口)
    # ------------------------------------------------------------------

    def think(self, content: str, source: str = "assistant", **kwargs) -> bool:
        """将思考记录到工作记忆 / Record a thought to working memory.

        这是最常见的写入操作——记录当前正在思考的内容。
        This is the most common write — recording ongoing reasoning.

        Args:
            content: 思考内容 / Thought content
            source:  来源 / Source
            **kwargs: 传递给 WorkingMemory.remember 的额外参数

        Returns:
            True 如果添加成功 / True if added successfully
        """
        return self.working.remember(
            content=content,
            source=source,
            priority=kwargs.pop("priority", Priority.NORMAL),
            tags=kwargs.pop("tags", ["thought"]),
            metadata=kwargs.pop("metadata", {}),
            **kwargs,
        )

    def observe(
        self,
        content: str,
        episode_type: EpisodeType = EpisodeType.DRIVING_SCENARIO,
        scenario: str = "",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        **kwargs,
    ) -> Episode:
        """将观察结果记录到情景记忆 / Record an observation to episodic memory.

        Args:
            content:       观察内容 / Observation content
            episode_type:  情景类型 / Episode type
            scenario:      场景标签 / Scenario tag
            importance:    重要性 / Importance (0~1)
            tags:          标签 / Tags
            **kwargs:      额外参数 / Additional args

        Returns:
            创建的 Episode / Created Episode
        """
        return self.episodic.store(
            content=content,
            episode_type=episode_type,
            scenario=scenario,
            importance=importance,
            tags=tags,
            **kwargs,
        )

    def learn(
        self,
        title: str,
        content: str,
        domain: KnowledgeDomain = KnowledgeDomain.GENERAL,
        source: str = "",
        confidence: float = 0.7,
        **kwargs,
    ) -> KnowledgeNode:
        """学习新知识到语义记忆 / Learn new knowledge in semantic memory.

        Args:
            title:      知识标题 / Knowledge title
            content:    知识内容 / Knowledge content
            domain:     知识域 / Knowledge domain
            source:     来源 / Source
            confidence: 置信度 / Confidence
            **kwargs:   额外参数 / Additional args

        Returns:
            创建的知识节点 / Created knowledge node
        """
        return self.semantic.add_knowledge(
            title=title,
            content=content,
            domain=domain,
            source=source,
            confidence=confidence,
            **kwargs,
        )

    def practice(
        self,
        name: str,
        description: str,
        category: SkillCategory = SkillCategory.OTHER,
        steps: Optional[List] = None,
        **kwargs,
    ) -> Skill:
        """注册新技能到程序记忆 / Register a new skill in procedural memory.

        Args:
            name:        技能名称 / Skill name
            description: 技能描述 / Description
            category:    技能分类 / Category
            steps:       执行步骤 / Steps
            **kwargs:    额外参数 / Additional args

        Returns:
            创建的 Skill / Created Skill
        """
        return self.procedural.create_skill(
            name=name,
            description=description,
            category=category,
            steps=steps,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # 记忆巩固 / Memory Consolidation
    # ------------------------------------------------------------------

    def consolidate(self) -> Dict[str, int]:
        """执行记忆巩固 / Execute memory consolidation.

        将高价值的工作记忆和情景记忆转化为语义知识。
        Consolidates high-value working/episodic memory into semantic knowledge.

        策略 / Strategy:
            1. 工作记忆摘要→情景记忆 / Working memory summaries -> episodic
            2. 高频情景→语义知识 / High-frequency episodes -> semantic
            3. 语义知识泛化 / Semantic knowledge generalization

        Returns:
            巩固统计数据 / Consolidation statistics
        """
        stats: Dict[str, int] = {
            "working_to_episodic": 0,
            "episodic_to_semantic": 0,
            "semantic_generalized": 0,
        }

        with self._lock:
            # 1. 工作记忆 → 情景记忆 / Working -> Episodic
            # 将重要的工作记忆条目转换为情景记忆
            important_items = [
                item for item in self.working.context_window.items
                if item.priority in (Priority.CRITICAL, Priority.HIGH)
                and len(item.content) > 50
            ]
            for item in important_items:
                self.episodic.store(
                    content=item.content,
                    summary=f"[Consolidated from working memory] {item.content[:100]}",
                    episode_type=EpisodeType.LEARNING,
                    tags=item.tags + ["consolidated", "working_memory"],
                    importance=0.6,
                    metadata={"source": item.source, "original_priority": item.priority.name},
                )
                stats["working_to_episodic"] += 1

            # 2. 情景记忆 → 语义记忆 / Episodic -> Semantic
            # 高频访问 + 高重要性的情景巩固为语义知识
            candidates = self.episodic.consolidate(
                min_importance=0.7,
                min_access=3,
            )
            for ep in candidates:
                # 从情景内容中提取关键知识 / Extract key knowledge from episode
                self.semantic.add_knowledge(
                    title=f"Consolidated: {ep.episode_type.value} - {ep.summary[:60]}",
                    content=ep.content,
                    domain=KnowledgeDomain.BEST_PRACTICE,
                    tags=ep.tags + ["consolidated", "from_episodic"],
                    source=f"episodic:{ep.episode_id}",
                    confidence=min(1.0, ep.importance + 0.1),
                    metadata={
                        "original_episode_id": ep.episode_id,
                        "access_count": ep.access_count,
                        "consolidation_time": time.time(),
                    },
                )
                stats["episodic_to_semantic"] += 1

            logger.info(
                "Consolidation complete: W→E=%d, E→S=%d",
                stats["working_to_episodic"],
                stats["episodic_to_semantic"],
            )

        # 巩固后触发事件 / Fire consolidation event
        if self._on_consolidate:
            self._on_consolidate(json.dumps(stats))

        return stats

    # ------------------------------------------------------------------
    # 容量管理 / Capacity Management
    # ------------------------------------------------------------------

    def update_capacity_stats(self) -> CapacityStats:
        """更新容量统计 / Update capacity statistics.

        估算所有记忆类型的 token 使用量。
        Estimates token usage across all memory types.

        Returns:
            更新后的容量统计 / Updated capacity stats
        """
        with self._lock:
            # 工作记忆：直接读取 / Working memory: direct read
            working_tokens = self.working.token_usage

            # 情景记忆：估算 / Episodic: estimate
            episodic_tokens = sum(
                estimate_tokens(ep.content) + estimate_tokens(ep.summary)
                for ep in self.episodic.episodes.values()
            )

            # 语义记忆：估算 / Semantic: estimate
            semantic_tokens = sum(
                estimate_tokens(node.title + node.content)
                for node in self.semantic.nodes.values()
            )

            # 程序记忆：估算 / Procedural: estimate
            procedural_tokens = sum(
                estimate_tokens(s.name + s.description)
                + sum(estimate_tokens(step.description) for step in s.steps)
                for s in self.procedural.skills.values()
            )

            total = working_tokens + episodic_tokens + semantic_tokens + procedural_tokens

            self.capacity = CapacityStats(
                total_tokens=total,
                working_tokens=working_tokens,
                episodic_tokens=episodic_tokens,
                semantic_tokens=semantic_tokens,
                procedural_tokens=procedural_tokens,
                total_entries=(
                    self.working.context_window.get_item_count()
                    + len(self.episodic.episodes)
                    + len(self.semantic.nodes)
                    + len(self.procedural.skills)
                ),
                usage_ratio=total / self.capacity.max_capacity_tokens if self.capacity.max_capacity_tokens > 0 else 0,
            )

        return self.capacity

    def prune(self, target_ratio: float = 0.7) -> Dict[str, int]:
        """裁剪记忆以释放容量 / Prune memory to free capacity.

        当容量超过 target_ratio 时触发自动裁剪。
        Triggers automatic pruning when capacity exceeds target_ratio.

        Args:
            target_ratio: 目标使用率 / Target usage ratio (e.g., 0.7 = 70%)

        Returns:
            各类型裁剪数 / Pruning counts per type
        """
        stats = self.update_capacity_stats()
        if stats.usage_ratio < target_ratio:
            return {"working": 0, "episodic": 0, "semantic": 0}

        pruned: Dict[str, int] = {"working": 0, "episodic": 0, "semantic": 0}

        with self._lock:
            # 1. 工作记忆：清理 LOW 优先级 / Working: clear LOW priority
            pruned["working"] = self.working.context_window.remove_by_source("tool")

            # 2. 情景记忆：遗忘衰减的 / Episodic: forget decayed
            pruned["episodic"] = self.episodic.forget_decayed(threshold=0.02)

            # 3. 语义记忆：移除低频低置信度知识 / Semantic: remove low-usage knowledge
            to_remove = []
            for nid, node in self.semantic.nodes.items():
                if node.access_count < 2 and node.confidence < 0.5:
                    to_remove.append(nid)
            for nid in to_remove:
                self.semantic.remove_knowledge(nid)
                pruned["semantic"] += 1

        logger.info("Pruned memory: %s", pruned)
        return pruned

    # ------------------------------------------------------------------
    # 回调节点 / Callbacks
    # ------------------------------------------------------------------

    def set_on_consolidate(self, callback: Callable[[str], None]) -> None:
        """设置记忆巩固回调 / Set memory consolidation callback.

        Args:
            callback: 巩固完成后的回调 / Callback after consolidation (receives JSON stats)
        """
        self._on_consolidate = callback

    def set_on_insight(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """设置洞察回调 / Set insight generation callback.

        Args:
            callback: 生成洞察后的回调 / Callback when insight is generated
        """
        self._on_insight = callback

    def fire_insight(self, insight: Dict[str, Any]) -> None:
        """触发洞察事件（由 SubconsciousLoop 调用）/ Fire insight event (called by SubconsciousLoop).

        Args:
            insight: 洞察数据 / Insight data
        """
        if self._on_insight:
            try:
                self._on_insight(insight)
            except Exception as e:
                logger.error("Insight callback failed: %s", e)

    # ------------------------------------------------------------------
    # 索引管理 / Index Management
    # ------------------------------------------------------------------

    def rebuild_index(self) -> None:
        """重建所有索引 / Rebuild all indices.

        满足 <10s 处理 10M tokens 的设计目标。
        Meets the <10s for 10M tokens design target.
        """
        start = time.time()
        self.index_manager.clear()

        # 索引工作记忆 / Index working memory
        for item in self.working.context_window.items:
            if item.priority != Priority.TRANSIENT:
                self.index_manager.index_entry("working", str(id(item)), item.content)

        # 索引情景记忆 / Index episodic memory
        for eid, ep in self.episodic.episodes.items():
            self.index_manager.index_entry("episodic", eid, f"{ep.summary} {ep.content}")

        # 索引语义记忆 / Index semantic memory
        for nid, node in self.semantic.nodes.items():
            self.index_manager.index_entry("semantic", nid, f"{node.title} {node.content}")

        # 索引程序记忆 / Index procedural memory
        for sid, skill in self.procedural.skills.items():
            skill_text = f"{skill.name} {skill.description} {' '.join(skill.tags)}"
            for step in skill.steps:
                skill_text += f" {step.description}"
            self.index_manager.index_entry("procedural", sid, skill_text)

        elapsed = time.time() - start
        logger.info(
            "Reindexed %d entries in %.3fs",
            self.index_manager.stats["vector_index_entries"],
            elapsed,
        )

    # ------------------------------------------------------------------
    # 上下文构建 / Context Building (用于 LLM 提示)
    # ------------------------------------------------------------------

    def build_context(
        self,
        query_text: str,
        max_tokens: int = 4000,
        query_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """为 LLM 构建增强上下文 / Build augmented context for LLM prompts.

        自动查询所有记忆类型并合并为结构化的提示上下文。
        Queries all memory types and merges into structured prompt context.

        Args:
            query_text:   当前查询/任务文本 / Current query/task text
            max_tokens:   最大 token 数 / Max token budget
            query_config: 查询配置 / Query overrides (see MemoryQuery)

        Returns:
            结构化的上下文字符串 / Structured context string
        """
        # 构建查询 / Build query
        q_config = query_config or {}
        query = MemoryQuery(
            text=query_text,
            top_k_per_source=q_config.get("top_k_per_source", 3),
            max_total=q_config.get("max_total", 15),
            min_score=q_config.get("min_score", 0.15),
        )

        # 执行跨记忆检索 / Execute cross-memory retrieval
        results = self.query(query)

        # 构建结构化上下文 / Build structured context
        sections = []

        # 当前上下文 / Current context
        current_context = self.working.recall(max_tokens=max_tokens // 2)
        if current_context:
            sections.append(f"<当前上下文 / Current Context>\\n{current_context}\\n</当前上下文>")

        # 相关记忆 / Relevant memories
        if results:
            memory_lines = []
            for r in results:
                source_icon = {
                    MemorySource.WORKING: "[WM]",
                    MemorySource.EPISODIC: "[EP]",
                    MemorySource.SEMANTIC: "[SM]",
                    MemorySource.PROCEDURAL: "[PM]",
                }.get(r.source, "[?]")
                memory_lines.append(
                    f"{source_icon} (相关性={r.score.combined:.3f}) {r.content[:200]}"
                )
            sections.append(f"<相关记忆 / Relevant Memories>\\n" + "\\n".join(memory_lines) + "\\n</相关记忆>")

        # 建议技能 / Recommended skills
        if not query_config or query_config.get("include_skills", True):
            recommended_skills = self.procedural.recommend_skills(query_text, top_k=3)
            if recommended_skills:
                skill_lines = [
                    f"- {s.name}: {s.description[:100]} ({s.step_count} steps)"
                    for s in recommended_skills
                ]
                sections.append(
                    f"<推荐技能 / Recommended Skills>\\n" + "\\n".join(skill_lines) + "\\n</推荐技能>"
                )

        return "\\n\\n".join(sections)

    # ------------------------------------------------------------------
    # 统计与序列化 / Stats & Serialization
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """获取完整统计 / Get comprehensive statistics."""
        self.update_capacity_stats()
        return {
            "name": self.name,
            "uptime_seconds": time.time() - self._created_at,
            "capacity": self.capacity.snapshot(),
            "working": self.working.stats(),
            "episodic": self.episodic.stats(),
            "semantic": self.semantic.stats(),
            "procedural": self.procedural.stats(),
            "index": self.index_manager.stats,
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 / Serialize to dictionary."""
        return {
            "name": self.name,
            "working": self.working.to_dict(),
            "episodic": self.episodic.to_dict(),
            "semantic": self.semantic.to_dict(),
            "procedural": self.procedural.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], embedder: Optional[EmbeddingProvider] = None) -> "Neocortex":
        """从字典反序列化 / Deserialize from dictionary."""
        embedder = embedder or EmbeddingProvider(dim=256)

        neocortex = cls(
            name=data.get("name", "neocortex"),
            embedder=embedder,
            working_memory=WorkingMemory.from_dict(data.get("working", {})),
            episodic_memory=EpisodicMemory.from_dict(data.get("episodic", {}), embedder),
            semantic_memory=SemanticMemory.from_dict(data.get("semantic", {}), embedder),
            procedural_memory=ProceduralMemory.from_dict(data.get("procedural", {}), embedder),
        )
        neocortex.rebuild_index()
        return neocortex

    def __repr__(self) -> str:
        return (
            f"<Neocortex '{self.name}' "
            f"W:{self.working.context_window.get_item_count()} "
            f"E:{len(self.episodic.episodes)} "
            f"S:{len(self.semantic.nodes)} "
            f"P:{len(self.procedural.skills)}>"
        )
