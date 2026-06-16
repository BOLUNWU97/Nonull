"""
记忆系统升级 / Memory System Upgrade — 集成 memory/ 完整架构到 core.agent_core

将 memory/ 包的完整记忆系统（Neocortex + SubconsciousLoop + Ebbinghaus
遗忘 + 嵌入向量搜索）集成到 Nonull 主智能体的 MemorySystem。

升级内容：
1. MemorySystem 改用 memory/neocortex.py 的 Neocortex 作为底层
2. 自动启动 SubconsciousLoop 潜意识循环
3. run() 方法在 REASONING 阶段调用 build_context() 注入记忆上下文
4. 保留向后兼容的 store/retrieve 接口
5. 可选：通过 .env 控制记忆后端（in_memory | redis | postgres | chroma）

@module: core.memory_system
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import NonullConfig

logger = logging.getLogger("Nonull.agent")


@dataclass
class MemoryStats:
    """记忆系统统计。/ Memory system statistics."""
    working_items: int = 0
    episodic_episodes: int = 0
    semantic_nodes: int = 0
    procedural_skills: int = 0
    total_tokens: int = 0
    token_usage_pct: float = 0.0
    subconscious_running: bool = False
    subconscious_cycles: int = 0
    subconscious_insights: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "working_items": self.working_items,
            "episodic_episodes": self.episodic_episodes,
            "semantic_nodes": self.semantic_nodes,
            "procedural_skills": self.procedural_skills,
            "total_tokens": self.total_tokens,
            "token_usage_pct": round(self.token_usage_pct, 2),
            "subconscious_running": self.subconscious_running,
            "subconscious_cycles": self.subconscious_cycles,
            "subconscious_insights": self.subconscious_insights,
        }


class _SimpleMemoryEntry:
    """简化模式的记忆条目 / Memory entry for the simple fallback backend."""

    __slots__ = ("content", "metadata", "importance", "timestamp")

    def __init__(self, content: Any, metadata: Optional[Dict[str, Any]] = None,
                 importance: float = 0.5) -> None:
        self.content = content
        self.metadata = metadata or {}
        self.importance = importance
        self.timestamp = time.time()


class _SimpleMemoryStore:
    """简化模式的记忆存储 / Minimal in-memory store for the fallback backend.

    当 memory/ 包不可用时使用，保证 MemorySystem.working/episodic/semantic/
    procedural 永远不为 None —— agent.run() 在降级模式下也能正常工作。
    Used when the memory/ package is unavailable; guarantees the four memory
    properties are never None so agent.run() works in degraded mode.
    """

    def __init__(self, name: str, max_entries: int = 500) -> None:
        self.name = name
        self._entries: List[_SimpleMemoryEntry] = []
        self._max_entries = max_entries

    def store(self, content: Any, metadata: Optional[Dict[str, Any]] = None,
              importance: float = 0.5, **kwargs: Any) -> _SimpleMemoryEntry:
        """存储条目 / Store an entry (extra kwargs tolerated and ignored)."""
        entry = _SimpleMemoryEntry(content, metadata, importance)
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            # 淘汰最旧的低重要性条目 / evict oldest low-importance first
            self._entries.sort(key=lambda e: (e.importance, e.timestamp))
            self._entries = self._entries[len(self._entries) - self._max_entries:]
        return entry

    def retrieve(self, query: str = "", k: int = 3, **kwargs: Any) -> List[_SimpleMemoryEntry]:
        """简单关键词检索 / Naive keyword retrieval (substring match, recency order)."""
        if not query:
            return list(self._entries[-k:])
        q = str(query).lower()
        matches = [e for e in self._entries if q in str(e.content).lower()]
        return matches[-k:] if matches else list(self._entries[-k:])[:k]

    def clear(self) -> None:
        """清空 / Clear all entries."""
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


class _MemoryAdapter:
    """向后兼容适配器 / Backward-compat adapter over a neocortex sub-memory.

    agent_core 期望每个记忆层提供 store/retrieve/clear 统一接口,
    而 Neocortex 子记忆的真实 API 是 remember/recall/query/add_knowledge 等。
    本适配器做翻译,其余属性(episodes/nodes/skills/context_window)直接透传。

    agent_core expects store/retrieve/clear on every memory layer; the real
    Neocortex sub-memories expose remember/recall/query/add_knowledge instead.
    This adapter translates, passing through all other attributes.
    """

    def __init__(self, backend: Any, store_fn: Any, retrieve_fn: Any, clear_fn: Any) -> None:
        # 用 object.__setattr__ 避免与 __getattr__ 透传互相干扰
        object.__setattr__(self, "_backend", backend)
        object.__setattr__(self, "_store_fn", store_fn)
        object.__setattr__(self, "_retrieve_fn", retrieve_fn)
        object.__setattr__(self, "_clear_fn", clear_fn)

    def store(self, content: Any, metadata: Optional[Dict[str, Any]] = None,
              importance: float = 0.5, **kwargs: Any) -> Any:
        return self._store_fn(content, metadata, importance)

    def retrieve(self, query: str = "", k: int = 3, **kwargs: Any) -> List[Any]:
        return self._retrieve_fn(query, k)

    def clear(self) -> None:
        self._clear_fn()

    def __getattr__(self, name: str) -> Any:
        # 透传底层属性: episodes / nodes / skills / context_window / ...
        return getattr(object.__getattribute__(self, "_backend"), name)

    def __len__(self) -> int:
        backend = object.__getattribute__(self, "_backend")
        try:
            return len(backend)
        except TypeError:
            # 底层无 __len__:尝试已知集合属性 / try known collection attrs
            for attr in ("episodes", "nodes", "skills"):
                coll = getattr(backend, attr, None)
                if coll is not None:
                    try:
                        return len(coll)
                    except TypeError:
                        continue
            return 0

    def __bool__(self) -> bool:
        # 适配器始终为真值:它代表一个存在的记忆层(可能为空)
        # Adapter is always truthy: it represents an existing (maybe empty) layer
        return True


class MemorySystem:
    """
    记忆系统 — 集成 memory/ 完整架构。/ Memory System with full memory/ integration.

    当 memory/ 包可用时，使用 Neocortex + SubconsciousLoop；
    否则回退到简化版。

    Attributes:
        neocortex:    Neocortex 中央记忆管理器（memory/ 包的完整实现）
        subconscious: SubconsciousLoop 潜意识循环（可选）
        backend:     使用的后端名称 ("neocortex" | "simple")
    """

    def __init__(self, config: Optional[NonullConfig] = None) -> None:
        self._config = config
        self._backend = "simple"
        self.neocortex = None  # type: Optional[Any]
        self.subconscious = None  # type: Optional[Any]
        self._EpisodeType = None  # type: Optional[Any]
        self._stats = MemoryStats()
        # 简化模式后备存储（neocortex 可用时不使用）
        # Fallback stores for simple mode (unused when neocortex is active)
        self._simple_working = _SimpleMemoryStore("working")
        self._simple_episodic = _SimpleMemoryStore("episodic")
        self._simple_semantic = _SimpleMemoryStore("semantic")
        self._simple_procedural = _SimpleMemoryStore("procedural")

        # 尝试使用 memory/ 包的完整实现
        if not self._try_load_full_memory():
            logger.info(
                "MemorySystem 使用简化版后端 / using simplified memory backend."
            )

    # ------------------------------------------------------------------
    # 向后兼容属性 / Backward-compatible properties
    # ------------------------------------------------------------------

    @property
    def working(self) -> Any:
        """工作记忆引用 / Working memory reference. 向后兼容。

        简化模式下返回后备存储而非 None，保证 agent.run() 可用。
        Neocortex 模式下返回适配器(store/retrieve/clear 统一接口)。
        Returns the fallback store in simple mode, an adapter in neocortex mode.
        """
        if self.neocortex is None:
            return self._simple_working
        nc = self.neocortex

        def _store(content: Any, metadata: Optional[Dict[str, Any]], importance: float) -> bool:
            tags = (metadata or {}).get("tags") or [str((metadata or {}).get("type", "stored"))]
            return nc.think(str(content), source="agent", tags=tags)

        def _retrieve(query: str, k: int) -> List[Any]:
            from types import SimpleNamespace
            text = nc.working.recall()
            return [SimpleNamespace(content=text)] if text else []

        return _MemoryAdapter(nc.working, _store, _retrieve, lambda: nc.working.forget())

    @property
    def episodic(self) -> Any:
        """情景记忆引用 / Episodic memory reference. 向后兼容。"""
        if self.neocortex is None:
            return self._simple_episodic
        nc = self.neocortex
        ep_type = self._EpisodeType

        def _store(content: Any, metadata: Optional[Dict[str, Any]], importance: float) -> Any:
            md = metadata or {}
            etype = ep_type.LEARNING if md.get("type") == "learning" else ep_type.OTHER
            return nc.observe(
                str(content), episode_type=etype,
                scenario=str(md.get("scenario", ""))[:30],
                importance=importance, tags=md.get("tags", []),
            )

        def _retrieve(query: str, k: int) -> List[Any]:
            return nc.episodic.recall(query, top_k=k)

        def _clear() -> None:
            if hasattr(nc.episodic, "clear"):
                nc.episodic.clear()

        return _MemoryAdapter(nc.episodic, _store, _retrieve, _clear)

    @property
    def semantic(self) -> Any:
        """语义记忆引用 / Semantic memory reference. 向后兼容。"""
        if self.neocortex is None:
            return self._simple_semantic
        nc = self.neocortex

        def _store(content: Any, metadata: Optional[Dict[str, Any]], importance: float) -> Any:
            md = metadata or {}
            title = str(md.get("title", str(content)[:60]))
            return nc.learn(
                title=title, content=str(content),
                confidence=importance, source=str(md.get("source", "agent")),
            )

        def _retrieve(query: str, k: int) -> List[Any]:
            from types import SimpleNamespace
            results = nc.semantic.query(query, top_k=k)
            return [
                SimpleNamespace(content=f"{node.title}: {node.content}", score=score)
                for node, score in results
            ]

        def _clear() -> None:
            if hasattr(nc.semantic, "clear"):
                nc.semantic.clear()

        return _MemoryAdapter(nc.semantic, _store, _retrieve, _clear)

    @property
    def procedural(self) -> Any:
        """程序记忆引用 / Procedural memory reference. 向后兼容。"""
        if self.neocortex is None:
            return self._simple_procedural
        nc = self.neocortex

        def _store(content: Any, metadata: Optional[Dict[str, Any]], importance: float) -> Any:
            md = metadata or {}
            name = str(md.get("name", str(content)[:60]))
            return nc.practice(name=name, description=str(content), steps=md.get("steps"))

        def _retrieve(query: str, k: int) -> List[Any]:
            from types import SimpleNamespace
            skills = nc.procedural.recommend_skills(query, top_k=k)
            return [
                SimpleNamespace(content=f"{s.name}: {s.description}")
                for s in skills
            ]

        def _clear() -> None:
            if hasattr(nc.procedural, "clear"):
                nc.procedural.clear()

        return _MemoryAdapter(nc.procedural, _store, _retrieve, _clear)

    @property
    def backend_name(self) -> str:
        """使用的后端名称 / Backend name used."""
        return self._backend

    def _try_load_full_memory(self) -> bool:
        """
        尝试加载 memory/ 包的完整 Neocortex 实现。
        如果失败，保持简化模式。
        """
        try:
            # 导入 memory/ 包的完整实现
            from memory import Neocortex, SubconsciousLoop, EpisodeType

            # 配置
            mem_cfg = self._config.get("memory", {}) if self._config else {}
            enabled = mem_cfg.get("enabled", True) if isinstance(mem_cfg, dict) else True
            backend_name = mem_cfg.get("backend", "in_memory") if isinstance(mem_cfg, dict) else "in_memory"

            if not enabled:
                logger.info("记忆系统已禁用 / Memory system disabled by config.")
                return False

            # 后端兼容性检查（简化版：只支持 in_memory）
            if backend_name != "in_memory":
                logger.warning(
                    "Memory backend '%s' 未在本实现中验证，回退到 in_memory / "
                    "Backend '%s' not verified, falling back to in_memory.",
                    backend_name, backend_name,
                )

            # 创建 Neocortex
            self.neocortex = Neocortex(
                name="NonullNeocortex",
            )
            self._backend = "neocortex"
            self._EpisodeType = EpisodeType

            # 可选：启动 SubconsciousLoop
            subconscious_enabled = mem_cfg.get("subconscious", True) if isinstance(mem_cfg, dict) else True
            if subconscious_enabled:
                self.subconscious = SubconsciousLoop(
                    neocortex=self.neocortex,
                    interval_seconds=60.0,  # 每60秒检查一次
                    auto_start=True,
                )
                logger.info("SubconsciousLoop 已启动（后台洞察生成）/ SubconsciousLoop started.")

            logger.info(
                "MemorySystem 使用完整 Neocortex 后端 / using full Neocortex backend."
            )
            return True

        except ImportError as e:
            logger.warning(
                "memory/ 包导入失败，使用简化版 / memory/ import failed (%s), "
                "falling back to simple backend.", e
            )
            return False
        except Exception as e:
            logger.warning(
                "MemorySystem 初始化失败，使用简化版 / init failed (%s), "
                "falling back to simple backend.", e
            )
            return False

    # ------------------------------------------------------------------
    # 存储 / Store
    # ------------------------------------------------------------------

    def store(
        self,
        content: Any,
        memory_type: str = "working",
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
    ) -> Optional[str]:
        """
        存储到指定记忆类型 / Store to specified memory type.

        Args:
            content:     记忆内容
            memory_type: working | episodic | semantic | procedural
            metadata:    元数据
            importance:  重要性 (0-1)

        Returns:
            条目 ID 或 None
        """
        if self.neocortex is None:
            # 简化模式:写入后备存储 / simple mode: write to fallback stores
            store_map = {
                "working": self._simple_working,
                "episodic": self._simple_episodic,
                "semantic": self._simple_semantic,
                "procedural": self._simple_procedural,
            }
            target = store_map.get(memory_type)
            if target is None:
                logger.warning("未知记忆类型 / Unknown memory type: %s", memory_type)
                return None
            target.store(content, metadata=metadata, importance=importance)
            return memory_type

        try:
            if memory_type == "working":
                self.neocortex.think(str(content), source="agent", tags=["stored"])
                return "working"
            elif memory_type == "episodic":
                ep_type = metadata.get("type") if metadata else None
                tags = metadata.get("tags", []) if metadata else []
                scenario = metadata.get("scenario", "") if metadata else ""
                self.neocortex.observe(
                    str(content),
                    episode_type=self._EpisodeType.LEARNING if ep_type == "learning" else self._EpisodeType.OTHER,
                    scenario=scenario,
                    importance=importance,
                    tags=tags,
                )
                return "episodic"
            elif memory_type == "semantic":
                title = metadata.get("title", str(content)[:60]) if metadata else str(content)[:60]
                self.neocortex.learn(
                    title=title,
                    content=str(content),
                    confidence=importance,
                    source=metadata.get("source", "agent") if metadata else "agent",
                    tags=metadata.get("tags", []) if metadata else [],
                )
                return "semantic"
            elif memory_type == "procedural":
                name = metadata.get("name", str(content)[:60]) if metadata else str(content)[:60]
                steps = metadata.get("steps") if metadata else None
                self.neocortex.practice(
                    name=name,
                    description=str(content),
                    steps=steps,
                )
                return "procedural"
            else:
                logger.warning("未知记忆类型 / Unknown memory type: %s", memory_type)
                return None
        except Exception as e:
            logger.error("记忆存储失败 / Memory store failed: %s", e)
            return None

    def store_experience(
        self,
        task: str,
        action: str,
        result: Any,
        success: bool,
    ) -> Optional[str]:
        """
        存储一次经验（情景记忆 + 工作记忆）/ Store an experience.

        失败的经验重要性更高。
        Failed experiences are stored with higher importance.

        结果可能是 dict (如 {'status':..., 'output':...}); str(dict)[:500] 会在
        截断时破坏 repr, 使后续召回无法重新解析, 把发现文本埋在 'status'/'output'
        键名后。这里先抽取真正的文本字段再截断, 保证存进去的就是可读的发现。
        The result may be a dict (e.g. {'status':..., 'output':...}); str(dict)[:500]
        corrupts the repr at truncation so later recall cannot re-parse it, burying
        the finding behind key names. We flatten to the real text field first.
        """
        def _flatten_result(r: Any, limit: int = 600) -> str:
            # 递归抽 dict 里的真正文本 (output/content/text/message), 避免存 dict-repr
            cur = r
            for _ in range(3):
                if isinstance(cur, dict):
                    nxt = (
                        cur.get("output")
                        or cur.get("content")
                        or cur.get("text")
                        or cur.get("message")
                        or cur.get("result")
                    )
                    if nxt is None or nxt is cur:
                        break
                    cur = nxt
                else:
                    break
            return str(cur)[:limit]

        content = {
            "task": task,
            "action": action,
            "result": _flatten_result(result),
            "success": success,
        }
        importance = 0.9 if not success else 0.3

        # 同时存入工作记忆和情景记忆
        if self.neocortex is None:
            # 简化模式:写入后备存储 / simple mode: fallback stores
            self._simple_working.store(
                f"[Experience] {task} -> {action} -> {'OK' if success else 'FAIL'}",
                metadata={"type": "experience", "success": success},
                importance=importance,
            )
            self._simple_episodic.store(
                content, metadata={"type": "experience", "success": success},
                importance=importance,
            )
            return "experience"

        self.neocortex.think(
            f"[Experience] {task} -> {action} -> {'OK' if success else 'FAIL'}: {content['result'][:100]}",
            source="experience",
            tags=["experience", "success" if success else "failure"],
        )
        self.neocortex.observe(
            content=str(content),
            episode_type=self._EpisodeType.LEARNING,
            scenario=task[:30],
            importance=importance,
            tags=["experience", f"{'success' if success else 'failure'}", task[:20]],
        )
        return "experience"

    def consolidate(self) -> int:
        """
        记忆巩固：工作记忆 → 情景记忆 → 语义知识。
        Consolidate: working → episodic → semantic.
        """
        if self.neocortex is None:
            return 0
        try:
            stats = self.neocortex.consolidate()
            return sum(stats.values())
        except Exception as e:
            logger.warning("记忆巩固失败 / Consolidation failed: %s", e)
            return 0

    def prune(self) -> Dict[str, int]:
        """清理过期记忆。/ Prune expired memories."""
        if self.neocortex is None:
            return {"episodic": 0}
        try:
            return self.neocortex.prune(target_ratio=0.7)
        except Exception as e:
            logger.warning("记忆裁剪失败 / Pruning failed: %s", e)
            return {"episodic": 0, "working": 0, "semantic": 0}

    def get_context(self, query: str = "", k: int = 3) -> Dict[str, List[Any]]:
        """
        获取所有记忆类型的上下文 / Get context from all memory types.

        使用 Neocortex 的跨记忆查询，返回结构化上下文。
        Uses Neocortex cross-memory query for structured context.
        """
        if self.neocortex is None:
            # 简化模式:从后备存储检索 / simple mode: retrieve from fallback stores
            return {
                "working": self._simple_working.retrieve(query, k=k),
                "episodic": self._simple_episodic.retrieve(query, k=k),
                "semantic": self._simple_semantic.retrieve(query, k=k),
                "procedural": self._simple_procedural.retrieve(query, k=k),
            }

        try:
            from types import SimpleNamespace

            from memory import MemoryQuery

            results = self.neocortex.query(
                MemoryQuery(
                    text=query,
                    top_k_per_source=k,
                    max_total=k * 4,
                    include_working=True,
                    include_episodic=True,
                    include_semantic=True,
                    include_procedural=True,
                )
            )

            # 按来源分组。统一包装为带 .content 属性的对象,
            # 与简化模式的 _SimpleMemoryEntry 接口一致（调用方用 e.content）。
            # Group by source. Wrap in attribute-style objects so both
            # backends expose `.content` uniformly to callers.
            grouped = {
                "working": [],
                "episodic": [],
                "semantic": [],
                "procedural": [],
            }
            for r in results:
                source = r.source.value
                if source in grouped:
                    grouped[source].append(SimpleNamespace(
                        content=r.content,
                        score=r.score.combined if hasattr(r.score, "combined") else 0,
                        tags=r.tags,
                        metadata=r.metadata,
                    ))

            # recency 兜底: 语义召回稀疏 (< k) 时补充最近的 episodic。
            # n-gram embedding 对抽象 query (如 "上次发现了什么 bug") 召回弱,
            # 此举保证最近的 learning 经验总能到 agent 眼前, 即使词面重叠低。
            # Recency fallback: top up sparse semantic recall with the most recent
            # episodes so the latest learning always reaches the agent's prompt.
            if len(grouped["episodic"]) < k:
                try:
                    recent_eps = sorted(
                        self.neocortex.episodic.episodes.values(),
                        key=lambda e: getattr(e, "timestamp", 0),
                        reverse=True,
                    )
                    seen = {id(e.content) for e in grouped["episodic"]}
                    for ep in recent_eps:
                        if len(grouped["episodic"]) >= k:
                            break
                        if id(ep.content) in seen:
                            continue
                        grouped["episodic"].append(SimpleNamespace(
                            content=ep.content,
                            score=0.0,
                            tags=getattr(ep, "tags", []),
                            metadata=getattr(ep, "metadata", {}),
                        ))
                        seen.add(id(ep.content))
                except Exception:
                    pass
            return grouped
        except Exception as e:
            logger.warning("上下文获取失败 / Context fetch failed: %s", e)
            return {
                "working": [],
                "episodic": [],
                "semantic": [],
                "procedural": [],
            }

    def get_context_for_llm(self, query_text: str, max_tokens: int = 4000) -> str:
        """
        为 LLM 提示构建结构化记忆上下文 / Build structured memory context for LLM prompts.

        这是记忆系统最核心的升级——在 plan/reason/reflect 阶段自动注入记忆。
        This is the key upgrade — auto-inject memory context during plan/reason/reflect.
        """
        if self.neocortex is None:
            return ""
        try:
            return self.neocortex.build_context(
                query_text=query_text,
                max_tokens=max_tokens,
                query_config={"include_skills": True},
            )
        except Exception as e:
            logger.warning("LLM 上下文构建失败 / LLM context build failed: %s", e)
            return ""

    def clear_all(self) -> None:
        """清空所有记忆 / Clear all memory."""
        if self.neocortex is None:
            # 简化模式:清空后备存储 / simple mode: clear fallback stores
            self._simple_working.clear()
            self._simple_episodic.clear()
            self._simple_semantic.clear()
            self._simple_procedural.clear()
            return
        try:
            if self.working is not None and hasattr(self.working, "context_window"):
                self.working.context_window.clear()
            if self.episodic is not None and hasattr(self.episodic, "clear"):
                self.episodic.clear()
            if self.semantic is not None and hasattr(self.semantic, "clear"):
                self.semantic.clear()
            if self.procedural is not None and hasattr(self.procedural, "clear"):
                self.procedural.clear()
        except Exception as e:
            logger.warning("记忆清空失败 / Clear failed: %s", e)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 / Serialize to dictionary."""
        if self.neocortex is None:
            return {"backend": "none", "stats": {}}
        try:
            return self.neocortex.to_dict()
        except Exception as e:
            logger.warning("记忆序列化失败 / Serialization failed: %s", e)
            return {"backend": "neocortex", "error": str(e)}

    # ------------------------------------------------------------------
    # 统计 / Statistics
    # ------------------------------------------------------------------

    def update_stats(self) -> MemoryStats:
        """更新记忆统计 / Update memory statistics."""
        s = self._stats
        if self.neocortex is not None:
            stats = self.neocortex.stats()
            s.working_items = stats.get("working", {}).get("context_window", {}).get("item_count", 0)
            s.episodic_episodes = stats.get("episodic", {}).get("total_episodes", 0)
            s.semantic_nodes = stats.get("semantic", {}).get("total_nodes", 0)
            s.procedural_skills = stats.get("procedural", {}).get("total_skills", 0)
            s.total_tokens = stats.get("capacity", {}).get("total_tokens", 0)
            s.token_usage_pct = stats.get("capacity", {}).get("usage_ratio", 0) * 100
        else:
            # 简化模式:统计后备存储 / simple mode: count fallback stores
            s.working_items = len(self._simple_working)
            s.episodic_episodes = len(self._simple_episodic)
            s.semantic_nodes = len(self._simple_semantic)
            s.procedural_skills = len(self._simple_procedural)
        if self.subconscious is not None:
            ss = self.subconscious.stats()
            s.subconscious_running = ss.get("running", False)
            s.subconscious_cycles = ss.get("cycle_count", 0)
            s.subconscious_insights = ss.get("total_insights_generated", 0)
        return s

    def stats(self) -> Dict[str, Any]:
        """获取完整统计 / Get full statistics."""
        return self.update_stats().to_dict()

    def close(self) -> None:
        """停止后台资源 (SubconsciousLoop 守护线程) / Stop background resources.

        每个启用了完整记忆的实例会启动一个 SubconsciousLoop 守护线程 (默认 60s
        轮询)。若不停止, 重复实例化 (测试/CLI 循环/多 agent 池) 会累积泄漏线程。
        Nonull.close()/__aexit__ 调用本方法。幂等, 可安全多次调用。

        Stops the SubconsciousLoop daemon thread so repeated instantiation does
        not leak threads for the process lifetime. Idempotent.
        """
        if self.subconscious is not None:
            try:
                self.subconscious.stop(wait=False)
            except Exception:
                logger.debug("SubconsciousLoop stop 失败", exc_info=True)

    def prune(self, target_ratio: float = 0.7) -> int:
        """裁剪记忆防无界增长 / Prune memory to prevent unbounded growth.

        在长会话里, 每个 run() 会 store_experience + task_start episode, Neocortex
        记忆会持续增长。本方法委托给 neocortex.prune (Ebbinghaus 遗忘 + 低重要性
        淘汰); 简化模式无操作。返回裁剪的条目数。

        Delegates to neocortex.prune (decay + low-importance eviction). No-op in
        simple mode. Returns the number of pruned entries.
        """
        if self.neocortex is not None and hasattr(self.neocortex, "prune"):
            try:
                pruned = self.neocortex.prune(target_ratio=target_ratio)
            except TypeError:
                # neocortex.prune 可能不接受 target_ratio
                try:
                    pruned = self.neocortex.prune()
                except Exception:
                    logger.debug("neocortex.prune 失败", exc_info=True)
                    return 0
            except Exception:
                logger.debug("neocortex.prune 失败", exc_info=True)
                return 0
            # neocortex.prune 返回 {layer: count} dict; 求和总数
            if isinstance(pruned, dict):
                return sum(int(v) for v in pruned.values())
            return int(pruned or 0)
        return 0

