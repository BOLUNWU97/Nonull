"""
DEPRECATED legacy memory implementation — 已废弃的旧版记忆实现。

Re-exported from core.agent_core for backward compatibility
(`from core.agent_core import MemorySystem` 仍然可用).
新代码请使用 `core.memory_system.MemorySystem` —— 它包装了完整的
Neocortex + SubconsciousLoop 实现并提供统一的 working/episodic/
semantic/procedural 属性接口.

Re-exported from core.agent_core for backward compatibility. New code
should use `core.memory_system.MemorySystem`, which wraps the full
Neocortex + SubconsciousLoop and provides a uniform working/episodic/
semantic/procedural interface.

Extracted from agent_core.py during the modular refactor (2026-06).
"""

import logging
import time
import uuid
from abc import ABC, abstractmethod
from threading import Lock
from typing import Any, Dict, List, Optional, Set

# 本地导入
from .config import NonullConfig

logger = logging.getLogger("Nonull.agent")


# ===================================================================
# 记忆系统 / Memory System  (openHuman 新皮层记忆架构)
# ===================================================================


class MemoryEntry:
    """
    记忆条目 / Memory Entry.

    Attributes:
        id:          唯一标识
        content:     记忆内容
        metadata:    元数据
        timestamp:   时间戳
        importance:  重要性 (0.0 - 1.0)
        embedding:   向量嵌入（可选）
    """

    def __init__(
        self,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        embedding: Optional[List[float]] = None,
        entry_id: Optional[str] = None,
    ) -> None:
        self.id = entry_id or str(uuid.uuid4())
        self.content = content
        self.metadata = metadata or {}
        self.timestamp = time.time()
        self.importance = max(0.0, min(1.0, importance))
        self.embedding = embedding
        self.access_count = 0
        self.last_access = self.timestamp

    def access(self) -> None:
        """记录访问 / Record access."""
        self.access_count += 1
        self.last_access = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_access": self.last_access,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        entry = cls(
            content=data["content"],
            metadata=data.get("metadata", {}),
            importance=data.get("importance", 0.5),
            entry_id=data.get("id"),
        )
        entry.timestamp = data.get("timestamp", time.time())
        entry.access_count = data.get("access_count", 0)
        entry.last_access = data.get("last_access", entry.timestamp)
        return entry

    def __repr__(self) -> str:
        return f"<MemoryEntry id={self.id[:8]} importance={self.importance:.2f}>"


class BaseMemory(ABC):
    """
    记忆基类 / Base Memory Class.

    提供统一的记忆存储接口，所有记忆类型继承此类。
    """

    def __init__(self, capacity: int = 100) -> None:
        self._capacity = capacity
        self._entries: List[MemoryEntry] = []
        self._lock = Lock()

    @abstractmethod
    def store(self, content: Any, metadata: Optional[Dict[str, Any]] = None,
              importance: float = 0.5) -> str:
        """存储记忆 / Store memory. 返回条目 ID."""
        ...

    @abstractmethod
    def retrieve(self, query: Any, k: int = 5) -> List[MemoryEntry]:
        """检索记忆 / Retrieve memory."""
        ...

    @abstractmethod
    def forget(self, entry_id: str) -> bool:
        """遗忘记忆 / Forget (delete) memory."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """清空记忆 / Clear all memory."""
        ...

    def recall_all(self) -> List[MemoryEntry]:
        """返回所有记忆 / Return all entries."""
        with self._lock:
            return list(self._entries)

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def capacity(self) -> int:
        return self._capacity

    def _evict_if_needed(self) -> None:
        """容量超限时驱逐最不重要的记忆 / Evict least important entries when over capacity."""
        if len(self._entries) <= self._capacity:
            return
        # 按重要性 + 访问频率排序
        self._entries.sort(
            key=lambda e: (e.importance, e.access_count / max(1, time.time() - e.timestamp + 1))
        )
        self._entries = self._entries[-self._capacity:]

    def _add_entry(self, entry: MemoryEntry) -> str:
        with self._lock:
            self._entries.append(entry)
            self._evict_if_needed()
        return entry.id


# DEPRECATED: This class is superseded by core.memory_system.MemorySystem.
# Kept for backward compatibility; will be removed in a future version.
class WorkingMemory(BaseMemory):
    """
    工作记忆 / Working Memory.

    对应 openHuman 的前额叶皮层，负责当前任务的短期信息存储。
    容量小，更新频繁，用于 ReAct 循环的上下文窗口。
    """

    def __init__(self, capacity: int = 20) -> None:
        super().__init__(capacity=capacity)

    def store(self, content: Any, metadata: Optional[Dict[str, Any]] = None,
              importance: float = 0.5) -> str:
        entry = MemoryEntry(content=content, metadata=metadata, importance=importance)
        return self._add_entry(entry)

    def retrieve(self, query: Any, k: int = 5) -> List[MemoryEntry]:
        with self._lock:
            # 工作记忆按时间倒序返回
            sorted_entries = sorted(self._entries, key=lambda e: e.timestamp, reverse=True)
            return sorted_entries[:k]

    def forget(self, entry_id: str) -> bool:
        with self._lock:
            before = len(self._entries)
            self._entries = [e for e in self._entries if e.id != entry_id]
            return len(self._entries) < before

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def update(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """快捷更新：清空后写入一条新记忆 / Quick update: clear then store one entry."""
        self.clear()
        return self.store(content, metadata, importance=1.0)


# DEPRECATED: This class is superseded by core.memory_system.MemorySystem.
# Kept for backward compatibility; will be removed in a future version.
class EpisodicMemory(BaseMemory):
    """
    情景记忆 / Episodic Memory.

    对应 openHuman 的海马体，记录具体事件和经验。
    支持基于时间的检索和重要性衰减。
    """

    def __init__(self, capacity: int = 1000, retention_days: int = 30) -> None:
        super().__init__(capacity=capacity)
        self._retention_days = retention_days

    def store(self, content: Any, metadata: Optional[Dict[str, Any]] = None,
              importance: float = 0.5) -> str:
        entry = MemoryEntry(
            content=content,
            metadata={**(metadata or {}), "type": "episodic"},
            importance=importance,
        )
        return self._add_entry(entry)

    def retrieve(self, query: Any, k: int = 5) -> List[MemoryEntry]:
        with self._lock:
            # 简单关键词匹配 + 时间衰减
            query_str = str(query).lower()
            scored = []
            now = time.time()
            for e in self._entries:
                age_days = (now - e.timestamp) / 86400
                decay = max(0.1, 1.0 - age_days / self._retention_days)
                # 关键词匹配
                content_str = str(e.content).lower()
                match_score = 1.0 if query_str in content_str else 0.0
                total_score = (match_score * 0.6 + e.importance * 0.2 + decay * 0.2)
                scored.append((total_score, e))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [e for _, e in scored[:k]]

    def forget(self, entry_id: str) -> bool:
        with self._lock:
            before = len(self._entries)
            self._entries = [e for e in self._entries if e.id != entry_id]
            return len(self._entries) < before

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def prune(self) -> int:
        """清理过期记忆 / Prune expired entries."""
        now = time.time()
        cutoff = now - self._retention_days * 86400
        with self._lock:
            before = len(self._entries)
            self._entries = [e for e in self._entries if e.timestamp >= cutoff]
            return before - len(self._entries)


# DEPRECATED: This class is superseded by core.memory_system.MemorySystem.
# Kept for backward compatibility; will be removed in a future version.
class SemanticMemory(BaseMemory):
    """
    语义记忆 / Semantic Memory.

    对应 openHuman 的新皮层，存储概念、知识和规则。
    用于领域知识、驾驶规则、交通法规等。
    """

    def __init__(self, capacity: int = 5000) -> None:
        super().__init__(capacity=capacity)
        self._index: Dict[str, List[str]] = {}  # keyword -> [entry_id]

    def store(self, content: Any, metadata: Optional[Dict[str, Any]] = None,
              importance: float = 0.5) -> str:
        entry = MemoryEntry(
            content=content,
            metadata={**(metadata or {}), "type": "semantic"},
            importance=importance,
        )
        entry_id = self._add_entry(entry)
        # 建立关键词索引
        self._index_entry(entry)
        return entry_id

    def retrieve(self, query: Any, k: int = 5) -> List[MemoryEntry]:
        query_str = str(query).lower()
        with self._lock:
            # 使用倒排索引加速
            candidates: Set[str] = set()
            for word in query_str.split():
                if word in self._index:
                    candidates.update(self._index[word])
            # 如果没有索引匹配，全量搜索
            if not candidates:
                candidates = {e.id for e in self._entries}
            # 排序
            scored = []
            for e in self._entries:
                if e.id not in candidates:
                    continue
                content_str = str(e.content).lower()
                match_count = sum(1 for w in query_str.split() if w in content_str)
                score = match_count / max(len(query_str.split()), 1) * 0.7 + e.importance * 0.3
                scored.append((score, e))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [e for _, e in scored[:k]]

    def forget(self, entry_id: str) -> bool:
        with self._lock:
            before = len(self._entries)
            self._entries = [e for e in self._entries if e.id != entry_id]
            if len(self._entries) < before:
                # 清理索引
                for word, ids in self._index.items():
                    self._index[word] = [i for i in ids if i != entry_id]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._index.clear()

    def _index_entry(self, entry: MemoryEntry) -> None:
        """为条目建立关键词索引 / Build keyword index for entry."""
        content_str = str(entry.content).lower()
        import re
        words = set(re.findall(r'\w{2,}', content_str))
        for word in words:
            if word not in self._index:
                self._index[word] = []
            self._index[word].append(entry.id)


# DEPRECATED: This class is superseded by core.memory_system.MemorySystem.
# Kept for backward compatibility; will be removed in a future version.
class ProceduralMemory(BaseMemory):
    """
    程序性记忆 / Procedural Memory.

    对应小脑和基底核，存储流程、技能和习惯。
    用于驾驶动作序列、标准操作流程等。
    """

    def __init__(self, capacity: int = 500) -> None:
        super().__init__(capacity=capacity)

    def store(self, content: Any, metadata: Optional[Dict[str, Any]] = None,
              importance: float = 0.5) -> str:
        # 程序性记忆期望 content 为 {name, steps, ...} 格式
        if isinstance(content, dict) and "name" not in content:
            metadata = {**(metadata or {}), "type": "procedural"}
        elif isinstance(content, dict):
            metadata = {**(metadata or {}), "name": content.get("name", "unknown_proc")}
        entry = MemoryEntry(content=content, metadata=metadata, importance=importance)
        return self._add_entry(entry)

    def retrieve(self, query: Any, k: int = 5) -> List[MemoryEntry]:
        query_str = str(query).lower()
        with self._lock:
            scored = []
            for e in self._entries:
                # 按名称匹配
                name = str(e.metadata.get("name", "")).lower()
                content_str = str(e.content).lower()
                if query_str in name:
                    match_score = 1.0
                elif query_str in content_str:
                    match_score = 0.6
                else:
                    match_score = 0.0
                score = match_score * 0.8 + e.importance * 0.2
                scored.append((score, e))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [e for _, e in scored[:k]]

    def forget(self, entry_id: str) -> bool:
        with self._lock:
            before = len(self._entries)
            self._entries = [e for e in self._entries if e.id != entry_id]
            return len(self._entries) < before

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def execute_procedure(self, name: str, **kwargs) -> Any:
        """按名称查找并解释执行存储的过程 / Find and execute a stored procedure by name."""
        entries = self.retrieve(name, k=1)
        if not entries:
            raise KeyError(f"未找到过程: {name} / Procedure not found: {name}")
        proc = entries[0].content
        if isinstance(proc, dict) and "steps" in proc:
            results = []
            for step in proc["steps"]:
                # 简单的步骤执行（实际项目中应接入工具调用）
                results.append({"step": step, "status": "recorded"})
            return results
        return proc


# ── 记忆聚合 ──────────────────────────────────────────────────


# DEPRECATED: This class is superseded by core.memory_system.MemorySystem.
# Kept for backward compatibility; will be removed in a future version.
class MemorySystem:
    """
    记忆系统聚合 / Memory System Aggregator.

    管理四种记忆类型，提供统一接口。
    对应 openHuman 的新皮层记忆架构。
    """

    def __init__(self, config: Optional[NonullConfig] = None) -> None:
        cfg = config or NonullConfig.instance()
        self.working = WorkingMemory(capacity=cfg.get("memory.working_capacity", 20))
        self.episodic = EpisodicMemory(
            capacity=1000,
            retention_days=cfg.get("memory.episodic_retention_days", 30),
        )
        self.semantic = SemanticMemory(capacity=5000)
        self.procedural = ProceduralMemory(capacity=500)
        self._enabled = cfg.get("memory.enabled", True)
        self._lock = Lock()
        logger.info("MemorySystem 已初始化 (working/episodic/semantic/procedural)")

    def store(self, content: Any, memory_type: str = "working",
              metadata: Optional[Dict[str, Any]] = None,
              importance: float = 0.5) -> Optional[str]:
        """
        存储到指定记忆类型 / Store to specified memory type.

        Args:
            content:     记忆内容
            memory_type: 记忆类型 (working/episodic/semantic/procedural)
            metadata:    元数据
            importance:  重要性

        Returns:
            条目 ID 或 None (记忆禁用时)
        """
        if not self._enabled:
            return None
        store_map = {
            "working": self.working.store,
            "episodic": self.episodic.store,
            "semantic": self.semantic.store,
            "procedural": self.procedural.store,
        }
        store_fn = store_map.get(memory_type)
        if store_fn is None:
            raise ValueError(f"未知记忆类型: {memory_type}")
        return store_fn(content, metadata, importance)

    def store_experience(self, task: str, action: str, result: Any,
                         success: bool) -> Optional[str]:
        """
        存储一次经验（情景记忆 + 工作记忆）/ Store an experience.

        Args:
            task:   任务描述
            action: 执行的动作
            result: 结果
            success: 是否成功

        Returns:
            条目 ID
        """
        content = {
            "task": task,
            "action": action,
            "result": result,
            "success": success,
        }
        importance = 0.9 if not success else 0.3  # 失败经验更重
        # 同时存入情景和工作记忆
        self.store(content, "working", importance=importance)
        return self.store(content, "episodic", importance=importance)

    def consolidate(self) -> int:
        """
        记忆巩固：工作记忆 → 情景记忆 / Consolidate: working -> episodic.

        Returns:
            巩固的条目数
        """
        count = 0
        for entry in self.working.recall_all():
            if entry.importance > 0.7:
                self.episodic.store(entry.content, entry.metadata, entry.importance)
                count += 1
        return count

    def prune(self) -> Dict[str, int]:
        """清理过期记忆 / Prune expired memories."""
        return {
            "episodic": self.episodic.prune(),
        }

    def get_context(self, query: str = "", k: int = 3) -> Dict[str, List[MemoryEntry]]:
        """
        获取所有记忆类型的上下文 / Get context from all memory types.

        Args:
            query: 查询字符串
            k:     每种记忆返回的条目数

        Returns:
            {memory_type: [entries]}
        """
        return {
            "working": self.working.retrieve(query, k),
            "episodic": self.episodic.retrieve(query, k),
            "semantic": self.semantic.retrieve(query, k),
            "procedural": self.procedural.retrieve(query, k),
        }

    def clear_all(self) -> None:
        """清空所有记忆 / Clear all memory."""
        self.working.clear()
        self.episodic.clear()
        self.semantic.clear()
        self.procedural.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "working": [e.to_dict() for e in self.working.recall_all()],
            "episodic": [e.to_dict() for e in self.episodic.recall_all()],
            "semantic": [e.to_dict() for e in self.semantic.recall_all()],
            "procedural": [e.to_dict() for e in self.procedural.recall_all()],
        }


__all__ = [
    "MemoryEntry",
    "BaseMemory",
    "WorkingMemory",
    "EpisodicMemory",
    "SemanticMemory",
    "ProceduralMemory",
    "MemorySystem",
]
