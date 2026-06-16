"""
原生本地语义嵌入 / Native local semantic embedder.

完全零外部依赖 (仅 numpy + 标准库) 的本地语义向量嵌入, 用于记忆语义检索召回。
相比项目原有的纯字符 n-gram 哈希嵌入 (EmbeddingProvider, 无语义), 本模块通过
以下手段把"字面匹配"提升到"语义近似":

  1. **多粒度特征**: 字符 n-gram(2/3) + 词 unigram + 词 bigram + 词干, 兼顾
     拼写鲁棒性 (字符级) 与语义 (词级)。
  2. **TF-IDF 加权**: 在语料上学习 IDF, 高频虚词 (the/的/是) 权重降低, 信息量
     大的词权重升高 —— 这是"语义区分度"的核心。未 fit 时退化为 log 词频。
  3. **轻量词干化**: 英文去常见后缀 (-ing/-ed/-s/-ly), 让 run/running/runs 共享
     特征维度; 中文按字 + 二元词。
  4. **符号哈希降维 (signed hashing)**: 每个特征哈希到维度时带 ±1 符号, 减少
     哈希冲突的系统性偏差 (feature hashing trick)。

接口与原 EmbeddingProvider 完全兼容 (encode/similarity), 可直接作为
`embedder=` 注入 Neocortex/EpisodicMemory/SemanticMemory 等, 零侵入升级。

能力边界 (诚实说明):
  本模块是"词汇/词形 + TF-IDF"的轻量语义近似, 擅长查询与文档有**词汇或词形
  重叠**的召回 (含错字/词形变化鲁棒)。对**纯概念同义** (查询与文档零字面重叠,
  如 "户外活动" ↔ "爬山看日出") 能力有限 —— 那需要训练过的神经嵌入
  (sentence-transformers / BGE 等)。零外部依赖与真神经语义不可兼得; 若需后者,
  本类接口兼容, 可直接换成 `embedder=SentenceTransformerWrapper(...)`。

@module: memory.local_embedder
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional

import numpy as np

# 常见英文停用词 (降权, 不删除 —— 仍保留少量信号)
_STOPWORDS_EN = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be",
    "to", "of", "in", "on", "at", "for", "with", "as", "by", "this", "that",
    "it", "its", "i", "you", "he", "she", "we", "they", "do", "does", "did",
}
# 常见中文虚词
_STOPWORDS_ZH = {"的", "了", "是", "在", "和", "与", "或", "也", "都", "就",
                 "我", "你", "他", "她", "它", "这", "那", "个", "把", "被"}

# 英文常见后缀 (轻量词干化)
_SUFFIXES = ("ing", "edly", "edly", "ed", "ly", "es", "s", "ment", "tion", "er")


def _stem_en(word: str) -> str:
    """极简英文词干化 (去常见后缀)。不追求语言学正确, 只为让同根词共享特征。"""
    w = word
    for suf in _SUFFIXES:
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _is_cjk(ch: str) -> bool:
    return "一" <= ch <= "鿿"


def _tokenize(text: str) -> List[str]:
    """混合中英分词: 英文按词 + 词干; 中文按单字 + 相邻二元。"""
    text = text.lower()
    tokens: List[str] = []
    # 英文/数字词
    for w in re.findall(r"[a-z0-9]+", text):
        if len(w) > 1:
            tokens.append(_stem_en(w))
    # 中文: 单字 + 二元
    cjk = [ch for ch in text if _is_cjk(ch)]
    tokens.extend(cjk)
    for i in range(len(cjk) - 1):
        tokens.append(cjk[i] + cjk[i + 1])
    return tokens


def _char_ngrams(text: str, n: int) -> Iterable[str]:
    t = re.sub(r"\s+", " ", text.lower())
    for i in range(len(t) - n + 1):
        yield t[i : i + n]


def _signed_hash(feature: str, dim: int) -> tuple[int, float]:
    """符号哈希: 返回 (维度索引, ±1 符号)。减少哈希冲突的系统偏差。

    用 md5 而非内置 hash(): Python 对 str 的 hash() 受 PYTHONHASHSEED 随机化,
    会导致同一文本在不同进程产生不同向量 —— 跨进程持久化/检索就失效了。
    md5 是确定性的, 保证可复现 (这里只用作特征散列, 非加密用途)。
    """
    h = int.from_bytes(hashlib.md5(feature.encode("utf-8")).digest()[:8], "big")
    idx = (h & 0x7FFFFFFF) % dim
    sign = 1.0 if (h >> 63) & 1 else -1.0
    return idx, sign


class LocalSemanticEmbedder:
    """原生本地语义嵌入器 / Native local semantic embedder (numpy-only).

    接口兼容原 EmbeddingProvider:
        embedder = LocalSemanticEmbedder(dim=512)
        embedder.fit(corpus)          # 可选: 学习 IDF 提升语义区分度
        vec = embedder.encode(text)   # -> np.ndarray[dim]
        sim = embedder.similarity(a, b)  # -> float 0..1

    未调用 fit() 也能用 (IDF 退化为 log 词频), 但 fit 后语义召回明显更好。
    """

    def __init__(self, dim: int = 512, use_char_ngrams: bool = True,
                 use_cooccurrence: bool = False):
        """
        use_cooccurrence: 共现扩散增强。默认 **关闭** —— 共现统计需要大语料才可靠,
          小语料下噪声会污染基础语义召回 (实测会让相关性反转)。仅在有较大同主题
          语料 (数百+文档) 时开启可能增益概念关联召回。基础 TF-IDF 召回已足够稳健。
        """
        self.dim = dim
        self.use_char_ngrams = use_char_ngrams
        self.use_cooccurrence = use_cooccurrence
        self._idf: Dict[str, float] = {}
        self._n_docs = 0
        self._fitted = False
        # 共现增强: token -> [(相关token, 权重), ...] (fit 时学习)
        self._cooc: Dict[str, List[tuple]] = {}

    # ── 训练 IDF / Fit ───────────────────────────────────────────

    def fit(self, corpus: Iterable[str]) -> "LocalSemanticEmbedder":
        """在语料上学习 IDF + 词共现 / Learn IDF + co-occurrence from a corpus.

        IDF(t) = log((N + 1) / (df(t) + 1)) + 1 —— 高频词降权。

        共现增强 (零依赖的"概念关联"近似): 统计哪些词常出现在同一文档, 用
        PMI-ish 权重记录每个词的 top 相关词。encode 时把相关词的信号按权重
        "扩散"到向量, 让 "散步" 和 "户外"(若常共现) 即使不同字面也能靠近 ——
        这是纯字面匹配做不到、又无需神经网络的概念关联召回。
        """
        df: Counter = Counter()
        cooc: Dict[str, Counter] = defaultdict(Counter)
        n = 0
        corpus_list = list(corpus)
        for doc in corpus_list:
            n += 1
            toks = list(set(_tokenize(doc)))
            for tok in toks:
                df[tok] += 1
            # 同文档内词两两共现
            if self.use_cooccurrence:
                for i in range(len(toks)):
                    for j in range(i + 1, len(toks)):
                        cooc[toks[i]][toks[j]] += 1
                        cooc[toks[j]][toks[i]] += 1
        self._n_docs = n
        self._idf = {
            tok: math.log((n + 1) / (cnt + 1)) + 1.0 for tok, cnt in df.items()
        }
        # 为每个词保留 top-5 共现词 (PMI 加权: 共现频次 / sqrt(df_a·df_b))
        self._cooc = {}
        if self.use_cooccurrence:
            for tok, partners in cooc.items():
                scored = []
                for other, c in partners.items():
                    denom = math.sqrt(max(1, df[tok]) * max(1, df[other]))
                    pmi = c / denom
                    if pmi > 0.3:  # 只保留强关联, 小语料下阈值要高, 避免噪声扩散
                        scored.append((other, pmi))
                scored.sort(key=lambda x: x[1], reverse=True)
                if scored:
                    self._cooc[tok] = scored[:5]
        self._fitted = n > 0
        return self

    def _idf_weight(self, token: str, local_count: int) -> float:
        """token 权重 = TF(log) × IDF。未 fit 时 IDF 退化为 1。"""
        tf = 1.0 + math.log(local_count)
        if self._fitted:
            idf = self._idf.get(token)
            if idf is None:
                # 未见过的词: 给中高 IDF (视为稀有 → 有信息量)
                idf = math.log((self._n_docs + 1) / 1.0) + 1.0
            return tf * idf
        # 未 fit: 词级特征给更高基础权重, 停用词降权
        base = 0.4 if (token in _STOPWORDS_EN or token in _STOPWORDS_ZH) else 2.0
        return tf * base

    # ── 编码 / Encode ────────────────────────────────────────────

    def encode(self, text: str) -> np.ndarray:
        """文本 → 归一化语义向量 / Text → L2-normalized semantic vector."""
        vec = np.zeros(self.dim, dtype=np.float32)
        if not text:
            return vec

        # 1) 词级特征 (TF-IDF 加权, 语义主力)
        tokens = _tokenize(text)
        tok_counts = Counter(tokens)
        for tok, cnt in tok_counts.items():
            w = self._idf_weight(tok, cnt)
            idx, sign = _signed_hash(f"w::{tok}", self.dim)
            vec[idx] += sign * w
            # 1b) 共现扩散: 把该词的相关词信号按权重加入 (零依赖概念关联)。
            #     保守: 仅 top-2 相关词 + 0.2 衰减 —— 共现在小语料上噪声大, 过强会
            #     污染基础语义 (实测 0.5 衰减会让相关性反转), 弱扩散才稳健增益。
            if self.use_cooccurrence and self._cooc:
                for other, pmi in self._cooc.get(tok, ())[:2]:  # 仅 top-2 相关词
                    o_idx, o_sign = _signed_hash(f"w::{other}", self.dim)
                    vec[o_idx] += o_sign * w * pmi * 0.2  # 弱扩散

        # 2) 词 bigram (捕捉局部搭配 / 短语语义)
        for i in range(len(tokens) - 1):
            bg = f"{tokens[i]}_{tokens[i+1]}"
            idx, sign = _signed_hash(f"bg::{bg}", self.dim)
            vec[idx] += sign * 1.2

        # 3) 字符 n-gram (拼写鲁棒性, 处理错字/词形)
        if self.use_char_ngrams:
            for n in (2, 3):
                for g in _char_ngrams(text, n):
                    idx, sign = _signed_hash(f"c{n}::{g}", self.dim)
                    vec[idx] += sign * (0.3 if n == 2 else 0.5)

        # L2 归一化 → 余弦相似度可用点积
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def similarity(self, a: str, b: str) -> float:
        """两文本余弦相似度 (0..1, clip 负值) / Cosine similarity, clipped to 0..1."""
        va = self.encode(a)
        vb = self.encode(b)
        sim = float(np.dot(va, vb))
        return max(0.0, sim)  # 符号哈希可能产生负点积, clip 到 0

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """批量编码 → [n, dim] 矩阵。"""
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.vstack([self.encode(t) for t in texts])

    def __repr__(self) -> str:
        return (f"<LocalSemanticEmbedder dim={self.dim} "
                f"fitted={self._fitted} vocab={len(self._idf)}>")
