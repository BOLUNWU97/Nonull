"""
工作记忆模块 / Working Memory Module (短期记忆 / Short-Term Memory)

管理当前对话/任务的上下文窗口和 token 预算。
Manages context window, token budget, and auto-summarization for active tasks.

设计要点 / Design Highlights:
    - 滑动窗口上下文管理 / Sliding window context management
    - Token 预算追踪与告警 / Token budget tracking with alerts
    - 自动摘要压缩（溢出时）/ Auto-summarization on overflow
    - 优先级驱动的上下文保留 / Priority-driven context retention
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token 估算 / Token Estimation
# ---------------------------------------------------------------------------

# 粗略估算：中文 ~1.5 token/字，英文 ~0.75 token/词
# Rough estimation: Chinese ~1.5 tokens/char, English ~0.75 tokens/word
TOKEN_RATE_CHINESE = 1.5
TOKEN_RATE_ENGLISH = 0.75


def estimate_tokens(text: str) -> int:
    """估算文本的 token 数量 / Estimate token count for a text string.

    Args:
        text: 输入文本 / Input text

    Returns:
        估算的 token 数量 / Estimated token count
    """
    if not text:
        return 0

    chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
    other_chars = len(text) - chinese_chars

    tokens = int(chinese_chars * TOKEN_RATE_CHINESE + other_chars * TOKEN_RATE_ENGLISH)
    return max(1, tokens)


# ---------------------------------------------------------------------------
# 枚举与数据结构 / Enums and Data Structures
# ---------------------------------------------------------------------------

class Priority(Enum):
    """上下文优先级 / Context priority level."""
    CRITICAL = 0     # 绝不丢弃，手动固定 / Never evict, manually pinned
    HIGH = 1         # 高优先级，最后被淘汰 / Evicted last
    NORMAL = 2       # 正常优先级 / Normal eviction order
    LOW = 3          # 低优先级，最先被淘汰 / Evicted first
    TRANSIENT = 4    # 瞬时信息，用完即弃 / Ephemeral, discarded immediately


@dataclass
class ContextItem:
    """上下文片段 / A single context item within the working window.

    Attributes:
        content:    文本内容 / Content text
        source:     来源标识（user/assistant/system/tool）/ Source identifier
        priority:   优先级 / Priority level
        token_count: 预估 token 数 / Estimated token count
        timestamp:  创建时间戳 / Creation timestamp
        tags:       标签列表 / Tags for categorization
        metadata:   附加元数据 / Additional metadata
    """
    content: str
    source: str = "system"
    priority: Priority = Priority.NORMAL
    token_count: int = 0
    timestamp: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.token_count <= 0:
            self.token_count = estimate_tokens(self.content)

    def __len__(self) -> int:
        return self.token_count


@dataclass
class SummaryBuffer:
    """摘要缓冲区 / Buffer storing compressed summaries of evicted context.

    Attributes:
        summaries:    摘要列表 / List of (timestamp, summary_text) tuples
        total_tokens: 摘要总 token 数 / Total tokens in summaries
    """
    summaries: List[Tuple[float, str]] = field(default_factory=list)
    total_tokens: int = 0

    def add(self, summary: str) -> None:
        """添加一条摘要 / Add a summary entry."""
        self.summaries.append((time.time(), summary))
        self.total_tokens += estimate_tokens(summary)

    def get_recent(self, n: int = 5) -> List[str]:
        """获取最近的 n 条摘要 / Get the most recent n summaries."""
        return [s for _, s in self.summaries[-n:]]

    def clear(self) -> None:
        """清空摘要缓冲区 / Clear all summaries."""
        self.summaries.clear()
        self.total_tokens = 0


# ---------------------------------------------------------------------------
# Token 预算 / Token Budget
# ---------------------------------------------------------------------------

@dataclass
class TokenBudget:
    """Token 预算追踪器 / Token budget tracker.

    支持软限制（告警）和硬限制（强制裁剪）。
    Supports soft limit (warning) and hard limit (forced eviction).

    Attributes:
        soft_limit:   软限制 token 数（告警阈值）/ Soft limit (warning threshold)
        hard_limit:   硬限制 token 数（强制裁剪阈值）/ Hard limit (eviction threshold)
        _used:        当前已用 token 数 / Current token usage
        _peak:        峰值 token 数 / Peak token usage
        _warnings:    告警次数 / Warning count
    """
    soft_limit: int = 4000
    hard_limit: int = 8000
    _used: int = 0
    _peak: int = 0
    _warnings: int = 0

    @property
    def used(self) -> int:
        """当前已用 token 数 / Current token usage."""
        return self._used

    @property
    def peak(self) -> int:
        """峰值 token 数 / Peak token usage."""
        return self._peak

    @property
    def available(self) -> int:
        """剩余可用 token 数 / Remaining available tokens."""
        return max(0, self.hard_limit - self._used)

    @property
    def utilization(self) -> float:
        """使用率（0~1）/ Utilization ratio (0~1)."""
        return self._used / self.hard_limit if self.hard_limit > 0 else 0.0

    @property
    def is_over_soft(self) -> bool:
        """是否超过软限制 / Whether over soft limit."""
        return self._used > self.soft_limit

    @property
    def is_over_hard(self) -> bool:
        """是否超过硬限制 / Whether over hard limit."""
        return self._used > self.hard_limit

    def add(self, tokens: int) -> bool:
        """添加 token 用量 / Add token usage.

        Args:
            tokens: 新增 token 数 / Tokens to add

        Returns:
            True 如果仍在硬限制内 / True if still within hard limit
        """
        self._used += tokens
        if self._used > self._peak:
            self._peak = self._used
        if self.is_over_soft:
            self._warnings += 1
            logger.warning(
                "Token budget: %d/%d (soft), %d/%d (hard) — warning #%d",
                self._used, self.soft_limit, self._used, self.hard_limit,
                self._warnings
            )
        return not self.is_over_hard

    def release(self, tokens: int) -> None:
        """释放 token 用量 / Release token usage."""
        self._used = max(0, self._used - tokens)

    def reset(self) -> None:
        """重置所有计数 / Reset all counters."""
        self._used = 0
        self._peak = 0
        self._warnings = 0

    def snapshot(self) -> Dict[str, Any]:
        """获取快照 / Get a statistics snapshot."""
        return {
            "used": self._used,
            "peak": self._peak,
            "soft_limit": self.soft_limit,
            "hard_limit": self.hard_limit,
            "available": self.available,
            "utilization": round(self.utilization, 4),
            "warnings": self._warnings,
        }


# ---------------------------------------------------------------------------
# 上下文窗口 / Context Window
# ---------------------------------------------------------------------------

class ContextWindow:
    """滑动上下文窗口 / Sliding context window with priority-based eviction.

    按优先级管理上下文片段，超出硬限制时自动淘汰低优先级内容。
    Manages context items with priority-based eviction when over hard limit.

    Attributes:
        items:        上下文片段列表 / List of context items
        max_items:    最大片段数（0=无限制）/ Max item count (0=unlimited)
        budget:       Token 预算追踪器 / Token budget tracker
        summary_buf:  摘要缓冲区 / Summary buffer
        summarizer:   可选的摘要回调 / Optional summarization callback
    """
    def __init__(
        self,
        soft_limit: int = 4000,
        hard_limit: int = 8000,
        max_items: int = 0,
        summarizer: Optional[Callable[[str], str]] = None,
    ):
        self.items: List[ContextItem] = []
        self.max_items = max_items
        self.budget = TokenBudget(soft_limit=soft_limit, hard_limit=hard_limit)
        self.summary_buf = SummaryBuffer()
        self.summarizer = summarizer
        self._lock = threading.Lock()
        self._eviction_count = 0
        self._summarization_count = 0

    # ------------------------------------------------------------------
    # 核心操作 / Core Operations
    # ------------------------------------------------------------------

    def add(
        self,
        content: str,
        source: str = "system",
        priority: Priority = Priority.NORMAL,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """添加上下文片段 / Add a context item.

        Args:
            content:  内容文本 / Content text
            source:   来源标识 / Source identifier
            priority: 优先级 / Priority level
            tags:     标签列表 / Tags for categorization
            metadata: 附加元数据 / Additional metadata

        Returns:
            True 添加成功 / True if added successfully
        """
        item = ContextItem(
            content=content,
            source=source,
            priority=priority,
            tags=tags or [],
            metadata=metadata or {},
        )

        with self._lock:
            # 瞬时信息跳过预算检查 / Transient items skip budget check
            if priority == Priority.TRANSIENT:
                self.items.append(item)
                return True

            # 添加并检查预算 / Add and check budget
            within_budget = self.budget.add(item.token_count)
            self.items.append(item)

            # 如果超过硬限制，触发淘汰 / Evict if over hard limit
            if not within_budget:
                self._evict()

            # 限制最大条目数 / Limit max item count
            if self.max_items > 0 and len(self.items) > self.max_items:
                self._trim_to_max()

            return within_budget

    def get_context(
        self,
        max_tokens: Optional[int] = None,
        include_summary: bool = True,
    ) -> str:
        """获取当前上下文文本 / Get current context as text.

        Args:
            max_tokens:     最大 token 数（None=全部）/ Max tokens (None=all)
            include_summary: 是否在前面附加摘要 / Whether to prepend summaries

        Returns:
            拼接后的上下文文本 / Concatenated context text
        """
        with self._lock:
            parts: List[str] = []

            # 附加摘要缓冲区 / Prepend summary buffer
            if include_summary and self.summary_buf.summaries:
                summary_text = "<历史摘要>\\n" + "\\n".join(
                    self.summary_buf.get_recent(3)
                ) + "\\n</历史摘要>\\n"
                parts.append(summary_text)

            budget = max_tokens or self.budget.hard_limit
            accumulated = estimate_tokens("".join(part for part in parts))

            for item in self.items:
                item_tokens = item.token_count
                if accumulated + item_tokens > budget:
                    break
                if item.priority == Priority.TRANSIENT:
                    continue
                parts.append(f"[{item.source}] {item.content}")
                accumulated += item_tokens

            return "\\n".join(parts)

    def get_item_count(self) -> int:
        """获取当前条目数 / Get current item count."""
        with self._lock:
            return len(self.items)

    def clear(self) -> None:
        """清空上下文 / Clear all context items."""
        with self._lock:
            self.items.clear()
            self.budget.reset()

    def remove_by_source(self, source: str) -> int:
        """移除指定来源的条目 / Remove items by source.

        Returns:
            移除的条目数 / Number of items removed
        """
        with self._lock:
            before = len(self.items)
            removed_tokens = sum(
                item.token_count
                for item in self.items
                if item.source == source
            )
            self.items = [item for item in self.items if item.source != source]
            self.budget.release(removed_tokens)
            return before - len(self.items)

    def pin_item(self, index: int) -> bool:
        """固定条目（设为 CRITICAL 防止被淘汰）/ Pin an item to prevent eviction.

        Returns:
            True 成功 / True if successful
        """
        with self._lock:
            if 0 <= index < len(self.items):
                self.items[index].priority = Priority.CRITICAL
                return True
            return False

    # ------------------------------------------------------------------
    # 淘汰与摘要 / Eviction & Summarization
    # ------------------------------------------------------------------

    def _evict(self) -> int:
        """淘汰低优先级条目直到预算正常 / Evict low-priority items until within budget.

        Returns:
            淘汰的条目数 / Number of items evicted
        """
        if not self.budget.is_over_hard:
            return 0

        # 按优先级分组（CRITICAL 永不淘汰）/ Group by priority (CRITICAL never evicted)
        priority_order = [
            Priority.TRANSIENT,
            Priority.LOW,
            Priority.NORMAL,
            Priority.HIGH,
        ]

        evicted = 0
        for pri in priority_order:
            while self.budget.is_over_hard:
                # 找到该优先级中最早的条目 / Find oldest item at this priority
                to_evict = None
                for i, item in enumerate(self.items):
                    if item.priority == pri:
                        to_evict = i
                        break

                if to_evict is None:
                    break  # 该优先级无更多条目 / No more items at this priority

                item = self.items.pop(to_evict)
                self.budget.release(item.token_count)
                evicted += 1
                self._eviction_count += 1

                # 尝试摘要 / Attempt summarization
                if self.summarizer is not None:
                    try:
                        summary = self.summarizer(item.content)
                        self.summary_buf.add(summary)
                        self._summarization_count += 1
                    except Exception as e:
                        logger.error("Summarization failed: %s", e)

        logger.info(
            "Evicted %d items (total evictions: %d, summarizations: %d)",
            evicted, self._eviction_count, self._summarization_count,
        )
        return evicted

    def _trim_to_max(self) -> int:
        """按 max_items 裁剪 / Trim to max_items limit.

        Returns:
            移除的条目数 / Number of items removed
        """
        removed = 0
        # 按优先级排序（CRITICAL 永不淘汰），淘汰最低优先级的条目
        # Sort by priority (CRITICAL never evicted), remove lowest priority items
        while len(self.items) > self.max_items:
            # 找到最低优先级的非 CRITICAL 条目
            # Find the lowest priority non-CRITICAL item
            idx = -1
            worst_value = -1

            for i, item in enumerate(self.items):
                if item.priority == Priority.CRITICAL:
                    continue
                if item.priority.value > worst_value:
                    worst_value = item.priority.value
                    idx = i

            if idx < 0:
                break  # 只剩下 CRITICAL 条目，无法继续裁剪 / Only CRITICAL items remain

            item = self.items.pop(idx)
            self.budget.release(item.token_count)
            removed += 1

        return removed

    def force_summarize(self, n_items: int = 5) -> List[str]:
        """强制摘要最早的一批条目 / Force summarization of the oldest items.

        Args:
            n_items: 要摘要的条目数 / Number of items to summarize

        Returns:
            生成的摘要列表 / Generated summaries list
        """
        summaries = []
        with self._lock:
            # 按时间戳排序，排除 CRITICAL / Sort by timestamp, skip CRITICAL
            candidates = sorted(
                [i for i in self.items if i.priority != Priority.CRITICAL],
                key=lambda x: x.timestamp,
            )[:n_items]

            for item in candidates:
                if self.summarizer:
                    try:
                        summary = self.summarizer(item.content)
                        self.summary_buf.add(summary)
                        summaries.append(summary)
                        self.items.remove(item)
                        self.budget.release(item.token_count)
                    except Exception as e:
                        logger.error("Summarization failed: %s", e)

        return summaries

    # ------------------------------------------------------------------
    # 序列化 / Serialization
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """获取完整快照 / Get a complete snapshot."""
        with self._lock:
            return {
                "item_count": len(self.items),
                "eviction_count": self._eviction_count,
                "summarization_count": self._summarization_count,
                "budget": self.budget.snapshot(),
                "summary_buffer_tokens": self.summary_buf.total_tokens,
                "items": [
                    {
                        "source": item.source,
                        "priority": item.priority.name,
                        "tokens": item.token_count,
                        "tags": item.tags,
                        "timestamp": item.timestamp,
                        "preview": item.content[:80] + "..." if len(item.content) > 80 else item.content,
                    }
                    for item in self.items
                ],
            }

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 / Serialize to dictionary."""
        with self._lock:
            return {
                "items": [
                    {
                        "content": item.content,
                        "source": item.source,
                        "priority": item.priority.name,
                        "token_count": item.token_count,
                        "timestamp": item.timestamp,
                        "tags": item.tags,
                        "metadata": item.metadata,
                    }
                    for item in self.items
                ],
                "summaries": [
                    {"timestamp": ts, "summary": s}
                    for ts, s in self.summary_buf.summaries
                ],
                "budget": self.budget.snapshot(),
                "max_items": self.max_items,
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextWindow":
        """从字典反序列化 / Deserialize from dictionary."""
        cw = cls(
            soft_limit=data.get("budget", {}).get("soft_limit", 4000),
            hard_limit=data.get("budget", {}).get("hard_limit", 8000),
            max_items=data.get("max_items", 0),
        )
        for item_data in data.get("items", []):
            cw.items.append(ContextItem(
                content=item_data["content"],
                source=item_data.get("source", "system"),
                priority=Priority[item_data.get("priority", "NORMAL")],
                token_count=item_data.get("token_count", 0),
                timestamp=item_data.get("timestamp", time.time()),
                tags=item_data.get("tags", []),
                metadata=item_data.get("metadata", {}),
            ))
        for summ in data.get("summaries", []):
            cw.summary_buf.add(summ["summary"])
        cw.budget._used = data.get("budget", {}).get("used", 0)
        cw.budget._peak = data.get("budget", {}).get("peak", 0)
        return cw


# ---------------------------------------------------------------------------
# 工作记忆主类 / Working Memory (Main Class)
# ---------------------------------------------------------------------------

class WorkingMemory:
    """工作记忆 — 短期上下文管理 / Working memory for active task context.

    集成上下文窗口、Token 预算和自动摘要，提供简洁的外部接口。
    Integrates context window, token budget, and auto-summarization.

    Attributes:
        context_window: 上下文窗口 / Context window instance
        name:           记忆名称 / Memory instance name
        active_task:    当前活跃任务 / Current active task
    """

    def __init__(
        self,
        name: str = "default",
        soft_limit: int = 4000,
        hard_limit: int = 8000,
        max_items: int = 200,
        summarizer: Optional[Callable[[str], str]] = None,
    ):
        self.name = name
        self.context_window = ContextWindow(
            soft_limit=soft_limit,
            hard_limit=hard_limit,
            max_items=max_items,
            summarizer=summarizer,
        )
        self.active_task: Optional[Dict[str, Any]] = None
        self._created_at = time.time()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # 上下文管理 / Context Management
    # ------------------------------------------------------------------

    def remember(
        self,
        content: str,
        source: str = "assistant",
        priority: Priority = Priority.NORMAL,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """记住一条信息 / Remember a piece of information.

        Args:
            content:  内容文本 / Content text
            source:   来源标识 / Source identifier
            priority: 优先级 / Priority level
            tags:     标签列表 / Tags for categorization
            metadata: 附加元数据 / Additional metadata

        Returns:
            True 如果添加成功 / True if added successfully
        """
        return self.context_window.add(
            content=content,
            source=source,
            priority=priority,
            tags=tags,
            metadata=metadata,
        )

    def recall(
        self,
        max_tokens: Optional[int] = None,
        include_summary: bool = True,
    ) -> str:
        """回忆当前上下文 / Recall current context.

        Args:
            max_tokens:     最大 token 数限制 / Max token limit
            include_summary: 是否包含历史摘要 / Include summary buffer

        Returns:
            上下文文本 / Context text
        """
        return self.context_window.get_context(
            max_tokens=max_tokens,
            include_summary=include_summary,
        )

    def forget(self, source: Optional[str] = None) -> int:
        """主动遗忘 / Actively forget context.

        Args:
            source: 指定来源（None=清空全部）/ Source to remove (None=clear all)

        Returns:
            遗忘的条目数 / Number of items forgotten
        """
        if source is None:
            count = self.context_window.get_item_count()
            self.context_window.clear()
            return count
        return self.context_window.remove_by_source(source)

    # ------------------------------------------------------------------
    # 活跃任务管理 / Active Task Management
    # ------------------------------------------------------------------

    def set_active_task(self, task_id: str, description: str, **kwargs) -> None:
        """设置当前活跃任务 / Set the current active task.

        Args:
            task_id:     任务 ID / Task identifier
            description: 任务描述 / Task description
            **kwargs:    附加任务元数据 / Additional task metadata
        """
        self.active_task = {
            "task_id": task_id,
            "description": description,
            "started_at": time.time(),
            **kwargs,
        }
        self.remember(
            content=f"[Task Start] {description}",
            source="system",
            priority=Priority.HIGH,
            tags=["task", task_id],
            metadata={"task_id": task_id, "event": "start"},
        )

    def end_active_task(self, result: str = "", success: bool = True) -> Optional[Dict[str, Any]]:
        """结束当前活跃任务 / End the current active task.

        Args:
            result:  任务结果摘要 / Task result summary
            success: 是否成功 / Whether the task succeeded

        Returns:
            任务快照或 None / Task snapshot or None
        """
        if self.active_task is None:
            return None

        task = self.active_task
        task["ended_at"] = time.time()
        task["duration"] = task["ended_at"] - task.get("started_at", task["ended_at"])
        task["success"] = success
        task["result"] = result

        self.remember(
            content=f"[Task End] {task['description']} — {'SUCCESS' if success else 'FAILURE'}: {result}",
            source="system",
            priority=Priority.NORMAL,
            tags=["task", task.get("task_id", "")],
            metadata={"task_id": task.get("task_id", ""), "event": "end"},
        )

        self.active_task = None
        return task

    # ------------------------------------------------------------------
    # Token 预算管理 / Token Budget Management
    # ------------------------------------------------------------------

    @property
    def token_usage(self) -> int:
        """当前 token 使用量 / Current token usage."""
        return self.context_window.budget.used

    @property
    def token_available(self) -> int:
        """剩余可用 token 数 / Available tokens."""
        return self.context_window.budget.available

    @property
    def utilization(self) -> float:
        """内存使用率（0~1）/ Memory utilization (0~1)."""
        return self.context_window.budget.utilization

    # ------------------------------------------------------------------
    # 统计与序列化 / Stats & Serialization
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """获取工作记忆统计 / Get working memory statistics."""
        return {
            "name": self.name,
            "age_seconds": time.time() - self._created_at,
            "active_task": self.active_task is not None,
            "context_window": self.context_window.snapshot(),
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 / Serialize to dictionary."""
        return {
            "name": self.name,
            "active_task": self.active_task,
            "context_window": self.context_window.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkingMemory":
        """从字典反序列化 / Deserialize from dictionary."""
        wm = cls(name=data.get("name", "default"))
        wm.context_window = ContextWindow.from_dict(data.get("context_window", {}))
        wm.active_task = data.get("active_task")
        return wm

    def __repr__(self) -> str:
        return (
            f"<WorkingMemory '{self.name}' "
            f"items={self.context_window.get_item_count()} "
            f"tokens={self.token_usage}/{self.context_window.budget.hard_limit}>"
        )
