"""
多模型协作层 / Multi-model collaboration layer.

针对超复杂任务: 自动拆解子任务 → 分发多个模型并行执行 → 模型间交叉校验 →
汇总整合最终输出。简单任务不进此层 (单模型独立执行, 避免资源浪费)。

协作流水线 (4 阶段):
  1. DECOMPOSE  — 用一个强模型把任务拆成 N 个子任务 (JSON)
  2. PARALLEL   — 每个子任务路由到合适模型, 并行执行 (asyncio)
  3. CROSS_CHECK— (可选) 子结果交叉校验: 让另一模型审查/纠错
  4. SYNTHESIZE — 汇总模型整合所有子结果为最终答案

@module: multimodel.collaborator
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .registry import ModelEntry, ModelRegistry, ModelTier
from .router import TaskRouter, RoutingStrategy
from .dispatcher import ModelDispatcher, DispatchResult

logger = logging.getLogger("Nonull.multimodel.collaborator")


@dataclass
class SubTask:
    """拆解出的子任务 / A decomposed subtask."""
    id: str
    description: str
    depends_on: List[str] = field(default_factory=list)
    result: Optional[str] = None
    model_used: Optional[str] = None
    verified: bool = False


@dataclass
class CollaborationResult:
    """协作最终结果 / Final collaboration result."""
    final_output: str
    subtasks: List[SubTask]
    decompose_model: str
    synthesize_model: str
    total_models_used: int
    cross_checked: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "final_output": self.final_output,
            "subtask_count": len(self.subtasks),
            "subtasks": [
                {"id": s.id, "desc": s.description[:80], "model": s.model_used,
                 "verified": s.verified, "result": (s.result or "")[:200]}
                for s in self.subtasks
            ],
            "decompose_model": self.decompose_model,
            "synthesize_model": self.synthesize_model,
            "total_models_used": self.total_models_used,
            "cross_checked": self.cross_checked,
        }


_DECOMPOSE_PROMPT = """You are a task decomposition expert. Break the following complex task into 2-5 independent subtasks that can be worked on in parallel by different AI models.

Task: {task}

Return ONLY a JSON object:
{{"subtasks": [{{"id": "s1", "description": "<clear standalone subtask>", "depends_on": []}}, ...]}}

Rules: each subtask must be self-contained and independently solvable. Use depends_on only when a subtask genuinely needs another's output. Keep to 2-5 subtasks."""

_CROSS_CHECK_PROMPT = """Review the following answer to a subtask for correctness, completeness, and errors. If it's correct, confirm briefly. If it has issues, provide the corrected version.

Subtask: {subtask}

Answer to review:
{answer}

Provide your reviewed/corrected answer:"""

_SYNTHESIZE_PROMPT = """You are a synthesis expert. Integrate the following subtask results into one coherent, complete final answer for the original task.

Original task: {task}

Subtask results:
{results}

Produce the final integrated answer (well-structured, no redundancy, resolve any contradictions between subtask results):"""


class MultiModelCollaborator:
    """多模型协作器 / Orchestrates multiple models on a super-complex task.

    Usage:
        collab = MultiModelCollaborator(registry, router, dispatcher)
        result = await collab.collaborate("设计一个完整的分布式限流系统方案")
        print(result.final_output)
        print(result.to_dict())
    """

    def __init__(
        self,
        registry: ModelRegistry,
        router: TaskRouter,
        dispatcher: ModelDispatcher,
        enable_cross_check: bool = True,
        max_parallel: int = 4,
    ):
        self.registry = registry
        self.router = router
        self.dispatcher = dispatcher
        self.enable_cross_check = enable_cross_check
        self.max_parallel = max_parallel

    def _strong_model(self) -> ModelEntry:
        """取一个强模型 (拆解/汇总用)。"""
        large = self.registry.by_tier(ModelTier.LARGE)
        if large:
            return large[0]
        allm = self.registry.all()
        if not allm:
            raise RuntimeError("无可用模型 / no models available")
        return allm[0]

    def _msg(self, content: str, role: str = "user") -> Any:
        from core.llm_client import LLMMessage
        return LLMMessage(role=role, content=content)

    async def _dispatch_async(self, entry: ModelEntry, prompt: str, json_mode: bool = False) -> DispatchResult:
        """把同步 dispatch 包装为 async (跑在线程池, 不阻塞 event loop)。"""
        messages = [self._msg(prompt)]
        return await asyncio.to_thread(
            self.dispatcher.dispatch, entry, messages, json_mode=json_mode,
        )

    # ── 阶段 1: 拆解 / Decompose ─────────────────────────────────

    async def decompose(self, task: str) -> List[SubTask]:
        strong = self._strong_model()
        prompt = _DECOMPOSE_PROMPT.format(task=task)
        result = await self._dispatch_async(strong, prompt, json_mode=True)
        subtasks: List[SubTask] = []
        if result.success:
            try:
                from core.structured_output import extract_json
                data = extract_json(result.content)
                for i, st in enumerate(data.get("subtasks", [])):
                    subtasks.append(SubTask(
                        id=st.get("id", f"s{i+1}"),
                        description=st.get("description", ""),
                        depends_on=st.get("depends_on", []),
                    ))
            except Exception as e:
                logger.warning("拆解 JSON 解析失败 / decompose parse failed: %s", e)
        if not subtasks:
            # 兜底: 不拆解, 整任务当单个子任务
            subtasks = [SubTask(id="s1", description=task)]
        logger.info("任务拆解为 %d 个子任务 / decomposed into %d subtasks",
                    len(subtasks), len(subtasks))
        return subtasks

    # ── 阶段 2: 并行执行 / Parallel execution ────────────────────

    async def _execute_subtask(self, st: SubTask, context: Dict[str, str]) -> SubTask:
        """执行单个子任务 (路由 + 调用)。context 含已完成依赖的结果。"""
        prompt = st.description
        if st.depends_on:
            dep_ctx = "\n".join(
                f"[{d}]: {context.get(d, '(pending)')[:500]}" for d in st.depends_on
            )
            prompt = f"Context from prior subtasks:\n{dep_ctx}\n\nNow: {st.description}"
        decision = self.router.route(st.description)
        result = await self._dispatch_async(decision.model, prompt)
        st.result = result.content if result.success else f"(failed: {result.log.error})"
        st.model_used = result.model_used
        return st

    async def execute_parallel(self, subtasks: List[SubTask]) -> List[SubTask]:
        """按依赖分层并行执行 / Execute in dependency layers, parallel within a layer."""
        context: Dict[str, str] = {}
        done: Dict[str, SubTask] = {}
        remaining = {s.id: s for s in subtasks}
        sem = asyncio.Semaphore(self.max_parallel)

        async def run_one(st: SubTask) -> SubTask:
            async with sem:
                return await self._execute_subtask(st, context)

        # 拓扑分层: 每轮跑所有依赖已满足的子任务
        while remaining:
            ready = [s for s in remaining.values()
                     if all(d in done for d in s.depends_on)]
            if not ready:
                # 循环依赖兜底: 全部直接跑
                ready = list(remaining.values())
            results = await asyncio.gather(*[run_one(s) for s in ready])
            for st in results:
                done[st.id] = st
                context[st.id] = st.result or ""
                remaining.pop(st.id, None)
        return [done[s.id] for s in subtasks]

    # ── 阶段 3: 交叉校验 / Cross-check ───────────────────────────

    async def cross_check(self, subtasks: List[SubTask]) -> List[SubTask]:
        """每个子结果让另一个模型审查纠错 / Each result reviewed by a different model."""
        async def check_one(st: SubTask) -> SubTask:
            if not st.result or st.result.startswith("(failed"):
                return st
            # 用与原模型不同的模型校验 (交叉)
            reviewers = [e for e in self.registry.by_tier(ModelTier.LARGE)
                         if e.name != st.model_used]
            reviewer = reviewers[0] if reviewers else self._strong_model()
            prompt = _CROSS_CHECK_PROMPT.format(subtask=st.description, answer=st.result)
            result = await self._dispatch_async(reviewer, prompt)
            if result.success and result.content.strip():
                # 只在 reviewer 明确给出"更长/不同"的修正时才替换原答案;
                # 否则 (只是确认正确) 保留原答案, 仅标记已校验 —— 避免把好答案
                # 替换成简短的 "looks correct" 审查语。
                reviewed = result.content.strip()
                original = (st.result or "").strip()
                # 启发式: 修正版显著不同且不太短才采纳
                if reviewed != original and len(reviewed) >= 0.5 * len(original):
                    st.result = reviewed
                st.verified = True
            return st

        return await asyncio.gather(*[check_one(s) for s in subtasks])

    # ── 阶段 4: 汇总 / Synthesize ────────────────────────────────

    async def synthesize(self, task: str, subtasks: List[SubTask]) -> tuple[str, str]:
        strong = self._strong_model()
        results_text = "\n\n".join(
            f"### Subtask {s.id}: {s.description}\n{s.result or '(no result)'}"
            for s in subtasks
        )
        prompt = _SYNTHESIZE_PROMPT.format(task=task, results=results_text)
        result = await self._dispatch_async(strong, prompt)
        final = result.content if result.success else results_text  # 兜底: 拼接子结果
        return final, strong.name

    # ── 主入口 / Main entry ──────────────────────────────────────

    async def collaborate(self, task: str) -> CollaborationResult:
        """超复杂任务的完整协作流程 / Full collaboration pipeline."""
        logger.info("启动多模型协作 / starting collaboration: %s", task[:80])

        # 1) 拆解
        subtasks = await self.decompose(task)
        decompose_model = self._strong_model().name

        # 2) 并行执行
        subtasks = await self.execute_parallel(subtasks)

        # 3) 交叉校验 (可选)
        cross_checked = False
        if self.enable_cross_check and len(subtasks) > 1:
            subtasks = await self.cross_check(subtasks)
            cross_checked = any(s.verified for s in subtasks)

        # 4) 汇总
        final, synth_model = await self.synthesize(task, subtasks)

        models_used = len({s.model_used for s in subtasks if s.model_used} |
                          {decompose_model, synth_model})
        return CollaborationResult(
            final_output=final,
            subtasks=subtasks,
            decompose_model=decompose_model,
            synthesize_model=synth_model,
            total_models_used=models_used,
            cross_checked=cross_checked,
        )
