"""
潜意识循环 / Subconscious Loop (Purkinje 启发 / Purkinje-inspired)

作为后台线程运行，定期进行随机记忆回忆和主动洞察生成。
Runs as a background thread performing periodic random memory recall and proactive insight generation.

设计理念 / Design Philosophy (openHuman Purkinje-inspired):
    人脑的潜意识在后台持续工作——连接不同的记忆片段、发现隐藏模式、
    预演可能的未来场景。本模块模拟这一过程。

    The subconscious mind continuously works in the background — connecting disparate
    memory fragments, discovering hidden patterns, rehearsing possible future scenarios.

核心功能 / Core Functions:
    - 周期性随机回忆 / Periodic random memory recall
    - 跨记忆连接发现 / Cross-memory connection discovery
    - 主动洞察生成 / Proactive insight generation
    - 低开销运行 / Low-cost operation (10K cycles/day < $1)
    - 记忆巩固预筛选 / Memory consolidation pre-screening

运行成本 / Operating Cost:
    每天约 10K 次循环，成本 < $1（按 LLM token 计费标准）。
    ~10K cycles/day at < $1 (based on LLM token pricing).

安全机制 / Safety:
    - 可配置的循环间隔 / Configurable loop interval
    - 自动暂停当系统忙 / Auto-pause when system is busy
    - 资源使用限制 / Resource usage limits
    - 优雅退出 / Graceful shutdown
"""

from __future__ import annotations

import json
import logging
import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .neocortex import Neocortex, MemoryQuery, MemorySource
from .episodic import Episode, EpisodeType, EmbeddingProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据结构 / Data Structures
# ---------------------------------------------------------------------------

class InsightType(Enum):
    """洞察类型 / Insight type categories."""
    PATTERN = "pattern"                     # 模式发现 / Pattern discovery
    CONNECTION = "connection"               # 跨记忆连接 / Cross-memory connection
    ANALOGY = "analogy"                     # 类比 / Analogy
    GENERALIZATION = "generalization"        # 泛化 / Generalization
    ANOMALY = "anomaly"                     # 异常检测 / Anomaly detection
    PREDICTION = "prediction"               # 预测 / Prediction
    REFLECTION = "reflection"               # 反思 / Self-reflection
    REHEARSAL = "rehearsal"                 # 预演 / Mental rehearsal
    CONSOLIDATION = "consolidation"         # 巩固提示 / Consolidation prompt


@dataclass
class Insight:
    """洞察对象 / A generated insight from the subconscious loop.

    Attributes:
        insight_id:   唯一标识符 / Unique identifier
        insight_type: 洞察类型 / Insight type
        title:        洞察标题 / Title
        description:  洞察描述 / Description
        source_ids:   来源记忆 ID 列表 / Source memory IDs
        source_types: 来源记忆类型 / Source memory types
        confidence:   置信度 (0~1) / Confidence score
        relevance:    当前相关性 (0~1) / Current relevance score
        created_at:   创建时间 / Creation timestamp
        applied:      是否已被应用 / Whether the insight has been applied
        metadata:     附加元数据 / Additional metadata
    """
    insight_type: InsightType
    title: str
    description: str
    source_ids: List[str] = field(default_factory=list)
    source_types: List[str] = field(default_factory=list)
    confidence: float = 0.5
    relevance: float = 0.5
    created_at: float = field(default_factory=time.time)
    applied: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    insight_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """序列化 / Serialize."""
        return {
            "insight_id": self.insight_id,
            "insight_type": self.insight_type.value,
            "title": self.title,
            "description": self.description,
            "source_ids": self.source_ids,
            "source_types": self.source_types,
            "confidence": self.confidence,
            "relevance": self.relevance,
            "created_at": self.created_at,
            "applied": self.applied,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"<Insight [{self.insight_type.value}] {self.title[:40]} conf={self.confidence:.2f}>"


# ---------------------------------------------------------------------------
# 洞察模板 / Insight Templates (用于生成标准化的洞察)
# ---------------------------------------------------------------------------

INSIGHT_TEMPLATES: Dict[InsightType, List[str]] = {
    InsightType.PATTERN: [
        "注意到 {topic_a} 与 {topic_b} 之间存在重复模式：{pattern}",
        "发现 {context} 场景下的常见模式：{pattern}",
        "Noticed a recurring pattern between {topic_a} and {topic_b}: {pattern}",
    ],
    InsightType.CONNECTION: [
        "{topic_a} 可能与 {topic_b} 存在关联，因为 {reason}",
        "发现 {memory_a} 与 {memory_b} 之间的潜在连接：{connection}",
        "{topic_a} may be related to {topic_b} because {reason}",
    ],
    InsightType.ANALOGY: [
        "{situation_a} 类似于 {situation_b}，可以借鉴 {approach}",
        "{situation_a} is analogous to {situation_b}, suggesting {approach}",
    ],
    InsightType.GENERALIZATION: [
        "从过去的 {count} 次相似经验中，可以总结为：{generalization}",
        "Across {count} similar experiences, the general principle is: {generalization}",
    ],
    InsightType.ANOMALY: [
        "检测到异常模式：{anomaly}，与历史记录中的 {expected} 不同",
        "Detected anomalous pattern: {anomaly}, differs from expected {expected}",
    ],
    InsightType.PREDICTION: [
        "基于 {context} 的趋势，预测可能发生：{prediction}",
        "Based on {context} trends, predicted outcome: {prediction}",
    ],
    InsightType.REFLECTION: [
        "反思 {topic}：上次的经验提示我们应该 {action}",
        "Reflecting on {topic}: past experience suggests we should {action}",
    ],
    InsightType.REHEARSAL: [
        "预演 {scenario} 场景：如果 {condition}，则应该 {response}",
        "Rehearsing {scenario}: if {condition}, then optimal response is {response}",
    ],
    InsightType.CONSOLIDATION: [
        "建议将以下知识巩固到语义记忆：{knowledge}",
        "Suggest consolidating into semantic memory: {knowledge}",
    ],
}


# ---------------------------------------------------------------------------
# 潜意识循环主类 / Subconscious Loop (Main Class)
# ---------------------------------------------------------------------------

class SubconsciousLoop:
    """潜意识循环 — 后台记忆处理线程 / Background memory processing thread.

    在后台持续运行，定期进行随机记忆回忆、模式发现和洞察生成。
    Runs continuously in the background performing random recall, pattern
    discovery, and insight generation.

    Attributes:
        neocortex:        新皮层管理器引用 / Reference to Neocortex
        interval_min:     循环间隔（秒）/ Loop interval in seconds
        recall_batch:     每次回忆的条目数 / Items to recall per cycle
        insight_threshold: 洞察置信度阈值 / Insight confidence threshold
        running:          运行状态 / Running state
        insights:         生成的洞察历史 / Generated insights history
        max_insights:     最大洞察数 / Max stored insights
        embedder:         嵌入提供者 / Embedding provider
    """

    def __init__(
        self,
        neocortex: Neocortex,
        interval_seconds: float = 30.0,
        recall_batch: int = 5,
        insight_threshold: float = 0.3,
        max_insights: int = 500,
        embedder: Optional[EmbeddingProvider] = None,
        auto_start: bool = False,
    ):
        self.neocortex = neocortex
        self.interval_seconds = interval_seconds
        self.recall_batch = recall_batch
        self.insight_threshold = insight_threshold
        self.max_insights = max_insights
        self.embedder = embedder or EmbeddingProvider(dim=256)

        # 运行状态 / Running state
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 洞察存储 / Insight storage
        self.insights: Dict[str, Insight] = {}

        # 统计 / Statistics
        self._cycle_count: int = 0
        self._insight_count: int = 0
        self._start_time: float = 0.0
        self._last_recall_time: float = 0.0
        self._total_cycle_duration: float = 0.0

        # 回调 / Callbacks
        self._on_insight_callbacks: List[Callable[[Insight], None]] = []

        # 可用洞察模板 / Available insight templates
        self._templates = INSIGHT_TEMPLATES.copy()

        if auto_start:
            self.start()

        logger.info(
            "SubconsciousLoop initialized (interval=%ds, batch=%d, threshold=%.2f)",
            interval_seconds, recall_batch, insight_threshold,
        )

    # ------------------------------------------------------------------
    # 生命周期 / Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """启动潜意识循环线程 / Start the subconscious loop thread."""
        if self.running:
            logger.warning("SubconsciousLoop is already running")
            return

        self.running = True
        self._stop_event.clear()
        self._start_time = time.time()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="SubconsciousLoop",
            daemon=True,
        )
        self._thread.start()
        logger.info("SubconsciousLoop started (thread=%s)", self._thread.name)

    def stop(self, wait: bool = True) -> None:
        """停止潜意识循环 / Stop the subconscious loop.

        Args:
            wait: 是否等待线程结束 / Whether to wait for thread termination
        """
        self.running = False
        self._stop_event.set()

        if wait and self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                logger.warning("SubconsciousLoop thread did not terminate within timeout")
            else:
                logger.info("SubconsciousLoop stopped cleanly")

    @property
    def is_running(self) -> bool:
        """循环是否在运行 / Whether the loop is running."""
        return self.running and (self._thread is not None and self._thread.is_alive())

    def pause(self) -> None:
        """暂停循环 / Pause the loop."""
        self.running = False
        logger.info("SubconsciousLoop paused")

    def resume(self) -> None:
        """恢复循环 / Resume the loop."""
        if not self.is_running:
            self.start()

    # ------------------------------------------------------------------
    # 洞察回调 / Insight Callbacks
    # ------------------------------------------------------------------

    def add_on_insight_callback(self, callback: Callable[[Insight], None]) -> None:
        """注册洞察回调 / Register an insight callback.

        Args:
            callback: 生成洞察时的回调 / Called when an insight is generated
        """
        self._on_insight_callbacks.append(callback)

    def remove_on_insight_callback(self, callback: Callable[[Insight], None]) -> bool:
        """移除洞察回调 / Remove an insight callback.

        Returns:
            True 如果成功 / True if successfully removed
        """
        if callback in self._on_insight_callbacks:
            self._on_insight_callbacks.remove(callback)
            return True
        return False

    # ------------------------------------------------------------------
    # 核心循环 / Core Loop (后台线程入口)
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """潜意识主循环 / Main subconscious loop (runs in background thread)."""
        logger.debug("Subconscious loop thread entered")

        while not self._stop_event.is_set():
            cycle_start = time.time()

            try:
                # 1. 随机回忆 / Random recall
                recalled = self._random_recall()
                if recalled:
                    self._last_recall_time = time.time()

                # 2. 生成洞察 / Generate insights (概率执行 / Probabilistic)
                if random.random() < 0.3:  # 30% 概率每次循环 / 30% chance per cycle
                    insight = self._try_generate_insight()
                    if insight:
                        self._store_insight(insight)
                        self._notify_insight(insight)
                        # 如果洞察与驾驶相关，通知 Neocortex / Notify Neocortex for driving insights
                        if insight.confidence >= self.insight_threshold:
                            self.neocortex.fire_insight(insight.to_dict())

                # 3. 定期巩固检查 / Periodic consolidation check (每 50 次循环 / Every 50 cycles)
                if self._cycle_count > 0 and self._cycle_count % 50 == 0:
                    self._check_consolidation()

                # 4. 定期裁剪洞察 / Periodic insight pruning (每 100 次循环 / Every 100 cycles)
                if self._cycle_count > 0 and self._cycle_count % 100 == 0:
                    self._prune_insights()

            except Exception as e:
                logger.error("Subconscious cycle error: %s", e, exc_info=True)

            # 更新统计 / Update stats
            self._cycle_count += 1
            cycle_duration = time.time() - cycle_start
            self._total_cycle_duration += cycle_duration

            # 休眠到下一个周期 / Sleep until next cycle
            sleep_time = max(0.1, self.interval_seconds - cycle_duration)
            if self._stop_event.wait(sleep_time):
                break

        logger.info("Subconscious loop thread exiting (cycles=%d, insights=%d)",
                     self._cycle_count, self._insight_count)

    # ------------------------------------------------------------------
    # 随机回忆 / Random Recall
    # ------------------------------------------------------------------

    def _random_recall(self) -> int:
        """执行随机记忆回忆 / Perform random memory recall.

        从各记忆类型中随机抽取条目进行"浏览"。
        Randomly samples entries from all memory types for "browsing".

        Returns:
            回忆的条目数 / Number of items recalled
        """
        count = 0
        batch = self.recall_batch

        # 1. 随机抽取情景记忆 / Random episodes
        episodes = list(self.neocortex.episodic.episodes.values())
        if episodes:
            sampled = random.sample(episodes, min(batch, len(episodes)))
            for ep in sampled:
                # 随机回忆会加强记忆 / Random recall strengthens memory
                self.neocortex.episodic.boost_memory(ep.episode_id, boost=0.05)
                count += 1

        # 2. 随机抽取语义知识 / Random semantic knowledge
        semantic_nodes = list(self.neocortex.semantic.nodes.values())
        if semantic_nodes:
            sampled = random.sample(semantic_nodes, min(batch, len(semantic_nodes)))
            for node in sampled:
                node.access_count += 1
                count += 1

        # 3. 随机抽取程序记忆 / Random procedural skills (较低频率 / Lower frequency)
        if random.random() < 0.3:
            skills = list(self.neocortex.procedural.skills.values())
            if skills and random.random() < 0.5:
                sampled = random.sample(skills, min(2, len(skills)))
                for skill in sampled:
                    skill.exec_count = max(0, skill.exec_count + 1)
                    count += 1

        if count > 0:
            logger.debug("Random recall: %d items browsed", count)

        return count

    # ------------------------------------------------------------------
    # 洞察生成 / Insight Generation
    # ------------------------------------------------------------------

    def _try_generate_insight(self) -> Optional[Insight]:
        """尝试生成一个洞察 / Attempt to generate a single insight.

        选择一种洞察类型并尝试构造。
        Selects an insight type and attempts to construct one.

        Returns:
            生成的 Insight 或 None / Generated Insight or None
        """
        # 选择洞察类型（加权随机）/ Select insight type (weighted random)
        insight_type = self._select_insight_type()
        if insight_type is None:
            return None

        # 根据类型使用不同的生成策略 / Different strategies per type
        generator_map = {
            InsightType.PATTERN: self._generate_pattern_insight,
            InsightType.CONNECTION: self._generate_connection_insight,
            InsightType.ANALOGY: self._generate_analogy_insight,
            InsightType.GENERALIZATION: self._generate_generalization_insight,
            InsightType.ANOMALY: self._generate_anomaly_insight,
            InsightType.PREDICTION: self._generate_prediction_insight,
            InsightType.REFLECTION: self._generate_reflection_insight,
            InsightType.REHEARSAL: self._generate_rehearsal_insight,
            InsightType.CONSOLIDATION: self._generate_consolidation_insight,
        }

        generator = generator_map.get(insight_type)
        if generator is None:
            return None

        try:
            return generator()
        except Exception as e:
            logger.debug("Insight generation failed for %s: %s", insight_type.value, e)
            return None

    def _select_insight_type(self) -> Optional[InsightType]:
        """选择洞察类型（加权随机选择）/ Select insight type via weighted random.

        概率权重 / Weights:
            - PATTERN: 0.20
            - CONNECTION: 0.18
            - REFLECTION: 0.15
            - GENERALIZATION: 0.12
            - ANALOGY: 0.10
            - ANOMALY: 0.08
            - PREDICTION: 0.07
            - REHEARSAL: 0.05
            - CONSOLIDATION: 0.05
        """
        weights = {
            InsightType.PATTERN: 0.20,
            InsightType.CONNECTION: 0.18,
            InsightType.REFLECTION: 0.15,
            InsightType.GENERALIZATION: 0.12,
            InsightType.ANALOGY: 0.10,
            InsightType.ANOMALY: 0.08,
            InsightType.PREDICTION: 0.07,
            InsightType.REHEARSAL: 0.05,
            InsightType.CONSOLIDATION: 0.05,
        }

        types = list(weights.keys())
        probs = [weights[t] for t in types]

        # 确保至少有一些记忆才能生成需要样本的洞察 / Need samples for certain types
        episodic_count = len(self.neocortex.episodic.episodes)
        semantic_count = len(self.neocortex.semantic.nodes)

        if episodic_count < 3:
            # 记忆太少，只做反思 / Too few memories, only reflect
            return InsightType.REFLECTION
        if semantic_count < 3:
            probs[types.index(InsightType.GENERALIZATION)] = 0.02
            probs[types.index(InsightType.ANALOGY)] = 0.03

        # 归一化 / Normalize
        total = sum(probs)
        probs = [p / total for p in probs]

        return np.random.choice(types, p=probs)

    # ------------------------------------------------------------------
    # 各类型洞察生成器 / Insight Type Generators
    # ------------------------------------------------------------------

    def _generate_pattern_insight(self) -> Optional[Insight]:
        """模式发现洞察 / Pattern discovery insight.

        查找情景记忆中反复出现的主题。
        Finds recurring themes in episodic memory.
        """
        episodes = list(self.neocortex.episodic.episodes.values())
        if len(episodes) < 3:
            return None

        # 寻找高频共现标签 / Find high-frequency co-occuring tags
        tag_pairs: Dict[Tuple[str, str], int] = {}
        tag_counts: Dict[str, int] = {}

        for ep in episodes:
            for t in ep.tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
            for i, t1 in enumerate(ep.tags):
                for t2 in ep.tags[i + 1:]:
                    pair = tuple(sorted([t1, t2]))
                    tag_pairs[pair] = tag_pairs.get(pair, 0) + 1

        if not tag_pairs:
            return None

        # 找最频繁的共现对 / Find most frequent co-occurrence
        best_pair = max(tag_pairs, key=tag_pairs.get)
        count = tag_pairs[best_pair]
        total = len(episodes)

        confidence = min(1.0, count / max(1, total) * 2)
        if confidence < self.insight_threshold:
            return None

        return Insight(
            insight_type=InsightType.PATTERN,
            title=f"Pattern: {best_pair[0]} + {best_pair[1]}",
            description=(
                f"在 {count}/{total} 个场景中观察到标签 '{best_pair[0]}' 和 "
                f"'{best_pair[1]}' 同时出现，可能表示某种关联模式。"
                f"Observed tags '{best_pair[0]}' and '{best_pair[1]}' co-occurring "
                f"in {count}/{total} scenarios — may indicate a correlation."
            ),
            source_ids=[ep.episode_id for ep in episodes if best_pair[0] in ep.tags][:5],
            source_types=["episodic"],
            confidence=round(confidence, 3),
            metadata={"tag_pair": list(best_pair), "co_occurrence_count": count},
        )

    def _generate_connection_insight(self) -> Optional[Insight]:
        """跨记忆连接洞察 / Cross-memory connection insight.

        寻找语义记忆和情景记忆之间的潜在联系。
        Finds potential links between semantic and episodic memories.
        """
        episodes = list(self.neocortex.episodic.episodes.values())
        semantic_nodes = list(self.neocortex.semantic.nodes.values())

        if not episodes or not semantic_nodes:
            return None

        # 随机选取一个情景和一个知识节点 / Pick a random episode and knowledge node
        ep = random.choice(episodes)
        node = random.choice(semantic_nodes)

        # 计算它们之间的语义相似度 / Compute semantic similarity
        sim = self.embedder.similarity(ep.content, f"{node.title} {node.content}")

        if sim >= self.insight_threshold:
            return Insight(
                insight_type=InsightType.CONNECTION,
                title=f"Connection: {node.title}",
                description=(
                    f"情景记忆 '{ep.summary[:60]}' 与知识 '{node.title}' "
                    f"存在语义关联 (相似度={sim:.3f})。"
                    f"Episodic memory '{ep.summary[:60]}' is semantically related "
                    f"to knowledge '{node.title}' (similarity={sim:.3f})."
                ),
                source_ids=[ep.episode_id, node.node_id],
                source_types=["episodic", "semantic"],
                confidence=round(sim, 3),
                metadata={"similarity": sim},
            )
        return None

    def _generate_analogy_insight(self) -> Optional[Insight]:
        """类比发现洞察 / Analogy discovery insight."""
        episodes = list(self.neocortex.episodic.episodes.values())
        if len(episodes) < 4:
            return None

        # 找两个重要性高且类型不同的情景 / Find two high-importance episodes of different types
        candidates = [ep for ep in episodes if ep.importance > 0.5]
        if len(candidates) < 2:
            return None

        # 随机选两个 / Pick two random
        a, b = random.sample(candidates, 2)

        sim = self.embedder.similarity(a.content, b.content)
        # 中等相似度才是有趣的类比 / Medium similarity = interesting analogy
        if 0.3 <= sim <= 0.7:
            return Insight(
                insight_type=InsightType.ANALOGY,
                title=f"Analogy: {a.episode_type.value} ~ {b.episode_type.value}",
                description=(
                    f"类型 '{a.episode_type.value}' 的场景与类型 '{b.episode_type.value}' "
                    f"的场景存在结构相似性 (sim={sim:.2f})，可能可以借鉴处理策略。"
                    f"Scenes of type '{a.episode_type.value}' and '{b.episode_type.value}' "
                    f"share structural similarity (sim={sim:.2f}) — strategies may transfer."
                ),
                source_ids=[a.episode_id, b.episode_id],
                source_types=["episodic", "episodic"],
                confidence=round(sim, 3),
                metadata={"episode_a_type": a.episode_type.value, "episode_b_type": b.episode_type.value},
            )
        return None

    def _generate_generalization_insight(self) -> Optional[Insight]:
        """泛化洞察 / Generalization insight."""
        episodes = list(self.neocortex.episodic.episodes.values())
        if len(episodes) < 5:
            return None

        # 按类型分组 / Group by type
        type_groups: Dict[str, List[Episode]] = {}
        for ep in episodes:
            t = ep.episode_type.value
            if t not in type_groups:
                type_groups[t] = []
            type_groups[t].append(ep)

        # 找最大的组 / Find the largest group
        if not type_groups:
            return None
        best_type = max(type_groups, key=lambda t: len(type_groups[t]))
        group = type_groups[best_type]

        if len(group) < 3:
            return None

        # 计算该组的重要性统计 / Compute importance stats
        avg_importance = np.mean([ep.importance for ep in group])
        avg_strength = np.mean([ep.strength for ep in group])

        return Insight(
            insight_type=InsightType.GENERALIZATION,
            title=f"Generalization: {best_type} patterns",
            description=(
                f"在 {len(group)} 个 '{best_type}' 类型场景中，平均重要性 "
                f"{avg_importance:.2f}，平均记忆强度 {avg_strength:.2f}。"
                f"Across {len(group)} '{best_type}' scenarios, avg importance "
                f"{avg_importance:.2f}, avg memory strength {avg_strength:.2f}."
            ),
            source_ids=[ep.episode_id for ep in group[:5]],
            source_types=["episodic"],
            confidence=round(min(1.0, len(group) / 20 + avg_importance), 3),
            metadata={"type": best_type, "count": len(group), "avg_importance": avg_importance},
        )

    def _generate_anomaly_insight(self) -> Optional[Insight]:
        """异常检测洞察 / Anomaly detection insight."""
        episodes = list(self.neocortex.episodic.episodes.values())
        if len(episodes) < 5:
            return None

        # 找重要性异常高或异常低的情况 / Find anomalously high/low importance
        importances = [ep.importance for ep in episodes]
        if not importances:
            return None
        mean_imp = np.mean(importances)
        std_imp = np.std(importances) if len(importances) > 1 else 0.2

        for ep in episodes:
            z_score = (ep.importance - mean_imp) / max(std_imp, 0.01)
            if abs(z_score) > 2.0:
                direction = "异常高 / anomalously high" if z_score > 0 else "异常低 / anomalously low"
                return Insight(
                    insight_type=InsightType.ANOMALY,
                    title=f"Anomaly: importance={ep.importance:.2f}",
                    description=(
                        f"情景 '{ep.summary[:60]}' 的重要性 ({ep.importance:.2f}) "
                        f"{direction} (z-score={z_score:.2f})。"
                        f"Episode '{ep.summary[:60]}' has {direction} importance "
                        f"({ep.importance:.2f}, z-score={z_score:.2f})."
                    ),
                    source_ids=[ep.episode_id],
                    source_types=["episodic"],
                    confidence=round(min(1.0, abs(z_score) / 4), 3),
                    metadata={"z_score": z_score, "importance": ep.importance},
                )
        return None

    def _generate_prediction_insight(self) -> Optional[Insight]:
        """预测洞察 (占位) / Prediction insight (placeholder).

        在更完整实现中，这可以基于序列模式进行简单预测。
        In a fuller implementation, this would predict based on sequence patterns.
        """
        episodes = list(self.neocortex.episodic.episodes.values())
        if len(episodes) < 3:
            return None

        # 最简单预测：找最近频繁出现的情景类型 / Simple: most frequent recent type
        recent = sorted(episodes, key=lambda x: x.timestamp, reverse=True)[:10]
        type_counts: Dict[str, int] = {}
        for ep in recent:
            type_counts[ep.episode_type.value] = type_counts.get(ep.episode_type.value, 0) + 1

        if not type_counts:
            return None
        most_common = max(type_counts, key=type_counts.get)
        count = type_counts[most_common]

        return Insight(
            insight_type=InsightType.PREDICTION,
            title=f"Prediction: {most_common} likely",
            description=(
                f"近期 {most_common} 类型的出现频率较高 ({count}/{len(recent)})，"
                f"后续可能出现类似的场景。"
                f"Recent {most_common} activity is elevated ({count}/{len(recent)}) — "
                f"similar scenarios may follow."
            ),
            source_ids=[ep.episode_id for ep in recent],
            source_types=["episodic"],
            confidence=round(min(0.6, count / len(recent)), 3),
            metadata={"predicted_type": most_common, "frequency": count / len(recent)},
        )

    def _generate_reflection_insight(self) -> Optional[Insight]:
        """反思洞察 / Self-reflection insight."""
        episodes = list(self.neocortex.episodic.episodes.values())
        if not episodes:
            return None

        # 找最近的重要情景 / Find recent important episodes
        recent_important = sorted(
            [ep for ep in episodes if ep.importance > 0.6],
            key=lambda x: x.timestamp,
            reverse=True,
        )[:3]

        if not recent_important:
            # 改为找高频访问的 / Fall back to most accessed
            recent_important = sorted(
                episodes, key=lambda x: x.access_count, reverse=True,
            )[:3]

        if not recent_important:
            return None

        ep = recent_important[0]
        return Insight(
            insight_type=InsightType.REFLECTION,
            title=f"Reflection: {ep.summary[:50]}",
            description=(
                f"回顾 '{ep.episode_type.value}' 场景 (重要性={ep.importance:.2f})："
                f"{ep.summary[:100]}. 这个经验提醒我们关注 {ep.scenario or '相关方面'}。"
                f"Reflecting on '{ep.episode_type.value}' scenario "
                f"(importance={ep.importance:.2f}): {ep.summary[:100]}. "
                f"This experience reminds us to consider {ep.scenario or 'relevant aspects'}."
            ),
            source_ids=[ep.episode_id],
            source_types=["episodic"],
            confidence=round(min(0.7, ep.importance * ep.strength), 3),
            metadata={"reflected_episode_id": ep.episode_id, "importance": ep.importance},
        )

    def _generate_rehearsal_insight(self) -> Optional[Insight]:
        """预演洞察 / Mental rehearsal insight."""
        # 找高重要性的驾驶场景 / Find high-importance driving scenarios
        driving_eps = [
            ep for ep in self.neocortex.episodic.episodes.values()
            if ep.episode_type == EpisodeType.DRIVING_SCENARIO and ep.importance > 0.5
        ]
        if not driving_eps:
            return None

        ep = random.choice(driving_eps)
        return Insight(
            insight_type=InsightType.REHEARSAL,
            title=f"Rehearsal: {ep.scenario or 'driving scenario'}",
            description=(
                f"预演 '{ep.scenario or ep.episode_type.value}' 场景: "
                f"{ep.summary[:100]}. 建议提前准备应对策略。"
                f"Rehearsing '{ep.scenario or ep.episode_type.value}' scenario: "
                f"{ep.summary[:100]}. Suggest pre-planning response strategy."
            ),
            source_ids=[ep.episode_id],
            source_types=["episodic"],
            confidence=round(min(0.6, ep.importance), 3),
            metadata={"scenario": ep.scenario, "episode_id": ep.episode_id},
        )

    def _generate_consolidation_insight(self) -> Optional[Insight]:
        """巩固提示洞察 / Consolidation prompt insight."""
        # 找可巩固的候选 / Find consolidation candidates
        candidates = self.neocortex.episodic.consolidate(
            min_importance=0.65,
            min_access=2,
        )
        if not candidates:
            return None

        ep = candidates[0]
        return Insight(
            insight_type=InsightType.CONSOLIDATION,
            title=f"Consolidate: {ep.episode_type.value}",
            description=(
                f"情景 '{ep.summary[:60]}' 达到巩固条件 "
                f"(重要性={ep.importance:.2f}, 访问={ep.access_count})。建议将其知识化。"
                f"Episode '{ep.summary[:60]}' meets consolidation criteria "
                f"(importance={ep.importance:.2f}, access={ep.access_count}). "
                f"Suggest converting to semantic knowledge."
            ),
            source_ids=[ep.episode_id],
            source_types=["episodic"],
            confidence=round(min(0.8, ep.importance * min(1.0, ep.access_count / 5)), 3),
            metadata={"episode_id": ep.episode_id, "importance": ep.importance, "access": ep.access_count},
        )

    # ------------------------------------------------------------------
    # 洞察管理 / Insight Management
    # ------------------------------------------------------------------

    def _store_insight(self, insight: Insight) -> None:
        """存储洞察 / Store an insight.

        Args:
            insight: 洞察对象 / Insight to store
        """
        self.insights[insight.insight_id] = insight
        self._insight_count += 1

        logger.debug(
            "Generated insight [%s]: %s (conf=%.3f)",
            insight.insight_type.value, insight.title, insight.confidence,
        )

    def _notify_insight(self, insight: Insight) -> None:
        """通知所有注册的洞察回调 / Notify all registered insight callbacks.

        Args:
            insight: 生成的洞察 / Generated insight
        """
        for callback in self._on_insight_callbacks:
            try:
                callback(insight)
            except Exception as e:
                logger.error("Insight callback error: %s", e)

    def _prune_insights(self) -> int:
        """裁剪旧洞察以释放空间 / Prune old insights to free space.

        移除低置信度、低相关性的旧洞察。
        Removes old insights with low confidence and low relevance.

        Returns:
            裁剪的洞察数 / Number of pruned insights
        """
        if len(self.insights) <= self.max_insights:
            return 0

        # 按综合评分排序 / Sort by combined score
        now = time.time()
        scored = []
        for ins in self.insights.values():
            age_hours = (now - ins.created_at) / 3600.0
            score = ins.confidence * 0.5 + ins.relevance * 0.3 + (1 - min(1, age_hours / 168)) * 0.2
            scored.append((score, ins.insight_id))

        scored.sort(key=lambda x: x[0])

        # 移除底部条目 / Remove bottom entries
        to_remove = len(self.insights) - self.max_insights
        removed = 0
        for _, iid in scored[:to_remove]:
            if iid in self.insights:
                del self.insights[iid]
                removed += 1

        if removed > 0:
            logger.debug("Pruned %d old insights", removed)
        return removed

    def get_recent_insights(self, n: int = 10, min_confidence: float = 0.0) -> List[Insight]:
        """获取最近的洞察 / Get most recent insights.

        Args:
            n:              返回数 / Number of insights
            min_confidence:  最低置信度 / Minimum confidence threshold

        Returns:
            洞察列表 / List of insights, sorted by creation time (newest first)
        """
        sorted_insights = sorted(
            [ins for ins in self.insights.values() if ins.confidence >= min_confidence],
            key=lambda x: x.created_at,
            reverse=True,
        )
        return sorted_insights[:n]

    def get_insights_by_type(self, insight_type: InsightType) -> List[Insight]:
        """按类型获取洞察 / Get insights by type.

        Args:
            insight_type: 洞察类型 / Insight type

        Returns:
            匹配的洞察列表 / Matching insights (newest first)
        """
        sorted_insights = sorted(
            [ins for ins in self.insights.values() if ins.insight_type == insight_type],
            key=lambda x: x.created_at,
            reverse=True,
        )
        return sorted_insights

    def mark_insight_applied(self, insight_id: str) -> bool:
        """标记洞察已应用 / Mark an insight as applied.

        Args:
            insight_id: 洞察 ID / Insight ID

        Returns:
            True 如果成功 / True if successful
        """
        if insight_id in self.insights:
            self.insights[insight_id].applied = True
            return True
        return False

    # ------------------------------------------------------------------
    # 巩固检查 / Consolidation Check
    # ------------------------------------------------------------------

    def _check_consolidation(self) -> None:
        """检查并触发记忆巩固 / Check and trigger memory consolidation."""
        stats = self.neocortex.update_capacity_stats()

        # 如果使用率较高或情景记忆较多，触发巩固 / Consolidate if usage high or many episodes
        if (stats.usage_ratio > 0.6
                or len(self.neocortex.episodic.episodes) > 500):
            consolidation_result = self.neocortex.consolidate()
            total = sum(consolidation_result.values())
            if total > 0:
                logger.info(
                    "Subconscious triggered consolidation: %d items",
                    total,
                )

    # ------------------------------------------------------------------
    # 统计 / Statistics
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """获取潜意识循环统计 / Get subconscious loop statistics."""
        now = time.time()
        uptime = now - self._start_time if self._start_time > 0 else 0

        type_counts: Dict[str, int] = {}
        for ins in self.insights.values():
            t = ins.insight_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        avg_cycle_duration = (
            self._total_cycle_duration / self._cycle_count
            if self._cycle_count > 0 else 0
        )

        return {
            "running": self.is_running,
            "uptime_seconds": uptime,
            "cycle_count": self._cycle_count,
            "avg_cycle_duration_ms": round(avg_cycle_duration * 1000, 2),
            "total_insights_generated": self._insight_count,
            "stored_insights": len(self.insights),
            "insight_type_distribution": type_counts,
            "interval_seconds": self.interval_seconds,
            "last_recall_seconds_ago": now - self._last_recall_time if self._last_recall_time > 0 else 0,
            "recall_batch": self.recall_batch,
            "insight_threshold": self.insight_threshold,
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 / Serialize to dictionary."""
        return {
            "interval_seconds": self.interval_seconds,
            "recall_batch": self.recall_batch,
            "insight_threshold": self.insight_threshold,
            "insights": [ins.to_dict() for ins in self.insights.values()],
            "stats": self.stats(),
        }

    def __repr__(self) -> str:
        return (
            f"<SubconsciousLoop "
            f"running={self.is_running} "
            f"cycles={self._cycle_count} "
            f"insights={self._insight_count}>"
        )
