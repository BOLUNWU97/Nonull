"""
Cost Tracker — LLM 成本追踪 / LLM cost & token tracking.

Records token usage and estimated cost across LLM calls, with per-model
aggregation, budget limits, and atomic persistence.

⚠️ IMPORTANT: prices are ROUGH PUBLIC ESTIMATES for developer budgeting only —
they are NOT official billing rates and MUST NOT be used for invoicing or
financial reporting. Verify against your provider's current pricing before
relying on these numbers.

记录 token 用量与估算成本,按模型聚合,支持预算上限与原子化持久化。
⚠️ 价格为公开估算值,仅供开发预算,非官方计费费率,不得用于计费/财务报告。

@module: core.cost_tracker
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .persistence import (
    atomic_write_json, read_json, wrap_payload, unwrap_payload,
)

logger = logging.getLogger("Nonull.cost")

# ---------------------------------------------------------------------------
# 价格表 / Price table (USD per 1K tokens) — 公开估算, 非官方计费
# ---------------------------------------------------------------------------

DEFAULT_PRICE_TABLE: Dict[str, Dict[str, float]] = {
    "gpt-4o":          {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini":     {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo":     {"input": 0.010, "output": 0.030},
    "gpt-3.5-turbo":   {"input": 0.0005, "output": 0.0015},
    "deepseek-chat":   {"input": 0.00014, "output": 0.00028},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "claude-3-opus":   {"input": 0.015, "output": 0.075},
    "minimax-m3":      {"input": 0.0007, "output": 0.0028},
    "llama3":          {"input": 0.0, "output": 0.0},   # 本地模型 / local
    "ollama":          {"input": 0.0, "output": 0.0},   # 本地模型 / local
}


class BudgetExceeded(Exception):
    """预算超限 / Budget exceeded.

    当累积成本超过设置的 budget 时,record() 抛出此异常。
    Raised by record() when cumulative cost exceeds the configured budget.
    """


@dataclass
class UsageRecord:
    """单次调用用量记录 / A single LLM usage record."""
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost: float
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost": round(self.cost, 6),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UsageRecord":
        return cls(
            model=data.get("model", "unknown"),
            prompt_tokens=int(data.get("prompt_tokens", 0)),
            completion_tokens=int(data.get("completion_tokens", 0)),
            cost=float(data.get("cost", 0.0)),
            timestamp=float(data.get("timestamp", time.time())),
        )


class CostTracker:
    """LLM 成本追踪器 / LLM cost & token tracker.

    Usage:
        tracker = CostTracker(budget=1.0)  # $1 budget
        tracker.record("gpt-4o", prompt_tokens=500, completion_tokens=100)
        print(tracker.summary())
    """

    def __init__(
        self,
        price_table: Optional[Dict[str, Dict[str, float]]] = None,
        budget: Optional[float] = None,
    ) -> None:
        # 深拷贝默认表, 避免污染模块级常量 / copy to avoid mutating the const
        self._prices: Dict[str, Dict[str, float]] = {
            k: dict(v) for k, v in (price_table or DEFAULT_PRICE_TABLE).items()
        }
        self._budget: Optional[float] = budget
        self._records: List[UsageRecord] = []
        self._lock = threading.Lock()

    # ── 计价 / Pricing ────────────────────────────────────────────

    def _unit_price(self, model: str) -> Dict[str, float]:
        """按模型名查价, 支持模糊匹配 / Look up price, with fuzzy matching."""
        key = model.lower()
        if key in self._prices:
            return self._prices[key]
        # 模糊匹配: 前缀包含 / fuzzy: prefix containment
        for known, price in self._prices.items():
            if key.startswith(known) or known.startswith(key):
                return price
        # 未知模型: 用保守默认 + 警告 / unknown → conservative default + warn
        logger.warning(
            "Unknown model '%s' — using gpt-4o-mini pricing as conservative default. "
            "Register its real price via register_price() for accurate tracking.",
            model,
        )
        return self._prices["gpt-4o-mini"]

    def register_price(self, model: str, input_per_1k: float, output_per_1k: float) -> None:
        """注册/更新某模型价格 / Register or update a model's price."""
        self._prices[model.lower()] = {"input": input_per_1k, "output": output_per_1k}
        logger.debug("Registered price for %s", model)

    # ── 记录 / Recording ──────────────────────────────────────────

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """记录一次调用, 返回本次成本 / Record a call, return its cost.

        Raises:
            BudgetExceeded: 若设置了 budget 且累积超限 / if budget set and exceeded
        """
        price = self._unit_price(model)
        cost = (
            (prompt_tokens / 1000.0) * price["input"]
            + (completion_tokens / 1000.0) * price["output"]
        )
        rec = UsageRecord(
            model=model,
            prompt_tokens=int(prompt_tokens),
            completion_tokens=int(completion_tokens),
            cost=cost,
            timestamp=time.time(),
        )
        with self._lock:
            self._records.append(rec)

        if self._budget is not None:
            total = self.total_cost()
            if total > self._budget:
                raise BudgetExceeded(
                    f"预算超限 / Budget ${self._budget:.4f} exceeded: "
                    f"current ${total:.4f} (model={model})"
                )
        return cost

    # ── 统计 / Aggregation ────────────────────────────────────────

    def total_cost(self) -> float:
        with self._lock:
            return round(sum(r.cost for r in self._records), 6)

    def total_tokens(self) -> Dict[str, int]:
        with self._lock:
            return {
                "prompt": sum(r.prompt_tokens for r in self._records),
                "completion": sum(r.completion_tokens for r in self._records),
                "total": sum(r.prompt_tokens + r.completion_tokens for r in self._records),
            }

    def by_model(self) -> Dict[str, Dict[str, float]]:
        """按模型聚合统计 / Aggregate stats per model."""
        agg: Dict[str, Dict[str, float]] = {}
        with self._lock:
            for r in self._records:
                slot = agg.setdefault(r.model, {"calls": 0, "prompt_tokens": 0,
                                                "completion_tokens": 0, "cost": 0.0})
                slot["calls"] += 1
                slot["prompt_tokens"] += r.prompt_tokens
                slot["completion_tokens"] += r.completion_tokens
                slot["cost"] += r.cost
        for slot in agg.values():
            slot["cost"] = round(slot["cost"], 6)
        return agg

    def check_budget(self) -> bool:
        """预算是否仍有余量 / Whether budget remains (True = OK)."""
        if self._budget is None:
            return True
        return self.total_cost() <= self._budget

    def summary(self) -> Dict[str, Any]:
        """汇总报告 / Summary report."""
        tokens = self.total_tokens()
        return {
            "total_cost": self.total_cost(),
            "budget": self._budget,
            "budget_remaining": (self._budget - self.total_cost())
                                if self._budget is not None else None,
            "call_count": len(self._records),
            "total_tokens": tokens,
            "by_model": self.by_model(),
            "note": "prices are public estimates, NOT official billing",
        }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __len__(self) -> int:
        return len(self._records)

    # ── 持久化 / Persistence ──────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "budget": self._budget,
                "records": [r.to_dict() for r in self._records],
            }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        price_table: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> "CostTracker":
        tracker = cls(price_table=price_table, budget=data.get("budget"))
        tracker._records = [UsageRecord.from_dict(r) for r in data.get("records", [])]
        return tracker

    def save(self, path: str) -> None:
        atomic_write_json(path, wrap_payload("cost_tracker", self.to_dict()))
        logger.info("CostTracker saved to %s (%d records, $%.4f)",
                    path, len(self._records), self.total_cost())

    @classmethod
    def load(
        cls,
        path: str,
        price_table: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> "CostTracker":
        data = unwrap_payload(read_json(path), "cost_tracker")
        tracker = cls.from_dict(data, price_table=price_table)
        logger.info("CostTracker loaded from %s (%d records)", path, len(tracker))
        return tracker
