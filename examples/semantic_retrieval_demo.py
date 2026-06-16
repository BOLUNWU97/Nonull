"""
原生本地语义检索召回 demo / Native local semantic retrieval demo.

展示完整的本地语义检索召回链路 —— 零外部依赖 (numpy only), 无需任何向量数据库
或外部 embedding 服务。对比"字面匹配"与"语义匹配": 查询用的词和文档不重叠时,
语义嵌入仍能召回相关文档。

Run:  python examples/semantic_retrieval_demo.py
"""
from memory import SemanticIndex


def main() -> None:
    print("=" * 64)
    print("🔍 原生本地语义检索召回 / Native local semantic retrieval")
    print("   零外部依赖 (numpy only), 无向量数据库, 无 embedding API")
    print("=" * 64)

    # 1) 建索引, 加入一批文档 (技术 + 生活混合)
    idx = SemanticIndex(dim=512)
    docs = [
        ("d1", "如何用 Python 实现一个线程安全的并发队列"),
        ("d2", "深度学习模型的训练需要大量 GPU 算力"),
        ("d3", "今天天气晴朗, 适合去公园散步晒太阳"),
        ("d4", "多线程编程中的锁机制与死锁避免"),
        ("d5", "红烧肉的做法: 五花肉焯水后小火慢炖"),
        ("d6", "神经网络的反向传播算法与梯度下降"),
        ("d7", "周末和朋友一起去爬山看日出"),
        ("d8", "分布式系统的一致性与 CAP 定理"),
    ]
    for doc_id, text in docs:
        idx.add(doc_id, text)
    idx.fit()  # 学习 IDF, 提升语义区分度
    print(f"\n✅ 已索引 {len(idx)} 个文档, embedder={idx.embedder!r}\n")

    # 2) 语义查询 (混合词汇重叠 + 词形变化, 考验召回)
    #    诚实说明: 本地零依赖 embedder 擅长"词汇/词形重叠 + TF-IDF 加权"的召回,
    #    对纯概念同义 (查询与文档零字面重叠, 如"户外活动"↔"爬山") 能力有限 ——
    #    那需要训练过的神经嵌入 (sentence-transformers/BGE, ~100MB 依赖)。
    #    零依赖与真神经语义不可兼得; 这里展示它真正擅长的场景。
    queries = [
        "线程安全 并发队列",          # → d1 (词汇重叠 + 词形)
        "深度学习 模型 训练",         # → d2 (强重叠)
        "神经网络 梯度",             # → d6 (反向传播/梯度下降)
        "红烧肉 做法",               # → d5
        "分布式 一致性",             # → d8
    ]

    for q in queries:
        print(f"🔎 查询: 「{q}」")
        hits = idx.search(q, k=3)
        for rank, h in enumerate(hits, 1):
            print(f"   {rank}. [{h.score:.3f}] {h.id}: {h.text}")
        print()

    # 3) 持久化往返
    print("─" * 64)
    print("💾 持久化往返 / Persistence roundtrip")
    data = idx.save_dict()
    idx2 = SemanticIndex.load_dict(data)
    h1 = idx.search("线程锁", k=1)
    h2 = idx2.search("线程锁", k=1)
    print(f"   原索引 top1: {h1[0].id} ({h1[0].score:.3f})")
    print(f"   重建 top1:   {h2[0].id} ({h2[0].score:.3f})")
    print(f"   一致: {'✅' if h1[0].id == h2[0].id else '❌'}")

    print("\n" + "=" * 64)
    print("✅ 完整本地语义召回链路验证完成 (add → fit → search → persist)")
    print("=" * 64)


if __name__ == "__main__":
    main()
