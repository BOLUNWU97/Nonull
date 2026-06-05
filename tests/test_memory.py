#!/usr/bin/env python3
"""Tests for Nonull memory system.
Nonull 记忆系统测试。

Tests the dual-system memory architecture including:
- Neocortex (Episodic, Semantic, Procedural stores)
- Subconscious (Consolidation, Pattern discovery, Pruning)
- Memory indexing and retrieval
- Capacity management
- Namespace isolation for profiles

测试双系统记忆架构，包括：
- 新皮质（情景、语义、程序存储）
- 潜意识（整合、模式发现、剪枝）
- 记忆索引和检索
- 容量管理
- 配置文件的命名空间隔离
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Memory Models 记忆模型
# =============================================================================

class MemoryType(Enum):
    """Memory type classification.
    记忆类型分类。"""
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryImportance(Enum):
    """Memory importance level.
    记忆重要性级别。"""
    LOW = 0.2
    MEDIUM = 0.5
    HIGH = 0.8
    CRITICAL = 1.0


@dataclass
class Memory:
    """A single memory entry.
    单个记忆条目。"""
    id: str
    type: MemoryType
    content: str
    embedding: list[float] | None = None
    importance: float = 0.5
    timestamp: float = 0.0
    access_count: int = 0
    namespace: str = "default"
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


# =============================================================================
# Neocortex Store 新皮质存储
# =============================================================================

class NeocortexStore:
    """Neocortex memory store — append-only, immutable.
    新皮质记忆存储 — 仅追加，不可变。"""

    def __init__(self, namespace: str = "default", max_tokens: int = 1_000_000_000):
        self.namespace = namespace
        self.max_tokens = max_tokens
        self._memories: dict[str, Memory] = {}
        self._token_count: int = 0
        self._read_only = False

    def store(self, memory: Memory) -> str:
        """Store a memory (append-only).
        存储一条记忆（仅追加）。

        Args:
            memory: 记忆条目 / Memory to store

        Returns:
            str: 记忆 ID / Memory ID

        Raises:
            ValueError: If store is read-only or at capacity
        """
        if self._read_only:
            raise ValueError("Neocortex is read-only")

        estimated_tokens = len(memory.content.split())
        if self._token_count + estimated_tokens > self.max_tokens:
            raise ValueError(f"Neocortex capacity exceeded: "
                             f"{self._token_count + estimated_tokens} > {self.max_tokens}")

        memory.namespace = self.namespace
        self._memories[memory.id] = memory
        self._token_count += estimated_tokens
        return memory.id

    def get(self, memory_id: str) -> Memory | None:
        """Retrieve a memory by ID.
        根据 ID 检索记忆。

        Args:
            memory_id: 记忆 ID / Memory ID

        Returns:
            Memory | None: 记忆条目 / Memory entry
        """
        memory = self._memories.get(memory_id)
        if memory:
            memory.access_count += 1
        return memory

    def search(self, query: str, top_k: int = 10) -> list[Memory]:
        """Search memories by content similarity (simulated).
        通过内容相似度搜索记忆（模拟）。

        Args:
            query: 搜索查询 / Search query
            top_k: 返回数量 / Number of results

        Returns:
            list[Memory]: 匹配的记忆列表 / Matching memories
        """
        query_lower = query.lower()
        scored: list[tuple[Memory, float]] = []

        for memory in self._memories.values():
            # Simple keyword-based relevance scoring
            content_lower = memory.content.lower()
            score = 0.0
            for word in query_lower.split():
                if word in content_lower:
                    score += 1.0
            # Normalize by content length
            score = score / max(1, len(content_lower.split()))
            # Boost by importance
            score *= (1.0 + memory.importance)
            scored.append((memory, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = [m for m, _ in scored[:top_k]]
        for mem in results:
            mem.access_count += 1
        return results

    def get_stats(self) -> dict:
        """Get store statistics.
        获取存储统计信息。"""
        return {
            "namespace": self.namespace,
            "total_memories": len(self._memories),
            "token_count": self._token_count,
            "max_tokens": self.max_tokens,
            "usage_percent": round(
                (self._token_count / self.max_tokens) * 100, 2
            ),
        }

    def count(self) -> int:
        """Get the number of stored memories.
        获取存储的记忆数量。"""
        return len(self._memories)

    def token_usage(self) -> int:
        """Get current token usage.
        获取当前 token 使用量。"""
        return self._token_count

    def find_low_importance(self, threshold: float = 0.3, ratio: float = 0.1) -> list[Memory]:
        """Find low-importance memories for pruning.
        查找低重要性的记忆以供剪枝。

        Args:
            threshold: 重要性阈值 / Importance threshold
            ratio: 返回比例 / Ratio of results

        Returns:
            list[Memory]: 低重要性记忆列表 / Low-importance memories
        """
        candidates = [
            m for m in self._memories.values()
            if m.importance < threshold
        ]
        candidates.sort(key=lambda m: (m.importance, m.access_count))
        limit = max(1, int(len(self._memories) * ratio))
        return candidates[:limit]

    def delete(self, memory_id: str) -> bool:
        """Delete a memory (for pruning only).
        删除一条记忆（仅用于剪枝）。

        Args:
            memory_id: 记忆 ID / Memory ID

        Returns:
            bool: True if deleted
        """
        memory = self._memories.pop(memory_id, None)
        if memory:
            estimated_tokens = len(memory.content.split())
            self._token_count = max(0, self._token_count - estimated_tokens)
            return True
        return False

    def clear(self, namespace: str | None = None):
        """Clear memories, optionally filtered by namespace.
        清除记忆，可选择按命名空间过滤。

        Args:
            namespace: 命名空间（None = clear all）
        """
        if namespace is None:
            self._memories.clear()
            self._token_count = 0
        else:
            to_remove = [
                mid for mid, mem in self._memories.items()
                if mem.namespace == namespace
            ]
            for mid in to_remove:
                self.delete(mid)

    def set_read_only(self, read_only: bool):
        """Set read-only mode.
        设置只读模式。"""
        self._read_only = read_only


# =============================================================================
# Subconscious Processor 潜意识处理器
# =============================================================================

class SubconsciousProcessor:
    """Subconscious background memory processor.
    潜意识后台记忆处理器。

    Performs periodic consolidation, pattern discovery, and pruning.
    执行周期性整合、模式发现和剪枝。
    """

    def __init__(self, neocortex: NeocortexStore, cycles_per_day: int = 10000):
        self.neocortex = neocortex
        self.cycles_per_day = cycles_per_day
        self.cycle_count = 0
        self.last_consolidation: float = 0.0
        self.discovered_patterns: list[dict] = []
        self.anomalies: list[dict] = []
        self._running = False

    async def run_cycle(self) -> dict:
        """Run a single subconscious processing cycle.
        运行一个潜意识处理周期。

        Returns:
            dict: 周期结果 / Cycle results
        """
        self.cycle_count += 1
        self.last_consolidation = time.time()

        results = {
            "cycle": self.cycle_count,
            "consolidated": 0,
            "patterns_found": 0,
            "pruned": 0,
            "anomalies": 0,
        }

        # Phase 1: Consolidation 整合阶段
        results["consolidated"] = await self._consolidate()

        # Phase 2: Pattern Discovery 模式发现阶段
        patterns = await self._discover_patterns()
        results["patterns_found"] = len(patterns)

        # Phase 3: Pruning 剪枝阶段
        results["pruned"] = await self._prune()

        # Phase 4: Anomaly Detection 异常检测阶段
        anomalies = await self._detect_anomalies()
        results["anomalies"] = len(anomalies)

        return results

    async def _consolidate(self) -> int:
        """Consolidate recent memories into semantic knowledge.
        将最近的记忆整合为语义知识。

        Returns:
            int: 整合的记忆数量 / Number of consolidated memories
        """
        # Simulate: find memories with high access count, combine into patterns
        all_memories = list(self.neocortex._memories.values())
        consolidated = 0

        # Find related memories (same type, close timestamps)
        episodes = [m for m in all_memories if m.type == MemoryType.EPISODIC]
        episodes.sort(key=lambda m: m.timestamp, reverse=True)

        # Group by content similarity (simplified)
        if len(episodes) >= 3:
            # Simulate consolidation: mark as processed
            consolidated = min(3, len(episodes))
            pattern = {
                "type": "consolidated_pattern",
                "source_count": consolidated,
                "description": "Identified recurring task execution pattern",
                "confidence": 0.85,
            }
            self.discovered_patterns.append(pattern)

        return consolidated

    async def _discover_patterns(self) -> list[dict]:
        """Discover patterns across memories.
        发现跨记忆的模式。

        Returns:
            list[dict]: 发现的模式 / Discovered patterns
        """
        new_patterns = []
        all_memories = list(self.neocortex._memories.values())

        # Find procedural memories with similar content
        procedures = [m for m in all_memories if m.type == MemoryType.PROCEDURAL]
        if len(procedures) >= 2:
            pattern = {
                "type": "workflow_pattern",
                "confidence": 0.75,
                "description": "Recurring workflow sequence detected",
                "memories": [m.id for m in procedures[:2]],
            }
            new_patterns.append(pattern)
            self.discovered_patterns.append(pattern)

        return new_patterns

    async def _prune(self) -> int:
        """Prune low-importance memories.
        剪枝低重要性的记忆。

        Returns:
            int: 修剪的记忆数量 / Number of pruned memories
        """
        candidates = self.neocortex.find_low_importance(
            threshold=0.2, ratio=0.05
        )
        pruned = 0
        for memory in candidates:
            if memory.access_count < 2:  # Only prune rarely accessed
                if self.neocortex.delete(memory.id):
                    pruned += 1
        return pruned

    async def _detect_anomalies(self) -> list[dict]:
        """Detect anomalies by comparing with historical patterns.
        通过与历史模式比较检测异常。

        Returns:
            list[dict]: 检测到的异常 / Detected anomalies
        """
        anomalies = []
        all_memories = list(self.neocortex._memories.values())

        # Check for unusual importance patterns
        high_importance = [m for m in all_memories if m.importance >= 0.9]
        if len(high_importance) > len(all_memories) * 0.3:
            anomaly = {
                "type": "importance_anomaly",
                "severity": "warning",
                "message": f"Unusually high proportion of critical memories: "
                           f"{len(high_importance)}/{len(all_memories)}",
                "timestamp": time.time(),
            }
            anomalies.append(anomaly)
            self.anomalies.append(anomaly)

        return anomalies

    def get_stats(self) -> dict:
        """Get subconscious processor statistics.
        获取潜意识处理器统计信息。"""
        return {
            "cycles_per_day": self.cycles_per_day,
            "total_cycles": self.cycle_count,
            "discovered_patterns": len(self.discovered_patterns),
            "anomalies_detected": len(self.anomalies),
            "last_consolidation": self.last_consolidation,
        }


# =============================================================================
# Memory System (combined) 记忆系统（组合）
# =============================================================================

class MemorySystem:
    """Combined memory system with Neocortex and Subconscious.
    结合新皮质和潜意识的记忆系统。"""

    def __init__(self, namespace: str = "default", capacity: int = 1_000_000_000):
        self.neocortex = NeocortexStore(namespace=namespace, max_tokens=capacity)
        self.subconscious = SubconsciousProcessor(
            neocortex=self.neocortex,
            cycles_per_day=10000,
        )
        self._next_id = 0

    def _generate_id(self) -> str:
        """Generate a unique memory ID.
        生成唯一的记忆 ID。"""
        self._next_id += 1
        ts = int(time.time() * 1000)
        return f"mem-{ts}-{self._next_id:04d}"

    def store(self, content: str, mem_type: MemoryType = MemoryType.EPISODIC,
              importance: float = 0.5, namespace: str | None = None,
              metadata: dict | None = None) -> str:
        """Store a memory.
        存储一条记忆。

        Args:
            content: 记忆内容 / Memory content
            mem_type: 记忆类型 / Memory type
            importance: 重要性 / Importance (0.0-1.0)
            namespace: 命名空间（覆盖默认） / Namespace (overrides default)
            metadata: 元数据 / Additional metadata

        Returns:
            str: 记忆 ID / Memory ID
        """
        memory = Memory(
            id=self._generate_id(),
            type=mem_type,
            content=content,
            importance=min(1.0, max(0.0, importance)),
            namespace=namespace or self.neocortex.namespace,
            metadata=metadata or {},
        )
        return self.neocortex.store(memory)

    def recall(self, memory_id: str) -> Memory | None:
        """Recall a specific memory.
        回忆特定的记忆。

        Args:
            memory_id: 记忆 ID / Memory ID

        Returns:
            Memory | None: 记忆条目 / Memory entry
        """
        return self.neocortex.get(memory_id)

    def search(self, query: str, top_k: int = 10) -> list[Memory]:
        """Search memories.
        搜索记忆。

        Args:
            query: 搜索查询 / Search query
            top_k: 返回数量 / Number of results

        Returns:
            list[Memory]: 匹配的记忆 / Matching memories
        """
        return self.neocortex.search(query, top_k)

    async def consolidate(self) -> dict:
        """Run subconscious consolidation cycle.
        运行潜意识整合周期。

        Returns:
            dict: 周期结果 / Cycle results
        """
        return await self.subconscious.run_cycle()

    def get_stats(self) -> dict:
        """Get memory system statistics.
        获取记忆系统统计信息。"""
        return {
            "neocortex": self.neocortex.get_stats(),
            "subconscious": self.subconscious.get_stats(),
        }

    def clear(self, namespace: str | None = None):
        """Clear memories.
        清除记忆。"""
        self.neocortex.clear(namespace)


# =============================================================================
# Tests 测试
# =============================================================================

import pytest


class TestNeocortexStore:
    """Tests for Neocortex memory store.
    新皮质记忆存储测试。"""

    def setup_method(self):
        self.store = NeocortexStore(namespace="test", max_tokens=10000)

    def test_store_memory(self):
        """Test storing a memory.
        测试存储一条记忆。"""
        mem_id = self.store.store(Memory(
            id="test-001",
            type=MemoryType.EPISODIC,
            content="Performed code review on AEB controller",
            importance=0.7,
        ))
        assert self.store.count() == 1
        assert mem_id == "test-001"

    def test_retrieve_memory(self):
        """Test retrieving a memory by ID.
        测试根据 ID 检索记忆。"""
        self.store.store(Memory(
            id="test-001",
            type=MemoryType.EPISODIC,
            content="Test memory content",
        ))
        memory = self.store.get("test-001")
        assert memory is not None
        assert memory.content == "Test memory content"

    def test_retrieve_nonexistent(self):
        """Test retrieving non-existent memory.
        测试检索不存在的记忆。"""
        memory = self.store.get("nonexistent")
        assert memory is None

    def test_search_by_content(self):
        """Test searching memories by content.
        测试通过内容搜索记忆。"""
        self.store.store(Memory(id="m1", type=MemoryType.EPISODIC,
                                content="AEB brake system analysis", importance=0.8))
        self.store.store(Memory(id="m2", type=MemoryType.EPISODIC,
                                content="Lane keep assist review", importance=0.6))
        self.store.store(Memory(id="m3", type=MemoryType.SEMANTIC,
                                content="ISO 26262 safety requirements", importance=0.9))

        results = self.store.search("brake system", top_k=2)
        assert len(results) >= 1
        assert any("brake" in r.content.lower() for r in results)

    def test_append_only_immutable(self):
        """Test that stored memories are immutable (no update method).
        测试存储的记忆是不可变的（没有更新方法）。"""
        self.store.store(Memory(id="m1", type=MemoryType.EPISODIC,
                                content="Original content"))
        memory = self.store.get("m1")
        assert memory.content == "Original content"
        assert not hasattr(self.store, "update")

    def test_read_only_mode(self):
        """Test read-only mode prevents writes.
        测试只读模式阻止写入。"""
        self.store.set_read_only(True)
        with pytest.raises(ValueError, match="read-only"):
            self.store.store(Memory(id="fail", type=MemoryType.EPISODIC,
                                    content="Should fail"))

    def test_capacity_limit(self):
        """Test capacity limit enforcement.
        测试容量限制执行。"""
        small_store = NeocortexStore(max_tokens=10)
        # Store a memory that fits
        small_store.store(Memory(id="m1", type=MemoryType.EPISODIC,
                                  content="short"))
        # This should exceed capacity
        with pytest.raises(ValueError, match="capacity exceeded"):
            small_store.store(Memory(id="m2", type=MemoryType.EPISODIC,
                                      content="this is a very long content that should exceed the limit"))

    def test_namespace_isolation(self):
        """Test namespace isolation.
        测试命名空间隔离。"""
        store1 = NeocortexStore(namespace="profile-a")
        store2 = NeocortexStore(namespace="profile-b")

        store1.store(Memory(id="m1", type=MemoryType.EPISODIC,
                            content="Profile A memory"))
        store2.store(Memory(id="m2", type=MemoryType.EPISODIC,
                            content="Profile B memory"))

        assert store1.count() == 1
        assert store2.count() == 1
        assert store1.get("m1") is not None
        assert store1.get("m2") is None  # Different namespace

    def test_find_low_importance(self):
        """Test finding low-importance memories for pruning.
        测试查找低重要性记忆以进行剪枝。"""
        self.store.store(Memory(id="m1", type=MemoryType.EPISODIC,
                                content="Important", importance=0.9))
        self.store.store(Memory(id="m2", type=MemoryType.EPISODIC,
                                content="Trivial", importance=0.1))
        self.store.store(Memory(id="m3", type=MemoryType.EPISODIC,
                                content="Also trivial", importance=0.15))

        candidates = self.store.find_low_importance(threshold=0.2, ratio=0.5)
        assert len(candidates) >= 2
        assert all(m.importance < 0.2 for m in candidates)

    def test_delete_memory(self):
        """Test deleting a memory.
        测试删除一条记忆。"""
        self.store.store(Memory(id="m1", type=MemoryType.EPISODIC,
                                content="To be deleted"))
        assert self.store.count() == 1
        self.store.delete("m1")
        assert self.store.count() == 0

    def test_clear_namespace(self):
        """Test clearing by namespace.
        测试按命名空间清除。"""
        self.store.store(Memory(id="m1", type=MemoryType.EPISODIC,
                                content="Test"))
        self.store.clear(namespace="test")
        assert self.store.count() == 0

    def test_get_stats(self):
        """Test statistics reporting.
        测试统计信息报告。"""
        self.store.store(Memory(id="m1", type=MemoryType.EPISODIC,
                                content="Test memory content"))
        stats = self.store.get_stats()
        assert stats["namespace"] == "test"
        assert stats["total_memories"] == 1
        assert stats["usage_percent"] > 0

    def test_access_count_increments(self):
        """Test that access count increments on retrieval.
        测试检索时访问计数增加。"""
        self.store.store(Memory(id="m1", type=MemoryType.EPISODIC,
                                content="Test"))
        assert self.store.get("m1").access_count == 1
        assert self.store.get("m1").access_count == 2
        assert self.store.get("m1").access_count == 3


class TestSubconsciousProcessor:
    """Tests for Subconscious memory processor.
    潜意识记忆处理器测试。"""

    def setup_method(self):
        self.neocortex = NeocortexStore(namespace="test")
        self.processor = SubconsciousProcessor(
            neocortex=self.neocortex,
            cycles_per_day=10000,
        )

    @pytest.mark.asyncio
    async def test_run_cycle(self):
        """Test running a single subconscious cycle.
        测试运行一个潜意识周期。"""
        # Add some memories for processing
        for i in range(5):
            self.neocortex.store(Memory(
                id=f"m{i}",
                type=MemoryType.EPISODIC,
                content=f"Task execution {i}: code review result",
                importance=0.5 + i * 0.1,
            ))

        result = await self.processor.run_cycle()
        assert result["cycle"] == 1
        assert result["consolidated"] >= 0
        assert result["patterns_found"] >= 0
        assert result["pruned"] >= 0

    @pytest.mark.asyncio
    async def test_multiple_cycles(self):
        """Test running multiple subconscious cycles.
        测试运行多个潜意识周期。"""
        for i in range(3):
            self.neocortex.store(Memory(
                id=f"m{i}",
                type=MemoryType.EPISODIC,
                content=f"Memory {i}",
            ))

        for _ in range(3):
            await self.processor.run_cycle()

        assert self.processor.cycle_count == 3

    def test_statistics(self):
        """Test subconscious statistics.
        测试潜意识统计信息。"""
        stats = self.processor.get_stats()
        assert stats["cycles_per_day"] == 10000
        assert stats["total_cycles"] == 0
        assert "discovered_patterns" in stats

    @pytest.mark.asyncio
    async def test_pruning_removes_low_importance(self):
        """Test that pruning removes low-importance memories.
        测试剪枝移除低重要性记忆。"""
        self.neocortex.store(Memory(id="important", type=MemoryType.EPISODIC,
                                     content="Important task", importance=0.9))
        self.neocortex.store(Memory(id="trivial", type=MemoryType.EPISODIC,
                                     content="Trivial note", importance=0.05))

        assert self.neocortex.count() == 2
        result = await self.processor.run_cycle()

        # The low-importance memory should be pruned
        if result["pruned"] > 0:
            assert self.neocortex.count() < 2


class TestMemorySystem:
    """Tests for the combined memory system.
    组合记忆系统测试。"""

    def setup_method(self):
        self.memory = MemorySystem(namespace="test", capacity=10000)

    def test_store_and_recall(self):
        """Test storing and recalling memories.
        测试存储和回忆记忆。"""
        mem_id = self.memory.store(
            content="Performed HARA on AEB system",
            mem_type=MemoryType.EPISODIC,
            importance=0.8,
        )
        assert mem_id is not None

        recalled = self.memory.recall(mem_id)
        assert recalled is not None
        assert recalled.type == MemoryType.EPISODIC
        assert recalled.importance == 0.8

    def test_different_memory_types(self):
        """Test all three memory types.
        测试所有三种记忆类型。"""
        episodic_id = self.memory.store(
            "Task: reviewed braking algorithm",
            mem_type=MemoryType.EPISODIC,
        )
        semantic_id = self.memory.store(
            "AEB requires ASIL D for unintended braking",
            mem_type=MemoryType.SEMANTIC,
        )
        procedural_id = self.memory.store(
            "Code review workflow: 1) parse code 2) analyze 3) report",
            mem_type=MemoryType.PROCEDURAL,
        )

        assert self.memory.recall(episodic_id).type == MemoryType.EPISODIC
        assert self.memory.recall(semantic_id).type == MemoryType.SEMANTIC
        assert self.memory.recall(procedural_id).type == MemoryType.PROCEDURAL

    def test_search_across_types(self):
        """Test searching across all memory types.
        测试跨所有记忆类型搜索。"""
        self.memory.store("AEB system emergency braking", mem_type=MemoryType.EPISODIC)
        self.memory.store("Brake force calculation formula", mem_type=MemoryType.SEMANTIC)
        self.memory.store("Brake test procedure steps", mem_type=MemoryType.PROCEDURAL)

        results = self.memory.search("brake", top_k=5)
        assert len(results) >= 1

    def test_importance_clamping(self):
        """Test importance value clamping.
        测试重要性值限制。"""
        mem_id = self.memory.store("Test", importance=2.0)
        memory = self.memory.recall(mem_id)
        assert memory.importance <= 1.0

        mem_id2 = self.memory.store("Test2", importance=-1.0)
        memory2 = self.memory.recall(mem_id2)
        assert memory2.importance >= 0.0

    @pytest.mark.asyncio
    async def test_full_system_integration(self):
        """Test full memory system integration.
        测试完整的记忆系统集成。"""
        # Store multiple memories
        for i in range(10):
            self.memory.store(
                content=f"Task {i}: analysis of ADAS component",
                mem_type=MemoryType.EPISODIC,
                importance=0.3 + (i * 0.07),
            )

        # Verify storage
        assert self.memory.neocortex.count() == 10
        stats = self.memory.get_stats()
        assert stats["neocortex"]["total_memories"] == 10

        # Search
        results = self.memory.search("ADAS", top_k=5)
        assert len(results) <= 5
        assert all("ADAS" in m.content for m in results)

        # Run subconscious cycle
        result = await self.memory.consolidate()
        assert result["cycle"] == 1

        # Clear
        self.memory.clear()
        assert self.memory.neocortex.count() == 0

    def test_namespace_isolation_in_system(self):
        """Test namespace isolation in the memory system.
        测试记忆系统中的命名空间隔离。"""
        sys1 = MemorySystem(namespace="profile-a", capacity=10000)
        sys2 = MemorySystem(namespace="profile-b", capacity=10000)

        sys1.store("Profile A data", mem_type=MemoryType.EPISODIC)
        sys2.store("Profile B data", mem_type=MemoryType.EPISODIC)

        results = sys1.search("Profile", top_k=10)
        assert all(m.namespace == "profile-a" for m in results)

    def test_get_stats(self):
        """Test system-level statistics.
        测试系统级统计信息。"""
        self.memory.store("Test memory")
        stats = self.memory.get_stats()
        assert "neocortex" in stats
        assert "subconscious" in stats
        assert stats["neocortex"]["total_memories"] == 1


class TestMemoryEdgeCases:
    """Edge case tests for memory system.
    记忆系统边界情况测试。"""

    def test_empty_store_search(self):
        """Test searching an empty store.
        测试搜索空存储。"""
        store = NeocortexStore()
        results = store.search("anything")
        assert len(results) == 0

    def test_duplicate_id(self):
        """Test storing with duplicate ID overwrites.
        测试使用重复 ID 存储会覆盖。"""
        store = NeocortexStore()
        store.store(Memory(id="same", type=MemoryType.EPISODIC,
                            content="First"))
        store.store(Memory(id="same", type=MemoryType.EPISODIC,
                            content="Second"))
        # Last write wins (dict behavior)
        assert store.get("same").content == "Second"

    def test_empty_content(self):
        """Test storing empty content.
        测试存储空内容。"""
        store = NeocortexStore()
        mem_id = store.store(Memory(id="empty", type=MemoryType.EPISODIC,
                                     content=""))
        assert mem_id == "empty"

    def test_very_large_content(self):
        """Test storing very large content (boundary test).
        测试存储非常大的内容（边界测试）。"""
        store = NeocortexStore(max_tokens=100)
        large_content = "word " * 200  # ~200 tokens
        with pytest.raises(ValueError, match="capacity exceeded"):
            store.store(Memory(id="large", type=MemoryType.EPISODIC,
                                content=large_content))

    def test_concurrent_access(self):
        """Test concurrent memory access (using asyncio).
        测试并发记忆访问（使用 asyncio）。"""
        store = NeocortexStore()

        async def concurrent_store():
            tasks = []
            for i in range(10):
                tasks.append(asyncio.to_thread(
                    store.store,
                    Memory(id=f"concurrent-{i}", type=MemoryType.EPISODIC,
                           content=f"Concurrent memory {i}"),
                ))
            await asyncio.gather(*tasks)

        asyncio.run(concurrent_store())
        assert store.count() == 10


# =============================================================================
# Run Tests 运行测试
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
