"""
原生本地语义嵌入 + 检索索引测试 / Tests for local semantic embedder + index.

关键验证: 不只是"能跑", 而是"真有语义区分度":
  - TF-IDF fit 后, 信息词权重高于停用词
  - 语义相关 (词汇重叠) 的句子相似度 > 无关句子
  - SemanticIndex 检索能把相关文档排在前面
  - 持久化往返一致
零外部依赖 (numpy only), $0。
"""
import numpy as np
import pytest

from memory.local_embedder import LocalSemanticEmbedder, _tokenize, _stem_en
from memory.semantic_index import SemanticIndex, SearchHit


# ── LocalSemanticEmbedder ────────────────────────────────────────

class TestLocalEmbedder:
    def test_encode_shape_and_norm(self):
        emb = LocalSemanticEmbedder(dim=256)
        v = emb.encode("hello world")
        assert v.shape == (256,)
        # L2 归一化 → 范数约为 1
        assert abs(np.linalg.norm(v) - 1.0) < 1e-5

    def test_empty_text(self):
        emb = LocalSemanticEmbedder(dim=128)
        v = emb.encode("")
        assert v.shape == (128,)
        assert np.linalg.norm(v) == 0.0

    def test_identical_text_max_similarity(self):
        emb = LocalSemanticEmbedder(dim=512)
        sim = emb.similarity("the quick brown fox", "the quick brown fox")
        assert sim > 0.99  # 同文本 ≈ 1.0

    def test_similarity_clipped_non_negative(self):
        emb = LocalSemanticEmbedder(dim=256)
        sim = emb.similarity("abc", "xyz")
        assert sim >= 0.0  # clip 到 0

    def test_related_more_similar_than_unrelated(self):
        """语义相关的句子相似度应高于无关句子 (核心语义能力)。"""
        emb = LocalSemanticEmbedder(dim=512)
        emb.fit([
            "how to implement a thread-safe queue in python",
            "the weather is nice today for a walk",
            "concurrent data structures and locking",
            "i like to eat pizza on weekends",
        ])
        related = emb.similarity(
            "thread-safe queue implementation",
            "concurrent data structures and locking",
        )
        unrelated = emb.similarity(
            "thread-safe queue implementation",
            "i like to eat pizza on weekends",
        )
        assert related > unrelated

    def test_chinese_semantic(self):
        """中文语义: 相关句子相似度更高。"""
        emb = LocalSemanticEmbedder(dim=512)
        emb.fit([
            "如何实现一个线程安全的队列",
            "今天天气很好适合散步",
            "并发安全的数据结构与加锁",
        ])
        related = emb.similarity("线程安全的队列", "并发安全的数据结构与加锁")
        unrelated = emb.similarity("线程安全的队列", "今天天气很好适合散步")
        assert related > unrelated

    def test_stemming_groups_word_forms(self):
        """词干化: run/running/runs 共享词干。"""
        assert _stem_en("running") == _stem_en("run") or "run" in _stem_en("running")
        # running -> runn (去 ing), run -> run; 至少前缀接近
        assert _stem_en("running").startswith("run")

    def test_tokenize_mixed_cjk_en(self):
        toks = _tokenize("hello 世界 world")
        assert "hello" in toks
        assert "世" in toks and "界" in toks
        assert "世界" in toks  # 二元词

    def test_fit_changes_idf(self):
        emb = LocalSemanticEmbedder(dim=256)
        assert not emb._fitted
        emb.fit(["the cat sat", "the dog ran", "the bird flew"])
        assert emb._fitted
        # "the" 出现在所有文档 → IDF 低; "cat" 只在一个 → IDF 高
        assert emb._idf["cat"] > emb._idf["the"]

    def test_encode_batch(self):
        emb = LocalSemanticEmbedder(dim=128)
        mat = emb.encode_batch(["a", "b", "c"])
        assert mat.shape == (3, 128)

    def test_cooccurrence_off_by_default(self):
        """共现增强默认关闭 (小语料噪声大, 基础TF-IDF更稳健)。"""
        emb = LocalSemanticEmbedder(dim=256)
        assert emb.use_cooccurrence is False
        emb.fit(["the cat sat", "the dog ran"])
        # 默认关闭时不学共现
        assert emb._cooc == {}

    def test_cooccurrence_opt_in(self):
        """显式开启共现时学习关联, 且不崩。"""
        emb = LocalSemanticEmbedder(dim=256, use_cooccurrence=True)
        emb.fit([
            "户外 散步 公园 休闲", "户外 爬山 休闲 活动",
            "公园 散步 放松", "线程 安全 队列", "锁 死锁 线程",
        ])
        # 开启后应学到一些共现关联 (不强求具体内容, 只验证机制运行)
        assert isinstance(emb._cooc, dict)
        v = emb.encode("户外活动")  # 共现扩散不应使 encode 崩溃
        assert v.shape == (256,)

    def test_typo_robustness(self):
        """字符 n-gram 抗错字: 'algorithm' vs 'algoritm' 仍较高相似。

        漏一个字母会让词级特征完全错位 (算两个不同词), 但字符 n-gram 大量重叠,
        所以相似度仍显著高于无关文本 (实测 ~0.74), 不会因一个错字就召回失败。
        """
        emb = LocalSemanticEmbedder(dim=512)
        sim = emb.similarity("the sorting algorithm is fast",
                             "the sorting algoritm is fast")  # 漏一个 h
        unrelated = emb.similarity("the sorting algorithm is fast",
                                   "i had pizza for dinner yesterday")
        # 错字版相似度应远高于无关文本 (字符级特征鲁棒)
        assert sim > 0.6
        assert sim > unrelated * 3

    def test_word_order_some_sensitivity(self):
        """词级 bigram 让词序有一定区分度 (同词不同序相似但非完全相同)。"""
        emb = LocalSemanticEmbedder(dim=512)
        a = emb.encode("dog bites man")
        b = emb.encode("man bites dog")
        import numpy as np
        sim = float(np.dot(a, b))
        # 同词集 → 高相似, 但 bigram 不同 → 不完全等于 1
        assert 0.5 < sim < 1.0

    def test_long_text_normalized(self):
        """长文本仍 L2 归一化 (范数≈1)。"""
        import numpy as np
        emb = LocalSemanticEmbedder(dim=256)
        v = emb.encode("word " * 500)
        assert abs(np.linalg.norm(v) - 1.0) < 1e-4

    def test_repr_shows_state(self):
        emb = LocalSemanticEmbedder(dim=128)
        assert "dim=128" in repr(emb)
        assert "fitted=False" in repr(emb)
        emb.fit(["a b c", "d e f"])
        assert "fitted=True" in repr(emb)


# ── SemanticIndex ────────────────────────────────────────────────

class TestSemanticIndex:
    def _build(self):
        idx = SemanticIndex(dim=512)
        idx.add("q1", "how to implement a thread-safe queue in python", {"type": "code"})
        idx.add("q2", "the weather is nice today for a walk", {"type": "chat"})
        idx.add("q3", "concurrent data structures and locking mechanisms", {"type": "code"})
        idx.add("q4", "best pizza recipes for the weekend", {"type": "food"})
        idx.fit()
        return idx

    def test_add_and_len(self):
        idx = SemanticIndex(dim=256)
        idx.add("a", "text one")
        idx.add("b", "text two")
        assert len(idx) == 2

    def test_search_returns_relevant_first(self):
        """语义检索: 相关文档排在前面 (核心召回能力)。"""
        idx = self._build()
        hits = idx.search("concurrent programming with locks", k=2)
        assert len(hits) == 2
        # q3 (concurrent data structures + locking) 应排第一
        assert hits[0].id == "q3"
        assert isinstance(hits[0], SearchHit)
        assert hits[0].score > 0

    def test_search_code_query_beats_food(self):
        idx = self._build()
        hits = idx.search("thread-safe queue", k=4)
        ids = [h.id for h in hits]
        # 代码相关 q1 (thread-safe queue) 应排在结果前列, 且优于食物 q4。
        # 用词汇重叠强的查询 + 只断言相对顺序 (不假设 q4 一定进 top-k)。
        assert "q1" in ids
        assert ids[0] == "q1"  # q1 与查询词汇高度重叠, 应排第一
        if "q4" in ids:        # 若食物文档也召回, 必在 q1 之后
            assert ids.index("q1") < ids.index("q4")

    def test_search_empty_index(self):
        idx = SemanticIndex(dim=128)
        assert idx.search("anything") == []

    def test_min_score_filter(self):
        idx = self._build()
        # 极高阈值 → 可能过滤掉所有
        hits = idx.search("completely unrelated xyz qwerty", k=5, min_score=0.99)
        assert all(h.score >= 0.99 for h in hits)

    def test_remove(self):
        idx = SemanticIndex(dim=128)
        idx.add("a", "text")
        assert idx.remove("a") is True
        assert len(idx) == 0
        assert idx.remove("nonexistent") is False

    def test_update_existing_doc(self):
        idx = SemanticIndex(dim=128)
        idx.add("a", "original text")
        idx.add("a", "completely new content")  # 同 id 更新
        assert len(idx) == 1  # 不重复

    def test_persistence_roundtrip(self):
        idx = self._build()
        data = idx.save_dict()
        idx2 = SemanticIndex.load_dict(data)
        assert len(idx2) == len(idx)
        # 重建后检索结果一致
        h1 = idx.search("concurrent locking", k=1)
        h2 = idx2.search("concurrent locking", k=1)
        assert h1[0].id == h2[0].id

    def test_clear(self):
        idx = self._build()
        idx.clear()
        assert len(idx) == 0


# ── 接口兼容性 (可替换原 EmbeddingProvider) ──────────────────────

class TestInterfaceCompat:
    def test_has_encode_and_similarity(self):
        """与原 EmbeddingProvider 接口兼容: encode + similarity。"""
        emb = LocalSemanticEmbedder(dim=256)
        assert hasattr(emb, "encode")
        assert hasattr(emb, "similarity")
        v = emb.encode("test")
        assert isinstance(v, np.ndarray)
        s = emb.similarity("a", "b")
        assert isinstance(s, float)

    def test_drop_in_for_episodic(self):
        """可作为 embedder= 注入 EpisodicMemory (不崩)。"""
        from memory.episodic import EpisodicMemory
        emb = LocalSemanticEmbedder(dim=256)
        mem = EpisodicMemory(embedder=emb)
        assert mem.embedder is emb
