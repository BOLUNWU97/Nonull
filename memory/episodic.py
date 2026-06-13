"""
情景记忆模块 / Episodic Memory Module (长期记忆 / Long-Term Memory)

管理过去的驾驶场景、调试会话、代码审查等经验。
Manages past driving scenarios, debugging sessions, code reviews, and experiences.

设计要点 / Design Highlights:
    - 时间感知检索 / Time-aware recall (when did this happen?)
    - 场景索引 / Scenario-based indexing (driving conditions, error types)
    - 语义相似度搜索 / Similarity search for similar past situations
    - 遗忘机制（openHuman 启发——"遗忘是功能"）/ Forgetting mechanism
    - 记忆衰退与巩固 / Memory decay and consolidation

Note on embeddings: the default EmbeddingProvider is a dependency-free
n-gram embedder (dim=256 by default). It is NOT a 1536-dim transformer
embedding. For higher-quality semantic search, plug in a custom provider
backed by sentence-transformers / OpenAI / Voyage and pass it via
`embedder=...` — see docs/architecture.md §5.4.

设计灵感 / Design Inspirations:
    - openHuman 的遗忘机制：记忆强度随时间衰减，但巩固后可以持久化
    - Ebbinghaus 遗忘曲线：指数衰减模型
    - 场景相似度匹配：用于自动驾驶工况匹配
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 嵌入工具 / Embedding Utilities
# ---------------------------------------------------------------------------

class EmbeddingProvider:
    """可插拔的嵌入向量生成器 / Pluggable embedding vector provider.

    默认使用轻量级 TF-IDF 风格词袋嵌入（无外部依赖）。
    生产环境应替换为 sentence-transformers 或 OpenAI/Claude API。
    Default: lightweight bag-of-words embedding (no external deps).
    Production: replace with sentence-transformers or LLM API.
    """

    def __init__(self, embedding_fn: Optional[Callable[[str], np.ndarray]] = None, dim: int = 256):
        self._fn = embedding_fn
        self.dim = dim
        self._vocab: Dict[str, int] = {}
        self._vocab_size = 0

    def encode(self, text: str) -> np.ndarray:
        """将文本编码为向量 / Encode text into a vector.

        Args:
            text: 输入文本 / Input text

        Returns:
            嵌入向量 / Embedding vector (shape: [dim])
        """
        if self._fn is not None:
            return self._fn(text)

        return self._default_encode(text)

    def _default_encode(self, text: str) -> np.ndarray:
        """默认的词袋嵌入（字符 n-gram）/ Default bag-of-words embedding (character n-grams)."""
        vec = np.zeros(self.dim, dtype=np.float32)
        if not text:
            return vec

        # 提取字符二元组和三元组特征 / Extract character bigrams and trigrams
        text_lower = text.lower()
        ngrams: Dict[str, float] = defaultdict(float)

        for i in range(len(text_lower) - 1):
            ngrams[text_lower[i:i+2]] += 1.0
        for i in range(len(text_lower) - 2):
            ngrams[text_lower[i:i+3]] += 1.5
        # 词级别特征 / Word-level features
        words = re.findall(r'\w+', text_lower)
        for w in words:
            if len(w) > 1:
                ngrams[f"word_{w}"] += 2.0

        # 哈希到向量维度 / Hash to vector dimensions
        for ngram, weight in ngrams.items():
            idx = abs(hash(ngram)) % self.dim
            vec[idx] += weight

        # L2 归一化 / L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm

        return vec

    def similarity(self, a: str, b: str) -> float:
        """计算两个文本的余弦相似度 / Compute cosine similarity between texts.

        Args:
            a: 文本 A / Text A
            b: 文本 B / Text B

        Returns:
            相似度 (0~1) / Similarity score (0~1)
        """
        va = self.encode(a)
        vb = self.encode(b)
        return float(np.dot(va, vb))


# ---------------------------------------------------------------------------
# 数据结构 / Data Structures
# ---------------------------------------------------------------------------

class EpisodeType(Enum):
    """情景类型 / Episode type categories."""
    DRIVING_SCENARIO = "driving_scenario"       # 驾驶场景 / Driving scenario
    DEBUGGING_SESSION = "debugging_session"     # 调试会话 / Debugging session
    CODE_REVIEW = "code_review"                 # 代码审查 / Code review
    DESIGN_DECISION = "design_decision"         # 设计决策 / Design decision
    TEST_RESULT = "test_result"                 # 测试结果 / Test result
    INCIDENT = "incident"                       # 事故/问题 / Incident or issue
    USER_FEEDBACK = "user_feedback"            # 用户反馈 / User feedback
    LEARNING = "learning"                       # 学习经验 / Learning experience
    OTHER = "other"                             # 其他 / Other


@dataclass
class Episode:
    """单一情景记忆 / A single episodic memory entry.

    Attributes:
        episode_id:     唯一标识符 / Unique identifier (UUID)
        content:        情景原始内容 / Original content
        summary:        情景摘要 / Summary
        episode_type:   情景类型 / Episode type
        scenario:       驾驶场景标签（如"高速变道""城区左转"）/ Driving scenario tag
        tags:           标签列表 / Tags
        timestamp:      发生时间 / When the episode occurred
        importance:     重要性 (0~1) / Importance score
        strength:       记忆强度 (0~1)，随时间衰减 / Memory strength (decays over time)
        access_count:   访问次数 / Access count
        last_accessed:  最后访问时间 / Last access timestamp
        embedding:      嵌入向量缓存 / Cached embedding vector
        metadata:       附加元数据 / Additional metadata
        consolidated:   是否已巩固到语义记忆 / Whether consolidated to semantic
    """
    content: str
    summary: str = ""
    episode_type: EpisodeType = EpisodeType.OTHER
    scenario: str = ""
    tags: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    importance: float = 0.5
    strength: float = 1.0
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    consolidated: bool = False
    episode_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    last_decayed_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.summary:
            self.summary = self.content[:120] + "..." if len(self.content) > 120 else self.content

    @property
    def age_hours(self) -> float:
        """距离现在的小时数 / Hours since episode occurred."""
        return (time.time() - self.timestamp) / 3600.0

    @property
    def is_decayed(self) -> bool:
        """记忆是否已基本衰减 / Whether memory has mostly decayed."""
        return self.strength < 0.05


# ---------------------------------------------------------------------------
# 情景记忆主类 / Episodic Memory
# ---------------------------------------------------------------------------

class EpisodicMemory:
    """情景记忆 / Episodic memory for past experiences.

    存储、检索和管理驾驶场景、调试会话等情景经验。
    Stores, retrieves, and manages episodic experiences.

    Attributes:
        name:             记忆名称 / Memory name
        episodes:         情景存储（episode_id -> Episode）/ Episode storage
        max_episodes:     最大情景数（0=无限制）/ Max episodes (0=unlimited)
        embedder:         嵌入提供者 / Embedding provider
        decay_rate:       遗忘衰减率 / Forgetting decay rate (per hour)
        recall_threshold: 相似度检索阈值 / Similarity retrieval threshold
    """

    def __init__(
        self,
        name: str = "default",
        max_episodes: int = 10000,
        embedder: Optional[EmbeddingProvider] = None,
        decay_rate: float = 0.02,
        recall_threshold: float = 0.3,
    ):
        self.name = name
        self.max_episodes = max_episodes
        self.embedder = embedder or EmbeddingProvider()
        self.decay_rate = decay_rate          # Ebbinghaus 遗忘曲线参数 / Ebbinghaus decay param
        self.recall_threshold = recall_threshold
        self.episodes: Dict[str, Episode] = {}
        self._scenario_index: Dict[str, List[str]] = defaultdict(list)  # scenario -> episode_ids
        self._tag_index: Dict[str, List[str]] = defaultdict(list)       # tag -> episode_ids
        self._type_index: Dict[EpisodeType, List[str]] = defaultdict(list)  # type -> episode_ids
        self._lock: Any = None  # 外部可设置锁 / External lock can be assigned
        self._created_at = time.time()
        self._consolidation_count = 0

    # ------------------------------------------------------------------
    # 记忆存储 / Memory Storage
    # ------------------------------------------------------------------

    def store(
        self,
        content: str,
        summary: str = "",
        episode_type: EpisodeType = EpisodeType.OTHER,
        scenario: str = "",
        tags: Optional[List[str]] = None,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> Episode:
        """存储一条情景记忆 / Store an episodic memory.

        Args:
            content:      情景内容 / Episode content
            summary:      摘要 / Summary
            episode_type: 情景类型 / Episode type
            scenario:     驾驶场景标签 / Driving scenario tag
            tags:         标签 / Tags
            importance:   重要性 (0~1) / Importance
            metadata:     附加元数据 / Additional metadata
            timestamp:    自定义时间戳 / Custom timestamp

        Returns:
            创建的 Episode 对象 / Created Episode instance
        """
        # 检查上限，触发淘汰 / Check capacity, trigger eviction
        if self.max_episodes > 0 and len(self.episodes) >= self.max_episodes:
            self._evict()

        episode = Episode(
            content=content,
            summary=summary,
            episode_type=episode_type,
            scenario=scenario,
            tags=tags or [],
            importance=max(0.0, min(1.0, importance)),
            timestamp=timestamp or time.time(),
            metadata=metadata or {},
        )

        # 预计算嵌入 / Precompute embedding
        episode.embedding = self.embedder.encode(content)

        # 存储 / Store
        self.episodes[episode.episode_id] = episode

        # 更新索引 / Update indices
        if episode.scenario:
            self._scenario_index[episode.scenario].append(episode.episode_id)
        for tag in episode.tags:
            self._tag_index[tag].append(episode.episode_id)
        self._type_index[episode.episode_type].append(episode.episode_id)

        logger.debug(
            "Stored episode %s type=%s scenario=%s importance=%.2f",
            episode.episode_id[:8], episode_type.value, scenario, importance,
        )
        return episode

    # ------------------------------------------------------------------
    # 记忆检索 / Memory Retrieval
    # ------------------------------------------------------------------

    def recall(
        self,
        query: str,
        top_k: int = 10,
        threshold: Optional[float] = None,
    ) -> List[Episode]:
        """基于查询文本检索相似情景 / Retrieve episodes similar to query text.

        Args:
            query:      查询文本 / Query text
            top_k:      返回结果数 / Number of results
            threshold:  相似度阈值（None=使用默认）/ Similarity threshold (None=default)

        Returns:
            按相似度排序的情景列表 / Episodes sorted by similarity (descending)
        """
        threshold = threshold if threshold is not None else self.recall_threshold
        query_vec = self.embedder.encode(query)

        # 对所有情景应用衰减 / Apply decay to all episodes
        self._apply_decay()

        scored: List[Tuple[float, Episode]] = []
        for episode in self.episodes.values():
            if episode.is_decayed:
                continue
            if episode.embedding is None:
                episode.embedding = self.embedder.encode(episode.content)

            sim = float(np.dot(query_vec, episode.embedding))
            # 综合评分 = 相似度 * (0.7 + 0.3 * 重要性) * 记忆强度 / Combined score
            combined = sim * (0.7 + 0.3 * episode.importance) * episode.strength
            if combined >= threshold:
                scored.append((combined, episode))

        # 排序并截取 / Sort and slice
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [ep for _, ep in scored[:top_k]]

        # 更新访问信息 / Update access info
        for ep in results:
            ep.access_count += 1
            ep.last_accessed = time.time()

        return results

    def recall_by_scenario(self, scenario: str, top_k: int = 10) -> List[Episode]:
        """按场景索引检索 / Retrieve episodes by scenario tag.

        Args:
            scenario: 场景标签 / Scenario tag
            top_k:    返回结果数 / Number of results

        Returns:
            匹配的情景列表 / Matching episodes
        """
        self._apply_decay()
        episode_ids = self._scenario_index.get(scenario, [])
        results = []
        for eid in episode_ids:
            ep = self.episodes.get(eid)
            if ep and not ep.is_decayed:
                results.append(ep)
                ep.access_count += 1
                ep.last_accessed = time.time()
        # 按重要性排序 / Sort by importance
        results.sort(key=lambda x: x.importance, reverse=True)
        return results[:top_k]

    def recall_by_type(self, episode_type: EpisodeType, top_k: int = 20) -> List[Episode]:
        """按情景类型检索 / Retrieve episodes by type.

        Args:
            episode_type: 情景类型 / Episode type
            top_k:        返回结果数 / Number of results

        Returns:
            匹配的情景列表 / Matching episodes
        """
        self._apply_decay()
        episode_ids = self._type_index.get(episode_type, [])
        results = []
        for eid in episode_ids:
            ep = self.episodes.get(eid)
            if ep and not ep.is_decayed:
                results.append(ep)
        results.sort(key=lambda x: x.importance * x.strength, reverse=True)
        return results[:top_k]

    def recall_by_tag(self, tag: str, top_k: int = 20) -> List[Episode]:
        """按标签检索 / Retrieve episodes by tag.

        Args:
            tag:   标签 / Tag
            top_k: 返回结果数 / Number of results

        Returns:
            匹配的情景列表 / Matching episodes
        """
        self._apply_decay()
        episode_ids = self._tag_index.get(tag, [])
        results = []
        for eid in episode_ids:
            ep = self.episodes.get(eid)
            if ep and not ep.is_decayed:
                results.append(ep)
        results.sort(key=lambda x: x.importance * x.strength, reverse=True)
        return results[:top_k]

    def recall_recent(self, hours: float = 24, top_k: int = 50) -> List[Episode]:
        """检索最近一段时间内的情景 / Retrieve episodes from recent time window.

        Args:
            hours:  回溯小时数 / Lookback hours
            top_k:  返回结果数 / Max results

        Returns:
            最近的情景列表 / Recent episodes
        """
        cutoff = time.time() - hours * 3600
        results = sorted(
            [ep for ep in self.episodes.values() if ep.timestamp >= cutoff],
            key=lambda x: x.timestamp,
            reverse=True,
        )
        for ep in results:
            ep.access_count += 1
        return results[:top_k]

    # ------------------------------------------------------------------
    # 记忆巩固 / Memory Consolidation
    # ------------------------------------------------------------------

    def consolidate(
        self,
        min_importance: float = 0.7,
        min_access: int = 3,
    ) -> List[Episode]:
        """标记可巩固到语义记忆的条目 / Tag episodes for semantic consolidation.

        高频访问 + 高重要性的情景适合巩固为语义知识。
        High-frequency + high-importance episodes are candidates for semantic knowledge.

        Args:
            min_importance: 最小重要性 / Minimum importance
            min_access:     最小访问次数 / Minimum access count

        Returns:
            巩固候选列表 / Consolidation candidates
        """
        candidates = []
        for episode in self.episodes.values():
            if (episode.importance >= min_importance
                    and episode.access_count >= min_access
                    and not episode.consolidated):
                episode.consolidated = True
                candidates.append(episode)
                self._consolidation_count += 1

        logger.info(
            "Consolidation: %d candidates found (total consolidated: %d)",
            len(candidates), self._consolidation_count,
        )
        return candidates

    # ------------------------------------------------------------------
    # 遗忘机制 / Forgetting Mechanism
    # ------------------------------------------------------------------

    def _apply_decay(self) -> None:
        """应用 Ebbinghaus 遗忘曲线衰减 / Apply Ebbinghaus forgetting curve decay.

        强度 = 原强度 * exp(-衰减率 * 时间差)
        strength = original * exp(-decay_rate * time_diff)
        """
        now = time.time()
        for episode in self.episodes.values():
            if episode.strength <= 0.0:
                continue
            hours_since = (now - episode.last_decayed_at) / 3600.0
            if hours_since > 0:
                decay_factor = math.exp(-self.decay_rate * hours_since)
                episode.strength *= decay_factor
                episode.strength = max(0.0, min(1.0, episode.strength))
                episode.last_decayed_at = now

    def forget_decayed(self, threshold: float = 0.01) -> int:
        """移除已严重衰减的旧记忆 / Remove heavily decayed memories.

        Args:
            threshold: 强度阈值，低于此值则移除 / Strength threshold for removal

        Returns:
            移除的条目数 / Number of removed episodes
        """
        self._apply_decay()
        to_remove = [
            eid for eid, ep in self.episodes.items()
            if ep.strength < threshold
        ]
        for eid in to_remove:
            self._remove_episode(eid)

        if to_remove:
            logger.info("Forgot %d decayed episodes (threshold=%.3f)", len(to_remove), threshold)
        return len(to_remove)

    def forget_intentional(self, episode_id: str) -> bool:
        """主动遗忘特定记忆 / Intentionally forget a specific episode.

        Args:
            episode_id: 情景 ID / Episode ID

        Returns:
            True 如果成功 / True if successful
        """
        if episode_id in self.episodes:
            self._remove_episode(episode_id)
            logger.info("Intentionally forgot episode %s", episode_id[:8])
            return True
        return False

    def boost_memory(self, episode_id: str, boost: float = 0.3) -> bool:
        """加强特定记忆（用于复习）/ Boost memory strength (e.g., during review).

        Args:
            episode_id: 情景 ID / Episode ID
            boost:      强度增量 / Strength increase

        Returns:
            True 如果成功 / True if successful
        """
        if episode_id not in self.episodes:
            return False
        episode = self.episodes[episode_id]
        episode.strength = min(1.0, episode.strength + boost)
        episode.last_accessed = time.time()
        episode.access_count += 1
        return True

    # ------------------------------------------------------------------
    # 内部方法 / Internal Methods
    # ------------------------------------------------------------------

    def _evict(self) -> int:
        """淘汰最不重要的情景 / Evict least important episodes.

        综合考量：低重要性、低访问、低频。
        Consider: low importance, low access count, low frequency.

        Returns:
            淘汰数 / Eviction count
        """
        self._apply_decay()
        # 评分：分数越低越容易被淘汰 / Lower score = higher eviction priority
        scored = []
        for eid, ep in self.episodes.items():
            score = (ep.importance * 0.5
                     + min(1.0, ep.access_count / 10) * 0.3
                     + ep.strength * 0.2)
            scored.append((score, eid))

        scored.sort(key=lambda x: x[0])
        # 淘汰底部 10% / Evict bottom 10%
        n_evict = max(1, len(scored) // 10)
        evicted = 0
        for _, eid in scored[:n_evict]:
            self._remove_episode(eid)
            evicted += 1

        logger.info("Evicted %d episodes to maintain capacity", evicted)
        return evicted

    def _remove_episode(self, episode_id: str) -> None:
        """从所有索引中移除情景 / Remove episode from all indices."""
        episode = self.episodes.pop(episode_id, None)
        if episode is None:
            return

        # 从场景索引移除 / Remove from scenario index
        if episode.scenario and episode_id in self._scenario_index.get(episode.scenario, []):
            self._scenario_index[episode.scenario].remove(episode_id)

        # 从标签索引移除 / Remove from tag index
        for tag in episode.tags:
            if episode_id in self._tag_index.get(tag, []):
                self._tag_index[tag].remove(episode_id)

        # 从类型索引移除 / Remove from type index
        if episode_id in self._type_index.get(episode.episode_type, []):
            self._type_index[episode.episode_type].remove(episode_id)

    # ------------------------------------------------------------------
    # 统计与序列化 / Stats & Serialization
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """清空所有情景记忆 / Clear all episodic memories."""
        self.episodes.clear()
        self._scenario_index.clear()
        self._tag_index.clear()
        self._type_index.clear()

    def stats(self) -> Dict[str, Any]:
        """获取记忆统计 / Get memory statistics."""
        self._apply_decay()
        type_counts = defaultdict(int)
        for ep in self.episodes.values():
            type_counts[ep.episode_type.value] += 1

        return {
            "name": self.name,
            "total_episodes": len(self.episodes),
            "max_episodes": self.max_episodes,
            "type_distribution": dict(type_counts),
            "scenario_count": len(self._scenario_index),
            "tag_count": len(self._tag_index),
            "avg_importance": np.mean([ep.importance for ep in self.episodes.values()]) if self.episodes else 0.0,
            "avg_strength": np.mean([ep.strength for ep in self.episodes.values()]) if self.episodes else 0.0,
            "avg_access_count": np.mean([ep.access_count for ep in self.episodes.values()]) if self.episodes else 0.0,
            "consolidation_count": self._consolidation_count,
            "decayed_ready_to_forget": sum(1 for ep in self.episodes.values() if ep.is_decayed),
            "created_at": self._created_at,
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 / Serialize to dictionary."""
        episodes_dict = {}
        for eid, ep in self.episodes.items():
            episodes_dict[eid] = {
                "episode_id": ep.episode_id,
                "content": ep.content,
                "summary": ep.summary,
                "episode_type": ep.episode_type.value,
                "scenario": ep.scenario,
                "tags": ep.tags,
                "timestamp": ep.timestamp,
                "importance": ep.importance,
                "strength": ep.strength,
                "access_count": ep.access_count,
                "last_accessed": ep.last_accessed,
                "last_decayed_at": ep.last_decayed_at,
                "consolidated": ep.consolidated,
                "metadata": ep.metadata,
            }

        return {
            "name": self.name,
            "max_episodes": self.max_episodes,
            "episodes": episodes_dict,
            "decay_rate": self.decay_rate,
            "recall_threshold": self.recall_threshold,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        embedder: Optional[EmbeddingProvider] = None,
    ) -> "EpisodicMemory":
        """从字典反序列化 / Deserialize from dictionary."""
        em = cls(
            name=data.get("name", "default"),
            max_episodes=data.get("max_episodes", 10000),
            embedder=embedder,
            decay_rate=data.get("decay_rate", 0.02),
            recall_threshold=data.get("recall_threshold", 0.3),
        )
        for eid, ep_data in data.get("episodes", {}).items():
            episode = Episode(
                episode_id=ep_data.get("episode_id", eid),
                content=ep_data["content"],
                summary=ep_data.get("summary", ""),
                episode_type=EpisodeType(ep_data.get("episode_type", "other")),
                scenario=ep_data.get("scenario", ""),
                tags=ep_data.get("tags", []),
                timestamp=ep_data.get("timestamp", time.time()),
                importance=ep_data.get("importance", 0.5),
                strength=ep_data.get("strength", 1.0),
                access_count=ep_data.get("access_count", 0),
                last_accessed=ep_data.get("last_accessed", time.time()),
                last_decayed_at=ep_data.get("last_decayed_at", time.time()),
                consolidated=ep_data.get("consolidated", False),
                metadata=ep_data.get("metadata", {}),
            )
            episode.embedding = em.embedder.encode(episode.content)
            em.episodes[eid] = episode

            # Rebuild indices
            if episode.scenario:
                em._scenario_index[episode.scenario].append(eid)
            for tag in episode.tags:
                em._tag_index[tag].append(eid)
            em._type_index[episode.episode_type].append(eid)

        return em

    def __repr__(self) -> str:
        return (
            f"<EpisodicMemory '{self.name}' "
            f"episodes={len(self.episodes)} "
            f"avg_strength={np.mean([ep.strength for ep in self.episodes.values()]) if self.episodes else 0:.3f}>"
        )
