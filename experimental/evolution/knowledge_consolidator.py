"""
Knowledge Consolidator — 知识整合引擎
=========================================

将经验转化为结构化知识。从具体经验中提取通用原则，将工作记忆整合到语义记忆，
从学习到的模式生成文档，并交叉引用新旧知识。

Turns experiences into structured knowledge. Extracts general principles from
specific experiences, consolidates working memory into semantic memory, generates
documentation from learned patterns, and cross-references new knowledge with
existing knowledge.

Typical usage::

    consolidator = KnowledgeConsolidator()
    items = consolidator.consolidate(experiences)
    rule = consolidator.generate_rule(pattern)
    consolidator.update_knowledge_graph(items)
    docs = consolidator.create_documentation(patterns)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Types
# ---------------------------------------------------------------------------

class KnowledgeType(Enum):
    """知识类型 / Knowledge types."""
    PRINCIPLE = "principle"           # 通用原则 / General principle
    BEST_PRACTICE = "best_practice"   # 最佳实践 / Best practice
    SAFETY_RULE = "safety_rule"       # 安全规则 / Safety rule
    WORKFLOW = "workflow"             # 工作流 / Workflow
    HEURISTIC = "heuristic"           # 启发式规则 / Heuristic
    INSIGHT = "insight"               # 洞察 / Insight
    PATTERN = "pattern"               # 模式 / Pattern
    DOCUMENTATION = "documentation"   # 文档 / Documentation


class MemorySource(Enum):
    """记忆来源 / Memory source types."""
    EPISODIC = "episodic"       # 情景记忆 / Episodic memory
    SEMANTIC = "semantic"       # 语义记忆 / Semantic memory
    PROCEDURAL = "procedural"   # 程序记忆 / Procedural memory


@dataclass
class KnowledgeItem:
    """知识项 / A consolidated knowledge item."""
    knowledge_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    content: str = ""
    summary: str = ""
    knowledge_type: KnowledgeType = KnowledgeType.PRINCIPLE
    confidence: float = 0.0
    source_memory: MemorySource = MemorySource.SEMANTIC

    # 来源 / Provenance
    source_experiences: List[str] = field(default_factory=list)
    source_patterns: List[str] = field(default_factory=list)

    # 分类 / Classification
    category: str = ""
    tags: List[str] = field(default_factory=list)
    related_knowledge_ids: List[str] = field(default_factory=list)
    related_skills: List[str] = field(default_factory=list)

    # 使用 / Usage
    access_count: int = 0
    last_accessed: Optional[float] = None

    # 元数据 / Metadata
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def record_access(self) -> None:
        self.access_count += 1
        self.last_accessed = time.time()

    def update(self, content: str, confidence: float) -> None:
        self.content = content
        self.confidence = confidence
        self.version += 1
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "content": self.content[:300],
            "summary": self.summary,
            "knowledge_type": self.knowledge_type.value,
            "confidence": round(self.confidence, 4),
            "source_memory": self.source_memory.value,
            "category": self.category,
            "tags": self.tags,
            "related_knowledge_ids": self.related_knowledge_ids,
            "related_skills": self.related_skills,
            "access_count": self.access_count,
            "version": self.version,
            "created_at": self.created_at,
        }


@dataclass
class Rule:
    """从模式生成的规则 / A rule generated from patterns."""
    rule_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    rule_type: str = "safety"  # safety | best_practice | workflow
    priority: int = 0  # 0=highest
    condition: str = ""
    action: str = ""
    source_patterns: List[str] = field(default_factory=list)
    confidence: float = 0.0
    enabled: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "rule_type": self.rule_type,
            "priority": self.priority,
            "condition": self.condition,
            "action": self.action,
            "confidence": round(self.confidence, 4),
            "enabled": self.enabled,
        }


@dataclass
class KnowledgeGraphNode:
    """知识图谱节点 / A node in the knowledge graph."""
    node_id: str = ""
    label: str = ""
    node_type: str = "knowledge"  # knowledge | skill | pattern | rule
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class KnowledgeGraphEdge:
    """知识图谱边 / An edge in the knowledge graph."""
    source_id: str = ""
    target_id: str = ""
    relation: str = ""  # derives_from | related_to | supports | conflicts_with
    weight: float = 1.0
    created_at: float = field(default_factory=time.time)


@dataclass
class KnowledgeGraph:
    """知识图谱 / Knowledge graph for cross-referencing."""
    nodes: Dict[str, KnowledgeGraphNode] = field(default_factory=dict)
    edges: List[KnowledgeGraphEdge] = field(default_factory=list)

    def add_node(
        self,
        node_id: str,
        label: str,
        node_type: str = "knowledge",
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.nodes[node_id] = KnowledgeGraphNode(
            node_id=node_id,
            label=label,
            node_type=node_type,
            properties=properties or {},
        )

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        weight: float = 1.0,
    ) -> None:
        self.edges.append(KnowledgeGraphEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            weight=weight,
        ))

    def find_related(
        self, node_id: str, max_depth: int = 2
    ) -> List[Tuple[str, str, float]]:
        """BFS 查找关联节点 / BFS find related nodes."""
        visited: Set[str] = {node_id}
        queue: List[Tuple[str, int]] = [(node_id, 0)]
        related: List[Tuple[str, str, float]] = []

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            for edge in self.edges:
                neighbor = None
                if edge.source_id == current and edge.target_id not in visited:
                    neighbor = edge.target_id
                elif edge.target_id == current and edge.source_id not in visited:
                    neighbor = edge.source_id

                if neighbor:
                    visited.add(neighbor)
                    node = self.nodes.get(neighbor)
                    label = node.label if node else neighbor
                    related.append((neighbor, label, edge.weight))
                    queue.append((neighbor, depth + 1))

        return related

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes_count": len(self.nodes),
            "edges_count": len(self.edges),
            "nodes": {k: v.label for k, v in self.nodes.items()},
        }


# ---------------------------------------------------------------------------
# Knowledge Consolidator
# ---------------------------------------------------------------------------

class KnowledgeConsolidator:
    """知识整合引擎 — 将经验和模式转化为结构化知识。

    Knowledge Consolidator — transforms experiences and patterns into structured knowledge.

    能力 / Capabilities:
    - 从具体经验中提取通用原则 / Extract general principles from specific experiences
    - 生成安全和最佳实践规则 / Generate safety and best-practice rules
    - 构建知识图谱进行交叉引用 / Build knowledge graph for cross-referencing
    - 从学习到的模式生成文档 / Generate documentation from learned patterns
    - 管理知识项的版本和置信度 / Version and confidence management
    """

    def __init__(self):
        # 知识库 / Knowledge base
        self._knowledge: Dict[str, KnowledgeItem] = {}

        # 规则 / Rules
        self._rules: Dict[str, Rule] = {}

        # 知识图谱 / Knowledge graph
        self.graph = KnowledgeGraph()

        # 分类统计 / Category statistics
        self._category_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "avg_confidence": 0.0, "items": []}
        )

        # 去重缓存 / Deduplication cache
        self._content_hash_index: Dict[str, str] = {}  # hash -> knowledge_id

        self.stats: Dict[str, Any] = {
            "total_knowledge_items": 0,
            "total_rules": 0,
            "graphs_nodes": 0,
            "graphs_edges": 0,
            "consolidation_runs": 0,
            "conflicts_detected": 0,
        }

        logger.info("KnowledgeConsolidator initialized | 知识整合引擎已初始化")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def consolidate(
        self, experiences: List[Dict[str, Any]]
    ) -> List[KnowledgeItem]:
        """将一组经验整合为知识项。

        Consolidate a batch of experiences into knowledge items.

        Args:
            experiences: 经验列表，每个包含 content, category, source, confidence 等
                         List of experiences with content, category, source, confidence

        Returns:
            生成的知识项列表 / List of generated knowledge items
        """
        if not experiences:
            return []

        logger.info(f"Consolidating {len(experiences)} experiences | 整合 {len(experiences)} 条经验")
        items: List[KnowledgeItem] = []

        # Step 1: 分类经验 / Categorize experiences
        categorized = self._categorize_experiences(experiences)

        # Step 2: 从每类中提取原则 / Extract principles from each category
        for category, group in categorized.items():
            if len(group) >= 2:
                principle = self._extract_principle(group, category)
                if principle:
                    items.append(principle)

        # Step 3: 提取洞察 / Extract insights
        for exp in experiences:
            if exp.get("confidence", 0) > 0.8:
                insight = self._create_knowledge_item(
                    content=exp.get("content", ""),
                    summary=f"High-confidence insight: {exp.get('content', '')[:80]}",
                    knowledge_type=KnowledgeType.INSIGHT,
                    confidence=exp.get("confidence", 0.8),
                    category=exp.get("category", "general"),
                    source_id=exp.get("source_id", ""),
                    tags=exp.get("tags", []),
                )
                if insight:
                    items.append(insight)

        # Step 4: 检测并解决冲突 / Detect and resolve conflicts
        conflicts = self._detect_conflicts(items)
        if conflicts:
            self.stats["conflicts_detected"] += len(conflicts)
            items = self._resolve_conflicts(items, conflicts)

        # Step 5: 合并到知识库 / Merge into knowledge base
        merged_items = []
        for item in items:
            merged = self._merge_with_existing(item)
            merged_items.append(merged)

        # Step 6: 更新知识图谱 / Update knowledge graph
        self._update_graph_from_items(merged_items)

        self.stats["consolidation_runs"] += 1
        self.stats["total_knowledge_items"] = len(self._knowledge)

        logger.info(
            f"Consolidated {len(merged_items)} knowledge items from {len(experiences)} experiences | "
            f"从 {len(experiences)} 条经验整合了 {len(merged_items)} 条知识"
        )
        return merged_items

    def generate_rule(self, pattern: Dict[str, Any]) -> Optional[Rule]:
        """从模式生成安全或最佳实践规则。

        Generate a safety or best-practice rule from a pattern.

        Args:
            pattern: 模式字典，包含 name, pattern_type, steps_sequence, outcome 等
                     Pattern dict with name, pattern_type, steps_sequence, outcome

        Returns:
            生成的规则 / Generated rule, or None if pattern not suitable
        """
        pattern_type = pattern.get("pattern_type", "")
        if pattern_type not in ("mistake", "best_practice", "workflow"):
            return None

        name = pattern.get("name", "unnamed_pattern")
        confidence = pattern.get("confidence", 0.5)
        outcome = pattern.get("outcome", "unknown")

        rule_type = "safety" if pattern_type == "mistake" else "best_practice"
        priority = 0 if outcome == "error" else 1

        # 构建条件-动作规则 / Build condition-action rule
        conditions = pattern.get("conditions", [])
        steps = pattern.get("steps_sequence", [])

        condition_str = "; ".join(conditions) if conditions else (
            f"当遇到类似 '{name}' 的场景时 | "
            f"When encountering scenarios similar to '{name}'"
        )

        action_str = (
            f"遵循 {len(steps)} 步最佳实践流程 | "
            f"Follow the {len(steps)}-step best practice workflow"
            if outcome == "success" else
            f"避免上述操作序列中的错误 | "
            f"Avoid the errors in the above action sequence"
        )

        rule = Rule(
            name=f"rule_{name}",
            description=pattern.get("description", ""),
            rule_type=rule_type,
            priority=priority,
            condition=condition_str,
            action=action_str,
            source_patterns=[pattern.get("pattern_id", "")],
            confidence=confidence,
        )

        self._rules[rule.rule_id] = rule
        self.stats["total_rules"] = len(self._rules)

        logger.info(
            f"Generated rule '{rule.name}' (type={rule_type}, confidence={confidence:.2f}) | "
            f"已生成规则 '{rule.name}'"
        )
        return rule

    def update_knowledge_graph(
        self, items: List[KnowledgeItem]
    ) -> None:
        """用新的知识项更新知识图谱。

        Update the knowledge graph with new knowledge items.

        Args:
            items: 知识项列表 / List of knowledge items to integrate
        """
        for item in items:
            # 添加节点 / Add node
            self.graph.add_node(
                node_id=item.knowledge_id,
                label=item.summary[:60] or item.content[:60],
                node_type="knowledge",
                properties={
                    "type": item.knowledge_type.value,
                    "category": item.category,
                    "confidence": item.confidence,
                },
            )

            # 关联到相似知识项 / Link to similar knowledge items
            for other_id, score in self._find_similar_items(item):
                if score > 0.5:
                    self.graph.add_edge(
                        source_id=item.knowledge_id,
                        target_id=other_id,
                        relation="related_to",
                        weight=score,
                    )

            # 关联到相关规则 / Link to related rules
            for rule in self._rules.values():
                if item.category in rule.description or any(
                    t in rule.description for t in item.tags
                ):
                    self.graph.add_edge(
                        source_id=item.knowledge_id,
                        target_id=rule.rule_id,
                        relation="supports",
                        weight=0.5,
                    )

        self.stats["graphs_nodes"] = len(self.graph.nodes)
        self.stats["graphs_edges"] = len(self.graph.edges)

        logger.info(
            f"Knowledge graph updated: {len(self.graph.nodes)} nodes, "
            f"{len(self.graph.edges)} edges | "
            f"知识图谱已更新: {len(self.graph.nodes)} 节点, {len(self.graph.edges)} 边"
        )

    def create_documentation(
        self, patterns: List[Dict[str, Any]]
    ) -> str:
        """从学习到的模式生成文档。

        Generate markdown documentation from learned patterns.

        Args:
            patterns: 模式列表 / List of pattern dicts

        Returns:
            生成的 Markdown 文档字符串 / Generated markdown document
        """
        if not patterns:
            return "# 知识文档 / Knowledge Documentation\n\n暂无内容 / No content."

        lines = [
            "# Nonull 自进化知识文档 / Self-Evolution Knowledge Documentation",
            "",
            f"*生成时间 / Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}*",
            f"*来源模式数 / Source patterns: {len(patterns)}*",
            "",
            "---",
            "",
        ]

        # 按类型分组 / Group by type
        by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for p in patterns:
            by_type[p.get("pattern_type", "unknown")].append(p)

        # 安全规则 / Safety rules
        if "mistake" in by_type:
            lines.append("## ⚠ 安全规则 / Safety Rules\n")
            for p in by_type["mistake"]:
                lines.append(f"- **{p.get('name', 'unnamed')}** (confidence: {p.get('confidence', 0):.2f})")
                lines.append(f"  - {p.get('description', 'No description')}")
                if p.get("conditions"):
                    lines.append(f"  - 条件 / Conditions: {', '.join(p['conditions'])}")
                lines.append("")

        # 最佳实践 / Best practices
        if "best_practice" in by_type:
            lines.append("## ✅ 最佳实践 / Best Practices\n")
            for p in by_type["best_practice"]:
                lines.append(f"- **{p.get('name', 'unnamed')}**")
                lines.append(f"  - {p.get('description', '')}")
                lines.append(f"  - 置信度 / Confidence: {p.get('confidence', 0):.2f}")
                lines.append("")

        # 工作流 / Workflows
        if "workflow" in by_type:
            lines.append("## 🔄 工作流 / Workflows\n")
            for p in by_type["workflow"]:
                steps = p.get("steps_sequence", [])
                lines.append(f"### {p.get('name', 'unnamed')}\n")
                lines.append(f"步骤数 / Steps: {len(steps)}")
                lines.append(f"置信度 / Confidence: {p.get('confidence', 0):.2f}")
                lines.append("")
                for i, step in enumerate(steps[:10]):
                    action = step.get("action", "?")
                    tool = step.get("tool", "")
                    tool_str = f" [{tool}]" if tool else ""
                    lines.append(f"  {i+1}. {action}{tool_str}")
                if len(steps) > 10:
                    lines.append(f"  ... 还有 {len(steps) - 10} 步 / ... {len(steps) - 10} more steps")
                lines.append("")

        # 知识库引用 / Knowledge base references
        if self._knowledge:
            lines.append("## 📚 相关知识 / Related Knowledge\n")
            for item in list(self._knowledge.values())[:10]:
                lines.append(f"- [{item.knowledge_type.value}] {item.summary[:100]}")
                lines.append(f"  - 置信度 / Confidence: {item.confidence:.2f}")
                lines.append("")

        return "\n".join(lines)

    def get_knowledge(self, knowledge_id: str) -> Optional[KnowledgeItem]:
        """通过 ID 获取知识项 / Get knowledge item by ID."""
        item = self._knowledge.get(knowledge_id)
        if item:
            item.record_access()
        return item

    def find_knowledge(
        self,
        category: Optional[str] = None,
        knowledge_type: Optional[KnowledgeType] = None,
        min_confidence: float = 0.0,
        tags: Optional[List[str]] = None,
    ) -> List[KnowledgeItem]:
        """搜索知识项 / Search knowledge items.

        Args:
            category: 按类别过滤 / Filter by category
            knowledge_type: 按类型过滤 / Filter by knowledge type
            min_confidence: 最低置信度 / Minimum confidence
            tags: 按标签过滤 / Filter by tags (AND logic)

        Returns:
            匹配的知识项列表 / Matching knowledge items
        """
        results = []
        for item in self._knowledge.values():
            if category and item.category != category:
                continue
            if knowledge_type and item.knowledge_type != knowledge_type:
                continue
            if item.confidence < min_confidence:
                continue
            if tags and not all(t in item.tags for t in tags):
                continue
            results.append(item)

        # 按置信度降序 / Sort by confidence descending
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """通过 ID 获取规则 / Get rule by ID."""
        return self._rules.get(rule_id)

    def get_active_rules(self) -> List[Rule]:
        """获取所有启用中的规则 / Get all enabled rules."""
        return [r for r in self._rules.values() if r.enabled]

    def get_statistics(self) -> Dict[str, Any]:
        """获取整合统计 / Get consolidation statistics."""
        stats = dict(self.stats)
        type_counts = Counter(
            item.knowledge_type.value for item in self._knowledge.values()
        )
        stats.update({
            "knowledge_by_type": dict(type_counts),
            "rules_by_type": dict(
                Counter(r.rule_type for r in self._rules.values())
            ),
            "category_count": len(self._category_stats),
        })
        return stats

    def reset(self) -> None:
        """重置所有知识 / Reset all knowledge."""
        self._knowledge.clear()
        self._rules.clear()
        self.graph = KnowledgeGraph()
        self._category_stats.clear()
        self._content_hash_index.clear()
        self.stats = {
            "total_knowledge_items": 0,
            "total_rules": 0,
            "graphs_nodes": 0,
            "graphs_edges": 0,
            "consolidation_runs": 0,
            "conflicts_detected": 0,
        }
        logger.info("KnowledgeConsolidator reset | 知识整合引擎已重置")

    # ------------------------------------------------------------------
    # Internal: Experience Consolidation
    # ------------------------------------------------------------------

    def _categorize_experiences(
        self, experiences: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """按类别对经验分组 / Group experiences by category."""
        categorized: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for exp in experiences:
            cat = exp.get("category", "general")
            categorized[cat].append(exp)
            self._category_stats[cat]["count"] += 1
        return categorized

    def _extract_principle(
        self,
        group: List[Dict[str, Any]],
        category: str,
    ) -> Optional[KnowledgeItem]:
        """从一组同类经验中提取通用原则 / Extract general principle from a group."""
        if not group:
            return None

        # 从组中提取共性 / Extract commonalities
        contents = [e.get("content", "") for e in group]
        common_tags: Counter = Counter()
        for e in group:
            common_tags.update(e.get("tags", []))

        avg_confidence = sum(
            e.get("confidence", 0.5) for e in group
        ) / len(group)

        # 构建原则描述 / Build principle description
        principle_content = (
            f"通用原则 / General Principle [{category}]: "
            f"基于 {len(group)} 条经验总结。"
            f"核心发现: {contents[0][:200] if contents else '无'}"
        )

        # 更新分类统计 / Update category statistics
        self._category_stats[category]["avg_confidence"] = (
            (self._category_stats[category]["avg_confidence"]
             * (self._category_stats[category]["count"] - len(group))
             + sum(e.get("confidence", 0.5) for e in group))
            / max(self._category_stats[category]["count"], 1)
        )

        return self._create_knowledge_item(
            content=principle_content,
            summary=f"原则 / Principle: {category} ({len(group)} experiences)",
            knowledge_type=KnowledgeType.PRINCIPLE,
            confidence=avg_confidence * 0.85,
            category=category,
            tags=[t for t, _ in common_tags.most_common(5)],
        )

    def _create_knowledge_item(
        self,
        content: str,
        summary: str,
        knowledge_type: KnowledgeType,
        confidence: float,
        category: str,
        source_id: str = "",
        tags: Optional[List[str]] = None,
    ) -> Optional[KnowledgeItem]:
        """创建带去重的知识项 / Create a deduplicated knowledge item."""
        # 内容去重 / Content deduplication
        content_hash = hashlib.md5(content.encode()).hexdigest()[:16]
        if content_hash in self._content_hash_index:
            existing_id = self._content_hash_index[content_hash]
            existing = self._knowledge.get(existing_id)
            if existing:
                existing.update(content, max(existing.confidence, confidence))
                return existing
            return None

        item = KnowledgeItem(
            content=content,
            summary=summary,
            knowledge_type=knowledge_type,
            confidence=confidence,
            category=category,
            tags=tags or [],
        )
        if source_id:
            item.source_experiences.append(source_id)

        self._content_hash_index[content_hash] = item.knowledge_id
        return item

    def _detect_conflicts(
        self, items: List[KnowledgeItem]
    ) -> List[Tuple[KnowledgeItem, KnowledgeItem, str]]:
        """检测知识项之间的冲突 / Detect conflicts between knowledge items."""
        conflicts: List[Tuple[KnowledgeItem, KnowledgeItem, str]] = []

        for i, a in enumerate(items):
            for b in items[i + 1:]:
                # 检查类别和类型的冲突 / Check category+type conflict
                if a.category == b.category and a.knowledge_type == b.knowledge_type:
                    # 内容明显不同可能构成冲突 / Different content may conflict
                    if self._content_similarity(a.content, b.content) < 0.3:
                        conflicts.append((a, b, f"Conflicting {a.knowledge_type.value} in {a.category}"))

        return conflicts

    def _resolve_conflicts(
        self,
        items: List[KnowledgeItem],
        conflicts: List[Tuple[KnowledgeItem, KnowledgeItem, str]],
    ) -> List[KnowledgeItem]:
        """通过置信度投票解决冲突 / Resolve conflicts via confidence voting."""
        # 移除低置信度的冲突项 / Remove lower-confidence items
        resolved = set(range(len(items)))
        for a, b, _ in conflicts:
            idx_a = items.index(a)
            idx_b = items.index(b)

            if a.confidence > b.confidence:
                resolved.discard(idx_b)
            elif b.confidence > a.confidence:
                resolved.discard(idx_a)
            else:
                # 置信度相同，保留更新版本 / Same confidence, keep newer
                if a.version > b.version:
                    resolved.discard(idx_b)
                else:
                    resolved.discard(idx_a)

        return [items[i] for i in sorted(resolved)]

    def _merge_with_existing(self, item: KnowledgeItem) -> KnowledgeItem:
        """将新项合并到已有知识库 / Merge new item into existing knowledge base."""
        existing = self._knowledge.get(item.knowledge_id)
        if existing:
            existing.update(item.content, max(existing.confidence, item.confidence))
            existing.tags = list(set(existing.tags + item.tags))
            existing.related_knowledge_ids = list(set(
                existing.related_knowledge_ids + item.related_knowledge_ids
            ))
            return existing
        else:
            self._knowledge[item.knowledge_id] = item
            return item

    def _find_similar_items(
        self, item: KnowledgeItem
    ) -> List[Tuple[str, float]]:
        """查找相似的知识项 / Find similar knowledge items."""
        similar: List[Tuple[str, float]] = []

        for existing in self._knowledge.values():
            if existing.knowledge_id == item.knowledge_id:
                continue
            similarity = self._content_similarity(item.content, existing.content)
            if similarity > 0.3:
                similar.append((existing.knowledge_id, similarity))

        similar.sort(key=lambda x: x[1], reverse=True)
        return similar[:5]

    @staticmethod
    def _content_similarity(a: str, b: str) -> float:
        """使用 Jaccard 相似度比较内容 / Compare content using Jaccard similarity."""
        if not a or not b:
            return 0.0

        set_a = set(a.lower().split()[:50])
        set_b = set(b.lower().split()[:50])

        intersection = set_a & set_b
        union = set_a | set_b

        return len(intersection) / max(len(union), 1)

    def _update_graph_from_items(
        self, items: List[KnowledgeItem]
    ) -> None:
        """从知识项更新图谱 / Update graph from knowledge items."""
        for item in items:
            self.graph.add_node(
                node_id=item.knowledge_id,
                label=item.summary[:60],
                node_type="knowledge",
                properties={
                    "type": item.knowledge_type.value,
                    "category": item.category,
                },
            )

            # 按类别关联 / Link by category
            for other in self._knowledge.values():
                if (
                    other.knowledge_id != item.knowledge_id
                    and other.category == item.category
                ):
                    self.graph.add_edge(
                        item.knowledge_id, other.knowledge_id,
                        "related_to", weight=0.7,
                    )


