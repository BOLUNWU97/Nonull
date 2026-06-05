"""
Code Skills - 代码技能

自动驾驶领域的代码审查、优化、重构和缺陷检测。
Code review, optimization, refactoring, and bug detection for autonomous driving.
"""

from __future__ import annotations

import re
import ast
import enum
import logging
from typing import Any, Dict, List, Optional, Tuple

from skills.base import (
    BaseSkill,
    SkillMetadata,
    SkillCategory,
    SkillResult,
    SkillValidationError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 代码审查技能 / Code Review Skill
# =============================================================================


class CodeReviewSkill(BaseSkill):
    """
    C++/Python 代码审查技能。
    C++/Python code review skill for AD/ADAS.

    检查项 / Checks:
        - MISRA 编码规范 / MISRA coding guidelines
        - AUTOSAR C++14 规范 / AUTOSAR C++14 rules
        - 常见安全漏洞 / Common security vulnerabilities
        - ADAS 相关代码模式 / ADAS-specific code patterns
        - 代码风格一致性 / Code style consistency
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="code_review",
            version="1.1.0",
            category=SkillCategory.CODE,
            description="C++/Python代码审查：检查编码规范、安全漏洞和ADAS最佳实践",
            author="Nonull",
            tags=["code", "review", "cpp", "python", "misra", "autosar"],
            input_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "源代码 / Source code"},
                    "language": {
                        "type": "string",
                        "enum": ["python", "cpp", "c++"],
                        "description": "编程语言 / Programming language",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "文件路径（可选） / File path (optional)",
                    },
                    "strictness": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "严格程度 / Strictness level",
                    },
                },
                "required": ["code", "language"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "issues": {"type": "array"},
                    "summary": {"type": "string"},
                    "score": {"type": "number"},
                },
            },
            safety_level=2,
        )

    def _validate_input(self, context: Dict[str, Any]) -> None:
        code = context.get("code", "")
        language = context.get("language", "")
        if not code or not code.strip():
            raise SkillValidationError("'code' field is required and must not be empty.")
        if not language:
            raise SkillValidationError("'language' field is required.")
        if language.lower() not in ("python", "cpp", "c++"):
            raise SkillValidationError(
                f"Unsupported language: {language}. Supported: python, cpp, c++"
            )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        code: str = context["code"]
        language: str = context["language"].lower()
        strictness: str = context.get("strictness", "medium")
        file_path: str = context.get("file_path", "")

        issues: List[Dict[str, Any]] = []
        summary_parts: List[str] = []

        # 语言特定检查 / Language-specific checks
        if language == "python":
            issues.extend(self._review_python(code, strictness))
        else:
            issues.extend(self._review_cpp(code, strictness))

        # 通用检查 / General checks
        issues.extend(self._check_general_patterns(code, language))

        # 生成报告 / Generate report
        total_issues = len(issues)
        critical = sum(1 for i in issues if i["severity"] == "critical")
        major = sum(1 for i in issues if i["severity"] == "major")
        minor = sum(1 for i in issues if i["severity"] == "minor")

        score = self._calculate_score(total_issues, critical, major)

        summary_parts.append(f"发现 {total_issues} 个问题")
        summary_parts.append(f"严重: {critical}, 主要: {major}, 轻微: {minor}")
        summary_parts.append(f"代码质量评分: {score}/100")

        return {
            "issues": sorted(issues, key=lambda x: {"critical": 0, "major": 1, "minor": 2}.get(x.get("severity", "minor"), 3)),
            "summary": "; ".join(summary_parts),
            "score": score,
            "language": language,
            "file_path": file_path,
            "total_issues": total_issues,
            "critical_count": critical,
            "major_count": major,
            "minor_count": minor,
        }

    def _review_python(self, code: str, strictness: str) -> List[Dict[str, Any]]:
        """Python 专用代码审查 / Python-specific code review."""
        issues: List[Dict[str, Any]] = []
        lines = code.split("\n")
        threshold = {"low": 3, "medium": 2, "high": 1}

        # AST 解析检查 / AST parsing check
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            issues.append({
                "line": e.lineno or 0,
                "column": e.offset or 0,
                "severity": "critical",
                "type": "SYNTAX_ERROR",
                "message": f"语法错误: {e.msg}",
                "suggestion": "修复语法错误后重新审查",
            })
            return issues

        # 检查裸 except / Bare except check
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                line = getattr(node, "lineno", 0)
                issues.append({
                    "line": line,
                    "severity": "major",
                    "type": "BARE_EXCEPT",
                    "message": "使用裸 except 会捕获所有异常，包括 SystemExit",
                    "suggestion": "改为 except Exception as e:",
                    "code_snippet": f"Line {line}: except:",
                })

        # ADAS 专用检查 / ADAS-specific checks
        adas_patterns: List[Tuple[str, str, str, str]] = [
            (r"while\s+True", "INFINITE_LOOP", "使用 'while True' 可能导致死循环",
             "考虑添加超时或条件终止 / Add timeout or termination condition"),
            (r"\.sleep\(\s*(-?\d+\.?\d*)", "MAGIC_SLEEP", "使用固定延时可能导致时序问题",
             "使用基于事件的同步机制 / Use event-based synchronization"),
            (r"global\s+\w+", "GLOBAL_STATE", "全局变量在多线程环境下不安全",
             "考虑使用线程安全的数据结构或依赖注入"),
            (r"eval\s*\(|exec\s*\(", "CODE_EXECUTION", "动态执行代码存在安全风险",
             "避免使用 eval/exec，可选 ast.literal_eval"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, issue_type, msg, suggestion in adas_patterns:
                if re.search(pattern, line):
                    issues.append({
                        "line": i,
                        "severity": "major",
                        "type": issue_type,
                        "message": msg,
                        "suggestion": suggestion,
                        "code_snippet": line.strip()[:80],
                    })

        # 检查长函数 / Long function check
        current_func = ""
        func_start = 0
        func_lines = 0
        for i, line in enumerate(lines):
            func_match = re.match(r"^def\s+\w+", line)
            if func_match:
                if func_lines > 50:
                    issues.append({
                        "line": func_start,
                        "severity": "minor",
                        "type": "LONG_FUNCTION",
                        "message": f"函数 '{current_func}' 过长 ({func_lines} 行)",
                        "suggestion": "考虑拆分为多个小函数",
                    })
                current_func = func_match.group(0).split()[1]
                func_start = i + 1
                func_lines = 0
            elif line.strip() and not line.strip().startswith("#"):
                func_lines += 1

        return issues

    def _review_cpp(self, code: str, strictness: str) -> List[Dict[str, Any]]:
        """C++ 专用代码审查 / C++-specific code review."""
        issues: List[Dict[str, Any]] = []
        lines = code.split("\n")

        # MISRA / AUTOSAR 模式检查 / MISRA/AUTOSAR pattern checks
        cpp_patterns: List[Tuple[str, str, str, str, str]] = [
            (r"malloc\s*\(", "MISRA_C_MALLOC", "critical",
             "禁止使用 malloc/free (MISRA C:2012 Rule 22.1)",
             "使用智能指针或标准容器 / Use smart pointers or std containers"),
            (r"printf\s*\(", "MISRA_PRINTF", "major",
             "避免使用 printf (MISRA C:2012 Rule 21.6)",
             "使用 iostream 或 spdlog"),
            (r"goto\s+", "MISRA_GOTO", "major",
             "禁止使用 goto (MISRA C:2012 Rule 15.1)",
             "使用结构化控制流 / Use structured control flow"),
            (r"\bnew\b", "RAW_NEW", "major",
             "使用裸 new 可能导致内存泄漏",
             "使用 std::make_unique 或 std::make_shared"),
            (r"delete\s+", "RAW_DELETE", "major",
             "使用裸 delete 不安全",
             "使用智能指针自动管理生命周期"),
            (r"using\s+namespace\s+std", "USING_NAMESPACE_STD", "minor",
             "using namespace std 可能导致命名冲突 (AUTOSAR Rule A7-2-2)",
             "使用 std:: 前缀"),
            (r"/\*\s*TODO", "UNRESOLVED_TODO", "minor",
             "存在未完成的 TODO 注释",
             "完成实现或创建跟踪 issue"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, issue_type, severity, msg, suggestion in cpp_patterns:
                if re.search(pattern, line):
                    issues.append({
                        "line": i,
                        "severity": severity,
                        "type": issue_type,
                        "message": msg,
                        "suggestion": suggestion,
                        "code_snippet": line.strip()[:80],
                    })

        # 未初始化变量 / Uninitialized variables
        for i, line in enumerate(lines, 1):
            match = re.match(
                r"^\s*(int|float|double|bool|char|uint\d+_t|int\d+_t)\s+\w+;?\s*$",
                line,
            )
            if match:
                issues.append({
                    "line": i,
                    "severity": "major",
                    "type": "UNINIT_VAR",
                    "message": f"变量 '{match.group(0).split()[1]}' 未初始化",
                    "suggestion": "声明时立即初始化 / Initialize at declaration",
                    "code_snippet": line.strip()[:80],
                })

        # 检查函数长度 / Function length check (C++)
        current_func = ""
        brace_depth = 0
        func_start = 0
        func_lines = 0
        in_func = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            # 简单函数定义检测 / Simple function detection
            if re.match(r"^(?:virtual\s+)?(?:void|int|float|double|bool|"
                        r"std::\w+|auto)\s+\w+\s*\(", stripped):
                current_func = stripped.split("(")[0].split()[-1]
                func_start = i + 1
                in_func = True
                func_lines = 0

            if in_func:
                brace_depth += stripped.count("{") - stripped.count("}")
                func_lines += 1
                if brace_depth <= 0 and i > func_start:
                    if func_lines > 80:
                        issues.append({
                            "line": func_start,
                            "severity": "minor",
                            "type": "LONG_FUNCTION",
                            "message": f"函数 '{current_func}' 过长 ({func_lines} 行)",
                            "suggestion": "按单一职责原则拆分",
                        })
                    in_func = False

        return issues

    def _check_general_patterns(
        self, code: str, language: str
    ) -> List[Dict[str, Any]]:
        """通用代码模式检查 / General code pattern checks."""
        issues: List[Dict[str, Any]] = []
        lines = code.split("\n")

        # 硬编码常量 / Hardcoded constants
        threshold_values = 0.0, 1.0, 3.14159, 2.71828  # 已知常量
        for i, line in enumerate(lines, 1):
            # 检测魔法数字 / Magic number detection
            magic = re.findall(r'\b\d+\.?\d*\b', line)
            for m in magic:
                val = float(m)
                if val > 10 and val not in threshold_values:
                    if not re.search(r'(?:constexpr|const|#define|MAX_|MIN_|THRESHOLD)', line):
                        issues.append({
                            "line": i,
                            "severity": "minor",
                            "type": "MAGIC_NUMBER",
                            "message": f"硬编码数值 {m}，建议定义为命名常量",
                            "suggestion": "提取为 const/constexpr 变量 / Extract to named constant",
                            "code_snippet": line.strip()[:80],
                        })

        # 检查缺少日志 / Missing logging checks
        if language == "cpp" and "catch" in code:
            catch_blocks = re.findall(r'catch\s*\([^)]+\)\s*\{([^}]*)\}', code)
            for idx, block in enumerate(catch_blocks):
                if "log" not in block.lower() and "cerr" not in block:
                    issues.append({
                        "line": 0,
                        "severity": "minor",
                        "type": "MISSING_LOG_IN_CATCH",
                        "message": f"catch 块 #{idx + 1} 缺少日志记录",
                        "suggestion": "在 catch 中添加错误日志 / Add error logging in catch",
                    })

        return issues

    def _calculate_score(self, total: int, critical: int, major: int) -> float:
        """计算代码质量评分 / Calculate code quality score."""
        score = 100.0
        score -= critical * 15.0
        score -= major * 5.0
        score -= (total - critical - major) * 1.0
        return max(0.0, min(100.0, score))


# =============================================================================
# 代码优化技能 / Code Optimization Skill
# =============================================================================


class CodeOptimizationSkill(BaseSkill):
    """
    代码性能优化技能。
    Code performance optimization skill for AD/ADAS.

    检查项 / Checks:
        - 算法复杂度 / Algorithm complexity
        - 内存分配模式 / Memory allocation patterns
        - 并行化机会 / Parallelization opportunities
        - 编译器优化提示 / Compiler optimization hints
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="code_optimization",
            version="1.0.0",
            category=SkillCategory.CODE,
            description="代码性能优化：分析瓶颈、提出优化方案",
            author="Nonull",
            tags=["code", "optimization", "performance", "cpp", "python"],
            input_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "源代码"},
                    "language": {"type": "string", "enum": ["python", "cpp"]},
                    "profile_data": {
                        "type": "object",
                        "description": "性能分析数据（可选）",
                    },
                    "target": {
                        "type": "string",
                        "enum": ["latency", "throughput", "memory", "general"],
                        "description": "优化目标",
                    },
                },
                "required": ["code", "language"],
            },
            safety_level=1,
        )

    def _validate_input(self, context: Dict[str, Any]) -> None:
        if not context.get("code"):
            raise SkillValidationError("'code' is required")
        if context.get("language") not in ("python", "cpp"):
            raise SkillValidationError("Unsupported language")

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        code: str = context["code"]
        language: str = context["language"].lower()
        profile_data: Optional[Dict] = context.get("profile_data")
        target: str = context.get("target", "general")

        optimizations: List[Dict[str, Any]] = []
        suggestions: List[str] = []

        if language == "python":
            optimizations.extend(self._optimize_python(code, target))
        else:
            optimizations.extend(self._optimize_cpp(code, target))

        if profile_data:
            optimizations.extend(self._profile_guided(profile_data))

        summary = (
            f"发现 {len(optimizations)} 个优化机会 "
            f"(目标: {target}, 语言: {language})"
        )

        estimated_gain = sum(o.get("estimated_gain", 0) for o in optimizations)
        priority_count = {
            "high": sum(1 for o in optimizations if o.get("priority") == "high"),
            "medium": sum(1 for o in optimizations if o.get("priority") == "medium"),
            "low": sum(1 for o in optimizations if o.get("priority") == "low"),
        }

        return {
            "optimizations": sorted(
                optimizations,
                key=lambda x: {"high": 0, "medium": 1, "low": 2}[x.get("priority", "low")],
            ),
            "summary": summary,
            "estimated_performance_gain_pct": estimated_gain,
            "priority_counts": priority_count,
            "target": target,
            "language": language,
        }

    def _optimize_python(self, code: str, target: str) -> List[Dict[str, Any]]:
        """Python 代码优化 / Python code optimization."""
        optimizations: List[Dict[str, Any]] = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            # 列表推导式 / List comprehension
            if re.search(r'\bfor\s+\w+\s+in\s+.+:\s*$', line):
                next_line = lines[i] if i < len(lines) else ""
                if '.append(' in next_line:
                    optimizations.append({
                        "line": i,
                        "type": "LIST_COMPREHENSION",
                        "message": "for + append 可改为列表推导式",
                        "original": f"{line}\n{next_line}",
                        "suggestion": "使用 [expr for item in iterable]",
                        "priority": "medium",
                        "estimated_gain": 15,
                    })

            # 字符串拼接 / String concatenation
            if re.search(r'\w+\s*\+=\s*["\']', line):
                optimizations.append({
                    "line": i,
                    "type": "STRING_CONCAT",
                    "message": "低效字符串拼接，建议使用 join()",
                    "original": line.strip()[:80],
                    "suggestion": '改为 "".join([...]) 或 f-string',
                    "priority": "medium",
                    "estimated_gain": 10,
                })

        # 全局分析 / Global analysis
        try:
            tree = ast.parse(code)
            # 检测向量化机会 / Vectorization opportunities
            for node in ast.walk(tree):
                if isinstance(node, ast.For):
                    if self._detect_simple_loop(node):
                        optimizations.append({
                            "line": getattr(node, "lineno", 0),
                            "type": "VECTORIZATION",
                            "message": "检测到可向量化的循环",
                            "suggestion": "使用 NumPy 或 Numba 加速 / Use NumPy or Numba",
                            "priority": "high",
                            "estimated_gain": 50,
                        })
                    break
        except SyntaxError:
            pass

        return optimizations

    def _optimize_cpp(self, code: str, target: str) -> List[Dict[str, Any]]:
        """C++ 代码优化 / C++ code optimization."""
        optimizations: List[Dict[str, Any]] = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            # 传值改传引用 / Pass by value -> const ref
            match = re.search(
                r'\b(void|int|float|double|bool|std::\w+)\s+(\w+)\s*\(\s*'
                r'(?:const\s+)?(std::\w+(?:<[^>]+>)?)\s+(\w+)',
                line,
            )
            if match:
                param_type = match.group(3)
                param_name = match.group(4)
                if param_type.startswith("std::") and "string" in param_type or \
                   param_type.endswith("vector") or param_type.endswith("map"):
                    optimizations.append({
                        "line": i,
                        "type": "PASS_BY_REF",
                        "message": f"参数 '{param_name}' 按值传递导致拷贝",
                        "original": line.strip()[:80],
                        "suggestion": f"改为 const {param_type}& {param_name}",
                        "priority": "high",
                        "estimated_gain": 30,
                    })

            # 未使用 reserve / Missing reserve
            if re.search(r'std::\s*vector\s*<', line) and "reserve" not in code:
                if i <= 5:  # 只在近声明处提示 / Hint near declaration
                    optimizations.append({
                        "line": i,
                        "type": "MISSING_RESERVE",
                        "message": "vector 声明后建议调用 reserve() 预分配",
                        "suggestion": "vec.reserve(expected_size)",
                        "priority": "low",
                        "estimated_gain": 5,
                    })

            # 移动语义 / Move semantics
            if re.search(r'return\s+\w+\s*;', line) and "return std::move" not in line:
                if re.search(r'(?:vector|string|map|set|unique_ptr)', line):
                    pass  # NRVO 通常已足够 / NRVO is usually sufficient

        return optimizations

    def _detect_simple_loop(self, node: ast.For) -> bool:
        """检测简单循环是否可向量化 / Detect vectorizable simple loops."""
        if not isinstance(node.body[0], (ast.Assign, ast.AugAssign)):
            return False
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and \
               isinstance(child.func, ast.Attribute):
                if child.func.attr in ("append", "extend"):
                    return True
        return False

    def _profile_guided(self, profile_data: Dict) -> List[Dict[str, Any]]:
        """性能分析引导的优化 / Profile-guided optimization."""
        optimizations = []
        hotspots = profile_data.get("hotspots", [])
        for hs in hotspots:
            optimizations.append({
                "function": hs.get("function", "unknown"),
                "type": "PROFILE_HOTSPOT",
                "message": f"热点函数 '{hs.get('function')}' 占总耗时 {hs.get('percent', 0)}%",
                "suggestion": "考虑内联、算法改进或并行化 / Inline, improve algorithm, or parallelize",
                "priority": "high",
                "estimated_gain": hs.get("percent", 0) * 0.5,
            })
        return optimizations


# =============================================================================
# 重构技能 / Refactoring Skill
# =============================================================================


class RefactoringSkill(BaseSkill):
    """
    代码重构技能。
    Code refactoring skill for improved maintainability.

    重构策略 / Refactoring strategies:
        - 提取函数 / Extract function
        - 消除重复代码 / Remove duplicate code
        - 简化条件逻辑 / Simplify conditional logic
        - 改进命名 / Improve naming
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="refactoring",
            version="1.0.0",
            category=SkillCategory.CODE,
            description="代码重构：提高可维护性和代码质量",
            author="Nonull",
            tags=["code", "refactoring", "clean-code"],
            input_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "language": {"type": "string", "enum": ["python", "cpp"]},
                    "strategy": {
                        "type": "string",
                        "enum": ["extract", "simplify", "rename", "all"],
                    },
                },
                "required": ["code", "language"],
            },
            safety_level=1,
        )

    def _validate_input(self, context: Dict[str, Any]) -> None:
        if not context.get("code"):
            raise SkillValidationError("'code' is required")

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        code: str = context["code"]
        language: str = context["language"].lower()
        strategy: str = context.get("strategy", "all")

        refactorings: List[Dict[str, Any]] = []

        if strategy in ("extract", "all"):
            refactorings.extend(self._detect_extraction_opportunities(code, language))
        if strategy in ("simplify", "all"):
            refactorings.extend(self._detect_simplification(code, language))
        if strategy in ("rename", "all"):
            refactorings.extend(self._detect_renaming(code, language))

        return {
            "refactorings": refactorings,
            "total_suggestions": len(refactorings),
            "language": language,
            "strategy": strategy,
            "summary": f"提出 {len(refactorings)} 个重构建议",
        }

    def _detect_extraction_opportunities(
        self, code: str, language: str
    ) -> List[Dict[str, Any]]:
        opportunities = []
        lines = code.split("\n")

        # 检查复杂表达式 / Check complex expressions
        for i, line in enumerate(lines, 1):
            if re.search(r'if\s+.*and.*or.*and', line):
                opportunities.append({
                    "line": i,
                    "type": "EXTRACT_CONDITION",
                    "message": "复杂条件表达式可提取为具名函数",
                    "suggestion": "将条件提取为 with_lane_change() 等描述性函数",
                    "original": line.strip()[:80],
                    "difficulty": "easy",
                })

        return opportunities

    def _detect_simplification(
        self, code: str, language: str
    ) -> List[Dict[str, Any]]:
        simplifications = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            # 多余 else / Redundant else
            if re.search(r'^\s+if\s+.*:.*\n\s+return', code):
                if re.search(r'else:', line):
                    simplifications.append({
                        "line": i,
                        "type": "REDUNDANT_ELSE",
                        "message": "if 中有 return 语句时 else 是多余的",
                        "suggestion": "移除 else，减少嵌套层级",
                        "difficulty": "easy",
                    })

            if re.search(r'if\s+not\s+not\s+', line):
                simplifications.append({
                    "line": i,
                    "type": "DOUBLE_NEGATION",
                    "message": "双重否定可简化",
                    "suggestion": "移除 not not",
                    "difficulty": "easy",
                })

        return simplifications

    def _detect_renaming(
        self, code: str, language: str
    ) -> List[Dict[str, Any]]:
        renames = []
        lines = code.split("\n")

        # 检查不规范的命名 / Check naming conventions
        for i, line in enumerate(lines, 1):
            # Python: 函数名应为 snake_case
            if language == "python":
                match = re.search(r'^def\s+([A-Z][a-zA-Z0-9_]*)\s*\(', line)
                if match:
                    renames.append({
                        "line": i,
                        "type": "RENAME_FUNCTION",
                        "message": f"函数名 '{match.group(1)}' 应为 snake_case",
                        "suggestion": f"重命名为 {self._to_snake_case(match.group(1))}",
                        "original": match.group(1),
                        "difficulty": "easy",
                    })

            # 单字母变量 / Single-letter variables
            match = re.search(r'\b([a-z])\s*=\s*(?:self\.)?\w+', line)
            if match and match.group(1) not in ('e', 'i', 'j', 'k', 'x', 'y', 'z'):
                renames.append({
                    "line": i,
                    "type": "RENAME_VARIABLE",
                    "message": f"单字母变量 '{match.group(1)}' 不利于可读性",
                    "suggestion": "使用描述性名称 / Use descriptive name",
                    "difficulty": "easy",
                })

        return renames

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """驼峰转蛇形 / CamelCase to snake_case."""
        s1 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
        return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


# =============================================================================
# 缺陷检测技能 / Bug Detection Skill
# =============================================================================


class BugDetectionSkill(BaseSkill):
    """
    静态缺陷检测技能。
    Static bug detection for autonomous driving code.

    检测类型 / Detection types:
        - 空指针解引用 / Null pointer dereference
        - 数组越界 / Buffer overflow
        - 死代码 / Dead code
        - 竞态条件 / Race conditions
        - 资源泄漏 / Resource leaks
        - ADAS 常见缺陷 / Common ADAS bugs
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="bug_detection",
            version="1.0.0",
            category=SkillCategory.CODE,
            description="缺陷检测：静态分析ADAS代码中的常见缺陷",
            author="Nonull",
            tags=["code", "bug", "static-analysis", "cpp", "python"],
            input_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "language": {"type": "string", "enum": ["python", "cpp"]},
                    "detection_level": {
                        "type": "string",
                        "enum": ["basic", "extended", "full"],
                    },
                },
                "required": ["code", "language"],
            },
            safety_level=3,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        code: str = context["code"]
        language: str = context["language"].lower()
        level: str = context.get("detection_level", "extended")

        bugs: List[Dict[str, Any]] = []
        lines = code.split("\n")

        if language == "python":
            bugs.extend(self._detect_python_bugs(code, lines, level))
        else:
            bugs.extend(self._detect_cpp_bugs(code, lines, level))

        bugs.extend(self._detect_adas_specific_bugs(code, language, lines))

        # 安全检查 / Safety check
        safety_score = 1.0
        critical_bugs = [b for b in bugs if b.get("severity") == "critical"]
        if critical_bugs:
            safety_score = max(0.1, 1.0 - len(critical_bugs) * 0.2)

        return {
            "bugs": bugs,
            "total_bugs": len(bugs),
            "critical_count": sum(1 for b in bugs if b.get("severity") == "critical"),
            "warning_count": sum(1 for b in bugs if b.get("severity") == "warning"),
            "info_count": sum(1 for b in bugs if b.get("severity") == "info"),
            "safety_score": safety_score,
            "language": language,
            "summary": f"发现 {len(bugs)} 个潜在缺陷",
        }

    def _detect_python_bugs(
        self, code: str, lines: List[str], level: str
    ) -> List[Dict[str, Any]]:
        bugs = []

        try:
            tree = ast.parse(code)

            # 检测可变默认参数 / Mutable default arguments
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for default in node.args.defaults:
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            bugs.append({
                                "line": getattr(node, "lineno", 0),
                                "type": "MUTABLE_DEFAULT",
                                "severity": "warning",
                                "message": f"函数 '{node.name}' 使用了可变对象作为默认参数",
                                "suggestion": '改为 None 并在函数体内初始化: if param is None: param = []',
                                "code_snippet": f"def {node.name}(...)",
                            })

            # 检测未处理的异常 / Unhandled exceptions
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr == "get" and \
                           isinstance(node.func.value, ast.Dict):
                            bugs.append({
                                "line": getattr(node, "lineno", 0),
                                "type": "DICT_GET_NO_DEFAULT",
                                "severity": "info",
                                "message": "dict.get() 未提供默认值",
                                "suggestion": "提供默认值或使用安全访问",
                            })

            # 检测 except pass / Bare except pass
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    for child in ast.walk(node):
                        if isinstance(child, ast.Pass):
                            if node.type is None:
                                bugs.append({
                                    "line": getattr(node, "lineno", 0),
                                    "type": "SILENT_EXCEPT",
                                    "severity": "warning",
                                    "message": "bare except + pass 会静默吞掉所有异常",
                                    "suggestion": "至少记录日志: logger.exception()",
                                })
                            break

        except SyntaxError as e:
            bugs.append({
                "line": e.lineno or 0,
                "type": "SYNTAX_ERROR",
                "severity": "critical",
                "message": f"语法错误: {e.msg}",
                "suggestion": "修复语法错误",
            })

        return bugs

    def _detect_cpp_bugs(
        self, code: str, lines: List[str], level: str
    ) -> List[Dict[str, Any]]:
        bugs = []

        for i, line in enumerate(lines, 1):
            # 空指针检查 / Null pointer check
            if re.search(r'\b(ptr|p|pointer)\s*==\s*NULL\b', line) or \
               re.search(r'\b(ptr|p|pointer)\s*==\s*nullptr\b', line):
                next_lines = lines[i:i + 3]
                next_code = "\n".join(next_lines)
                if not re.search(r'\b(ptr|p|pointer)\s*->', next_code):
                    bugs.append({
                        "line": i,
                        "type": "NULL_CHECK_WITHOUT_USE",
                        "severity": "info",
                        "message": "空指针检查后未使用该指针",
                        "suggestion": "确认逻辑完整性 / Verify logic completeness",
                    })

            # 数组越界风险 / Array bounds risk
            match = re.search(r'(\w+)\[(\d+)\]', line)
            if match:
                index = int(match.group(2))
                if index > 100:
                    bugs.append({
                        "line": i,
                        "type": "LARGE_STATIC_INDEX",
                        "severity": "warning",
                        "message": f"静态索引 {index} 可能导致越界",
                        "suggestion": "使用常量或边界检查 / Use constants or bounds check",
                        "code_snippet": line.strip()[:80],
                    })

            # 潜在的除零 / Potential division by zero
            if re.search(r'/\s*\w+\s*;', line) and not re.search(r'==\s*0|!=', line):
                var = re.findall(r'/\s*(\w+)', line)
                if var and var[0] not in ('2', '1', '0.5'):
                    bugs.append({
                        "line": i,
                        "type": "POTENTIAL_DIV_BY_ZERO",
                        "severity": "warning",
                        "message": f"变量 '{var[0]}' 可能为 0",
                        "suggestion": "除前检查: if (divisor != 0)",
                        "code_snippet": line.strip()[:80],
                    })

        return bugs

    def _detect_adas_specific_bugs(
        self, code: str, language: str, lines: List[str]
    ) -> List[Dict[str, Any]]:
        """ADAS 特定缺陷检测 / ADAS-specific bug detection."""
        bugs = []

        adas_patterns: List[Tuple[str, str, str, str]] = [
            (r"(?i)(speed|velocity|acceleration)\s*=\s*-?\d+\.?\d*",
             "HARDCODED_THRESHOLD", "warning",
             "硬编码速度阈值应定义为可配置参数"),
            (r"(?i)(if\s+not\s+(is_lane_valid|is_object_detected|is_sensor_ready))",
             "INVALID_STATE_CHECK", "critical",
             "传感器状态检查反向，可能导致误报"),
            (r"(?i)(timeout|time_out)\s*=\s*\d+\s*$",
             "HARDCODED_TIMEOUT", "info",
             "超时值应来自配置文件"),
            (r"(?i)(\bbreak\b.*\bcase\b|fall.?through)",
             "FALL_THROUGH", "warning",
             "switch fall-through 可能导致意外行为"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, bug_type, severity, msg in adas_patterns:
                if re.search(pattern, line):
                    bugs.append({
                        "line": i,
                        "type": bug_type,
                        "severity": severity,
                        "message": msg,
                        "code_snippet": line.strip()[:80],
                    })

        return bugs
