"""
智能路由调度层 / Intelligent task router.

把任务自动分类并路由到合适的模型:
  - 简单任务 (短问答/翻译/简短总结/闲聊) → 小模型/本地模型 (低成本低延迟)
  - 复杂任务 (长文档分析/代码/逻辑推理/方案设计/多步解题) → 强模型
  - 隐私数据 (内网/机密) → 强制本地模型
  - 策略: 成本优先 / 速度优先 / 质量优先 / 手动优先级

分类用两级策略:
  1. 启发式 (heuristic): 零成本零延迟, 基于长度/关键词/代码特征。覆盖大多数。
  2. (可选) LLM 分类器: 启发式置信度低时, 用一个小模型判分类 (默认关闭, 省成本)。

@module: multimodel.router
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional

from .registry import ModelEntry, ModelRegistry, ModelTier, PrivacyLevel

logger = logging.getLogger("Nonull.multimodel.router")


class TaskComplexity(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"
    SUPER_COMPLEX = "super_complex"  # 需多模型协作拆解


class RoutingStrategy(str, Enum):
    """路由策略 / Routing strategy (which model to pick within a tier)."""
    QUALITY = "quality"    # 质量优先: 选 priority 最高的强模型
    COST = "cost"          # 成本优先: 选最便宜的合格模型
    SPEED = "speed"        # 速度优先: 选延迟最低的合格模型
    BALANCED = "balanced"  # 平衡


@dataclass
class RoutingDecision:
    """路由决策结果 / The routing decision."""
    model: ModelEntry
    complexity: TaskComplexity
    privacy: PrivacyLevel
    strategy: RoutingStrategy
    reason: str
    needs_collaboration: bool = False  # 超复杂任务标记, 触发多模型协作

    def to_dict(self) -> dict:
        return {
            "model": self.model.name,
            "model_id": self.model.model_id,
            "complexity": self.complexity.value,
            "privacy": self.privacy.value,
            "strategy": self.strategy.value,
            "reason": self.reason,
            "needs_collaboration": self.needs_collaboration,
            "is_local": self.model.is_local,
        }


# ── 分类启发式信号 / Classification heuristics ──────────────────

# 复杂任务关键词 (中英)
_COMPLEX_KEYWORDS = [
    "分析", "设计", "方案", "架构", "推理", "证明", "调试", "重构", "优化",
    "实现", "编写代码", "算法", "多步", "逐步", "为什么", "如何实现", "比较",
    "evaluate", "analyze", "design", "architect", "implement", "debug",
    "refactor", "optimize", "algorithm", "prove", "reason", "step by step",
    "trade-off", "compare", "explain why", "write code", "function", "class",
]

# 简单任务关键词
_SIMPLE_KEYWORDS = [
    "翻译", "你好", "谢谢", "什么是", "简短", "一句话", "闲聊", "问候",
    "translate", "hello", "hi", "thanks", "what is", "briefly", "in short",
    "summarize in one", "say ",
]

# 隐私敏感关键词 (强制本地)
_PRIVACY_KEYWORDS = [
    "内网", "机密", "保密", "隐私", "敏感", "内部", "不要外传", "本地处理",
    "confidential", "internal", "private", "sensitive", "do not share",
    "on-premise", "local only", "company secret",
]

# 代码特征正则
_CODE_PATTERN = re.compile(
    r"```|def\s+\w+|class\s+\w+|function\s+\w+|import\s+\w+|"
    r"#include|public\s+\w+|=>|console\.log|System\.out", re.IGNORECASE
)

# 超复杂任务信号 (需协作)
_SUPER_COMPLEX_KEYWORDS = [
    "全面", "完整方案", "端到端", "从0到1", "系统性", "多个方面", "综合",
    "comprehensive", "end-to-end", "full solution", "multi-faceted",
    "thoroughly", "from scratch", "complete system",
]


class TaskRouter:
    """智能任务路由器 / Routes a task to the right model.

    Usage:
        router = TaskRouter(registry, default_strategy=RoutingStrategy.BALANCED)
        decision = router.route("帮我设计一个分布式限流方案")
        # decision.model -> 强模型; decision.needs_collaboration -> True (超复杂)

    自定义规则:
        router.force_local_on_privacy = True   # 隐私数据强制本地
        router.complex_token_threshold = 1500  # 超过视为复杂
    """

    def __init__(
        self,
        registry: ModelRegistry,
        default_strategy: RoutingStrategy = RoutingStrategy.BALANCED,
        force_local_on_privacy: bool = True,
        complex_char_threshold: int = 1500,
        super_complex_char_threshold: int = 4000,
    ):
        self.registry = registry
        self.default_strategy = default_strategy
        self.force_local_on_privacy = force_local_on_privacy
        self.complex_char_threshold = complex_char_threshold
        self.super_complex_char_threshold = super_complex_char_threshold

    # ── 分类 / Classification ────────────────────────────────────

    def classify_privacy(self, task: str) -> PrivacyLevel:
        low = task.lower()
        if any(k in task or k.lower() in low for k in _PRIVACY_KEYWORDS):
            return PrivacyLevel.INTERNAL
        return PrivacyLevel.PUBLIC

    def classify_complexity(self, task: str) -> TaskComplexity:
        """启发式任务复杂度分类 / Heuristic complexity classification."""
        low = task.lower()
        length = len(task)

        # 强信号: 代码特征 → 复杂
        has_code = bool(_CODE_PATTERN.search(task))

        simple_hits = sum(1 for k in _SIMPLE_KEYWORDS if k in task or k.lower() in low)
        complex_hits = sum(1 for k in _COMPLEX_KEYWORDS if k in task or k.lower() in low)
        super_hits = sum(1 for k in _SUPER_COMPLEX_KEYWORDS if k in task or k.lower() in low)

        # 超复杂: 满足任一 →
        #   (a) 显式超复杂信号 + 长文本, 或
        #   (b) 多个复杂信号 + 长文本, 或
        #   (c) 强关键词组合 (超复杂信号 + 多复杂信号), 不依赖长度 ——
        #       "全面设计端到端完整方案" 这类即便不算超长也该走协作。
        # Strong keyword combos qualify regardless of length: a task explicitly
        # asking for a comprehensive/end-to-end solution with many complex
        # signals is super-complex even if not extremely long.
        if (super_hits >= 1 and length > self.super_complex_char_threshold) or \
           (complex_hits >= 3 and length > self.super_complex_char_threshold) or \
           (super_hits >= 1 and complex_hits >= 3):
            return TaskComplexity.SUPER_COMPLEX

        # 复杂: 代码 / 长文本 / 复杂关键词占优
        if has_code or length > self.complex_char_threshold or complex_hits > simple_hits:
            return TaskComplexity.COMPLEX

        # 简单: 短 + 简单关键词 + 无复杂信号
        if length < 200 and (simple_hits > 0 or complex_hits == 0):
            return TaskComplexity.SIMPLE

        # 默认中等 → 当复杂处理 (宁可用强模型, 保证质量)
        return TaskComplexity.COMPLEX

    # ── 选模型 / Model selection ─────────────────────────────────

    def _candidates_for(self, complexity: TaskComplexity, privacy: PrivacyLevel) -> List[ModelEntry]:
        """根据复杂度 + 隐私选候选模型池 / Candidate pool by complexity + privacy."""
        # 隐私强制本地
        if privacy != PrivacyLevel.PUBLIC and self.force_local_on_privacy:
            locals_ = self.registry.local_models()
            if locals_:
                return locals_
            logger.warning("隐私任务但无本地模型可用, 降级到云端 / privacy task but no local model")

        if complexity == TaskComplexity.SIMPLE:
            # 简单: 小模型优先, 含本地小模型
            pool = self.registry.by_tier(ModelTier.SMALL) + self.registry.local_models()
            return pool or self.registry.by_tier(ModelTier.MEDIUM)
        else:
            # 复杂/超复杂: 强模型优先
            pool = self.registry.by_tier(ModelTier.LARGE)
            return pool or self.registry.by_tier(ModelTier.MEDIUM) or self.registry.all()

    def _pick(self, candidates: List[ModelEntry], strategy: RoutingStrategy) -> Optional[ModelEntry]:
        if not candidates:
            return None
        if strategy == RoutingStrategy.COST:
            return self.registry.cheapest(candidates)
        if strategy == RoutingStrategy.SPEED:
            return self.registry.fastest(candidates)
        # QUALITY / BALANCED: 按 priority (by_tier 已排序), 取第一个
        return candidates[0]

    def route(
        self,
        task: str,
        strategy: Optional[RoutingStrategy] = None,
        privacy_override: Optional[PrivacyLevel] = None,
    ) -> RoutingDecision:
        """路由一个任务 / Route a task to a model.

        Args:
            task: 任务文本
            strategy: 覆盖默认策略
            privacy_override: 显式指定隐私级别 (如调用方已知内网数据)
        """
        strategy = strategy or self.default_strategy
        privacy = privacy_override or self.classify_privacy(task)
        complexity = self.classify_complexity(task)

        candidates = self._candidates_for(complexity, privacy)
        model = self._pick(candidates, strategy)

        if model is None:
            # 兜底: 注册表任意可用模型
            allm = self.registry.all()
            if not allm:
                raise RuntimeError("ModelRegistry 为空, 无可路由模型 / no models registered")
            model = allm[0]
            reason = "兜底: 无匹配候选, 用首个可用模型"
        else:
            reason = (
                f"complexity={complexity.value}, privacy={privacy.value}, "
                f"strategy={strategy.value} → tier={model.tier.value}"
            )

        needs_collab = complexity == TaskComplexity.SUPER_COMPLEX
        decision = RoutingDecision(
            model=model, complexity=complexity, privacy=privacy,
            strategy=strategy, reason=reason, needs_collaboration=needs_collab,
        )
        logger.info("路由决策 / routing: %s", decision.to_dict())
        return decision
