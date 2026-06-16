"""
本地语义检索索引 / Local semantic retrieval index.

把 LocalSemanticEmbedder 包装成一个可增删查的内存向量索引, 提供完整的
本地语义检索召回链路: add → (fit) → search。零外部依赖 (numpy only),
无需 FAISS / Chroma / Milvus / 任何向量数据库或外部 embedding 服务。

用于记忆语义召回、技能检索、知识查询等场景。

  index = SemanticIndex(dim=512)
  index.add("doc1", "如何实现一个线程安全的队列")
  index.add("doc2", "今天天气不错适合出门")
  index.fit()                          # 学习 IDF (可选但推荐)
  hits = index.search("并发安全的数据结构", k=3)
  # -> [SearchHit(id="doc1", score=0.7, ...), ...]

@module: memory.semantic_index
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .local_embedder import LocalSemanticEmbedder

logger = logging.getLogger("Nonull.memory.semantic_index")


@dataclass
class SearchHit:
    """检索命中 / A retrieval hit."""
    id: str
    score: float
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "score": round(self.score, 4),
                "text": self.text[:200], "metadata": self.metadata}


class SemanticIndex:
    """本地语义向量索引 / In-memory local semantic vector index.

    完整召回链路, 无外部依赖:
      - add/add_batch: 加文档 (文本 + 可选 metadata)
      - fit: 在已加入的文档上学习 IDF (提升语义区分度)
      - search: 语义检索 top-k (余弦相似度)
      - remove/clear: 删除/清空
      - save_dict/load_dict: 持久化 (向量 + 文本 + IDF)

    线程安全性: 调用方负责 (与项目其他内存结构一致, 单 agent 顺序访问)。
    """

    def __init__(self, dim: int = 512, embedder: Optional[LocalSemanticEmbedder] = None):
        self.dim = dim
        self.embedder = embedder or LocalSemanticEmbedder(dim=dim)
        self._ids: List[str] = []
        self._texts: Dict[str, str] = {}
        self._meta: Dict[str, Dict[str, Any]] = {}
        self._vectors: Dict[str, np.ndarray] = {}
        self._dirty = False  # 加入新文档后需重新 encode (fit 改变了 IDF)

    # ── 增 / Add ─────────────────────────────────────────────────

    def add(self, doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """加入/更新一个文档。"""
        if doc_id not in self._texts:
            self._ids.append(doc_id)
        self._texts[doc_id] = text
        self._meta[doc_id] = metadata or {}
        self._vectors[doc_id] = self.embedder.encode(text)

    def add_batch(self, items: List[Tuple[str, str]]) -> None:
        """批量加入 [(id, text), ...]。"""
        for doc_id, text in items:
            self.add(doc_id, text)

    # ── 学习 IDF / Fit ───────────────────────────────────────────

    def fit(self) -> "SemanticIndex":
        """在当前所有文档上学习 IDF, 然后重新编码所有向量。

        这是语义质量的关键一步: fit 后高频虚词降权、信息词升权, 召回更"懂语义"。
        加入新文档后建议重新 fit (或定期 fit)。
        """
        if not self._texts:
            return self
        self.embedder.fit(self._texts.values())
        # IDF 变了, 重新编码全部向量
        for doc_id, text in self._texts.items():
            self._vectors[doc_id] = self.embedder.encode(text)
        logger.info("SemanticIndex.fit: %d 文档, embedder=%r", len(self._texts), self.embedder)
        return self

    # ── 查 / Search ──────────────────────────────────────────────

    def search(self, query: str, k: int = 5, min_score: float = 0.0) -> List[SearchHit]:
        """语义检索 top-k / Semantic top-k retrieval (cosine similarity)."""
        if not self._ids:
            return []
        qv = self.embedder.encode(query)
        scored: List[Tuple[str, float]] = []
        for doc_id in self._ids:
            v = self._vectors.get(doc_id)
            if v is None:
                continue
            score = float(np.dot(qv, v))
            if score >= min_score:
                scored.append((doc_id, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            SearchHit(id=doc_id, score=max(0.0, score),
                      text=self._texts[doc_id], metadata=self._meta.get(doc_id, {}))
            for doc_id, score in scored[:k]
        ]

    # ── 删 / Remove ──────────────────────────────────────────────

    def remove(self, doc_id: str) -> bool:
        if doc_id not in self._texts:
            return False
        self._ids.remove(doc_id)
        self._texts.pop(doc_id, None)
        self._meta.pop(doc_id, None)
        self._vectors.pop(doc_id, None)
        return True

    def clear(self) -> None:
        self._ids.clear()
        self._texts.clear()
        self._meta.clear()
        self._vectors.clear()

    def __len__(self) -> int:
        return len(self._ids)

    # ── 持久化 / Persistence ─────────────────────────────────────

    def save_dict(self) -> Dict[str, Any]:
        """导出为可 JSON 序列化的 dict (向量转 list)。"""
        return {
            "dim": self.dim,
            "ids": list(self._ids),
            "texts": dict(self._texts),
            "meta": dict(self._meta),
            "idf": dict(self.embedder._idf),
            "cooc": {k: [list(p) for p in v] for k, v in self.embedder._cooc.items()},
            "n_docs": self.embedder._n_docs,
            "fitted": self.embedder._fitted,
        }

    @classmethod
    def load_dict(cls, data: Dict[str, Any]) -> "SemanticIndex":
        """从 save_dict 的输出重建索引 (重新编码向量, 不存原始向量省空间)。"""
        idx = cls(dim=int(data.get("dim", 512)))
        idx.embedder._idf = dict(data.get("idf", {}))
        idx.embedder._cooc = {
            k: [tuple(p) for p in v] for k, v in data.get("cooc", {}).items()
        }
        idx.embedder._n_docs = int(data.get("n_docs", 0))
        idx.embedder._fitted = bool(data.get("fitted", False))
        for doc_id in data.get("ids", []):
            text = data["texts"].get(doc_id, "")
            idx.add(doc_id, text, data.get("meta", {}).get(doc_id, {}))
        return idx

    def __repr__(self) -> str:
        return f"<SemanticIndex docs={len(self._ids)} dim={self.dim} embedder={self.embedder!r}>"
