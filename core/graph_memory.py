"""
Knowledge Graph Memory — 知识图谱记忆 (Mem0-lite)

Lightweight in-memory knowledge graph for storing entities and relationships
alongside the existing Neocortex vector memory. Enables multi-hop relational
queries like "what components connect to sensor X?"

Inspired by Mem0's graph memory pattern and Zep/Graphiti temporal graphs.

@module: core.graph_memory
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("Nonull.graph_memory")


@dataclass
class Entity:
    """
    A node in the knowledge graph. / 知识图谱中的节点。
    """
    entity_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    name: str = ""
    entity_type: str = "unknown"
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __hash__(self):
        return hash(self.entity_id)

    def __eq__(self, other):
        if isinstance(other, Entity):
            return self.entity_id == other.entity_id
        return False


@dataclass
class Relation:
    """
    An edge in the knowledge graph. / 知识图谱中的边。
    """
    relation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    source_id: str = ""
    relation_type: str = ""
    target_id: str = ""
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Triple:
    """
    A subject-predicate-object triple. / 主谓宾三元组。
    """
    subject: str
    predicate: str
    obj: str
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphQuery:
    """Result of a graph query. / 图查询结果。"""
    entities: List[Entity] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)
    paths: List[List[str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "paths": self.paths,
        }


class KnowledgeGraph:
    """
    In-memory knowledge graph with entity and relation management.
    内存知识图谱，支持实体和关系管理。

    Features:
    - Add/remove entities and relations
    - Query neighbors (1-hop and multi-hop)
    - Find paths between entities
    - Extract triples from text (via callback)
    - Decay old unused nodes
    - Export/import JSON
    """

    def __init__(self, max_entities: int = 10000):
        self._entities: Dict[str, Entity] = {}
        self._relations: List[Relation] = []
        self._adjacency: Dict[str, List[Relation]] = defaultdict(list)
        self._reverse_adj: Dict[str, List[Relation]] = defaultdict(list)
        self._name_index: Dict[str, str] = {}
        self._max_entities = max_entities

    # ── Entity Operations ────────────────────────────────────────

    def add_entity(self, name: str, entity_type: str = "unknown",
                   properties: Optional[Dict[str, Any]] = None) -> Entity:
        """Add or update an entity. / 添加或更新实体。"""
        existing_id = self._name_index.get(name.lower())
        if existing_id and existing_id in self._entities:
            entity = self._entities[existing_id]
            entity.updated_at = time.time()
            if properties:
                entity.properties.update(properties)
            return entity

        entity = Entity(
            name=name,
            entity_type=entity_type,
            properties=properties or {},
        )
        self._entities[entity.entity_id] = entity
        self._name_index[name.lower()] = entity.entity_id

        if len(self._entities) > self._max_entities:
            self._evict_oldest()

        return entity

    def get_entity(self, name_or_id: str) -> Optional[Entity]:
        """Get entity by name or ID. / 按名称或 ID 获取实体。"""
        if name_or_id in self._entities:
            entity = self._entities[name_or_id]
            entity.access_count += 1
            return entity
        entity_id = self._name_index.get(name_or_id.lower())
        if entity_id and entity_id in self._entities:
            entity = self._entities[entity_id]
            entity.access_count += 1
            return entity
        return None

    def remove_entity(self, name_or_id: str) -> bool:
        """Remove an entity and its relations. / 删除实体及其关系。"""
        entity = self.get_entity(name_or_id)
        if entity is None:
            return False
        eid = entity.entity_id
        self._entities.pop(eid, None)
        self._name_index.pop(entity.name.lower(), None)
        self._relations = [r for r in self._relations if r.source_id != eid and r.target_id != eid]
        self._adjacency.pop(eid, None)
        self._reverse_adj.pop(eid, None)
        for adj_list in self._adjacency.values():
            adj_list[:] = [r for r in adj_list if r.target_id != eid]
        for adj_list in self._reverse_adj.values():
            adj_list[:] = [r for r in adj_list if r.source_id != eid]
        return True

    # ── Relation Operations ──────────────────────────────────────

    def add_relation(self, source: str, relation_type: str, target: str,
                     weight: float = 1.0, properties: Optional[Dict[str, Any]] = None) -> Relation:
        """
        Add a relation between two entities (creates entities if needed).
        添加两个实体之间的关系（如果不存在则创建实体）。
        """
        src_entity = self.get_entity(source) or self.add_entity(source)
        tgt_entity = self.get_entity(target) or self.add_entity(target)

        relation = Relation(
            source_id=src_entity.entity_id,
            relation_type=relation_type,
            target_id=tgt_entity.entity_id,
            weight=weight,
            properties=properties or {},
        )
        self._relations.append(relation)
        self._adjacency[src_entity.entity_id].append(relation)
        self._reverse_adj[tgt_entity.entity_id].append(relation)
        return relation

    def add_triple(self, triple: Triple) -> Relation:
        """Add a subject-predicate-object triple. / 添加主谓宾三元组。"""
        return self.add_relation(
            triple.subject, triple.predicate, triple.obj,
            weight=triple.weight, properties=triple.metadata,
        )

    # ── Query Operations ─────────────────────────────────────────

    def neighbors(self, name_or_id: str, hops: int = 1, direction: str = "both") -> GraphQuery:
        """
        Find neighbor entities within N hops.
        查找 N 跳范围内的邻居实体。
        """
        entity = self.get_entity(name_or_id)
        if entity is None:
            return GraphQuery()

        visited: Set[str] = {entity.entity_id}
        current_layer = {entity.entity_id}
        all_entities = [entity]
        all_relations: List[Relation] = []

        for _ in range(hops):
            next_layer: Set[str] = set()
            for eid in current_layer:
                if direction in ("out", "both"):
                    for rel in self._adjacency.get(eid, []):
                        if rel.target_id not in visited:
                            visited.add(rel.target_id)
                            next_layer.add(rel.target_id)
                            all_relations.append(rel)
                            target = self._entities.get(rel.target_id)
                            if target:
                                all_entities.append(target)
                if direction in ("in", "both"):
                    for rel in self._reverse_adj.get(eid, []):
                        if rel.source_id not in visited:
                            visited.add(rel.source_id)
                            next_layer.add(rel.source_id)
                            all_relations.append(rel)
                            source = self._entities.get(rel.source_id)
                            if source:
                                all_entities.append(source)
            current_layer = next_layer

        return GraphQuery(entities=all_entities, relations=all_relations)

    def find_path(self, source: str, target: str, max_depth: int = 5) -> Optional[List[str]]:
        """
        Find shortest path between two entities (BFS).
        查找两个实体之间的最短路径 (BFS)。
        """
        src = self.get_entity(source)
        tgt = self.get_entity(target)
        if src is None or tgt is None:
            return None

        from collections import deque
        queue = deque([(src.entity_id, [src.name], 0)])
        visited = {src.entity_id}

        while queue:
            current_id, path, hops = queue.popleft()
            if hops > max_depth:
                continue
            if current_id == tgt.entity_id:
                return path
            for rel in self._adjacency.get(current_id, []):
                if rel.target_id not in visited:
                    visited.add(rel.target_id)
                    target_entity = self._entities.get(rel.target_id)
                    if target_entity:
                        queue.append((rel.target_id, path + [f"--{rel.relation_type}-->", target_entity.name], hops + 1))

        return None

    def search(self, query: str, entity_type: Optional[str] = None, limit: int = 10) -> List[Entity]:
        """
        Simple text search over entity names and properties.
        对实体名称和属性进行简单文本搜索。
        """
        q = query.lower()
        results = []
        for entity in self._entities.values():
            if entity_type and entity.entity_type != entity_type:
                continue
            if q in entity.name.lower():
                results.append(entity)
                continue
            for val in entity.properties.values():
                if q in str(val).lower():
                    results.append(entity)
                    break
        results.sort(key=lambda e: e.access_count, reverse=True)
        return results[:limit]

    def get_relations_for(self, name_or_id: str) -> List[Dict[str, str]]:
        """Get all relations involving an entity in human-readable form. / 获取实体相关关系。"""
        entity = self.get_entity(name_or_id)
        if entity is None:
            return []
        eid = entity.entity_id
        result = []
        for rel in self._adjacency.get(eid, []):
            target = self._entities.get(rel.target_id)
            if target:
                result.append({
                    "subject": entity.name,
                    "predicate": rel.relation_type,
                    "object": target.name,
                })
        for rel in self._reverse_adj.get(eid, []):
            source = self._entities.get(rel.source_id)
            if source:
                result.append({
                    "subject": source.name,
                    "predicate": rel.relation_type,
                    "object": entity.name,
                })
        return result

    # ── Maintenance ──────────────────────────────────────────────

    def _evict_oldest(self) -> None:
        """Remove least recently accessed entities. / 移除最少访问的实体。"""
        if len(self._entities) <= self._max_entities:
            return
        sorted_entities = sorted(self._entities.values(), key=lambda e: (e.access_count, e.updated_at))
        to_remove = len(self._entities) - self._max_entities
        for entity in sorted_entities[:to_remove]:
            self.remove_entity(entity.entity_id)

    def decay(self, max_age_seconds: float = 86400 * 30, min_access: int = 0) -> int:
        """
        Remove old, unused entities (Ebbinghaus-inspired).
        移除旧的、未使用的实体（受艾宾浩斯启发）。
        """
        cutoff = time.time() - max_age_seconds
        to_remove = [
            eid for eid, entity in self._entities.items()
            if entity.updated_at < cutoff and entity.access_count <= min_access
        ]
        for eid in to_remove:
            self.remove_entity(eid)
        if to_remove:
            logger.info("Graph decay: removed %d stale entities", len(to_remove))
        return len(to_remove)

    # ── Stats / Export ───────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Get graph statistics. / 获取图统计。"""
        type_counts: Dict[str, int] = defaultdict(int)
        for entity in self._entities.values():
            type_counts[entity.entity_type] += 1
        rel_type_counts: Dict[str, int] = defaultdict(int)
        for rel in self._relations:
            rel_type_counts[rel.relation_type] += 1
        return {
            "entities": len(self._entities),
            "relations": len(self._relations),
            "entity_types": dict(type_counts),
            "relation_types": dict(rel_type_counts),
        }

    def export_json(self, filepath: Optional[str] = None) -> str:
        """Export graph to JSON. / 导出图到 JSON。"""
        json_str = json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str)
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_str)
        return json_str

    @classmethod
    def from_json(cls, json_str: str) -> "KnowledgeGraph":
        """Load graph from JSON. / 从 JSON 加载图。"""
        return cls.from_dict(json.loads(json_str))

    # ── 持久化 / Persistence ─────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 / Serialize to a dict (entities + relations + config)."""
        return {
            "max_entities": self._max_entities,
            "entities": [e.to_dict() for e in self._entities.values()],
            "relations": [r.to_dict() for r in self._relations],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeGraph":
        """从字典重建 / Rebuild from a dict produced by to_dict().

        索引（adjacency/name_index）在加载时重建，max_entities 被保留。
        Indexes are rebuilt on load; max_entities is preserved.
        """
        graph = cls(max_entities=data.get("max_entities", 10000))
        for e_data in data.get("entities", []):
            entity = Entity(**{k: v for k, v in e_data.items() if k in Entity.__dataclass_fields__})
            graph._entities[entity.entity_id] = entity
            graph._name_index[entity.name.lower()] = entity.entity_id
        for r_data in data.get("relations", []):
            rel = Relation(**{k: v for k, v in r_data.items() if k in Relation.__dataclass_fields__})
            graph._relations.append(rel)
            graph._adjacency[rel.source_id].append(rel)
            graph._reverse_adj[rel.target_id].append(rel)
        return graph

    def save(self, path: str) -> None:
        """原子化保存到 JSON 文件 / Atomically save to a JSON file."""
        from .persistence import atomic_write_json, wrap_payload
        atomic_write_json(path, wrap_payload("knowledge_graph", self.to_dict()))
        logger.info("KnowledgeGraph saved to %s (%d entities)", path, len(self._entities))

    @classmethod
    def load(cls, path: str) -> "KnowledgeGraph":
        """从 JSON 文件加载 / Load from a JSON file."""
        from .persistence import read_json, unwrap_payload
        data = unwrap_payload(read_json(path), "knowledge_graph")
        graph = cls.from_dict(data)
        logger.info("KnowledgeGraph loaded from %s (%d entities)", path, len(graph._entities))
        return graph

    def __len__(self) -> int:
        return len(self._entities)

    def __repr__(self) -> str:
        return f"KnowledgeGraph(entities={len(self._entities)}, relations={len(self._relations)})"
