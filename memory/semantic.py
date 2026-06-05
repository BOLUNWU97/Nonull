"""
语义记忆模块 / Semantic Memory Module (领域知识 / Domain Knowledge)

管理自动驾驶领域知识库：安全标准、技术栈、最佳实践等。
Manages the autonomous driving knowledge base: safety standards, tech stack, best practices.

设计要点 / Design Highlights:
    - 向量存储集成 / Vector store for semantic search
    - 结构化知识图 / Structured knowledge graph (nodes + relations)
    - 安全标准索引 / Safety standards indexing (ISO 26262, ASPICE)
    - 技术栈知识 / Tech stack knowledge (ROS, Autoware, Apollo, CARLA)
    - 最佳实践模式 / Best practices and design patterns
    - 知识版本追踪 / Knowledge version tracking
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .episodic import EmbeddingProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 枚举与常量 / Enums & Constants
# ---------------------------------------------------------------------------

class KnowledgeDomain(Enum):
    """知识域枚举 / Knowledge domain categories."""
    SAFETY = "safety"                           # 功能安全 / Functional safety
    TECH_STACK = "tech_stack"                   # 技术栈 / Technology stack
    BEST_PRACTICE = "best_practice"             # 最佳实践 / Best practices
    ARCHITECTURE = "architecture"               # 架构设计 / Architecture
    ALGORITHM = "algorithm"                     # 算法 / Algorithms
    PROTOCOL = "protocol"                       # 协议 / Communication protocols
    SENSOR = "sensor"                           # 传感器 / Sensor technology
    CONTROL = "control"                         # 控制 / Vehicle control
    PERCEPTION = "perception"                   # 感知 / Perception
    PLANNING = "planning"                       # 规划 / Motion planning
    STANDARD = "standard"                       # 标准 / Industry standards
    TOOL = "tool"                               # 工具 / Development tools
    GENERAL = "general"                         # 通用 / General


class RelationType(Enum):
    """知识图谱关系类型 / Knowledge graph relation types."""
    IS_A = "is_a"                               # 是一种 / Is a type of
    PART_OF = "part_of"                         # 是...的一部分 / Is part of
    REQUIRES = "requires"                       # 需要 / Requires
    RELATED_TO = "related_to"                   # 与...相关 / Related to
    PREREQUISITE = "prerequisite"               # 前置条件 / Prerequisite
    CONFLICTS_WITH = "conflicts_with"           # 与...冲突 / Conflicts with
    RECOMMENDS = "recommends"                   # 推荐 / Recommends
    STANDARDIZES = "standardizes"               # 标准化 / Standardizes
    IMPLEMENTS = "implements"                   # 实现 / Implements


@dataclass
class KnowledgeNode:
    """知识图谱节点 / A node in the knowledge graph.

    Attributes:
        node_id:      唯一标识符 / Unique identifier
        title:        标题 / Title
        content:      内容 / Content body
        domain:       知识域 / Knowledge domain
        tags:         标签 / Tags
        source:       来源 / Source (e.g., "ISO 26262", "ROS Wiki")
        confidence:   置信度 (0~1) / Confidence score
        version:      版本 / Version
        created_at:   创建时间 / Creation timestamp
        updated_at:   更新时间 / Last update timestamp
        access_count: 访问次数 / Access count
        embedding:    嵌入向量缓存 / Cached embedding
        metadata:     附加元数据 / Additional metadata
        relations:    关系列表（出边）/ Outgoing relations
    """
    title: str
    content: str
    domain: KnowledgeDomain = KnowledgeDomain.GENERAL
    tags: List[str] = field(default_factory=list)
    source: str = ""
    confidence: float = 0.8
    version: str = "1.0"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    relations: List[Tuple[str, RelationType, str]] = field(default_factory=list)
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def add_relation(self, target_id: str, rel_type: RelationType, label: str = "") -> None:
        """添加关系 / Add a relation to another node.

        Args:
            target_id: 目标节点 ID / Target node ID
            rel_type:  关系类型 / Relation type
            label:     关系标签 / Relation label
        """
        self.relations.append((target_id, rel_type, label))

    def get_preview(self, max_length: int = 150) -> str:
        """获取内容预览 / Get content preview."""
        if len(self.content) <= max_length:
            return self.content
        return self.content[:max_length] + "..."

    def __repr__(self) -> str:
        return f"<KnowledgeNode '{self.title}' [{self.domain.value}] conf={self.confidence}>"


# ---------------------------------------------------------------------------
# 语义记忆主类 / Semantic Memory
# ---------------------------------------------------------------------------

class SemanticMemory:
    """语义记忆 — 领域知识库 / Semantic memory for domain knowledge.

    集成向量检索与知识图谱，管理自动驾驶相关知识。
    Integrates vector search and knowledge graph for AD knowledge.

    Attributes:
        name:         记忆名称 / Memory name
        nodes:        知识节点（node_id -> KnowledgeNode）/ Knowledge nodes
        embedder:     嵌入提供者 / Embedding provider
        domains:      知识域分类 / Domain categories
        auto_index:   自动索引更新 / Auto-index on add
    """

    # 预置的自动驾驶知识种子 / Built-in AD knowledge seeds
    DEFAULT_KNOWLEDGE: List[Dict[str, Any]] = [
        {
            "title": "ISO 26262 功能安全标准",
            "content": (
                "ISO 26262 is an international standard for functional safety of "
                "electrical and/or electronic systems in production automobiles. "
                "It defines ASIL (Automotive Safety Integrity Levels) A, B, C, D "
                "for risk classification. Key concepts: hazard analysis (HAZOP), "
                "safety goals, functional safety concept, technical safety concept, "
                "and safety validation. For autonomous driving, ASIL D is typical "
                "for critical functions like perception and decision-making."
            ),
            "domain": KnowledgeDomain.SAFETY,
            "tags": ["ISO 26262", "functional safety", "ASIL", "automotive"],
            "source": "ISO 26262:2018",
            "confidence": 0.95,
        },
        {
            "title": "ASPICE 软件过程改进",
            "content": (
                "ASPICE (Automotive SPICE) is a standardized framework for assessing "
                "software development processes in the automotive industry. It defines "
                "capability levels from 0 (incomplete) to 5 (innovating). Key process "
                "areas relevant to autonomous driving: SWE.1 (software requirements), "
                "SWE.2 (software design), SWE.3 (software integration), SWE.4 (software "
                "testing), and SYS.5 (system qualification testing)."
            ),
            "domain": KnowledgeDomain.STANDARD,
            "tags": ["ASPICE", "SPICE", "automotive", "software process"],
            "source": "VDA ASPICE PAM 3.1",
            "confidence": 0.90,
        },
        {
            "title": "ROS 2 (Robot Operating System)",
            "content": (
                "ROS 2 is the next-generation robot operating system used extensively "
                "in autonomous driving research and development. Key features: DDS-based "
                "communication, node/pub-sub architecture, lifecycle management, "
                "parameter server, and launch system. For AD: use ros2_canopen for "
                "vehicle interface, nav2 for navigation, and perception packages. "
                "Key AD-related packages: Autoware.Auto, CARLA ROS2 bridge."
            ),
            "domain": KnowledgeDomain.TECH_STACK,
            "tags": ["ROS 2", "DDS", "middleware", "robotics"],
            "source": "ROS 2 Documentation",
            "confidence": 0.90,
        },
        {
            "title": "Autoware 自动驾驶框架",
            "content": (
                "Autoware is the world's leading open-source software for autonomous "
                "driving. Based on ROS 2, it provides modules for sensing, localization, "
                "perception, planning, and control. Autoware.Auto is the ROS 2 version. "
                "Key modules: LiDAR-based localization, object detection (vision + LiDAR), "
                "occupancy grid mapping, behavior planning, motion planning (MPC, lattice), "
                "and vehicle control (PID, LQR, MPC)."
            ),
            "domain": KnowledgeDomain.TECH_STACK,
            "tags": ["Autoware", "open-source", "autonomous driving"],
            "source": "Autoware Foundation",
            "confidence": 0.85,
        },
        {
            "title": "Apollo 百度自动驾驶平台",
            "content": (
                "Apollo is Baidu's open autonomous driving platform. It provides a "
                "full-stack solution including HD mapping, localization, perception, "
                "prediction, planning, and control. Key modules: Apollo Cyber RT (real-time "
                "framework), HD Map engine, 3D obstacle perception, V2X-based traffic "
                "light detection, and Open Space Planner for complex maneuvers."
            ),
            "domain": KnowledgeDomain.TECH_STACK,
            "tags": ["Apollo", "Baidu", "Cyber RT", "HD Map"],
            "source": "Apollo Developer Documentation",
            "confidence": 0.85,
        },
        {
            "title": "CARLA 模拟器",
            "content": (
                "CARLA (Car Learning to Act) is an open-source simulator for autonomous "
                "driving research. Built on Unreal Engine 4, it provides realistic urban "
                "environments, sensor simulation (LiDAR, camera, radar, GPS/IMU), "
                "traffic management, and a Python API for agent control. Key features: "
                "scenario runner for testing, dynamic weather, pedestrian simulation, "
                "and ROS 2 bridge integration."
            ),
            "domain": KnowledgeDomain.TOOL,
            "tags": ["CARLA", "simulation", "Unreal Engine", "sensor simulation"],
            "source": "CARLA Documentation",
            "confidence": 0.90,
        },
        {
            "title": "传感器融合架构",
            "content": (
                "Autonomous driving systems typically use a multi-sensor fusion architecture: "
                "Cameras for semantic understanding (lane detection, traffic signs, objects), "
                "LiDAR for 3D geometry and depth, Radar for velocity and all-weather detection, "
                "Ultrasonic for close-range parking, GNSS+IMU for localization. "
                "Sensor fusion levels: early fusion (raw data), feature-level fusion, "
                "and late fusion (object-level). Kalman filters and factor graphs are "
                "common fusion algorithms."
            ),
            "domain": KnowledgeDomain.ARCHITECTURE,
            "tags": ["sensor fusion", "LiDAR", "camera", "radar", "Kalman filter"],
            "source": "Autonomous Driving Sensors Survey",
            "confidence": 0.85,
        },
        {
            "title": "行为规划与运动规划",
            "content": (
                "Behavior planning determines high-level driving behaviors (lane follow, "
                "lane change, intersection handling). Motion planning computes feasible "
                "trajectories. Key approaches: Finite State Machines (FSM) for behavior, "
                "MPC (Model Predictive Control) for trajectory optimization, lattice "
                "planners for path generation, and RRT* for sampling-based planning. "
                "Safety-critical: ensure trajectories satisfy kinematic constraints, "
                "collision avoidance, and comfort metrics (jerk < 2 m/s^3)."
            ),
            "domain": KnowledgeDomain.PLANNING,
            "tags": ["motion planning", "behavior planning", "MPC", "trajectory"],
            "source": "Planning in Autonomous Driving",
            "confidence": 0.85,
        },
    ]

    def __init__(
        self,
        name: str = "default",
        embedder: Optional[EmbeddingProvider] = None,
        auto_index: bool = True,
        enable_default_knowledge: bool = True,
    ):
        self.name = name
        self.embedder = embedder or EmbeddingProvider(dim=256)
        self.auto_index = auto_index
        self.nodes: Dict[str, KnowledgeNode] = {}
        self._domain_index: Dict[str, List[str]] = defaultdict(list)
        self._tag_index: Dict[str, List[str]] = defaultdict(list)
        self._source_index: Dict[str, List[str]] = defaultdict(list)
        self._node_count = 0

        if enable_default_knowledge:
            self._load_default_knowledge()

    # ------------------------------------------------------------------
    # 知识存储 / Knowledge Storage
    # ------------------------------------------------------------------

    def add_knowledge(
        self,
        title: str,
        content: str,
        domain: KnowledgeDomain = KnowledgeDomain.GENERAL,
        tags: Optional[List[str]] = None,
        source: str = "",
        confidence: float = 0.8,
        version: str = "1.0",
        metadata: Optional[Dict[str, Any]] = None,
        relations: Optional[List[Tuple[str, RelationType, str]]] = None,
    ) -> KnowledgeNode:
        """添加一条知识 / Add a knowledge entry.

        Args:
            title:      标题 / Title
            content:    内容 / Content
            domain:     知识域 / Knowledge domain
            tags:       标签 / Tags
            source:     来源 / Source
            confidence: 置信度 (0~1) / Confidence
            version:    版本 / Version
            metadata:   附加元数据 / Additional metadata
            relations:  关系列表 / Relations

        Returns:
            创建的知识节点 / Created knowledge node
        """
        node = KnowledgeNode(
            title=title,
            content=content,
            domain=domain,
            tags=tags or [],
            source=source,
            confidence=max(0.0, min(1.0, confidence)),
            version=version,
            metadata=metadata or {},
            relations=relations or [],
            embedding=self.embedder.encode(f"{title}\n{content}"),
        )

        self.nodes[node.node_id] = node
        self._node_count += 1

        # 更新索引 / Update indices
        self._domain_index[domain.value].append(node.node_id)
        for tag in node.tags:
            self._tag_index[tag].append(node.node_id)
        if node.source:
            self._source_index[node.source].append(node.node_id)

        logger.debug(
            "Added knowledge: '%s' domain=%s confidence=%.2f",
            title, domain.value, confidence,
        )
        return node

    def update_knowledge(self, node_id: str, **updates) -> bool:
        """更新已有知识 / Update an existing knowledge node.

        Args:
            node_id: 节点 ID / Node ID
            **updates: 要更新的字段 / Fields to update

        Returns:
            True 如果成功 / True if successful
        """
        node = self.nodes.get(node_id)
        if node is None:
            return False

        for key, value in updates.items():
            if hasattr(node, key) and key not in ("node_id", "created_at", "embedding"):
                setattr(node, key, value)

        node.updated_at = time.time()
        if "title" in updates or "content" in updates:
            node.embedding = self.embedder.encode(f"{node.title}\n{node.content}")

        logger.info("Updated knowledge node %s", node_id[:8])
        return True

    def remove_knowledge(self, node_id: str) -> bool:
        """删除知识节点 / Remove a knowledge node.

        Args:
            node_id: 节点 ID / Node ID

        Returns:
            True 如果成功 / True if successful
        """
        node = self.nodes.pop(node_id, None)
        if node is None:
            return False

        # 从索引移除 / Remove from indices
        if node.domain.value in self._domain_index:
            try:
                self._domain_index[node.domain.value].remove(node_id)
            except ValueError:
                pass
        for tag in node.tags:
            if tag in self._tag_index:
                try:
                    self._tag_index[tag].remove(node_id)
                except ValueError:
                    pass
        if node.source in self._source_index:
            try:
                self._source_index[node.source].remove(node_id)
            except ValueError:
                pass

        self._node_count -= 1
        logger.info("Removed knowledge node %s", node_id[:8])
        return True

    # ------------------------------------------------------------------
    # 知识检索 / Knowledge Retrieval
    # ------------------------------------------------------------------

    def query(
        self,
        query: str,
        top_k: int = 10,
        domain: Optional[KnowledgeDomain] = None,
        threshold: float = 0.2,
    ) -> List[Tuple[KnowledgeNode, float]]:
        """语义搜索知识库 / Semantic search over the knowledge base.

        Args:
            query:     查询文本 / Query text
            top_k:     返回结果数 / Number of results
            domain:    限制知识域 / Filter by domain
            threshold: 相似度阈值 / Similarity threshold

        Returns:
            (节点, 相关性分数) 列表 / List of (node, relevance score)
        """
        query_vec = self.embedder.encode(query)

        # 确定候选集 / Determine candidate set
        if domain:
            candidate_ids = self._domain_index.get(domain.value, [])
        else:
            candidate_ids = list(self.nodes.keys())

        # 计算相似度 / Compute similarities
        scored: List[Tuple[float, KnowledgeNode]] = []
        for nid in candidate_ids:
            node = self.nodes.get(nid)
            if node is None:
                continue
            if node.embedding is None:
                node.embedding = self.embedder.encode(f"{node.title}\n{node.content}")

            sim = float(np.dot(query_vec, node.embedding))
            combined = sim * node.confidence
            if combined >= threshold:
                scored.append((combined, node))

        # 排序 / Sort
        scored.sort(key=lambda x: x[0], reverse=True)

        results = scored[:top_k]
        for _, node in results:
            node.access_count += 1

        return results

    def get_by_domain(self, domain: KnowledgeDomain) -> List[KnowledgeNode]:
        """按知识域获取 / Get all nodes in a domain.

        Args:
            domain: 知识域 / Knowledge domain

        Returns:
            节点列表 / List of nodes
        """
        return [
            self.nodes[nid] for nid in self._domain_index.get(domain.value, [])
            if nid in self.nodes
        ]

    def get_by_tag(self, tag: str) -> List[KnowledgeNode]:
        """按标签获取 / Get all nodes with a given tag.

        Args:
            tag: 标签 / Tag

        Returns:
            节点列表 / List of nodes
        """
        return [
            self.nodes[nid] for nid in self._tag_index.get(tag, [])
            if nid in self.nodes
        ]

    def get_by_source(self, source: str) -> List[KnowledgeNode]:
        """按来源获取 / Get all nodes from a given source.

        Args:
            source: 来源名称 / Source name

        Returns:
            节点列表 / List of nodes
        """
        return [
            self.nodes[nid] for nid in self._source_index.get(source, [])
            if nid in self.nodes
        ]

    def get_related(self, node_id: str, max_depth: int = 1) -> List[KnowledgeNode]:
        """获取相关节点（通过关系图）/ Get related nodes via relation graph.

        Args:
            node_id:   起始节点 ID / Start node ID
            max_depth: 最大遍历深度 / Max traversal depth

        Returns:
            相关节点列表 / Related nodes
        """
        node = self.nodes.get(node_id)
        if node is None:
            return []

        visited = {node_id}
        results = []
        queue = [(node_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            current = self.nodes.get(current_id)
            if current is None:
                continue

            for target_id, rel_type, _ in current.relations:
                if target_id not in visited and target_id in self.nodes:
                    visited.add(target_id)
                    results.append(self.nodes[target_id])
                    queue.append((target_id, depth + 1))

        return results

    # ------------------------------------------------------------------
    # 内部方法 / Internal Methods
    # ------------------------------------------------------------------

    def _load_default_knowledge(self) -> None:
        """加载预置的自动驾驶领域知识 / Load built-in AD domain knowledge."""
        for item in self.DEFAULT_KNOWLEDGE:
            self.add_knowledge(
                title=item["title"],
                content=item["content"],
                domain=item["domain"],
                tags=item["tags"],
                source=item["source"],
                confidence=item["confidence"],
            )
        logger.info(
            "Loaded %d default knowledge entries into '%s'",
            len(self.DEFAULT_KNOWLEDGE), self.name,
        )

    # ------------------------------------------------------------------
    # 统计与序列化 / Stats & Serialization
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """获取知识库统计 / Get knowledge base statistics."""
        domain_counts = defaultdict(int)
        total_confidence = 0.0
        for node in self.nodes.values():
            domain_counts[node.domain.value] += 1
            total_confidence += node.confidence

        return {
            "name": self.name,
            "total_nodes": self._node_count,
            "domain_distribution": dict(domain_counts),
            "avg_confidence": total_confidence / self._node_count if self._node_count > 0 else 0,
            "source_count": len(self._source_index),
            "tag_count": len(self._tag_index),
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 / Serialize to dictionary."""
        nodes_dict = {}
        for nid, node in self.nodes.items():
            nodes_dict[nid] = {
                "node_id": node.node_id,
                "title": node.title,
                "content": node.content,
                "domain": node.domain.value,
                "tags": node.tags,
                "source": node.source,
                "confidence": node.confidence,
                "version": node.version,
                "created_at": node.created_at,
                "updated_at": node.updated_at,
                "access_count": node.access_count,
                "metadata": node.metadata,
                "relations": [
                    {"target_id": r[0], "rel_type": r[1].value, "label": r[2]}
                    for r in node.relations
                ],
            }

        return {
            "name": self.name,
            "nodes": nodes_dict,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        embedder: Optional[EmbeddingProvider] = None,
    ) -> "SemanticMemory":
        """从字典反序列化 / Deserialize from dictionary."""
        sm = cls(
            name=data.get("name", "default"),
            embedder=embedder,
            auto_index=False,
            enable_default_knowledge=False,
        )
        for nid, node_data in data.get("nodes", {}).items():
            relations = [
                (r["target_id"], RelationType(r["rel_type"]), r.get("label", ""))
                for r in node_data.get("relations", [])
            ]
            node = KnowledgeNode(
                node_id=node_data.get("node_id", nid),
                title=node_data["title"],
                content=node_data["content"],
                domain=KnowledgeDomain(node_data.get("domain", "general")),
                tags=node_data.get("tags", []),
                source=node_data.get("source", ""),
                confidence=node_data.get("confidence", 0.8),
                version=node_data.get("version", "1.0"),
                created_at=node_data.get("created_at", time.time()),
                updated_at=node_data.get("updated_at", time.time()),
                access_count=node_data.get("access_count", 0),
                metadata=node_data.get("metadata", {}),
                relations=relations,
            )
            node.embedding = sm.embedder.encode(f"{node.title}\n{node.content}")
            sm.nodes[nid] = node
            sm._node_count += 1

            # Rebuild indices
            sm._domain_index[node.domain.value].append(nid)
            for tag in node.tags:
                sm._tag_index[tag].append(nid)
            if node.source:
                sm._source_index[node.source].append(nid)

        return sm

    def __repr__(self) -> str:
        return (
            f"<SemanticMemory '{self.name}' "
            f"nodes={self._node_count} "
            f"domains={len(self._domain_index)}>"
        )
