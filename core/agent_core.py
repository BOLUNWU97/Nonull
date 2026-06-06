"""
ADVISORY SAFETY — The deny-first validation and risk-scoring code in this
file (SafetyGuardian) is an ADVISORY software gate. Risk scores and the
"max_risk_score" threshold are developer-configured heuristics, NOT certified
ISO 26262 ASIL-D (or any ASIL) classifications. The "deny-first" label is
borrowed from Claude Code's security pattern, not from a certified safety
process. See README §Disclaimer and `safety.disclaimer: advisory_only` in
config.

Nonull - 主智能体循环 (Main Agent Loop)
================================================

融合架构核心 (Fusion Architecture Core):
  - OpenClaw: Gateway/Agents/Channels 三层, SOUL identity, Nexus+Tendrils
  - Hermes Agent: Provider-agnostic, tool registry, profile isolation, session persistence
  - openHuman: Neocortex memory (working/episodic/semantic/procedural), subconscious loop
  - Claude Code: Deny-first safety, hook system, subagent isolation, compaction

状态机 (State Machine):
  IDLE → PLANNING → REASONING → ACTING → REFLECTING → COMPLETED
                                    ↓                    ↑
                                 ERROR → RECOVERING → REFLECTING

@module: core.agent_core
"""

import asyncio
import copy
import inspect
import json
import logging
import os
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from threading import Lock
from typing import (Any, Awaitable, Callable, Dict, Generic, List, Optional,
                    Set, Tuple, Type, TypeVar, Union)

# 本地导入
from .config import NonullConfig

logger = logging.getLogger("Nonull.agent")

# ===================================================================
# 常量 / Constants
# ===================================================================

DEFAULT_SESSION_DIR = os.path.join(os.path.expanduser("~"), ".Nonull", "sessions")
T = TypeVar("T")

# ===================================================================
# 状态枚举 / State Enum
# ===================================================================


class AgentState(str, Enum):
    """
    智能体状态枚举 / Agent State Enumeration.

    融合 ReAct + Plan-and-Execute + Reflexion 的生命周期状态。
    """
    # ── 基础状态 ──────────────────────────────────────────────
    IDLE = "idle"                     # 空闲 / Idle
    PLANNING = "planning"             # 规划中 / Planning
    REASONING = "reasoning"           # 推理中 / Reasoning
    ACTING = "acting"                 # 执行中 / Acting
    REFLECTING = "reflecting"         # 反思中 / Reflecting
    COMPLETED = "completed"           # 已完成 / Completed
    # ── 异常状态 ──────────────────────────────────────────────
    ERROR = "error"                   # 错误 / Error
    RECOVERING = "recovering"         # 恢复中 / Recovering
    # ── 子智能体状态 ──────────────────────────────────────────
    SPAWNING = "spawning"             # 生成子智能体 / Spawning subagent
    WAITING_SUBAGENT = "waiting_subagent"  # 等待子智能体 / Waiting for subagent


# ===================================================================
# 异常 / Exceptions
# ===================================================================


class NonullError(Exception):
    """智能体基础异常 / Base agent exception."""
    pass


class SafetyViolation(NonullError):
    """
    安全违规异常 / Safety Violation Exception.

    当 Safety Guardian 拒绝某个操作时抛出。
    """

    def __init__(
        self,
        action: str,
        reason: str,
        risk_score: float = 1.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.action = action
        self.reason = reason
        self.risk_score = risk_score
        self.details = details or {}
        super().__init__(f"SafetyViolation: {reason} (action={action!r}, risk={risk_score:.2f})")


class RecoveryFailedError(NonullError):
    """恢复失败异常 / Recovery failed error."""
    pass


class SubagentError(NonullError):
    """子智能体异常 / Subagent error."""
    pass


class HookExecutionError(NonullError):
    """钩子执行异常 / Hook execution error."""
    pass


# ===================================================================
# 安全监护 / Safety Guardian  (Claude Code deny-first 风格)
# ===================================================================


class SafetyGuardian:
    """
    安全监护器 / Safety Guardian.

    采用 Claude Code 风格的 Deny-First 安全策略：
      - 默认拒绝所有操作
      - 仅显式允许的操作可通过
      - 每次动作执行前检查
      - 风险评分机制

    特性:
      - 命令白名单 / Command allowlist
      - 正则模式黑名单 / Regex pattern blocklist
      - 风险评分 / Risk scoring
      - 上下文物联网关 / Context-aware gating
    """

    def __init__(self, config: Optional[NonullConfig] = None) -> None:
        self._config = config or NonullConfig.instance()
        self._allowed_commands: Set[str] = set(
            self._config.get("safety.allowed_commands", [])
        )
        self._blocked_patterns: List[str] = list(
            self._config.get("safety.blocked_patterns", [])
        )
        self._deny_first: bool = self._config.get("safety.deny_first", True)
        self._max_risk_score: float = self._config.get("safety.max_risk_score", 0.7)
        self._enabled: bool = self._config.get("safety.enabled", True)
        self._violation_log: List[SafetyViolation] = []
        self._lock = Lock()
        # 导入 re 惰性
        import re
        self._compiled_patterns = [re.compile(p) for p in self._blocked_patterns]
        logger.info(
            "SafetyGuardian 已初始化 | deny_first=%s | max_risk=%.2f | enabled=%s",
            self._deny_first, self._max_risk_score, self._enabled,
        )

    # ── 核心检查 ──────────────────────────────────────────────

    def validate(
        self,
        action: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, float, str]:
        """
        校验操作是否安全 / Validate whether an action is safe.

        Args:
            action:  操作描述 (如 "exec:ls -la", "file:write:/tmp/x")
            context: 可选的上下文信息

        Returns:
            (is_safe, risk_score, reason) 三元组
        """
        context = context or {}
        risk_score = 0.0
        reason = ""

        if not self._enabled:
            return True, 0.0, "safety_disabled"

        # 0) Deny-first: 默认拒绝
        # ADVISORY: "deny-first" here is a software gate pattern, not a certified
        # safety mechanism. The 0.5 starting risk_score is an arbitrary heuristic,
        # NOT an ASIL rating (there is no ASIL mapping in this file).
        if self._deny_first:
            risk_score = 0.5  # 起步分数 (advisory heuristic, not ASIL)

        # 1) 正则黑名单检查
        import re
        for pattern, compiled in zip(self._blocked_patterns, self._compiled_patterns):
            if compiled.search(action):
                # ADVISORY: 1.0 risk_score is "denied" in this heuristic; it does
                # NOT mean the action is ASIL-D or worse in any certified sense.
                risk_score = 1.0
                reason = f"命中黑名单模式: {pattern}"
                logger.warning("安全拦截: %s | %s", action, reason)
                self._log_violation(action, reason, risk_score)
                return False, risk_score, reason

        # 2) 命令白名单检查
        action_type = action.split(":")[0] if ":" in action else action
        if self._allowed_commands and action_type not in self._allowed_commands:
            # ADVISORY: the +0.3 increment and max_risk_score threshold are
            # developer-configured heuristics, not safety-rated limits.
            risk_score = min(1.0, risk_score + 0.3)
            if risk_score > self._max_risk_score:
                reason = f"操作类型不在白名单中: {action_type}"
                logger.warning("安全拦截: %s | %s", action, reason)
                self._log_violation(action, reason, risk_score)
                return False, risk_score, reason

        # 3) 上下文风险评估
        context_risk = self._evaluate_context_risk(action, context)
        risk_score = min(1.0, risk_score + context_risk)

        if risk_score > self._max_risk_score:
            reason = f"风险评分超限: {risk_score:.2f} > {self._max_risk_score:.2f}"
            logger.warning("安全拦截(风险): %s | %s", action, reason)
            self._log_violation(action, reason, risk_score)
            return False, risk_score, reason

        return True, risk_score, "ok"

    def validate_or_raise(
        self,
        action: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        校验操作，不通过则抛出 SafetyViolation / Validate or raise.

        Args:
            action:  操作描述
            context: 上下文

        Raises:
            SafetyViolation: 当操作不安全时
        """
        is_safe, risk, reason = self.validate(action, context)
        if not is_safe:
            raise SafetyViolation(
                action=action,
                reason=reason,
                risk_score=risk,
                details={"context": context},
            )

    # ── 配置 ───────────────────────────────────────────────────

    def allow_command(self, command: str) -> "SafetyGuardian":
        """添加命令到白名单 / Add command to allowlist."""
        with self._lock:
            self._allowed_commands.add(command)
        return self

    def block_pattern(self, pattern: str) -> "SafetyGuardian":
        """添加拦截正则模式 / Add blocked regex pattern."""
        import re
        with self._lock:
            self._blocked_patterns.append(pattern)
            self._compiled_patterns.append(re.compile(pattern))
        return self

    def set_max_risk(self, score: float) -> "SafetyGuardian":
        """设置最大风险评分 / Set max risk score."""
        self._max_risk_score = max(0.0, min(1.0, score))
        return self

    # ── 查询 ───────────────────────────────────────────────────

    @property
    def violation_count(self) -> int:
        """违规次数 / Violation count."""
        return len(self._violation_log)

    @property
    def recent_violations(self, n: int = 10) -> List[SafetyViolation]:
        """最近的违规记录 / Recent violations."""
        with self._lock:
            return list(self._violation_log[-n:])

    # ── 内部 ───────────────────────────────────────────────────

    def _evaluate_context_risk(self, action: str, context: Dict[str, Any]) -> float:
        """评估上下文风险 / Evaluate contextual risk."""
        risk = 0.0
        # 文件系统操作
        if "write" in action.lower() or "delete" in action.lower():
            risk += 0.2
        # 网络操作
        if "network" in action.lower() or "http" in action.lower():
            risk += 0.1
        # 系统命令
        if action.startswith("exec:"):
            cmd = action[5:]
            dangerous = ["rm -rf", "format", "del /f", "shutdown", "reboot"]
            if any(d in cmd.lower() for d in dangerous):
                risk += 0.5
        # 文件路径
        target = context.get("target", "")
        if isinstance(target, str):
            import os
            dangerous_paths = ["/etc", "/proc", "/sys", "/bin", "/boot", "/dev"]
            if os.name == "nt":
                dangerous_paths += ["C:\\Windows", "C:\\Program Files", "C:\\System32"]
            if ".." in target or any(target.startswith(p) for p in dangerous_paths):
                risk += 0.4
        return risk

    def _log_violation(self, action: str, reason: str, risk: float) -> None:
        """记录违规 / Log violation."""
        with self._lock:
            self._violation_log.append(
                SafetyViolation(action=action, reason=reason, risk_score=risk)
            )

    def __repr__(self) -> str:
        return (
            f"<SafetyGuardian enabled={self._enabled} "
            f"allowlist={len(self._allowed_commands)} "
            f"blocklist={len(self._blocked_patterns)} "
            f"violations={len(self._violation_log)}>"
        )


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


# ===================================================================
# 工具注册表 / Tool Registry  (Hermes Agent 风格)
# ===================================================================


class BaseTool(ABC):
    """
    工具基类 / Base Tool Class.

    所有可执行工具继承此类，自动注册到 ToolRegistry。
    """

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}
    requires_safety_check: bool = True

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name:
            cls.name = cls.__name__.lower()

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """执行工具逻辑 / Execute tool logic."""
        ...

    def to_spec(self) -> Dict[str, Any]:
        """返回工具规范（用于 LLM 函数调用）/ Return tool spec for LLM."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def __repr__(self) -> str:
        return f"<BaseTool name={self.name!r}>"


class ToolRegistry:
    """
    工具注册表 / Tool Registry.

    管理所有可用的工具，支持注册、注销、查找和批量执行。
    Hermes Agent 风格的工具管理。
    """

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._lock = Lock()

    def register(self, tool: BaseTool) -> "ToolRegistry":
        """
        注册工具 / Register a tool.

        Args:
            tool: 工具实例

        Returns:
            self (支持链式调用)
        """
        if not isinstance(tool, BaseTool):
            raise TypeError(f"工具必须继承 BaseTool: {type(tool)}")
        with self._lock:
            if tool.name in self._tools:
                logger.warning("工具 %s 已存在，将被覆盖", tool.name)
            self._tools[tool.name] = tool
            logger.debug("工具已注册: %s", tool.name)
        return self

    def unregister(self, name: str) -> bool:
        """注销工具 / Unregister a tool."""
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                return True
            return False

    def get(self, name: str) -> Optional[BaseTool]:
        """获取工具 / Get tool by name."""
        with self._lock:
            return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """列出所有工具名称 / List all tool names."""
        with self._lock:
            return sorted(self._tools.keys())

    def specs(self) -> List[Dict[str, Any]]:
        """返回所有工具的 LLM 规范 / Return spec list for LLM."""
        with self._lock:
            return [t.to_spec() for t in self._tools.values()]

    async def execute(self, name: str, **kwargs: Any) -> Any:
        """
        执行工具 / Execute a tool.

        Args:
            name:   工具名称
            **kwargs: 工具参数

        Returns:
            执行结果

        Raises:
            KeyError: 工具不存在
        """
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"工具不存在: {name} / Tool not found: {name}")
        logger.info("执行工具: %s | args=%s", name, kwargs)
        result = await tool.execute(**kwargs)
        logger.debug("工具结果 %s: %s", name, str(result)[:200])
        return result

    @property
    def count(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        return f"<ToolRegistry tools={list(self._tools.keys())}>"


# ===================================================================
# 技能注册表 / Skill Registry
# ===================================================================


class BaseSkill(ABC):
    """
    技能基类 / Base Skill Class.

    比工具更高层次的封装，可包含多个工具调用和推理逻辑。
    支持动态加载和卸载。
    """

    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    dependencies: List[str] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name:
            cls.name = cls.__name__.lower()

    @abstractmethod
    async def execute(self, context: Dict[str, Any], **kwargs: Any) -> Any:
        """执行技能 / Execute the skill."""
        ...

    def validate_context(self, context: Dict[str, Any]) -> bool:
        """验证上下文是否满足执行条件 / Validate context."""
        return True

    def __repr__(self) -> str:
        return f"<BaseSkill name={self.name!r} v{self.version}>"


class SkillRegistry:
    """
    技能注册表 / Skill Registry.

    管理技能的生命周期：注册、加载、卸载、执行。
    支持动态发现和依赖解析。
    """

    def __init__(self) -> None:
        self._skills: Dict[str, BaseSkill] = {}
        self._lock = Lock()

    def register(self, skill: BaseSkill) -> "SkillRegistry":
        """注册技能 / Register a skill."""
        if not isinstance(skill, BaseSkill):
            raise TypeError(f"技能必须继承 BaseSkill: {type(skill)}")
        with self._lock:
            if skill.name in self._skills:
                logger.warning("技能 %s 已存在，将被覆盖", skill.name)
            self._skills[skill.name] = skill
            logger.info("技能已注册: %s v%s", skill.name, skill.version)
        return self

    def unregister(self, name: str) -> bool:
        """卸载技能 / Unregister a skill."""
        with self._lock:
            if name in self._skills:
                del self._skills[name]
                return True
            return False

    def get(self, name: str) -> Optional[BaseSkill]:
        return self._skills.get(name)

    def list_skills(self) -> List[Dict[str, str]]:
        return [
            {"name": s.name, "version": s.version, "description": s.description}
            for s in self._skills.values()
        ]

    async def execute(self, name: str, context: Dict[str, Any],
                      **kwargs: Any) -> Any:
        """执行技能 / Execute a skill."""
        skill = self.get(name)
        if skill is None:
            raise KeyError(f"技能不存在: {name}")
        if not skill.validate_context(context):
            raise ValueError(f"技能 {name} 上下文验证失败")
        logger.info("执行技能: %s", name)
        return await skill.execute(context, **kwargs)

    @property
    def count(self) -> int:
        return len(self._skills)

    def __contains__(self, name: object) -> bool:
        """Allow ``name in registry`` syntax."""
        return isinstance(name, str) and name in self._skills

    def __iter__(self):
        """Iterate over registered skills (yields BaseSkill instances)."""
        with self._lock:
            return iter(list(self._skills.values()))

    def __len__(self) -> int:
        return self.count

    def __repr__(self) -> str:
        return f"<SkillRegistry skills={list(self._skills.keys())}>"


# ===================================================================
# 子智能体 / Subagent  (Claude Code 子智能体隔离)
# ===================================================================


@dataclass
class SubagentSpec:
    """
    子智能体规格 / Subagent Specification.

    Attributes:
        task:          子任务描述
        agent_type:    子智能体类型 (reasoning / acting / reflexion / data)
        config_override: 配置覆盖
        timeout:       超时时间（秒）
        isolation:     隔离级别
        parent_id:     父智能体 ID
    """
    task: str
    agent_type: str = "reasoning"
    config_override: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 120.0
    isolation: str = "process"
    parent_id: str = ""


@dataclass
class SubagentResult:
    """
    子智能体执行结果 / Subagent Execution Result.

    Attributes:
        subagent_id: 子智能体 ID
        success:     是否成功
        output:      输出内容
        error:       错误信息
        duration:    执行耗时（秒）
        state:       最终状态
        artifacts:   产物路径
    """
    subagent_id: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    state: str = "completed"
    artifacts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subagent_id": self.subagent_id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration": self.duration,
            "state": self.state,
            "artifacts": self.artifacts,
        }


class SubagentManager:
    """
    子智能体管理器 / Subagent Manager.

    管理子智能体的生命周期：生成、监控、通信、回收。
    实现 Claude Code 风格的子进程隔离。
    """

    def __init__(self, config: Optional[NonullConfig] = None) -> None:
        cfg = config or NonullConfig.instance()
        self._max_children = cfg.get("subagent.max_children", 5)
        self._default_timeout = cfg.get("subagent.child_timeout_seconds", 120.0)
        self._isolation = cfg.get("subagent.isolation_level", "process")
        self._children: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    async def spawn(
        self,
        spec: SubagentSpec,
        parent_context: Optional[Dict[str, Any]] = None,
    ) -> SubagentResult:
        """
        生成子智能体 / Spawn a subagent.

        Args:
            spec:           子智能体规格
            parent_context: 父智能体上下文

        Returns:
            子智能体执行结果
        """
        subagent_id = f"sub_{uuid.uuid4().hex[:12]}"
        spec.parent_id = spec.parent_id or subagent_id

        # 检查容量
        with self._lock:
            if len(self._children) >= self._max_children:
                raise SubagentError(
                    f"子智能体数量已达上限 ({self._max_children})"
                )
            self._children[subagent_id] = {
                "id": subagent_id,
                "spec": spec,
                "status": "spawning",
                "started_at": time.time(),
            }

        timeout = spec.timeout or self._default_timeout
        start = time.time()

        logger.info(
            "生成子智能体: id=%s type=%s task=%s",
            subagent_id, spec.agent_type, spec.task[:80],
        )

        try:
            # 根据隔离级别执行
            if self._isolation == "thread":
                result = await self._run_in_thread(subagent_id, spec)
            else:
                # 默认在同一进程中隔离运行
                result = await self._run_in_process(subagent_id, spec)

            duration = time.time() - start

            output = SubagentResult(
                subagent_id=subagent_id,
                success=True,
                output=result,
                duration=duration,
                state="completed",
            )
            self._update_status(subagent_id, "completed")
            logger.info("子智能体完成: id=%s duration=%.2fs", subagent_id, duration)
            return output

        except asyncio.TimeoutError:
            duration = time.time() - start
            self._update_status(subagent_id, "timeout")
            logger.warning("子智能体超时: id=%s timeout=%.1fs", subagent_id, timeout)
            return SubagentResult(
                subagent_id=subagent_id,
                success=False,
                error=f"Timeout after {timeout}s",
                duration=duration,
                state="timeout",
            )

        except Exception as e:
            duration = time.time() - start
            self._update_status(subagent_id, "error")
            logger.exception("子智能体异常: id=%s", subagent_id)
            return SubagentResult(
                subagent_id=subagent_id,
                success=False,
                error=str(e),
                duration=duration,
                state="error",
            )

        finally:
            with self._lock:
                if subagent_id in self._children:
                    self._children[subagent_id]["ended_at"] = time.time()

    async def _run_in_thread(self, subagent_id: str, spec: SubagentSpec) -> Any:
        """在线程中运行子智能体 / Run subagent in thread."""
        loop = asyncio.get_event_loop()
        # 在线程池中运行
        return await loop.run_in_executor(
            None,
            self._execute_subagent_task,
            spec,
        )

    async def _run_in_process(self, subagent_id: str, spec: SubagentSpec) -> Any:
        """在进程中运行子智能体 / Run subagent in process."""
        # 当前实现为协程内直接执行，未来可通过 multiprocessing 实现进程隔离
        return await asyncio.wait_for(
            self._execute_subagent_task_async(spec),
            timeout=spec.timeout or self._default_timeout,
        )

    def _execute_subagent_task(self, spec: SubagentSpec) -> Any:
        """同步执行子智能体任务 / Execute subagent task synchronously."""
        # 占位实现 - 实际项目中接入 LLM 调用
        return {
            "status": "simulated",
            "task": spec.task,
            "agent_type": spec.agent_type,
            "result": f"Simulated result for: {spec.task[:50]}",
        }

    async def _execute_subagent_task_async(self, spec: SubagentSpec) -> Any:
        """异步执行子智能体任务 / Execute subagent task asynchronously."""
        # 占位实现 - 实际项目中接入 LLM 调用链
        await asyncio.sleep(0.1)  # 模拟计算
        return {
            "status": "simulated_async",
            "task": spec.task,
            "agent_type": spec.agent_type,
            "result": f"Async simulated result for: {spec.task[:50]}",
        }

    def _update_status(self, subagent_id: str, status: str) -> None:
        with self._lock:
            if subagent_id in self._children:
                self._children[subagent_id]["status"] = status

    def get_child(self, subagent_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._children.get(subagent_id)

    def list_children(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "id": c["id"],
                    "type": c["spec"].agent_type,
                    "status": c["status"],
                    "task": c["spec"].task[:60],
                }
                for c in self._children.values()
            ]

    def cleanup(self) -> int:
        """清理已完成的子智能体 / Clean up completed children."""
        with self._lock:
            before = len(self._children)
            self._children = {
                k: v for k, v in self._children.items()
                if v.get("status") not in ("completed", "error", "timeout")
            }
            return before - len(self._children)

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(
                1 for c in self._children.values()
                if c.get("status") in ("spawning", "running")
            )


# ===================================================================
# 钩子系统 / Hook System  (Claude Code 风格)
# ===================================================================


class HookPoint(str, Enum):
    """
    钩子点枚举 / Hook Point Enumeration.

    定义智能体生命周期中的所有可挂载点。
    """
    # ── 全局 ──
    ON_INIT = "on_init"
    ON_SHUTDOWN = "on_shutdown"
    ON_ERROR = "on_error"
    # ── 规划 ──
    PRE_PLAN = "pre_plan"
    POST_PLAN = "post_plan"
    # ── 推理 ──
    PRE_REASON = "pre_reason"
    POST_REASON = "post_reason"
    # ── 执行 ──
    PRE_ACT = "pre_act"
    POST_ACT = "post_act"
    # ── 反思 ──
    PRE_REFLECT = "pre_reflect"
    POST_REFLECT = "post_reflect"
    # ── 安全 ──
    PRE_SAFETY_CHECK = "pre_safety_check"
    POST_SAFETY_CHECK = "post_safety_check"
    # ── 子智能体 ──
    PRE_SPAWN = "pre_spawn"
    POST_SPAWN = "post_spawn"
    # ── 记忆 ──
    PRE_MEMORY_STORE = "pre_memory_store"
    POST_MEMORY_STORE = "post_memory_store"
    # ── 状态 ──
    ON_STATE_CHANGE = "on_state_change"


class HookRegistry:
    """
    钩子注册表 / Hook Registry.

    管理钩子的注册和执行。
    支持同步和异步钩子。
    支持优先级排序。
    """

    def __init__(self) -> None:
        self._hooks: Dict[HookPoint, List[Dict[str, Any]]] = {
            hp: [] for hp in HookPoint
        }
        self._lock = Lock()

    def register(
        self,
        hook_point: HookPoint,
        handler: Callable[..., Any],
        name: Optional[str] = None,
        priority: int = 100,
        async_handler: Optional[Callable[..., Awaitable[Any]]] = None,
    ) -> "HookRegistry":
        """
        注册钩子 / Register a hook.

        Args:
            hook_point:    钩子点
            handler:       同步处理器
            name:          钩子名称
            priority:      优先级 (数值越小越先执行)
            async_handler: 异步处理器（可选）

        Returns:
            self
        """
        if hook_point not in HookPoint:
            raise ValueError(f"无效的钩子点: {hook_point}")
        entry = {
            "name": name or f"{handler.__name__}@{hook_point.value}",
            "handler": handler,
            "async_handler": async_handler,
            "priority": priority,
        }
        with self._lock:
            self._hooks[hook_point].append(entry)
            self._hooks[hook_point].sort(key=lambda h: h["priority"])
        logger.debug("钩子已注册: %s @ %s", entry["name"], hook_point.value)
        return self

    def unregister(self, hook_point: HookPoint, name: str) -> bool:
        """注销钩子 / Unregister a hook."""
        with self._lock:
            before = len(self._hooks[hook_point])
            self._hooks[hook_point] = [
                h for h in self._hooks[hook_point] if h["name"] != name
            ]
            return len(self._hooks[hook_point]) < before

    async def execute(
        self,
        hook_point: HookPoint,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Any]:
        """
        执行指定钩子点的所有处理器 / Execute all handlers for a hook point.

        Args:
            hook_point: 钩子点
            context:    上下文
            **kwargs:   传递给处理器的额外参数

        Returns:
            处理器返回值列表
        """
        results: List[Any] = []
        with self._lock:
            hooks = list(self._hooks[hook_point])

        for hook in hooks:
            try:
                handler = hook["handler"]
                async_handler = hook.get("async_handler")

                if async_handler:
                    result = await async_handler(context=context, **kwargs)
                else:
                    if asyncio.iscoroutinefunction(handler):
                        result = await handler(context=context, **kwargs)
                    else:
                        result = handler(context=context, **kwargs)
                results.append(result)

            except Exception as e:
                logger.error(
                    "钩子执行失败: %s @ %s | %s",
                    hook["name"], hook_point.value, e,
                )
                if isinstance(e, HookExecutionError):
                    raise
                # 非关键钩子异常不传播

        return results

    def has_hooks(self, hook_point: HookPoint) -> bool:
        """检查是否有注册的钩子 / Check if hooks exist for a point."""
        with self._lock:
            return len(self._hooks[hook_point]) > 0

    def list_hooks(self, hook_point: Optional[HookPoint] = None) -> Dict[str, List[str]]:
        """列出所有已注册的钩子 / List all registered hooks."""
        with self._lock:
            if hook_point:
                return {
                    hook_point.value: [h["name"] for h in self._hooks[hook_point]]
                }
            return {
                hp.value: [h["name"] for h in hooks]
                for hp, hooks in self._hooks.items() if hooks
            }

    def clear(self) -> None:
        """清空所有钩子 / Clear all hooks."""
        with self._lock:
            for hp in HookPoint:
                self._hooks[hp] = []


# ===================================================================
# 主智能体 / Main Agent
# ===================================================================


class Nonull:
    """
    Nonull - 自动驾驶AI智能体核心类
    ========================================

    融合架构核心 (Fusion Architecture Core):
      - OpenClaw: 三层智能体架构
      - Hermes Agent: 配置档隔离 + 工具注册表
      - openHuman: 新皮层记忆 + 潜意识循环
      - Claude Code: 拒绝优先安全 + 钩子系统 + 子智能体隔离

    状态机 (State Machine):
      IDLE → PLANNING → REASONING → ACTING → REFLECTING → COMPLETED
                                        ↓                    ↑
                                     ERROR → RECOVERING → REFLECTING

    双语文档 / Bilingual Documentation:
      所有公共方法同时包含中文和英文 docstring。
      代码注释以中文为主，关键术语附英文。

    Usage::
        agent = Nonull()
        result = await agent.run("Analyze traffic situation at intersection A")
        status = agent.get_status()
        agent.save_state("./checkpoint.json")
    """

    def __init__(
        self,
        config: Optional[NonullConfig] = None,
        session_id: Optional[str] = None,
        name: str = "Nonull",
    ) -> None:
        """
        初始化智能体 / Initialize agent.

        Args:
            config:     配置实例（自动使用默认配置）
            session_id: 会话 ID（自动生成）
            name:       智能体名称
        """
        # ── 配置 / Configuration ──
        self._config = config or NonullConfig.instance()
        self._name: str = name
        self._session_id: str = session_id or f"session_{uuid.uuid4().hex[:12]}"

        # ── 状态 / State ──
        self._state: AgentState = AgentState.IDLE
        self._previous_state: Optional[AgentState] = None
        self._current_task: str = ""
        self._iteration: int = 0
        self._max_iterations: int = self._config.get("agent.max_iterations", 50)
        self._timeout: float = self._config.get("agent.timeout_seconds", 300.0)
        self._recovery_attempts: int = self._config.get("agent.recovery_attempts", 3)
        self._error_count: int = 0
        self._started_at: Optional[float] = None

        # ── 安全 / Safety ──
        self._safety: SafetyGuardian = SafetyGuardian(self._config)

        # ── 记忆 / Memory ──
        self._memory: MemorySystem = MemorySystem(self._config)

        # ── 工具 / Tools ──
        self._tool_registry: ToolRegistry = ToolRegistry()

        # ── 技能 / Skills ──
        self._skill_registry: SkillRegistry = SkillRegistry()

        # ── 子智能体 / Subagents ──
        self._subagent_mgr: SubagentManager = SubagentManager(self._config)

        # ── 钩子 / Hooks ──
        self._hooks: HookRegistry = HookRegistry()

        # ── 运行上下文 / Execution context ──
        self._context: Dict[str, Any] = {
            "session_id": self._session_id,
            "config_snapshot": self._config.snapshot().all(),
            "started_at": None,
            "task_history": [],
            "action_history": [],
            "reflection_history": [],
        }

        # ── 步骤历史 / Step history ──
        self._steps: List[Dict[str, Any]] = []

        # ── 异步锁 / Async lock ──
        self._lock = asyncio.Lock()

        # ── 日志 / Logging ──
        self._setup_logging()

        logger.info(
            "Nonull 已初始化 | name=%s session=%s state=%s",
            self._name, self._session_id, self._state.value,
        )

    # ─────────────────────────────────────────────────────────────
    # 属性 / Properties
    # ─────────────────────────────────────────────────────────────

    @property
    def state(self) -> AgentState:
        """当前状态 / Current state."""
        return self._state

    @property
    def session_id(self) -> str:
        """会话 ID / Session ID."""
        return self._session_id

    @property
    def name(self) -> str:
        """智能体名称 / Agent name."""
        return self._name

    @property
    def memory(self) -> MemorySystem:
        """记忆系统引用 / Memory system reference."""
        return self._memory

    @property
    def safety(self) -> SafetyGuardian:
        """安全监护器引用 / Safety guardian reference."""
        return self._safety

    @property
    def tools(self) -> ToolRegistry:
        """工具注册表引用 / Tool registry reference."""
        return self._tool_registry

    @property
    def skills(self) -> SkillRegistry:
        """技能注册表引用 / Skill registry reference."""
        return self._skill_registry

    @property
    def hooks(self) -> HookRegistry:
        """钩子注册表引用 / Hook registry reference."""
        return self._hooks

    # ─────────────────────────────────────────────────────────────
    # 主入口 / Main Entry Point
    # ─────────────────────────────────────────────────────────────

    async def run(
        self,
        task_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        主入口：运行智能体处理任务 / Main entry: run agent to process a task.

        完整的 ReAct + Plan-and-Execute + Reflexion 循环：
          1. PLAN:    分解任务为子步骤
          2. REASON:  基于当前状态和记忆推理
          3. ACT:     通过安全监护执行动作
          4. REFLECT: 反思结果并更新记忆
          5. 循环 1-4 直到完成或超时

        Args:
            task_input: 任务描述 / Task description
            context:    可选的初始上下文 / Optional initial context

        Returns:
            {
                "status":     最终状态,
                "output":     最终输出,
                "steps":      执行步骤,
                "iterations": 迭代次数,
                "duration":   总耗时（秒）,
                "error":      错误信息（如有）
            }
        """
        async with self._lock:
            if self._state not in (AgentState.IDLE, AgentState.COMPLETED, AgentState.ERROR):
                return {
                    "status": self._state.value,
                    "error": f"智能体正在运行中 (当前状态: {self._state.value})",
                }

            self._reset_for_new_task(task_input, context)
            self._set_state(AgentState.PLANNING)

        # 总计时
        overall_start = time.time()

        try:
            while self._iteration < self._max_iterations:
                self._iteration += 1
                logger.info(
                    "=== 迭代 %d/%d | 状态: %s | 任务: %s ===",
                    self._iteration, self._max_iterations,
                    self._state.value, self._current_task[:60],
                )

                # ── 1) PLANNING ────────────────────────────────
                if self._state == AgentState.PLANNING:
                    plan = await self._safe_execute_step(
                        self.plan, self._current_task
                    )
                    if self._state == AgentState.ERROR:
                        continue
                    self._context["plan"] = plan
                    self._set_state(AgentState.REASONING)

                # ── 2) REASONING ──────────────────────────────
                elif self._state == AgentState.REASONING:
                    reason_result = await self._safe_execute_step(
                        self.reason, self._context
                    )
                    if self._state == AgentState.ERROR:
                        continue
                    self._context["reasoning"] = reason_result
                    self._set_state(AgentState.ACTING)

                # ── 3) ACTING ─────────────────────────────────
                elif self._state == AgentState.ACTING:
                    action = self._context.get("reasoning", {}).get("next_action", "")
                    if not action:
                        action = "complete"
                    act_result = await self._safe_execute_step(
                        self.act, action, self._context
                    )
                    if self._state == AgentState.ERROR:
                        continue
                    self._context["last_result"] = act_result
                    self._context["action_history"].append({
                        "iteration": self._iteration,
                        "action": action,
                        "result": act_result,
                    })
                    self._set_state(AgentState.REFLECTING)

                # ── 4) REFLECTING ─────────────────────────────
                elif self._state == AgentState.REFLECTING:
                    reflection = await self._safe_execute_step(
                        self.reflect, self._context
                    )
                    if self._state == AgentState.ERROR:
                        continue
                    self._context["reflection_history"].append({
                        "iteration": self._iteration,
                        "reflection": reflection,
                    })

                    # 判断是否完成
                    if reflection.get("completed", False):
                        self._set_state(AgentState.COMPLETED)
                        break
                    else:
                        # 继续循环：回到推理阶段
                        self._set_state(AgentState.REASONING)

                # ── 5) COMPLETED / ERROR ──────────────────────
                else:
                    break

                # 超时检查
                if time.time() - overall_start > self._timeout:
                    logger.warning("任务超时 (%.1fs)", self._timeout)
                    self._set_state(AgentState.ERROR)
                    self._context["error"] = f"Task timeout after {self._timeout}s"
                    break

            # 循环结束
            if self._state not in (AgentState.COMPLETED, AgentState.ERROR):
                if self._iteration >= self._max_iterations:
                    self._set_state(AgentState.COMPLETED)
                    self._context["output"] = "Max iterations reached, forced completion"

        except Exception as e:
            logger.exception("运行异常 / Runtime error")
            self._set_state(AgentState.ERROR)
            self._context["error"] = str(e)

        finally:
            duration = time.time() - overall_start
            async with self._lock:
                self._context["duration"] = duration

            # 钩子: 关闭
            await self._hooks.execute(HookPoint.ON_SHUTDOWN, context=self._context)

            logger.info(
                "任务完成 | state=%s iterations=%d duration=%.2fs",
                self._state.value, self._iteration, duration,
            )

        return {
            "status": self._state.value,
            "output": self._context.get("output"),
            "plan": self._context.get("plan"),
            "steps": len(self._steps),
            "iterations": self._iteration,
            "duration": duration,
            "error": self._context.get("error"),
        }

    # ─────────────────────────────────────────────────────────────
    # 核心步骤 / Core Steps
    # ─────────────────────────────────────────────────────────────

    async def plan(self, task: str) -> Dict[str, Any]:
        """
        规划阶段：分解任务为可执行的子步骤 / Plan: decompose task into executable steps.

        使用 Plan-and-Execute 策略将复杂任务分解为子任务序列。

        Args:
            task: 原始任务描述

        Returns:
            {
                "task":          原始任务,
                "subtasks":      [{ "id", "description", "dependencies", "tools" }],
                "strategy":      执行策略,
                "estimated_steps": 预估步骤数,
            }
        """
        await self._hooks.execute(HookPoint.PRE_PLAN, context={"task": task})

        # 检索相关的语义记忆和程序性记忆
        similar_tasks = self._memory.semantic.retrieve(task, k=3)
        procedures = self._memory.procedural.retrieve(task, k=2)

        # 构建规划上下文
        plan_context = {
            "task": task,
            "similar_past_tasks": [e.content for e in similar_tasks],
            "available_procedures": [e.content for e in procedures],
            "available_tools": self._tool_registry.list_tools(),
        }

        # ---- 占位实现: 实际项目中应调用 LLM 进行规划 ----
        # Placeholder: In production, this would invoke an LLM planner
        subtasks = self._generate_plan(task)

        plan_result = {
            "task": task,
            "subtasks": subtasks,
            "strategy": "plan_and_execute",
            "estimated_steps": len(subtasks),
            "context": plan_context,
        }

        # 存储到工作记忆
        self._memory.working.store(
            plan_result, metadata={"type": "plan"}, importance=0.8
        )

        await self._hooks.execute(HookPoint.POST_PLAN, context=plan_result)
        logger.info("规划完成: %d 个子步骤", len(subtasks))
        return plan_result

    async def reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        推理阶段：基于当前状态决定下一步动作 / Reason: decide next action based on state.

        ReAct 循环的核心推理步骤，结合当前上下文、记忆和可用工具。

        Args:
            context: 当前上下文（包含 plan, action_history, reflection_history 等）

        Returns:
            {
                "next_action":   下一步动作描述,
                "reasoning":     推理过程,
                "tool_needed":   是否需要工具,
                "tool_name":     工具名称（如需要）,
                "tool_args":     工具参数,
                "confidence":    置信度 (0-1),
            }
        """
        await self._hooks.execute(HookPoint.PRE_REASON, context=context)

        # 获取记忆上下文
        mem_context = self._memory.get_context(
            query=context.get("task", ""), k=3
        )

        # 构建推理输入
        reasoning_input = {
            "task": self._current_task,
            "plan": context.get("plan"),
            "last_result": context.get("last_result"),
            "last_action": context.get("action_history", [None])[-1] if context.get("action_history") else None,
            "reflections": context.get("reflection_history", [])[-3:],
            "working_memory": [e.content for e in mem_context.get("working", [])],
            "episodic_memory": [e.content for e in mem_context.get("episodic", [])],
            "semantic_knowledge": [e.content for e in mem_context.get("semantic", [])],
            "available_tools": self._tool_registry.specs(),
            "iteration": self._iteration,
        }

        # ---- 占位实现: 实际项目中应调用 LLM 进行推理 ----
        # Placeholder: In production, this would invoke an LLM
        result = self._simulate_reasoning(reasoning_input)

        await self._hooks.execute(HookPoint.POST_REASON, context=result)
        logger.debug("推理结果: action=%s confidence=%.2f", result.get("next_action"), result.get("confidence", 0))
        return result

    async def act(self, action: str, context: Dict[str, Any]) -> Any:
        """
        执行阶段：通过安全监护执行动作 / Act: execute action through safety guardian.

        所有动作在执行前都必须经过 Safety Guardian 的校验。

        Args:
            action:  要执行的动作描述
            context: 当前上下文

        Returns:
            执行结果

        Raises:
            SafetyViolation: 动作被安全系统拒绝
        """
        # 钩子: 执行前
        await self._hooks.execute(HookPoint.PRE_ACT, context={"action": action})

        # 安全校验 (Deny-first)
        is_safe, risk, reason = self._safety.validate(action, context)
        await self._hooks.execute(
            HookPoint.POST_SAFETY_CHECK,
            context={"action": action, "safe": is_safe, "risk": risk, "reason": reason},
        )

        if not is_safe:
            logger.warning("安全拦截: %s (risk=%.2f, reason=%s)", action, risk, reason)
            self._memory.store_experience(
                self._current_task, action,
                {"safety_blocked": True, "reason": reason}, success=False,
            )
            raise SafetyViolation(action=action, reason=reason, risk_score=risk)

        # 执行动作
        try:
            result = await self._execute_action(action, context)
        except Exception as e:
            logger.exception("动作执行失败: %s", action)
            self._memory.store_experience(
                self._current_task, action, {"error": str(e)}, success=False,
            )
            raise

        # 记录到情景记忆
        self._memory.store_experience(self._current_task, action, result, success=True)

        # 钩子: 执行后
        await self._hooks.execute(HookPoint.POST_ACT, context={"action": action, "result": result})

        logger.info("动作执行成功: %s", action[:80])
        return result

    async def reflect(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        反思阶段：评估结果并改进策略 (Reflexion 模式) / Reflect: evaluate and improve.

        Reflexion 模式的核心，基于执行结果进行自我评估和改进。

        Args:
            context: 当前上下文

        Returns:
            {
                "completed":     任务是否完成,
                "summary":       执行摘要,
                "issues":        发现的问题,
                "improvements":  改进建议,
                "score":         自我评分 (0-1),
                "should_retry":  是否需要重试,
            }
        """
        await self._hooks.execute(HookPoint.PRE_REFLECT, context=context)

        last_result = context.get("last_result", {})
        action_history = context.get("action_history", [])
        plan = context.get("plan", {})

        reflection_input = {
            "task": self._current_task,
            "plan": plan,
            "action_history": action_history[-5:],  # 最近 5 步
            "last_result": last_result,
            "iterations_used": self._iteration,
            "max_iterations": self._max_iterations,
        }

        # ---- 占位实现: 实际项目中应调用 LLM 进行反思 ----
        # Placeholder: In production, this would invoke an LLM
        reflection = self._simulate_reflection(reflection_input)

        # 如果反思发现重要经验，存入语义记忆
        if reflection.get("score", 0.5) < 0.3 or reflection.get("issues"):
            self._memory.semantic.store(
                {
                    "type": "reflection_insight",
                    "task": self._current_task,
                    "issues": reflection.get("issues"),
                    "improvements": reflection.get("improvements"),
                },
                importance=0.8,
            )

        await self._hooks.execute(HookPoint.POST_REFLECT, context=reflection)
        logger.info(
            "反思完成: completed=%s score=%.2f issues=%d",
            reflection.get("completed"), reflection.get("score", 0),
            len(reflection.get("issues", [])),
        )
        return reflection

    # ─────────────────────────────────────────────────────────────
    # 子智能体 / Subagent
    # ─────────────────────────────────────────────────────────────

    async def spawn_subagent(
        self,
        task: str,
        agent_type: str = "reasoning",
        config_override: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> SubagentResult:
        """
        生成子智能体处理子任务 / Spawn subagent for subtask.

        Claude Code 风格的子智能体隔离执行。

        Args:
            task:            子任务描述
            agent_type:      子智能体类型 (reasoning / acting / reflexion / data)
            config_override: 配置覆盖（如不同的模型参数）
            timeout:         超时时间（秒）

        Returns:
            子智能体执行结果
        """
        self._set_state(AgentState.SPAWNING)

        prev_state = self._state
        try:
            spec = SubagentSpec(
                task=task,
                agent_type=agent_type,
                config_override=config_override or {},
                timeout=timeout or 120.0,
                parent_id=self._session_id,
            )

            await self._hooks.execute(
                HookPoint.PRE_SPAWN,
                context={"spec": spec, "parent": self._session_id},
            )

            parent_ctx = {
                "session_id": self._session_id,
                "task": self._current_task,
                "context": self._context,
            }
            result = await self._subagent_mgr.spawn(spec, parent_ctx)

            await self._hooks.execute(
                HookPoint.POST_SPAWN,
                context={"result": result},
            )

            logger.info(
                "子智能体完成: %s type=%s success=%s",
                result.subagent_id, agent_type, result.success,
            )
            return result

        finally:
            self._set_state(prev_state if prev_state != AgentState.SPAWNING else AgentState.REASONING)

    # ─────────────────────────────────────────────────────────────
    # 状态管理 / State Management
    # ─────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """
        获取智能体当前状态 / Get current agent status.

        Returns:
            包含状态、会话、任务、进度等信息的字典
        """
        return {
            "state": self._state.value,
            "previous_state": self._previous_state.value if self._previous_state else None,
            "session_id": self._session_id,
            "name": self._name,
            "current_task": self._current_task,
            "iteration": self._iteration,
            "max_iterations": self._max_iterations,
            "error_count": self._error_count,
            "started_at": self._started_at,
            "duration": time.time() - self._started_at if self._started_at else 0,
            "memory_sizes": {
                "working": self._memory.working.size,
                "episodic": self._memory.episodic.size,
                "semantic": self._memory.semantic.size,
                "procedural": self._memory.procedural.size,
            },
            "tools_available": self._tool_registry.count,
            "skills_available": self._skill_registry.count,
            "subagents_active": self._subagent_mgr.active_count,
            "hooks_registered": sum(
                len(v) for v in self._hooks.list_hooks().values()
            ),
            "safety_violations": self._safety.violation_count,
        }

    def _set_state(self, new_state: AgentState) -> None:
        """
        设置新状态并触发钩子 / Set new state and fire hook.

        Args:
            new_state: 目标状态
        """
        self._previous_state = self._state
        self._state = new_state
        logger.debug(
            "状态变更: %s -> %s",
            self._previous_state.value if self._previous_state else "None",
            new_state.value,
        )
        # 触发状态变更钩子 (不等待)
        asyncio.ensure_future(
            self._hooks.execute(
                HookPoint.ON_STATE_CHANGE,
                context={
                    "from": self._previous_state.value if self._previous_state else None,
                    "to": new_state.value,
                    "agent": self._name,
                },
            )
        )

    # ─────────────────────────────────────────────────────────────
    # 持久化 / Persistence  (Hermes Agent 风格)
    # ─────────────────────────────────────────────────────────────

    async def save_state(self, path: Optional[str] = None) -> str:
        """
        保存智能体状态到磁盘 / Save agent state to disk.

        序列化当前状态、记忆、上下文和步骤历史。

        Args:
            path: 保存路径（默认 ~/.Nonull/sessions/<session_id>.json）

        Returns:
            保存的文件路径
        """
        path = path or os.path.join(
            DEFAULT_SESSION_DIR, f"{self._session_id}.json"
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)

        state_data = {
            "version": "0.1.0",
            "session_id": self._session_id,
            "name": self._name,
            "state": self._state.value,
            "current_task": self._current_task,
            "iteration": self._iteration,
            "max_iterations": self._max_iterations,
            "error_count": self._error_count,
            "started_at": self._started_at,
            "context": self._sanitize_for_serialization(self._context),
            "steps": self._sanitize_for_serialization(self._steps),
            "memory": self._memory.to_dict(),
            "saved_at": time.time(),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False, default=str)

        logger.info("状态已保存: %s (%d bytes)", path, os.path.getsize(path))
        return path

    async def load_state(self, path: str) -> bool:
        """
        从磁盘加载智能体状态 / Load agent state from disk.

        Args:
            path: 状态文件路径

        Returns:
            是否成功加载
        """
        if not os.path.isfile(path):
            logger.error("状态文件不存在: %s", path)
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                state_data = json.load(f)

            self._session_id = state_data.get("session_id", self._session_id)
            self._name = state_data.get("name", self._name)
            self._state = AgentState(state_data.get("state", "idle"))
            self._current_task = state_data.get("current_task", "")
            self._iteration = state_data.get("iteration", 0)
            self._max_iterations = state_data.get("max_iterations", 50)
            self._error_count = state_data.get("error_count", 0)
            self._started_at = state_data.get("started_at")
            self._context = state_data.get("context", self._context)
            self._steps = state_data.get("steps", [])

            # 恢复记忆
            memory_data = state_data.get("memory", {})
            for entry_data in memory_data.get("working", []):
                self._memory.working.store(
                    entry_data["content"],
                    entry_data.get("metadata"),
                    entry_data.get("importance", 0.5),
                )
            for entry_data in memory_data.get("episodic", []):
                self._memory.episodic.store(
                    entry_data["content"],
                    entry_data.get("metadata"),
                    entry_data.get("importance", 0.5),
                )

            logger.info("状态已加载: %s (session=%s)", path, self._session_id)
            return True

        except Exception as e:
            logger.exception("状态加载失败: %s", path)
            return False

    # ─────────────────────────────────────────────────────────────
    # 注册 / Registration helpers
    # ─────────────────────────────────────────────────────────────

    def register_tool(self, tool: BaseTool) -> "Nonull":
        """注册工具 / Register a tool."""
        self._tool_registry.register(tool)
        return self

    def register_skill(self, skill: BaseSkill) -> "Nonull":
        """注册技能 / Register a skill."""
        self._skill_registry.register(skill)
        return self

    def register_hook(
        self,
        hook_point: HookPoint,
        handler: Callable[..., Any],
        name: Optional[str] = None,
        priority: int = 100,
    ) -> "Nonull":
        """注册钩子 / Register a hook."""
        self._hooks.register(hook_point, handler, name=name, priority=priority)
        return self

    def allow_command(self, command: str) -> "Nonull":
        """添加安全白名单命令 / Add command to safety allowlist."""
        self._safety.allow_command(command)
        return self

    # ─────────────────────────────────────────────────────────────
    # 内部方法 / Internal Methods
    # ─────────────────────────────────────────────────────────────

    def _reset_for_new_task(
        self, task: str, context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """重置为新任务 / Reset for new task."""
        self._current_task = task
        self._iteration = 0
        self._error_count = 0
        self._started_at = time.time()
        self._steps = []
        self._context = {
            "session_id": self._session_id,
            "config_snapshot": self._config.snapshot().all(),
            "started_at": self._started_at,
            "task": task,
            "plan": None,
            "reasoning": None,
            "last_result": None,
            "action_history": [],
            "reflection_history": [],
            "error": None,
            "output": None,
            **(context or {}),
        }
        # 清空工作记忆但保留情景/语义
        self._memory.working.clear()
        # 记录新任务到情景记忆
        self._memory.episodic.store(
            {"event": "task_start", "task": task, "timestamp": self._started_at},
            importance=0.6,
        )
        logger.info("新任务开始: %s", task[:100])

    async def _safe_execute_step(
        self, step_fn: Callable[..., Any], *args: Any, **kwargs: Any,
    ) -> Any:
        """
        安全执行单步，带错误处理和恢复 / Safely execute a single step.

        Args:
            step_fn: 步骤函数
            *args, **kwargs: 传递给步骤函数的参数

        Returns:
            步骤执行结果
        """
        try:
            if asyncio.iscoroutinefunction(step_fn):
                return await step_fn(*args, **kwargs)
            else:
                return step_fn(*args, **kwargs)
        except SafetyViolation as e:
            logger.warning("步骤被安全系统拦截: %s", e)
            self._error_count += 1
            self._context["error"] = str(e)
            self._context["last_safety_violation"] = {
                "action": e.action,
                "reason": e.reason,
                "risk_score": e.risk_score,
            }
            if self._error_count >= self._recovery_attempts:
                self._set_state(AgentState.ERROR)
            else:
                self._set_state(AgentState.RECOVERING)
                await self._attempt_recovery(e)
            raise

        except (NonullError, asyncio.TimeoutError) as e:
            logger.error("步骤执行失败: %s", e)
            self._error_count += 1
            self._context["error"] = str(e)
            if self._error_count >= self._recovery_attempts:
                self._set_state(AgentState.ERROR)
            else:
                self._set_state(AgentState.RECOVERING)
                await self._attempt_recovery(e)
            raise

        except Exception as e:
            logger.exception("步骤未预期异常: %s", e)
            self._error_count += 1
            self._context["error"] = f"{type(e).__name__}: {e}"
            traceback.print_exc()
            if self._error_count >= self._recovery_attempts:
                self._set_state(AgentState.ERROR)
            else:
                self._set_state(AgentState.RECOVERING)
                await self._attempt_recovery(e)
            raise

    async def _attempt_recovery(self, error: Exception) -> bool:
        """
        尝试从错误中恢复 / Attempt recovery from error.

        Args:
            error: 发生的异常

        Returns:
            恢复是否成功
        """
        logger.info(
            "尝试恢复 (attempt %d/%d)...",
            self._error_count, self._recovery_attempts,
        )
        # 记录错误到情景记忆
        self._memory.episodic.store(
            {
                "event": "recovery_attempt",
                "error": str(error),
                "attempt": self._error_count,
                "state": self._previous_state.value if self._previous_state else None,
            },
            importance=0.9,
        )
        # 简化恢复：回到推理阶段重试
        # 生产环境中应有更复杂的恢复策略
        self._set_state(AgentState.REASONING)
        return True

    async def _execute_action(self, action: str, context: Dict[str, Any]) -> Any:
        """
        执行具体动作 / Execute concrete action.

        根据动作描述决定是调用工具、执行命令还是返回结果。

        Args:
            action:  动作描述
            context: 上下文

        Returns:
            动作结果
        """
        # 记录步骤
        self._steps.append({
            "iteration": self._iteration,
            "action": action,
            "timestamp": time.time(),
        })

        # 解析动作类型
        if action.startswith("tool:"):
            # 工具调用: tool:tool_name arg1=val1 arg2=val2
            parts = action[5:].strip().split(maxsplit=1)
            tool_name = parts[0]
            tool_args = {}
            if len(parts) > 1:
                # 简单参数解析 (生产环境应使用结构化格式)
                for arg_part in parts[1].split():
                    if "=" in arg_part:
                        k, v = arg_part.split("=", 1)
                        tool_args[k] = v
            return await self._tool_registry.execute(tool_name, **tool_args)

        elif action.startswith("skill:"):
            # 技能调用: skill:skill_name key=val ...
            parts = action[6:].strip().split(maxsplit=1)
            skill_name = parts[0]
            skill_args = {}
            if len(parts) > 1:
                for arg_part in parts[1].split():
                    if "=" in arg_part:
                        k, v = arg_part.split("=", 1)
                        skill_args[k] = v
            return await self._skill_registry.execute(skill_name, context, **skill_args)

        elif action == "complete":
            # 完成
            return {"status": "completed", "message": "Task completed by agent decision"}

        else:
            # 通用动作（生产环境应接入 LLM 调用）
            return {
                "status": "executed",
                "action": action,
                "message": f"Action executed: {action[:100]}",
            }

    def _generate_plan(self, task: str) -> List[Dict[str, Any]]:
        """
        生成任务计划（占位）/ Generate task plan (placeholder).

        生产环境中应调用 LLM 进行规划。
        """
        return [
            {
                "id": f"step_{i}",
                "description": f"Subtask {i}: Analyze {task[:30]}...",
                "dependencies": [] if i == 1 else [f"step_{i-1}"],
                "tools": [],
            }
            for i in range(1, 4)
        ]

    def _simulate_reasoning(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """模拟推理（占位）/ Simulate reasoning (placeholder)."""
        task = input_data.get("task", "")
        last_result = input_data.get("last_result")

        if last_result and last_result.get("status") == "completed":
            return {
                "next_action": "complete",
                "reasoning": "Task appears completed based on last result.",
                "tool_needed": False,
                "confidence": 0.9,
            }

        # 查找是否有可用的工具
        tools = input_data.get("available_tools", [])
        if tools:
            tool = tools[0]
            return {
                "next_action": f"tool:{tool['name']}",
                "reasoning": f"Using tool {tool['name']} to process task.",
                "tool_needed": True,
                "tool_name": tool["name"],
                "tool_args": {},
                "confidence": 0.7,
            }

        return {
            "next_action": f"Analyze step for: {task[:50]}",
            "reasoning": "Proceeding with analysis step.",
            "tool_needed": False,
            "confidence": 0.6,
        }

    def _simulate_reflection(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """模拟反思（占位）/ Simulate reflection (placeholder)."""
        action_count = len(input_data.get("action_history", []))
        return {
            "completed": action_count >= 3,
            "summary": f"Executed {action_count} actions.",
            "issues": [] if action_count < 5 else ["Too many iterations"],
            "improvements": ["Optimize tool selection"] if action_count > 3 else [],
            "score": min(1.0, action_count / 5),
            "should_retry": False,
        }

    def _setup_logging(self) -> None:
        """配置日志 / Setup logging."""
        log_level = self._config.get("observability.log_level", "INFO")
        log_file = self._config.get("observability.log_file", "")

        logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        if log_file:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setLevel(getattr(logging, log_level.upper(), logging.INFO))
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
            fh.setFormatter(formatter)
            logger.addHandler(fh)

    @staticmethod
    def _sanitize_for_serialization(obj: Any) -> Any:
        """清理对象以便序列化 / Sanitize object for serialization."""
        if isinstance(obj, dict):
            return {k: Nonull._sanitize_for_serialization(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [Nonull._sanitize_for_serialization(v) for v in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            try:
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                return str(obj)

    # ─────────────────────────────────────────────────────────────
    # 同步入口 / Synchronous Entry
    # ─────────────────────────────────────────────────────────────

    def run_sync(
        self,
        task: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Execute a task by calling the LLM synchronously.

        Returns a dict with keys:
          - 'output': the LLM's response text
          - 'model': the model used
          - 'usage': token usage dict
          - 'duration_ms': how long the call took
          - 'task': the original task

        Falls back to a "no LLM configured" message if api_key is empty.
        """
        import time
        from core.llm_client import LLMClient, LLMConfig, LLMMessage

        start = time.time()
        cfg = LLMConfig.from_env()
        if not cfg.api_key:
            return {
                "output": (
                    "[Nonull] LLM not configured. Set NONULL_LLM_API_KEY to enable the agent.\n"
                    "Other channels (slash commands, skills, scenarios) still work."
                ),
                "model": "none",
                "usage": {},
                "duration_ms": 0.0,
                "task": task,
                "status": "no_llm",
            }

        client = LLMClient(cfg)
        sys_prompt = system_prompt or (
            "You are Nonull, a domain-agnostic AI agent assistant. "
            "You have access to 31+ domain skills across multiple verticals (ADAS, "
            "general programming, data analysis, etc.). When asked to perform a task, "
            "decide which skills to use and explain your reasoning. "
            "ADVISORY: you are a development assistant, not a certified safety system. "
            "Always suggest the user verify critical outputs."
        )

        try:
            resp = client.simple_chat(
                user_message=task,
                system_message=sys_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            return {
                "output": f"[Nonull] LLM call failed: {type(e).__name__}: {e}",
                "model": cfg.model,
                "usage": {},
                "duration_ms": (time.time() - start) * 1000,
                "task": task,
                "status": "error",
            }

        return {
            "output": resp,
            "model": cfg.model,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},  # filled in by client
            "duration_ms": (time.time() - start) * 1000,
            "task": task,
            "status": "ok",
        }

    def __repr__(self) -> str:
        return (
            f"<Nonull name={self._name!r} "
            f"session={self._session_id[:12]} "
            f"state={self._state.value} "
            f"iteration={self._iteration}>"
        )
