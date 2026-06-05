"""
Skill Genesis Engine — 技能生成引擎
=====================================

Hermes Agent 启发的自主技能生成系统。分析成功的执行模式，自动生成新的技能定义，
验证安全性，构建依赖图，并注册到技能系统。

Inspired by Hermes Agent's autonomous skill generation. Analyzes successful execution
patterns, auto-generates new skill definitions, validates against safety rules,
builds dependency graphs, and registers with the skill system.

Typical usage::

    genesis = SkillGenesis()
    skill = genesis.generate_skill(pattern, name="my_new_skill", category="utility")
    report = genesis.validate_skill(skill)
    skill = genesis.auto_learn_from_trace(trace)
    ideas = genesis.suggest_skill_improvements("skill_001")
"""

from __future__ import annotations

import ast
import inspect
import logging
import re
import textwrap
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Types
# ---------------------------------------------------------------------------

class SkillCategory(Enum):
    """技能类别 / Skill categories."""
    UTILITY = "utility"
    TOOL = "tool"
    WORKFLOW = "workflow"
    ANALYSIS = "analysis"
    REASONING = "reasoning"
    COMMUNICATION = "communication"
    SAFETY = "safety"
    MEMORY = "memory"
    PLANNING = "planning"
    CUSTOM = "custom"


class SkillStatus(Enum):
    """技能状态 / Skill status."""
    DRAFT = "draft"
    VALIDATING = "validating"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


@dataclass
class SkillSchema:
    """技能输入/输出模式 / Skill input/output schema."""
    input_type: str = "dict"  # dict | str | int | list
    input_description: str = ""
    input_example: Dict[str, Any] = field(default_factory=dict)
    output_type: str = "dict"
    output_description: str = ""
    output_example: Dict[str, Any] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    optional_fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_type": self.input_type,
            "input_description": self.input_description,
            "input_example": self.input_example,
            "output_type": self.output_type,
            "output_description": self.output_description,
            "output_example": self.output_example,
            "required_fields": self.required_fields,
            "optional_fields": self.optional_fields,
        }


@dataclass
class SafetyHook:
    """安全验证钩子 / Safety validation hook."""
    name: str = ""
    description: str = ""
    check_func: Optional[Callable] = None
    severity: str = "error"  # error | warning | info
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "severity": self.severity,
            "error_message": self.error_message,
        }


@dataclass
class PerformanceMetrics:
    """技能性能指标 / Skill performance metrics."""
    avg_execution_ms: float = 0.0
    max_execution_ms: float = 0.0
    min_execution_ms: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    total_calls: int = 0
    last_executed: Optional[float] = None
    confidence_score: float = 0.0

    def success_rate(self) -> float:
        """计算成功率 / Calculate success rate."""
        if self.total_calls == 0:
            return 0.0
        return self.success_count / self.total_calls

    def to_dict(self) -> Dict[str, Any]:
        return {
            "avg_execution_ms": self.avg_execution_ms,
            "max_execution_ms": self.max_execution_ms,
            "min_execution_ms": self.min_execution_ms,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "total_calls": self.total_calls,
            "last_executed": self.last_executed,
            "success_rate": self.success_rate(),
            "confidence_score": self.confidence_score,
        }


@dataclass
class SkillDefinition:
    """技能的完整定义 / Complete definition of a generated skill."""
    skill_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    category: SkillCategory = SkillCategory.CUSTOM
    status: SkillStatus = SkillStatus.DRAFT
    version: str = "0.1.0"

    # 执行 / Execution
    code: str = ""
    execute_method: Optional[Callable] = None

    # 模式 / Schema
    input_schema: SkillSchema = field(default_factory=SkillSchema)
    output_schema: SkillSchema = field(default_factory=SkillSchema)

    # 安全 / Safety
    safety_hooks: List[SafetyHook] = field(default_factory=list)

    # 性能 / Performance
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)

    # 依赖 / Dependencies
    dependencies: List[str] = field(default_factory=list)
    conflict_skills: List[str] = field(default_factory=list)

    # 来源 / Source
    source_trace_id: Optional[str] = None
    source_pattern_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    # 元数据 / Metadata
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    author: str = "Nonull.SkillGenesis"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def activate(self) -> None:
        """激活技能 / Activate the skill."""
        self.status = SkillStatus.ACTIVE
        self.updated_at = time.time()

    def deprecate(self) -> None:
        """弃用技能 / Deprecate the skill."""
        self.status = SkillStatus.DEPRECATED
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "status": self.status.value,
            "version": self.version,
            "input_schema": self.input_schema.to_dict(),
            "output_schema": self.output_schema.to_dict(),
            "safety_hooks": [h.to_dict() for h in self.safety_hooks],
            "metrics": self.metrics.to_dict(),
            "dependencies": self.dependencies,
            "conflict_skills": self.conflict_skills,
            "source_trace_id": self.source_trace_id,
            "source_pattern_id": self.source_pattern_id,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "author": self.author,
        }


@dataclass
class ValidationReport:
    """技能验证报告 / Skill validation report."""
    skill_id: str = ""
    skill_name: str = ""
    passed: bool = True
    checks: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    safety_score: float = 1.0
    quality_score: float = 1.0

    def add_check(
        self,
        name: str,
        passed: bool,
        message: str = "",
        severity: str = "error",
    ) -> None:
        self.checks.append({
            "name": name,
            "passed": passed,
            "message": message,
            "severity": severity,
        })
        if not passed:
            if severity == "error":
                self.errors.append(message)
                self.passed = False
            else:
                self.warnings.append(message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "passed": self.passed,
            "checks": self.checks,
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "safety_score": self.safety_score,
            "quality_score": self.quality_score,
        }


@dataclass
class SkillDependencyGraph:
    """技能依赖关系图 / Skill dependency graph."""
    nodes: Dict[str, SkillDefinition] = field(default_factory=dict)
    edges: Dict[str, List[str]] = field(default_factory=dict)  # skill_id -> deps

    def add_skill(self, skill: SkillDefinition) -> None:
        self.nodes[skill.skill_id] = skill
        self.edges[skill.skill_id] = skill.dependencies.copy()

    def get_dependency_chain(self, skill_id: str) -> List[str]:
        """获取完整的依赖链（拓扑排序） / Get full dependency chain (topological order)."""
        visited: Set[str] = set()
        chain: List[str] = []

        def dfs(sid: str) -> None:
            if sid in visited:
                return
            visited.add(sid)
            for dep_id in self.edges.get(sid, []):
                dfs(dep_id)
            chain.append(sid)

        dfs(skill_id)
        return chain

    def detect_cycles(self) -> List[List[str]]:
        """检测依赖循环 / Detect dependency cycles."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {sid: WHITE for sid in self.nodes}
        cycles: List[List[str]] = []
        path: List[str] = []

        def dfs(sid: str) -> None:
            color[sid] = GRAY
            path.append(sid)
            for dep_id in self.edges.get(sid, []):
                if color.get(dep_id) == GRAY:
                    # 找到循环 / Found cycle
                    cycle_start = path.index(dep_id)
                    cycles.append(path[cycle_start:] + [dep_id])
                elif color.get(dep_id) == WHITE:
                    dfs(dep_id)
            path.pop()
            color[sid] = BLACK

        for sid in self.nodes:
            if color.get(sid) == WHITE:
                dfs(sid)

        return cycles

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_count": len(self.nodes),
            "edge_count": sum(len(deps) for deps in self.edges.values()),
            "edges": self.edges,
            "has_cycles": len(self.detect_cycles()) > 0,
        }


# ---------------------------------------------------------------------------
# Skill Code Generator
# ---------------------------------------------------------------------------

class SkillCodeGenerator:
    """自动生成技能的 Python 代码 / Auto-generates Python code for skills."""

    EXECUTE_TEMPLATE = '''
class {class_name}:
    """{description}

    Auto-generated by Nonull SkillGenesis | 由 Nonull SkillGenesis 自动生成.

    Category: {category}
    Tags: {tags}
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {{}}
        self.name = "{name}"
        self.description = "{description}"
        self.category = "{category}"
        self._metrics: dict = {{
            "execution_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "total_duration_ms": 0.0,
        }}

    def execute(self, **kwargs) -> dict:
        """执行技能的主方法 / Main execute method for the skill.

        Args:
            **kwargs: 按照输入模式传入的参数 / Parameters per input schema

        Returns:
            dict: 包含执行结果的字典 / Dictionary with execution results

        Raises:
            ValueError: 参数验证失败 / Parameter validation failed
            RuntimeError: 执行过程中出错 / Error during execution
        """
        import time
        start_time = time.time()

        try:
            # --- 输入验证 / Input validation ---
            self._validate_input(kwargs)

            # --- 安全检查 / Safety checks ---
            self._safety_check(kwargs)

            # --- 核心逻辑 / Core logic ---
            result = self._execute_impl(**kwargs)

            # --- 更新指标 / Update metrics ---
            elapsed = (time.time() - start_time) * 1000
            self._update_metrics(success=True, duration_ms=elapsed)

            return {{
                "success": True,
                "result": result,
                "duration_ms": elapsed,
            }}

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self._update_metrics(success=False, duration_ms=elapsed)
            return {{
                "success": False,
                "error": str(e),
                "duration_ms": elapsed,
            }}

    def _validate_input(self, params: dict) -> None:
        """验证输入参数 / Validate input parameters."""
        required = {required_fields}
        for field in required:
            if field not in params:
                raise ValueError(
                    f"缺少必需参数: {{field}} | Missing required parameter: {{field}}"
                )

    def _safety_check(self, params: dict) -> None:
        """执行安全检查 / Execute safety checks."""
        # 生成的安全钩子 / Generated safety hooks
        pass

    def _execute_impl(self, **kwargs) -> Any:
        """核心执行逻辑 — 需要根据模式定制 / Core execution logic — customize per pattern.

        这是从执行轨迹中提取的步骤序列的代码表示。
        This is the code representation of the step sequence extracted from traces.
        """
        # TODO: 实现从模式中提取的具体步骤 / Implement specific steps from pattern
        raise NotImplementedError("Subclass must implement _execute_impl")

    def _update_metrics(self, success: bool, duration_ms: float) -> None:
        """更新性能指标 / Update performance metrics."""
        self._metrics["execution_count"] += 1
        if success:
            self._metrics["success_count"] += 1
        else:
            self._metrics["failure_count"] += 1
        self._metrics["total_duration_ms"] += duration_ms

    def get_metrics(self) -> dict:
        """获取技能性能指标 / Get skill performance metrics."""
        m = self._metrics
        return {{
            **m,
            "success_rate": m["success_count"] / max(m["execution_count"], 1),
            "avg_duration_ms": m["total_duration_ms"] / max(m["execution_count"], 1),
        }}

    def reset_metrics(self) -> None:
        """重置性能指标 / Reset performance metrics."""
        self._metrics = {{
            "execution_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "total_duration_ms": 0.0,
        }}
'''

    @classmethod
    def generate_code(
        cls,
        name: str,
        description: str,
        category: str,
        tags: List[str],
        required_fields: List[str],
        steps_sequence: List[Dict[str, Any]],
    ) -> str:
        """生成技能的 Python 源代码 / Generate Python source code for a skill.

        Args:
            name: 技能名称 / Skill name
            description: 技能描述 / Skill description
            category: 技能类别 / Skill category
            tags: 标签列表 / List of tags
            required_fields: 必需输入字段 / Required input fields
            steps_sequence: 从模式提取的步骤序列 / Step sequence from pattern

        Returns:
            生成的 Python 代码字符串 / Generated Python code as string
        """
        class_name = cls._to_class_name(name)
        tags_str = ", ".join(tags)

        # 从步骤序列生成 _execute_impl 的注释 / Generate comments from step sequence
        impl_comment = cls._generate_impl_comment(steps_sequence)

        code = cls.EXECUTE_TEMPLATE.format(
            class_name=class_name,
            name=name,
            description=description.replace('"', '\\"'),
            category=category,
            tags=tags_str,
            required_fields=repr(required_fields),
        )

        # 替换 execute_impl 的占位注释 / Replace placeholder comment in execute_impl
        old_placeholder = "        # TODO: 实现从模式中提取的具体步骤 / Implement specific steps from pattern"
        code = code.replace(old_placeholder, impl_comment)

        return code

    @classmethod
    def _to_class_name(cls, name: str) -> str:
        """将技能名转换为类名 / Convert skill name to class name.

        e.g. "data_analysis" -> "DataAnalysisSkill"
        """
        # 蛇形转帕斯卡 / snake_case to PascalCase
        parts = name.replace("-", "_").split("_")
        return "".join(p.capitalize() for p in parts if p) + "Skill"

    @classmethod
    def _generate_impl_comment(
        cls, steps: List[Dict[str, Any]]
    ) -> str:
        """从步骤序列生成 _execute_impl 的注释和骨架。

        Generate comments and skeleton for _execute_impl from step sequence.
        """
        if not steps:
            return (
                "        # 此技能的步骤序列为空 | Step sequence is empty for this skill\n"
                "        return {\"message\": \"No steps defined\"}"
            )

        lines = [
            f"        # 从 {len(steps)} 步轨迹自动生成 / Auto-generated from {len(steps)}-step trace\n"
        ]
        for i, step in enumerate(steps):
            action = step.get("action", "unknown")
            tool = step.get("tool", "")
            tool_str = f" (tool: {tool})" if tool else ""
            lines.append(f"        # Step {i + 1}: {action}{tool_str}")

        lines.append("")
        lines.append('        return {"message": "Auto-generated skill skeleton"}')
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Skill Genesis Engine
# ---------------------------------------------------------------------------

class SkillGenesis:
    """技能生成引擎 — 自主创建、验证和管理技能。

    Skill Genesis Engine — autonomously creates, validates, and manages skills.

    负责：
    - 从执行模式生成技能定义
    - 自动生成技能 Python 代码
    - 验证技能的安全性和质量
    - 管理技能的依赖图
    - 从轨迹中自主学习新技能
    - 建议技能改进方案
    """

    def __init__(self, safety_rules: Optional[List[str]] = None):
        self.safety_rules = safety_rules or [
            "不得执行破坏性文件操作而不确认 | No destructive file ops without confirmation",
            "不得读取敏感文件 | No reading sensitive files",
            "不得执行远程命令 | No remote command execution",
            "输入参数必须进行类型验证 | Input params must be type-validated",
            "必须有错误处理和回滚 | Must have error handling and rollback",
        ]
        self.skills: Dict[str, SkillDefinition] = {}
        self.dependency_graph = SkillDependencyGraph()
        self.code_generator = SkillCodeGenerator()

        self.stats: Dict[str, Any] = {
            "skills_generated": 0,
            "skills_validated": 0,
            "validation_passed": 0,
            "validation_failed": 0,
            "skills_activated": 0,
            "auto_learned_skills": 0,
        }

        logger.info("SkillGenesis initialized | 技能生成引擎已初始化")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_skill(
        self,
        pattern: Any,
        name: Optional[str] = None,
        category: Optional[str] = None,
    ) -> SkillDefinition:
        """从模式生成新技能。

        Generate a new skill from an execution pattern.

        Args:
            pattern: 执行模式（ExtractedPattern 或包含所需字段的 dict）
                     Execution pattern (ExtractedPattern or dict with required fields)
            name: 技能名称（可选，默认从模式生成）
                  Optional skill name (defaults to pattern-derived name)
            category: 技能类别（可选，默认从模式推断）
                      Optional skill category (defaults to pattern-inferred)

        Returns:
            生成的技能定义 / Generated SkillDefinition

        Raises:
            ValueError: 如果模式无效 / If pattern is invalid
        """
        pattern_dict = self._normalize_pattern(pattern)
        if not pattern_dict:
            raise ValueError("无效的模式 | Invalid pattern")

        skill_name = name or pattern_dict.get("name", "unnamed_skill")
        skill_category = self._infer_category(
            category or pattern_dict.get("pattern_type", "custom")
        )

        # 生成代码 / Generate code
        code = self.code_generator.generate_code(
            name=skill_name,
            description=pattern_dict.get("description", ""),
            category=skill_category.value,
            tags=pattern_dict.get("tags", []),
            required_fields=self._infer_required_fields(pattern_dict),
            steps_sequence=pattern_dict.get("steps_sequence", []),
        )

        # 创建模式 / Create schema
        input_schema = SkillSchema(
            input_description=f"输入参数 for {skill_name}",
            required_fields=self._infer_required_fields(pattern_dict),
        )
        output_schema = SkillSchema(
            output_description=f"输出结果 for {skill_name}",
        )

        # 构建安全钩子 / Build safety hooks
        safety_hooks = self._create_safety_hooks(skill_name, pattern_dict)

        # 构建技能定义 / Build skill definition
        skill = SkillDefinition(
            name=skill_name,
            description=pattern_dict.get("description", f"Auto-generated skill: {skill_name}"),
            category=skill_category,
            code=code,
            input_schema=input_schema,
            output_schema=output_schema,
            safety_hooks=safety_hooks,
            source_trace_id=pattern_dict.get("source_trace_id"),
            source_pattern_id=pattern_dict.get("pattern_id"),
            tags=pattern_dict.get("tags", [skill_category.value]),
        )

        # 注册 / Register
        self.skills[skill.skill_id] = skill
        self.dependency_graph.add_skill(skill)
        self.stats["skills_generated"] += 1

        logger.info(
            f"Generated skill '{skill_name}' ({skill.skill_id[:8]}) | "
            f"已生成技能 '{skill_name}'"
        )
        return skill

    def validate_skill(self, skill: SkillDefinition) -> ValidationReport:
        """验证技能的完整性和安全性。

        Validate a skill's completeness and safety.

        Args:
            skill: 要验证的技能定义 / Skill definition to validate

        Returns:
            验证报告 / Validation report
        """
        report = ValidationReport(
            skill_id=skill.skill_id,
            skill_name=skill.name,
        )

        # --- Check 1: 基本字段 / Basic fields ---
        basic_fields_ok = all([
            bool(skill.name),
            bool(skill.description),
            bool(skill.code),
        ])
        report.add_check(
            "basic_fields",
            basic_fields_ok,
            "技能必须有名称、描述和代码 | Skill must have name, description, and code",
        )

        # --- Check 2: 代码可编译 / Code compilable ---
        code_ok = self._validate_code(skill.code)
        report.add_check(
            "code_compiles",
            code_ok,
            "技能代码必须可编译 | Skill code must compile without syntax errors",
        )

        # --- Check 3: 输入模式 / Input schema ---
        schema_ok = all([
            bool(skill.input_schema.input_description),
            bool(skill.output_schema.output_description),
        ])
        report.add_check(
            "schema_defined",
            schema_ok,
            "技能必须有输入和输出模式 | Skill must have input and output schemas",
            severity="warning",
        )

        # --- Check 4: 安全检查 / Safety rules ---
        safety_ok, safety_findings = self._check_safety_rules(skill)
        report.add_check(
            "safety_rules",
            safety_ok,
            f"安全检查: {'全部通过' if safety_ok else '发现 ' + str(safety_findings)} | "
            f"Safety: {'passed' if safety_ok else 'issues: ' + str(safety_findings)}",
        )

        # --- Check 5: 依赖循环 / Dependency cycles ---
        cycles = self.dependency_graph.detect_cycles()
        cycles_for_skill = [
            c for c in cycles if skill.skill_id in c
        ]
        no_cycles = len(cycles_for_skill) == 0
        report.add_check(
            "dependency_cycles",
            no_cycles,
            f"检测到 {len(cycles_for_skill)} 个依赖循环 | "
            f"Detected {len(cycles_for_skill)} dependency cycles",
        )

        # --- Check 6: execute 方法存在 / Execute method exists ---
        has_execute = "def execute" in skill.code
        report.add_check(
            "execute_method",
            has_execute,
            "技能必须有 execute 方法 | Skill must have an execute method",
        )

        # 计算分数 / Compute scores
        report.safety_score = 0.0 if not safety_ok else 1.0
        passed_count = sum(1 for c in report.checks if c["passed"])
        report.quality_score = passed_count / max(len(report.checks), 1)

        self.stats["skills_validated"] += 1
        if report.passed:
            self.stats["validation_passed"] += 1
        else:
            self.stats["validation_failed"] += 1

        logger.info(
            f"Validated skill '{skill.name}': {'PASS' if report.passed else 'FAIL'} "
            f"(safety={report.safety_score:.1f}, quality={report.quality_score:.1f}) | "
            f"已验证技能 '{skill.name}': {'通过' if report.passed else '未通过'}"
        )
        return report

    def auto_learn_from_trace(self, trace: Any) -> Optional[SkillDefinition]:
        """从执行轨迹中自动发现并创建新技能。

        Auto-discover and create a new skill from an execution trace.

        Args:
            trace: 执行轨迹（ExecutionTrace 或 dict）
                   Execution trace (ExecutionTrace or dict)

        Returns:
            生成的技能定义，如果无法生成则返回 None
            Generated SkillDefinition, or None if generation not possible
        """
        trace_dict = self._normalize_trace(trace)
        if not trace_dict:
            logger.warning("无效的轨迹，无法学习技能 | Invalid trace, cannot learn")
            return None

        steps = trace_dict.get("steps", [])
        if len(steps) < 3:
            logger.info(
                f"轨迹步骤太少 ({len(steps)} < 3)，不适合生成技能 | "
                f"Too few steps for skill generation"
            )
            return None

        # 从轨迹信息构建模式 / Build pattern from trace info
        name = f"auto_{trace_dict.get('task_type', 'task')}_{uuid.uuid4().hex[:6]}"
        description = f"从轨迹自动学习: {trace_dict.get('task', '')[:100]}"

        pattern = {
            "name": name,
            "description": description,
            "pattern_type": trace_dict.get("task_type", "workflow"),
            "steps_sequence": steps,
            "tags": [trace_dict.get("task_type", "general"), "auto_learned"],
            "source_trace_id": trace_dict.get("trace_id"),
        }

        try:
            skill = self.generate_skill(pattern, name=name)
            skill.status = SkillStatus.DRAFT

            # 自动验证 / Auto-validate
            report = self.validate_skill(skill)
            if report.passed:
                skill.activate()
                self.stats["skills_activated"] += 1

            self.stats["auto_learned_skills"] += 1
            logger.info(
                f"Auto-learned skill '{skill.name}' from trace | "
                f"从轨迹自动学习技能 '{skill.name}'"
            )
            return skill

        except Exception as e:
            logger.error(f"自动学习技能失败: {e} | Auto-learn skill failed: {e}")
            return None

    def suggest_skill_improvements(self, skill_id: str) -> List[str]:
        """建议技能改进方案 / Suggest improvements for a skill.

        Args:
            skill_id: 技能 ID / Skill identifier

        Returns:
            改进建议列表 / List of improvement suggestions
        """
        skill = self.skills.get(skill_id)
        if not skill:
            return [f"未找到技能: {skill_id} | Skill not found: {skill_id}"]

        suggestions: List[str] = []

        # 基于性能指标 / Based on performance metrics
        if skill.metrics.total_calls > 0:
            if skill.metrics.success_rate() < 0.8:
                suggestions.append(
                    f"成功率较低 ({skill.metrics.success_rate():.0%})，建议检查错误处理 | "
                    f"Low success rate, check error handling"
                )
            if skill.metrics.avg_execution_ms > 5000:
                suggestions.append(
                    f"平均执行时间较长 ({skill.metrics.avg_execution_ms:.0f}ms)，建议优化性能 | "
                    f"High avg execution time, consider optimization"
                )

        # 基于安全检查 / Based on safety checks
        if not skill.safety_hooks:
            suggestions.append(
                "缺少安全检查钩子，建议添加输入验证 | "
                "Missing safety hooks, add input validation"
            )

        # 基于代码结构 / Based on code structure
        if "TODO" in skill.code or "pass" in skill.code.split("\n")[-5:]:
            suggestions.append(
                "代码包含未实现的占位符，建议完善 _execute_impl | "
                "Code contains unimplemented placeholders"
            )

        # 基于依赖 / Based on dependencies
        if not skill.dependencies:
            suggestions.append(
                "无依赖声明，如果技能依赖其他功能请添加 | "
                "No dependencies declared"
            )

        if not suggestions:
            suggestions.append(
                "技能状态良好，暂无改进建议 | Skill is in good state, no improvements needed"
            )

        return suggestions

    def register_skill_callback(
        self, callback: Callable[[SkillDefinition], bool]
    ) -> None:
        """注册外部回调以在生成后持久化或通知技能。

        Register an external callback to persist or notify about generated skills.

        Args:
            callback: 接收 SkillDefinition 返回 bool 的回调
                      Callback that receives SkillDefinition and returns bool
        """
        self._register_callback = callback
        logger.info("External registration callback registered | 已注册外部注册回调")

    def get_skill(self, skill_id: str) -> Optional[SkillDefinition]:
        """通过 ID 获取技能 / Get a skill by ID."""
        return self.skills.get(skill_id)

    def find_skills_by_tag(self, tag: str) -> List[SkillDefinition]:
        """通过标签查找技能 / Find skills by tag."""
        return [s for s in self.skills.values() if tag in s.tags]

    def get_active_skills(self) -> List[SkillDefinition]:
        """获取所有已激活的技能 / Get all active skills."""
        return [s for s in self.skills.values() if s.status == SkillStatus.ACTIVE]

    def get_statistics(self) -> Dict[str, Any]:
        """获取技能生成统计 / Get skill genesis statistics."""
        stats = dict(self.stats)
        stats.update({
            "total_skills": len(self.skills),
            "active_skills": len(self.get_active_skills()),
            "draft_skills": sum(
                1 for s in self.skills.values() if s.status == SkillStatus.DRAFT
            ),
            "dependency_graph": self.dependency_graph.to_dict(),
        })
        return stats

    def reset(self) -> None:
        """重置所有已生成的技能 / Reset all generated skills."""
        self.skills.clear()
        self.dependency_graph = SkillDependencyGraph()
        self.stats = {
            "skills_generated": 0,
            "skills_validated": 0,
            "validation_passed": 0,
            "validation_failed": 0,
            "skills_activated": 0,
            "auto_learned_skills": 0,
        }
        logger.info("SkillGenesis reset | 技能生成引擎已重置")

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _normalize_pattern(self, pattern: Any) -> Optional[Dict[str, Any]]:
        """将不同格式的模式标准化为字典 / Normalize pattern to dict."""
        if hasattr(pattern, "to_dict"):
            return pattern.to_dict()
        if isinstance(pattern, dict):
            return pattern
        return None

    def _normalize_trace(self, trace: Any) -> Optional[Dict[str, Any]]:
        """将不同格式的轨迹标准化为字典 / Normalize trace to dict."""
        if hasattr(trace, "to_dict"):
            d = trace.to_dict()
            # 确保 steps 是 dict 列表 / Ensure steps are dicts
            if "steps" in d and hasattr(d["steps"], "__len__"):
                d["steps"] = [
                    s.to_dict() if hasattr(s, "to_dict") else s
                    for s in d.get("steps", [])
                ]
            return d
        if isinstance(trace, dict):
            return trace
        return None

    def _infer_category(self, type_str: str) -> SkillCategory:
        """从字符串推断技能类别 / Infer skill category from string."""
        mapping = {
            "utility": SkillCategory.UTILITY,
            "tool": SkillCategory.TOOL,
            "workflow": SkillCategory.WORKFLOW,
            "analysis": SkillCategory.ANALYSIS,
            "reasoning": SkillCategory.REASONING,
            "communication": SkillCategory.COMMUNICATION,
            "safety": SkillCategory.SAFETY,
            "memory": SkillCategory.MEMORY,
            "planning": SkillCategory.PLANNING,
        }
        return mapping.get(type_str.lower(), SkillCategory.CUSTOM)

    def _infer_required_fields(
        self, pattern_dict: Dict[str, Any]
    ) -> List[str]:
        """从模式推断必需字段 / Infer required fields from pattern."""
        # 从步骤序列的输入中推断 / Infer from step inputs
        fields: Set[str] = set()
        for step in pattern_dict.get("steps_sequence", []):
            inp = step.get("input", {})
            if isinstance(inp, dict):
                fields.update(inp.keys())

        # 限制到合理范围 / Limit to reasonable scope
        limited = list(fields)[:8]
        limited.sort()
        return limited

    def _create_safety_hooks(
        self, name: str, pattern_dict: Dict[str, Any]
    ) -> List[SafetyHook]:
        """为技能创建安全检查钩子 / Create safety check hooks for a skill."""
        hooks: List[SafetyHook] = []

        # 通用输入验证 / Generic input validation
        hooks.append(SafetyHook(
            name="input_validation",
            description="验证所有输入参数的类型和范围 | Validate input parameter types and ranges",
            severity="error",
            error_message="输入参数验证失败 | Input parameter validation failed",
        ))

        # 检测危险操作 / Detect dangerous operations
        dangerous_keywords = ["delete", "remove", "overwrite", "drop", "shutdown"]
        steps_text = str(pattern_dict.get("steps_sequence", []))
        for kw in dangerous_keywords:
            if kw in steps_text.lower():
                hooks.append(SafetyHook(
                    name=f"safety_{kw}",
                    description=f"检测到 '{kw}' 操作，需要确认 | '{kw}' operation requires confirmation",
                    severity="warning",
                    error_message=f"危险操作 '{kw}' 需要额外确认 | Dangerous operation requires confirmation",
                ))

        return hooks

    def _validate_code(self, code: str) -> bool:
        """验证代码语法 / Validate code syntax."""
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def _check_safety_rules(
        self, skill: SkillDefinition
    ) -> Tuple[bool, List[str]]:
        """检查技能是否符合安全规则 / Check skill against safety rules."""
        findings: List[str] = []
        code_lower = skill.code.lower()

        dangerous_patterns = [
            (r"\brm\s+-rf\b", "递归删除命令 | Recursive delete command"),
            (r"os\.remove\(", "文件删除操作 | File deletion"),
            (r"shutil\.rmtree\(", "目录删除操作 | Directory removal"),
            (r"eval\s*\(", "eval() 执行 | Eval execution"),
            (r"exec\s*\(", "exec() 执行 | Exec execution"),
            (r"__import__\s*\(", "动态导入 | Dynamic import"),
            (r"subprocess\.", "子进程调用 | Subprocess call"),
            (r"pickle\.loads\(", "反序列化危险操作 | Unsafe deserialization"),
        ]

        for pattern, desc in dangerous_patterns:
            if re.search(pattern, code_lower):
                findings.append(desc)

        return len(findings) == 0, findings
