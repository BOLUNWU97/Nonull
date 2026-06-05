#!/usr/bin/env python3
"""Nonull Code Review Example 代码审查示例.

This example demonstrates how to use Nonull to review
ADAS C++ code, identifying safety issues, MISRA violations,
and performance concerns.

本示例演示如何使用 Nonull 审查 ADAS C++ 代码，
识别安全问题、MISRA 违规和性能问题。
"""

import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Sample ADAS C++ Code 示例 ADAS C++ 代码
# =============================================================================

SAMPLE_AEB_CODE = """
#include <cstdint>
#include <vector>

class AEBController {
public:
    AEBController() : braking_force_(0.0f), active_(false) {}

    void processSensorData(const float* data, size_t size) {
        if (size == 0) return;

        float velocity = data[0];
        float distance = data[1];
        float mass = 1.5f;  // Vehicle mass in tons (hardcoded)

        // Calculate time to collision
        float ttc = distance / velocity;

        if (ttc < 2.0f && ttc > 0.0f) {
            // Emergency braking needed
            float braking_force = calculateBrakingForce(velocity, distance, mass);
            applyBrakes(braking_force);
        }
    }

    void applyBrakes(float force) {
        braking_force_ = force;
        // Directly write to hardware register
        *reinterpret_cast<volatile uint32_t*>(0x40021000) = static_cast<uint32_t>(force);
        active_ = true;
    }

private:
    float calculateBrakingForce(float velocity, float distance, float mass) {
        // F = m * a, where a = v^2 / (2 * d)
        float deceleration = (velocity * velocity) / (2.0f * distance);
        return mass * deceleration;
    }

    float braking_force_;
    bool active_;
};
"""


# =============================================================================
# Code Review Engine (模拟 / Mock)
# =============================================================================

class CodeReviewEngine:
    """ADAS C++ 代码审查引擎 / ADAS C++ Code Review Engine."""

    def __init__(self, strictness: int = 3):
        self.strictness = strictness
        self.rules = self._load_rules()

    def _load_rules(self) -> dict:
        """Load review rules.
        加载审查规则。

        Returns:
            dict: 规则字典 / Rules dictionary
        """
        return {
            "misra": {
                "5-0-1": "Implicit conversion may lose precision",
                "7-5-1": "No dynamic memory allocation after initialization",
                "15-5-1": "All switch cases must be covered",
                "18-4-1": "No use of reinterpret_cast",
            },
            "safety": {
                "RANGE-001": "Missing input range validation",
                "NULL-001": "Null pointer check missing",
                "DIV-001": "Division by zero risk",
                "HARD-001": "Direct hardware register access without abstraction",
                "MAGIC-001": "Magic number used without named constant",
            },
            "performance": {
                "PERF-001": "Heap allocation in critical path",
                "PERF-002": "Unnecessary data copy",
                "PERF-003": "Cache-inefficient memory access pattern",
            },
            "best_practice": {
                "BP-001": "Function too complex (exceeds cyclomatic complexity limit)",
                "BP-002": "Missing constexpr opportunity",
                "BP-003": "Incomplete error handling",
            },
        }

    def review(self, code: str, language: str = "cpp", focus: str = "all") -> dict:
        """Review source code.
        审查源代码。

        Args:
            code: 源代码 / Source code
            language: 编程语言 / Programming language
            focus: 审查重点 / Review focus

        Returns:
            dict: 审查结果 / Review results
        """
        issues = []
        critical_count = 0
        major_count = 0
        minor_count = 0

        # Rule 1: Division by zero risk (DIV-001) — critical
        if "ttc = distance / velocity" in code:
            issues.append({
                "id": "CRIT-001",
                "severity": "critical",
                "rule": "SAFETY-DIV-001",
                "line": 14,
                "message": "Division by zero risk: velocity could be zero",
                "recommendation": "Add check: if (velocity <= 0.0f) return;",
                "category": "safety",
            })
            critical_count += 1

        # Rule 2: Missing input range validation (RANGE-001) — critical
        issues.append({
            "id": "CRIT-002",
            "severity": "critical",
            "rule": "SAFETY-RANGE-001",
            "line": 9,
            "message": "Missing input range validation for sensor data",
            "recommendation": "Validate velocity range: velocity > MAX_SPEED",
            "category": "safety",
        })
        critical_count += 1

        # Rule 3: Direct hardware access (HARD-001) — major
        if "reinterpret_cast<volatile uint32_t*>(0x40021000)" in code:
            issues.append({
                "id": "MAJ-001",
                "severity": "major",
                "rule": "SAFETY-HARD-001",
                "line": 25,
                "message": "Direct hardware register access without abstraction layer",
                "recommendation": "Use HAL abstraction: HAL_GPIO_WritePin()",
                "category": "safety",
            })
            major_count += 1

        # Rule 4: Magic number (MAGIC-001) — major
        issues.append({
            "id": "MAJ-002",
            "severity": "major",
            "rule": "SAFETY-MAGIC-001",
            "line": 12,
            "message": "Magic number 2.0f used without named constant",
            "recommendation": "Define constexpr float TTC_THRESHOLD = 2.0f;",
            "category": "best_practice",
        })
        major_count += 1

        # Rule 5: Hardcoded vehicle mass — minor
        issues.append({
            "id": "MIN-001",
            "severity": "minor",
            "rule": "BEST-MAGIC-002",
            "line": 11,
            "message": "Hardcoded vehicle mass (1.5f) should be configurable",
            "recommendation": "Load mass from configuration or EEPROM",
            "category": "best_practice",
        })
        minor_count += 1

        # Rule 6: Missing constexpr — minor
        issues.append({
            "id": "MIN-002",
            "severity": "minor",
            "rule": "BEST-CONSTEXPR-001",
            "line": 37,
            "message": "calculateBrakingForce could be declared constexpr",
            "recommendation": "Add constexpr qualifier to pure function",
            "category": "performance",
        })
        minor_count += 1

        # Calculate scores
        safety_score = max(0, 100 - (critical_count * 20 + major_count * 10))
        performance_score = 85  # Mock score
        style_score = 70  # Mock score
        overall = (safety_score * 0.5 + performance_score * 0.25 + style_score * 0.25)

        return {
            "summary": {
                "total_issues": len(issues),
                "critical": critical_count,
                "major": major_count,
                "minor": minor_count,
            },
            "issues": issues,
            "score": {
                "overall": round(overall, 1),
                "safety": safety_score,
                "performance": performance_score,
                "style": style_score,
            },
            "language": language,
            "focus": focus,
        }


# =============================================================================
# ADAS Code Review Example ADAS 代码审查示例
# =============================================================================

def demonstrate_code_review():
    """Demonstrate ADAS code review workflow.
    演示 ADAS 代码审查工作流。
    """
    print("=" * 70)
    print("Nonull — ADAS C++ Code Review 代码审查")
    print("=" * 70)

    # Initialize review engine 初始化审查引擎
    engine = CodeReviewEngine(strictness=4)

    # Print the code being reviewed 打印待审查代码
    print("\n--- Code Under Review 待审查代码 (AEB Controller) ---")
    print(SAMPLE_AEB_CODE)
    print("--- End of Code ---\n")

    # Perform review 执行审查
    print("Running code review... 正在执行代码审查...")
    result = engine.review(SAMPLE_AEB_CODE, language="cpp", focus="all")

    # Display results 显示结果
    print(f"\n{'=' * 70}")
    print(f"Review Results 审查结果")
    print(f"{'=' * 70}")

    summary = result["summary"]
    print(f"\nSummary 摘要:")
    print(f"  Total Issues 总问题数: {summary['total_issues']}")
    print(f"  Critical 严重: {summary['critical']}")
    print(f"  Major 主要: {summary['major']}")
    print(f"  Minor 次要: {summary['minor']}")

    scores = result["score"]
    print(f"\nScores 评分:")
    print(f"  Overall 综合: {scores['overall']}/100")
    print(f"  Safety 安全: {scores['safety']}/100")
    print(f"  Performance 性能: {scores['performance']}/100")
    print(f"  Style 风格: {scores['style']}/100")

    print(f"\nDetailed Issues 详细问题:")
    for issue in result["issues"]:
        severity_icon = {
            "critical": "[CRITICAL]",
            "major": "[MAJOR]",
            "minor": "[MINOR]",
        }.get(issue["severity"], "[INFO]")

        print(f"\n  {severity_icon} {issue['id']}")
        print(f"    Rule 规则: {issue['rule']}")
        print(f"    Line 行号: {issue['line']}")
        print(f"    Message 信息: {issue['message']}")
        print(f"    Recommendation 建议: {issue['recommendation']}")

    # Generate summary report 生成摘要报告
    print(f"\n{'=' * 70}")
    print("Summary Report 摘要报告")
    print(f"{'=' * 70}")

    if summary["critical"] > 0:
        print(f"\n  WARNING: {summary['critical']} critical safety issues found!")
        print(f"  警告：发现 {summary['critical']} 个严重安全问题！")
        print(f"  Recommended action: Fix all critical issues before production deployment")
        print(f"  建议：在生产部署前修复所有严重问题")
    else:
        print(f"\n  No critical issues found. 未发现严重问题。")

    print(f"\n  MISRA violations: {summary['critical'] + summary['major']}")
    print(f"  Safety-related: {sum(1 for i in result['issues'] if i['category'] == 'safety')}")
    print(f"  Best practice: {sum(1 for i in result['issues'] if i['category'] == 'best_practice')}")

    return result


def export_json(result: dict, filepath: str = "code_review_result.json"):
    """Export review result as JSON.
    将审查结果导出为 JSON。

    Args:
        result: 审查结果 / Review result
        filepath: 输出路径 / Output path
    """
    output_path = os.path.join(os.path.dirname(__file__), filepath)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n  Result exported to 结果已导出到: {output_path}")


# =============================================================================
# Main 主程序
# =============================================================================

if __name__ == "__main__":
    print(r"""
    ╔══════════════════════════════════════════════════════════╗
    ║           Nonull 智驾智能体                       ║
    ║           ADAS Code Review ADAS 代码审查                  ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    result = demonstrate_code_review()
    export_json(result)

    print("\nCode review complete! 代码审查完成！")
    print("\nKey Takeaways 关键要点:")
    print("  1. Safety-critical: Division by zero and range validation")
    print("     安全关键：除零风险和范围验证")
    print("  2. Hardware abstraction: Avoid direct register access")
    print("     硬件抽象：避免直接访问寄存器")
    print("  3. Configuration: Avoid magic numbers and hardcoded values")
    print("     配置管理：避免魔法数字和硬编码值")
