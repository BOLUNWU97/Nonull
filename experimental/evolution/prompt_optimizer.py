"""
Prompt Self-Optimizer — 提示词自优化引擎
=============================================

智能体能够自我改进提示词（系统提示、任务提示、模板），追踪哪些提示对哪些
任务效果最好，执行 A/B 测试，学习最优提示结构，并生成任务特定的提示模板。

The agent self-improves its prompts (system prompts, task prompts, templates),
tracks which prompts work best for which tasks, runs A/B tests, learns optimal
prompt structure, and generates task-specific prompt templates.

Typical usage::

    optimizer = PromptOptimizer()
    improved = optimizer.optimize_prompt(template, outcomes)
    optimizer.learn_prompt_pattern(task_type, success)
    template = optimizer.generate_template(task)
    results = optimizer.ab_test(variant_a, variant_b, task)
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Types
# ---------------------------------------------------------------------------

@dataclass
class PromptOutcome:
    """提示词执行结果 / Outcome of a prompt execution."""
    outcome_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    prompt_hash: str = ""
    task_type: str = ""
    success: bool = False
    quality_score: float = 0.0
    duration_ms: float = 0.0
    safety_compliant: bool = True
    feedback: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "prompt_hash": self.prompt_hash,
            "task_type": self.task_type,
            "success": self.success,
            "quality_score": self.quality_score,
            "duration_ms": self.duration_ms,
            "safety_compliant": self.safety_compliant,
            "feedback": self.feedback,
            "timestamp": self.timestamp,
        }


@dataclass
class PromptVariant:
    """提示词变体 / A prompt variant."""
    variant_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    content: str = ""
    description: str = ""
    hash: str = ""
    created_at: float = field(default_factory=time.time)
    use_count: int = 0
    success_count: int = 0
    avg_quality: float = 0.0

    def __post_init__(self) -> None:
        if not self.hash and self.content:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        return hashlib.md5(self.content.encode()).hexdigest()[:12]

    def record_outcome(self, success: bool, quality: float) -> None:
        self.use_count += 1
        if success:
            self.success_count += 1
        self.avg_quality = (
            (self.avg_quality * (self.use_count - 1) + quality) / self.use_count
        )

    def success_rate(self) -> float:
        return self.success_count / max(self.use_count, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "description": self.description,
            "hash": self.hash,
            "use_count": self.use_count,
            "success_count": self.success_count,
            "success_rate": self.success_rate(),
            "avg_quality": round(self.avg_quality, 4),
        }


@dataclass
class ABTestResult:
    """A/B 测试结果 / A/B test result."""
    test_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_type: str = ""
    variant_a_id: str = ""
    variant_b_id: str = ""
    variant_a_success_rate: float = 0.0
    variant_b_success_rate: float = 0.0
    variant_a_avg_quality: float = 0.0
    variant_b_avg_quality: float = 0.0
    winner: Optional[str] = None
    confidence: float = 0.0
    samples_a: int = 0
    samples_b: int = 0
    completed: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "task_type": self.task_type,
            "variant_a_id": self.variant_a_id,
            "variant_b_id": self.variant_b_id,
            "variant_a_success_rate": round(self.variant_a_success_rate, 4),
            "variant_b_success_rate": round(self.variant_b_success_rate, 4),
            "variant_a_avg_quality": round(self.variant_a_avg_quality, 4),
            "variant_b_avg_quality": round(self.variant_b_avg_quality, 4),
            "winner": self.winner,
            "confidence": round(self.confidence, 4),
            "samples_a": self.samples_a,
            "samples_b": self.samples_b,
            "completed": self.completed,
        }


@dataclass
class PromptTemplate:
    """优化的提示模板 / An optimized prompt template."""
    template_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_type: str = ""
    template: str = ""
    description: str = ""
    variables: List[str] = field(default_factory=list)
    performance_score: float = 0.0
    use_count: int = 0
    source_variant_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "task_type": self.task_type,
            "template": self.template[:200],
            "variables": self.variables,
            "performance_score": round(self.performance_score, 4),
            "use_count": self.use_count,
            "tags": self.tags,
        }


# ---------------------------------------------------------------------------
# Prompt Optimizer
# ---------------------------------------------------------------------------

class PromptOptimizer:
    """提示词自优化引擎 — 通过经验不断改进自身提示词。

    Prompt Self-Optimizer — continuously improves its own prompts through experience.

    能力 / Capabilities:
    - 追踪提示词-任务效果映射 / Track prompt-task performance mapping
    - A/B 测试不同变体 / A/B test different variants
    - 学习最优提示结构 / Learn optimal prompt structure
    - 生成任务特定模板 / Generate task-specific templates
    - 自动优化系统提示 / Auto-optimize system prompts
    """

    # 系统提示的组件 / Components for system prompts
    SYSTEM_PROMPT_SECTIONS = [
        "role_definition",
        "capabilities",
        "constraints",
        "reasoning_guidelines",
        "tool_usage",
        "safety_rules",
        "output_format",
        "memory_instructions",
        "evolution_instructions",
    ]

    def __init__(self, min_ab_samples: int = 5):
        self.min_ab_samples = min_ab_samples  # A/B 测试最小采样数

        # 变体和结果 / Variants and outcomes
        self._variants: Dict[str, PromptVariant] = {}
        self._outcomes: List[PromptOutcome] = []

        # 按任务类型的表现 / Per-task-type performance
        self._task_performance: Dict[str, List[PromptOutcome]] = defaultdict(list)

        # 已学习的模式 / Learned patterns
        self._learned_patterns: Dict[str, Dict[str, Any]] = {}

        # A/B 测试 / A/B tests
        self._ab_tests: Dict[str, ABTestResult] = {}

        # 生成的模板 / Generated templates
        self._templates: Dict[str, PromptTemplate] = {}

        # 最优的提示结构知识 / Optimal prompt structure knowledge
        self._structure_knowledge: Dict[str, float] = {
            section: 1.0 for section in self.SYSTEM_PROMPT_SECTIONS
        }

        self.stats: Dict[str, Any] = {
            "total_optimizations": 0,
            "total_ab_tests": 0,
            "ab_tests_completed": 0,
            "patterns_learned": 0,
            "templates_generated": 0,
            "variants_tracked": 0,
        }

        logger.info("PromptOptimizer initialized | 提示词优化引擎已初始化")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def optimize_prompt(
        self,
        prompt_template: str,
        outcomes: List[PromptOutcome],
    ) -> str:
        """基于结果反馈优化提示模板。

        Optimize a prompt template based on outcome feedback.

        Args:
            prompt_template: 原始提示模板 / Original prompt template
            outcomes: 该模板的执行结果列表 / List of execution outcomes

        Returns:
            优化后的提示模板 / Optimized prompt template
        """
        if not outcomes:
            return prompt_template

        # 分析当前模板的效果 / Analyze current template effectiveness
        success_rate = sum(1 for o in outcomes if o.success) / len(outcomes)
        avg_quality = sum(o.quality_score for o in outcomes) / len(outcomes)

        logger.info(
            f"Optimizing prompt: current success_rate={success_rate:.2f}, "
            f"avg_quality={avg_quality:.2f} | "
            f"优化提示词: 当前成功率={success_rate:.2f}, 平均质量={avg_quality:.2f}"
        )

        # 如果表现已经很好，不做大的改动 / If already performing well, minimal changes
        if success_rate > 0.9 and avg_quality > 0.85:
            return prompt_template

        optimized = prompt_template

        # 应用一系列优化策略 / Apply a series of optimization strategies
        optimized = self._apply_structure_optimization(optimized, outcomes)
        optimized = self._apply_clarity_optimization(optimized, outcomes)
        optimized = self._apply_safety_reinforcement(optimized, outcomes)
        optimized = self._apply_task_specific_instructions(optimized, outcomes)

        self.stats["total_optimizations"] += 1

        # 记录为变体 / Record as variant
        variant = PromptVariant(
            content=optimized,
            description=f"Optimized from base template (sr={success_rate:.2f})",
        )
        self._variants[variant.variant_id] = variant
        self.stats["variants_tracked"] = len(self._variants)

        logger.info("Prompt optimization completed | 提示词优化完成")
        return optimized

    def learn_prompt_pattern(
        self, task_type: str, outcomes: List[PromptOutcome]
    ) -> Dict[str, Any]:
        """从任务执行结果中学习提示模式。

        Learn prompt patterns from task execution outcomes.

        Args:
            task_type: 任务类型 / Task type
            outcomes: 该任务类型的执行结果列表 / Outcomes for this task type

        Returns:
            学到的模式知识 / Learned pattern knowledge
        """
        if not outcomes:
            return {}

        # 分析成功和失败的模式 / Analyze success and failure patterns
        success_outcomes = [o for o in outcomes if o.success]
        failure_outcomes = [o for o in outcomes if not o.success]

        pattern = {
            "task_type": task_type,
            "total_samples": len(outcomes),
            "success_rate": len(success_outcomes) / len(outcomes),
            "avg_quality": sum(o.quality_score for o in outcomes) / len(outcomes),
            "avg_duration_ms": sum(o.duration_ms for o in outcomes) / len(outcomes),
            "safety_compliance_rate": sum(
                1 for o in outcomes if o.safety_compliant
            ) / len(outcomes),
            "learned_at": time.time(),
        }

        # 提取失败中的共性 / Extract commonalities from failures
        if failure_outcomes:
            failure_feedback = [
                o.feedback for o in failure_outcomes if o.feedback
            ]
            if failure_feedback:
                pattern["common_failure_feedback"] = Counter(
                    failure_feedback
                ).most_common(3)

        # 提取成功中的共性 / Extract commonalities from successes
        if success_outcomes:
            pattern["note"] = "Performance is adequate for this task type"

        self._learned_patterns[task_type] = pattern
        self.stats["patterns_learned"] = len(self._learned_patterns)

        logger.info(
            f"Learned prompt pattern for '{task_type}': "
            f"sr={pattern['success_rate']:.2f}, n={pattern['total_samples']} | "
            f"已学习 '{task_type}' 的提示模式"
        )
        return pattern

    def generate_template(self, task: Dict[str, Any]) -> PromptTemplate:
        """为特定任务生成最优提示模板。

        Generate an optimal prompt template for a specific task.

        Args:
            task: 任务描述，包含 type, description, examples 等字段
                  Task dict with type, description, examples fields

        Returns:
            生成的提示模板 / Generated prompt template
        """
        task_type = task.get("type", "general")
        task_description = task.get("description", "")
        examples = task.get("examples", [])

        # 构建模板组件 / Build template components
        components = []

        # 1. 角色定义 / Role definition
        components.append(self._build_role_section(task_type))

        # 2. 任务描述 / Task description
        if task_description:
            components.append(
                f"## 任务 / Task\n{task_description}"
            )

        # 3. 约束和安全规则 / Constraints and safety
        components.append(
            "## 约束 / Constraints\n"
            "- 始终遵循安全规则 / Always follow safety rules\n"
            "- 不要执行破坏性操作而不确认 / No destructive ops without confirmation\n"
            "- 验证所有输入 / Validate all inputs"
        )

        # 4. 推理指导 / Reasoning guidelines
        components.append(
            "## 推理 / Reasoning\n"
            "- 先分析再行动 / Analyze before acting\n"
            "- 考虑替代方案 / Consider alternatives\n"
            "- 验证每个步骤 / Verify each step"
        )

        # 5. 任务特定指令 / Task-specific instructions
        task_instructions = self._get_task_specific_instructions(task_type)
        if task_instructions:
            components.append(f"## 特定指令 / Specific Instructions\n{task_instructions}")

        # 6. 示例 / Examples
        if examples:
            formatted = "\n".join(f"- {ex}" for ex in examples[:3])
            components.append(f"## 示例 / Examples\n{formatted}")

        # 7. 输出格式 / Output format
        components.append(
            "## 输出 / Output\n"
            "提供清晰、结构化的结果 / Provide clear, structured results\n"
            "包含必要的中英文双语内容 / Include bilingual content"
        )

        template_text = "\n\n".join(components)

        # 提取变量 / Extract variables
        variables = re.findall(r"\{(\w+)\}", template_text)
        variables = list(set(variables))

        # 检查是否有已存储的高性能模板 / Check for existing high-performance template
        existing_templates = [
            t for t in self._templates.values()
            if t.task_type == task_type
        ]
        best_score = max(
            (t.performance_score for t in existing_templates),
            default=0.0,
        )

        new_template = PromptTemplate(
            task_type=task_type,
            template=template_text,
            description=f"Auto-generated template for {task_type}",
            variables=variables,
            performance_score=best_score or 0.5,
            tags=[task_type, "auto_generated"],
        )

        self._templates[new_template.template_id] = new_template
        self.stats["templates_generated"] += 1

        logger.info(
            f"Generated template for '{task_type}' ({len(variables)} variables) | "
            f"已为 '{task_type}' 生成模板 ({len(variables)} 个变量)"
        )
        return new_template

    def ab_test(
        self,
        variant_a: str,
        variant_b: str,
        task_type: str,
        test_name: Optional[str] = None,
    ) -> ABTestResult:
        """执行 A/B 测试比较两个提示变体。

        Execute an A/B test comparing two prompt variants.

        Args:
            variant_a: 变体 A 的内容 / Variant A content
            variant_b: 变体 B 的内容 / Variant B content
            task_type: 任务类型 / Task type
            test_name: 测试名称（可选）/ Test name (optional)

        Returns:
            A/B 测试结果 / A/B test result
        """
        va = PromptVariant(content=variant_a, description=test_name or "Variant A")
        vb = PromptVariant(content=variant_b, description=test_name or "Variant B")

        self._variants[va.variant_id] = va
        self._variants[vb.variant_id] = vb
        self.stats["variants_tracked"] = len(self._variants)

        test = ABTestResult(
            task_type=task_type,
            variant_a_id=va.variant_id,
            variant_b_id=vb.variant_id,
            created_at=time.time(),
        )
        self._ab_tests[test.test_id] = test
        self.stats["total_ab_tests"] += 1

        logger.info(
            f"A/B test created: {test_name or 'unnamed'} ({task_type}) | "
            f"A/B 测试已创建: {test_name or '未命名'} ({task_type})"
        )
        return test

    def record_ab_outcome(
        self,
        test_id: str,
        variant_id: str,
        success: bool,
        quality: float,
    ) -> None:
        """记录 A/B 测试的一次结果 / Record one outcome of an A/B test.

        Args:
            test_id: 测试 ID / Test ID
            variant_id: 变体 ID / Variant ID
            success: 是否成功 / Whether successful
            quality: 质量评分 / Quality score
        """
        test = self._ab_tests.get(test_id)
        if not test:
            logger.warning(f"A/B test not found: {test_id}")
            return

        variant = self._variants.get(variant_id)
        if variant:
            variant.record_outcome(success, quality)

        # 更新测试统计 / Update test statistics
        if variant_id == test.variant_a_id:
            test.samples_a += 1
        elif variant_id == test.variant_b_id:
            test.samples_b += 1

        # 尝试完成测试 / Try to complete the test
        self._try_complete_ab_test(test)

    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """通过 ID 获取模板 / Get template by ID."""
        return self._templates.get(template_id)

    def get_best_template(self, task_type: str) -> Optional[PromptTemplate]:
        """获取特定任务类型的最佳模板 / Get best template for a task type."""
        candidates = [
            t for t in self._templates.values()
            if t.task_type == task_type
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda t: t.performance_score)

    def get_learned_patterns(self) -> Dict[str, Dict[str, Any]]:
        """获取所有已学习的提示模式 / Get all learned prompt patterns."""
        return dict(self._learned_patterns)

    def get_statistics(self) -> Dict[str, Any]:
        """获取优化统计 / Get optimization statistics."""
        stats = dict(self.stats)
        stats.update({
            "total_variants": len(self._variants),
            "total_templates": len(self._templates),
            "active_ab_tests": sum(
                1 for t in self._ab_tests.values() if not t.completed
            ),
        })
        return stats

    def reset(self) -> None:
        """重置所有优化数据 / Reset all optimization data."""
        self._variants.clear()
        self._outcomes.clear()
        self._task_performance.clear()
        self._learned_patterns.clear()
        self._ab_tests.clear()
        self._templates.clear()
        self._structure_knowledge = {
            s: 1.0 for s in self.SYSTEM_PROMPT_SECTIONS
        }
        self.stats = {
            "total_optimizations": 0,
            "total_ab_tests": 0,
            "ab_tests_completed": 0,
            "patterns_learned": 0,
            "templates_generated": 0,
            "variants_tracked": 0,
        }
        logger.info("PromptOptimizer reset | 提示词优化引擎已重置")

    # ------------------------------------------------------------------
    # Internal: Optimization Strategies
    # ------------------------------------------------------------------

    def _apply_structure_optimization(
        self, prompt: str, outcomes: List[PromptOutcome]
    ) -> str:
        """优化提示结构 / Optimize prompt structure."""
        # 确保有清晰的结构 / Ensure clear structure
        sections = [
            "## 角色 / Role",
            "## 任务 / Task",
            "## 约束 / Constraints",
            "## 输出 / Output",
        ]

        has_all = all(s.lower() in prompt.lower() for s in sections)
        if not has_all:
            missing = [
                s for s in sections if s.lower() not in prompt.lower()
            ]
            additions = "\n\n".join(
                f"{s}\n" for s in missing
            )
            prompt += f"\n\n{additions}"

        return prompt

    def _apply_clarity_optimization(
        self, prompt: str, outcomes: List[PromptOutcome]
    ) -> str:
        """优化提示清晰度 / Optimize prompt clarity."""
        # 检查是否过长 / Check if too long
        words = len(prompt.split())
        if words > 1500:
            # 保持核心部分，压缩冗余 / Keep core, compress redundancy
            lines = prompt.split("\n")
            compressed = [
                l for l in lines
                if not any(word in l.lower() for word in [
                    "basically", "simply", "just", "actually",
                    "basically", "essentially",
                ])
            ]
            prompt = "\n".join(compressed)

        # 确保有具体示例 / Ensure concrete examples
        if "example" not in prompt.lower() and words < 500:
            prompt += "\n\n## 示例 / Example\n[Provide a concrete example here]"

        return prompt

    def _apply_safety_reinforcement(
        self, prompt: str, outcomes: List[PromptOutcome]
    ) -> str:
        """加强安全指令 / Reinforce safety instructions."""
        safety_issues = sum(1 for o in outcomes if not o.safety_compliant)

        if safety_issues > 0:
            safety_note = (
                "\n## 安全警告 / Safety Warning\n"
                "⚠️ 注意：历史执行中存在安全违规。请特别关注以下规则：\n"
                "- 执行破坏性操作前必须获得确认\n"
                "- 验证所有输入参数\n"
                "- 不要在未检查的情况下处理敏感数据\n"
            )
            if "安全警告" not in prompt:
                prompt += safety_note

        return prompt

    def _apply_task_specific_instructions(
        self, prompt: str, outcomes: List[PromptOutcome]
    ) -> str:
        """添加任务特定指令 / Add task-specific instructions."""
        if not outcomes:
            return prompt

        # 按任务类型分组的平均质量 / Average quality by task type
        task_quality: Dict[str, List[float]] = defaultdict(list)
        for o in outcomes:
            task_quality[o.task_type].append(o.quality_score)

        worst_type = min(
            task_quality,
            key=lambda t: sum(task_quality[t]) / len(task_quality[t]),
            default=None,
        )

        if worst_type:
            avg = sum(task_quality[worst_type]) / len(task_quality[worst_type])
            if avg < 0.6:
                prompt += (
                    f"\n## 特殊注意 / Special Attention\n"
                    f"任务类型 '{worst_type}' 的历史质量偏低 ({avg:.2f})，请额外谨慎处理。\n"
                )

        return prompt

    def _build_role_section(self, task_type: str) -> str:
        """根据任务类型构建角色定义 section / Build role section by task type."""
        role_map = {
            "coding": (
                "## 角色 / Role\n"
                "你是一位经验丰富的软件工程师，精通代码开发、调试和优化。\n"
                "You are an experienced software engineer skilled in development, debugging, and optimization."
            ),
            "analysis": (
                "## 角色 / Role\n"
                "你是一位数据分析专家，擅长从数据中提取洞察和模式。\n"
                "You are a data analysis expert skilled at extracting insights from data."
            ),
            "writing": (
                "## 角色 / Role\n"
                "你是一位专业的内容创作者，擅长清晰、有说服力的表达。\n"
                "You are a professional content creator skilled at clear, persuasive communication."
            ),
            "research": (
                "## 角色 / Role\n"
                "你是一位研究助理，擅长信息检索、综合和批判性分析。\n"
                "You are a research assistant skilled at information retrieval and critical analysis."
            ),
            "planning": (
                "## 角色 / Role\n"
                "你是一位战略规划师，擅长目标分解和路径规划。\n"
                "You are a strategic planner skilled at goal decomposition and path planning."
            ),
        }
        return role_map.get(
            task_type,
            (
                "## 角色 / Role\n"
                "你是一个能够自我进化的 AI 助手，持续学习和改进。\n"
                "You are a self-evolving AI assistant, continuously learning and improving."
            ),
        )

    def _get_task_specific_instructions(self, task_type: str) -> str:
        """获取任务特定指令 / Get task-specific instructions."""
        instructions_map = {
            "coding": (
                "编写简洁、可维护、类型安全的代码\n"
                "添加适当的错误处理和日志\n"
                "包含中文和英文注释\n"
            ),
            "analysis": (
                "先理解数据结构和含义\n"
                "使用适当的分析方法\n"
                "以可视化和摘要形式呈现结果\n"
            ),
            "safety": (
                "最严格地审查每个操作\n"
                "对任何破坏性操作要求双重确认\n"
                "记录所有安全相关的决策\n"
            ),
            "memory": (
                "优先从记忆中检索相关信息\n"
                "验证记忆的时效性和相关性\n"
                "更新记忆时保持一致性\n"
            ),
        }
        return instructions_map.get(task_type, "")

    # ------------------------------------------------------------------
    # Internal: A/B Testing
    # ------------------------------------------------------------------

    def _try_complete_ab_test(self, test: ABTestResult) -> None:
        """尝试完成 A/B 测试（如果采样数足够）。

        Try to complete an A/B test if enough samples collected.
        """
        if test.completed:
            return

        if test.samples_a < self.min_ab_samples or test.samples_b < self.min_ab_samples:
            return

        va = self._variants.get(test.variant_a_id)
        vb = self._variants.get(test.variant_b_id)

        if not va or not vb:
            return

        test.variant_a_success_rate = va.success_rate()
        test.variant_b_success_rate = vb.success_rate()
        test.variant_a_avg_quality = va.avg_quality
        test.variant_b_avg_quality = vb.avg_quality

        # 确定胜者 / Determine winner
        if va.success_rate() > vb.success_rate() + 0.05:
            test.winner = test.variant_a_id
        elif vb.success_rate() > va.success_rate() + 0.05:
            test.winner = test.variant_b_id
        else:
            # 检查质量分数 / Check quality scores
            if va.avg_quality > vb.avg_quality + 0.05:
                test.winner = test.variant_a_id
            elif vb.avg_quality > va.avg_quality + 0.05:
                test.winner = test.variant_b_id
            else:
                test.winner = "tie"

        # 计算置信度（简化版）/ Compute confidence (simplified)
        total = test.samples_a + test.samples_b
        test.confidence = min(total / (self.min_ab_samples * 2), 1.0)
        test.completed = True
        self.stats["ab_tests_completed"] += 1

        logger.info(
            f"A/B test completed: winner={test.winner}, "
            f"A={test.variant_a_success_rate:.2f}, B={test.variant_b_success_rate:.2f} | "
            f"A/B 测试完成: 胜者={test.winner}"
        )
