"""
Prompt Optimizer — 提示优化器 (DSPy-lite)

Auto-tunes prompts by collecting success/failure traces and selecting
optimal few-shot examples and instructions via a metric function.

Inspired by Stanford DSPy's BootstrapFewShot optimizer.

@module: core.prompt_optimizer
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("Nonull.prompt_optimizer")


@dataclass
class IOExample:
    """A single input-output example for few-shot prompting. / 少样本示例。"""
    input_text: str
    output_text: str
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_prompt_block(self) -> str:
        return f"Input: {self.input_text}\nOutput: {self.output_text}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input": self.input_text,
            "output": self.output_text,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass
class Signature:
    """
    Declares the input/output contract for a module.
    声明模块的输入/输出契约。

    Similar to DSPy's Signature — defines what the LLM receives and returns.
    """
    name: str
    instruction: str
    input_fields: List[str] = field(default_factory=list)
    output_fields: List[str] = field(default_factory=list)
    examples: List[IOExample] = field(default_factory=list)

    def build_prompt(self, inputs: Dict[str, str], max_examples: int = 3) -> str:
        """Build a prompt from the signature with few-shot examples. / 构建含少样本的提示。"""
        parts = [self.instruction]

        top_examples = sorted(self.examples, key=lambda e: e.score, reverse=True)[:max_examples]
        if top_examples:
            parts.append("\n--- Examples ---")
            for ex in top_examples:
                parts.append(ex.to_prompt_block())
            parts.append("--- End Examples ---\n")

        for field_name in self.input_fields:
            value = inputs.get(field_name, "")
            parts.append(f"{field_name}: {value}")

        if self.output_fields:
            parts.append(f"\nReturn a JSON with keys: {self.output_fields}")

        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "instruction": self.instruction,
            "input_fields": self.input_fields,
            "output_fields": self.output_fields,
            "num_examples": len(self.examples),
        }


@dataclass
class TraceRecord:
    """Record of one execution for optimization. / 一次执行的记录。"""
    inputs: Dict[str, str]
    output: str
    score: float
    prompt_used: str = ""
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.score > 0.5


class TraceCollector:
    """
    Collects execution traces for prompt optimization.
    收集执行轨迹用于提示优化。
    """

    def __init__(self, max_traces: int = 1000):
        self._traces: List[TraceRecord] = []
        self._max_traces = max_traces

    def record(self, inputs: Dict[str, str], output: str, score: float, **kwargs) -> TraceRecord:
        """Record an execution trace. / 记录一次执行轨迹。"""
        trace = TraceRecord(inputs=inputs, output=output, score=score, **kwargs)
        self._traces.append(trace)
        if len(self._traces) > self._max_traces:
            self._traces = self._traces[-self._max_traces:]
        return trace

    def get_passing(self, min_score: float = 0.5) -> List[TraceRecord]:
        """Get traces that pass the score threshold. / 获取通过分数阈值的轨迹。"""
        return [t for t in self._traces if t.score >= min_score]

    def get_failing(self, max_score: float = 0.5) -> List[TraceRecord]:
        """Get traces that fail the score threshold. / 获取未通过分数阈值的轨迹。"""
        return [t for t in self._traces if t.score < max_score]

    def stats(self) -> Dict[str, Any]:
        """Get statistics about collected traces. / 获取轨迹统计。"""
        if not self._traces:
            return {"total": 0, "passing": 0, "failing": 0, "avg_score": 0.0}
        scores = [t.score for t in self._traces]
        passing = sum(1 for s in scores if s > 0.5)
        return {
            "total": len(self._traces),
            "passing": passing,
            "failing": len(self._traces) - passing,
            "avg_score": round(sum(scores) / len(scores), 3),
            "best_score": round(max(scores), 3),
        }

    def clear(self) -> None:
        self._traces.clear()

    def __len__(self) -> int:
        return len(self._traces)


class DemoSelector:
    """
    Selects the best few-shot examples from passing traces.
    从通过的轨迹中选择最佳少样本示例。

    Strategies:
    - top_k: Select top K by score
    - diverse: Select K diverse examples (maximize input variety)
    """

    @staticmethod
    def top_k(traces: List[TraceRecord], k: int = 3) -> List[IOExample]:
        """Select top K traces by score. / 按分数选择前 K 个。"""
        sorted_traces = sorted(traces, key=lambda t: t.score, reverse=True)[:k]
        return [
            IOExample(
                input_text=json.dumps(t.inputs, ensure_ascii=False) if isinstance(t.inputs, dict) else str(t.inputs),
                output_text=t.output[:500],
                score=t.score,
                metadata=t.metadata,
            )
            for t in sorted_traces
        ]

    @staticmethod
    def diverse(traces: List[TraceRecord], k: int = 3) -> List[IOExample]:
        """
        Select K diverse traces by maximizing input variety.
        通过最大化输入多样性选择 K 个不同的轨迹。
        """
        if not traces:
            return []
        sorted_traces = sorted(traces, key=lambda t: t.score, reverse=True)
        selected: List[TraceRecord] = [sorted_traces[0]]

        for trace in sorted_traces[1:]:
            if len(selected) >= k:
                break
            input_key = str(trace.inputs)
            if all(str(s.inputs) != input_key for s in selected):
                selected.append(trace)

        if len(selected) < k:
            for trace in sorted_traces:
                if len(selected) >= k:
                    break
                if trace not in selected:
                    selected.append(trace)

        return [
            IOExample(
                input_text=json.dumps(t.inputs, ensure_ascii=False) if isinstance(t.inputs, dict) else str(t.inputs),
                output_text=t.output[:500],
                score=t.score,
            )
            for t in selected
        ]


class PromptOptimizer:
    """
    Optimizes prompts by selecting the best few-shot examples and instructions.
    通过选择最佳少样本示例和指令来优化提示。

    Usage:
        optimizer = PromptOptimizer()
        sig = Signature(name="plan", instruction="Plan a route", ...)

        # Collect traces over time
        optimizer.record(sig.name, inputs, output, score=0.9)
        optimizer.record(sig.name, inputs2, output2, score=0.2)

        # Optimize: update signature with best examples
        optimized_sig = optimizer.optimize(sig, strategy="top_k", k=3)
    """

    def __init__(self):
        self._collectors: Dict[str, TraceCollector] = defaultdict(TraceCollector)

    def record(self, signature_name: str, inputs: Dict[str, str], output: str,
               score: float, **kwargs) -> TraceRecord:
        """Record an execution trace for a signature. / 记录签名的执行轨迹。"""
        return self._collectors[signature_name].record(inputs, output, score, **kwargs)

    def optimize(
        self,
        signature: Signature,
        strategy: str = "top_k",
        k: int = 3,
        min_score: float = 0.5,
    ) -> Signature:
        """
        Optimize a signature with the best examples.
        使用最佳示例优化签名。

        Returns a new Signature with updated examples.
        """
        collector = self._collectors.get(signature.name)
        if collector is None or len(collector) == 0:
            logger.info("No traces for '%s', returning original signature", signature.name)
            return signature

        passing = collector.get_passing(min_score)
        if not passing:
            logger.info("No passing traces for '%s'", signature.name)
            return signature

        if strategy == "diverse":
            examples = DemoSelector.diverse(passing, k)
        else:
            examples = DemoSelector.top_k(passing, k)

        optimized = Signature(
            name=signature.name,
            instruction=signature.instruction,
            input_fields=signature.input_fields,
            output_fields=signature.output_fields,
            examples=examples,
        )
        logger.info(
            "Optimized '%s': %d examples selected from %d passing traces (strategy=%s)",
            signature.name, len(examples), len(passing), strategy,
        )
        return optimized

    def stats(self, signature_name: Optional[str] = None) -> Dict[str, Any]:
        """Get optimization statistics. / 获取优化统计。"""
        if signature_name:
            collector = self._collectors.get(signature_name)
            return collector.stats() if collector else {}
        return {name: c.stats() for name, c in self._collectors.items()}

    def get_collector(self, signature_name: str) -> TraceCollector:
        return self._collectors[signature_name]
