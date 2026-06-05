#!/usr/bin/env python3
"""Nonull Safety Analysis Example 安全分析示例.

This example demonstrates how to use Nonull to perform
HARA (Hazard Analysis and Risk Assessment) on an ADAS function,
following ISO 26262 Part 3 guidelines.

本示例演示如何使用 Nonull 对 ADAS 功能执行
HARA（危险分析和风险评估），遵循 ISO 26262 Part 3 指南。
"""

import json
import os
import sys
from enum import IntEnum
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Data Models 数据模型
# =============================================================================

class Severity(IntEnum):
    """Severity classification per ISO 26262-3.
    根据 ISO 26262-3 的严重度分类。"""
    S0 = 0   # No injuries 无伤害
    S1 = 1   # Light injuries 轻伤
    S2 = 2   # Severe injuries 重伤
    S3 = 3   # Life-threatening 危及生命


class Exposure(IntEnum):
    """Exposure classification per ISO 26262-3.
    根据 ISO 26262-3 的暴露率分类。"""
    E0 = 0   # Incredible 不可信
    E1 = 1   # Very low 非常低
    E2 = 2   # Low 低
    E3 = 3   # Medium 中
    E4 = 4   # High 高


class Controllability(IntEnum):
    """Controllability classification per ISO 26262-3.
    根据 ISO 26262-3 的可控性分类。"""
    C0 = 0   # Controllable 可控
    C1 = 1   # Simply controllable 简单可控
    C2 = 2   # Normally controllable 一般可控
    C3 = 3   # Difficult to control 难以控制


class ASIL(IntEnum):
    """ASIL (Automotive Safety Integrity Level) per ISO 26262.
    根据 ISO 26262 的汽车安全完整性等级。"""
    QM = 0
    ASIL_A = 1
    ASIL_B = 2
    ASIL_C = 3
    ASIL_D = 4


def determine_asil(severity: Severity, exposure: Exposure,
                   controllability: Controllability) -> ASIL:
    """Determine ASIL from S/E/C parameters per ISO 26262-3 Table 2.
    根据 ISO 26262-3 表 2 从 S/E/C 参数确定 ASIL。

    Args:
        severity: 严重度 / Severity classification
        exposure: 暴露率 / Exposure classification
        controllability: 可控性 / Controllability classification

    Returns:
        ASIL: 安全完整性等级 / Safety Integrity Level
    """
    # ASIL determination matrix (simplified)
    # See ISO 26262-3:2018 Table 2 for full matrix
    score = severity + exposure + controllability

    if score >= 9:
        return ASIL.ASIL_D
    elif score >= 7:
        return ASIL.ASIL_C
    elif score >= 5:
        return ASIL.ASIL_B
    elif score >= 3:
        return ASIL.ASIL_A
    else:
        return ASIL.QM


# =============================================================================
# Safety Analysis Engine 安全分析引擎
# =============================================================================

class Hazard:
    """A single hazard identified during HARA.
    HARA 过程中识别的一个危险。"""

    def __init__(
        self,
        hazard_id: str,
        hazard: str,
        situation: str,
        severity: Severity,
        exposure: Exposure,
        controllability: Controllability,
        safety_goal: str,
        safety_goal_asil: ASIL,
    ):
        self.id = hazard_id
        self.hazard = hazard
        self.situation = situation
        self.severity = severity
        self.exposure = exposure
        self.controllability = controllability
        self.asil = determine_asil(severity, exposure, controllability)
        self.safety_goal = safety_goal
        self.safety_goal_asil = safety_goal_asil

    def to_dict(self) -> dict:
        """Convert to dictionary.
        转换为字典。"""
        return {
            "id": self.id,
            "hazard": self.hazard,
            "situation": self.situation,
            "severity": self.severity.name,
            "severity_value": self.severity.value,
            "exposure": self.exposure.name,
            "exposure_value": self.exposure.value,
            "controllability": self.controllability.name,
            "controllability_value": self.controllability.value,
            "asil": self.asil.name,
            "safety_goal": {
                "id": f"SG-{self.id}",
                "description": self.safety_goal,
                "asil": self.safety_goal_asil.name,
            },
        }


class HARAAnalyzer:
    """HARA (Hazard Analysis and Risk Assessment) engine.
    HARA（危险分析和风险评估）引擎。"""

    def __init__(self, function_name: str, system_description: str):
        self.function_name = function_name
        self.system_description = system_description
        self.hazards: list[Hazard] = []

    def add_hazard(self, hazard: Hazard):
        """Add a hazard to the analysis.
        添加一个危险到分析中。"""
        self.hazards.append(hazard)

    def analyze(self) -> dict:
        """Perform the full HARA analysis.
        执行完整的 HARA 分析。"""
        # Item definition 项目定义
        item_definition = {
            "name": self.function_name,
            "description": self.system_description,
            "boundaries": [
                "Sensor input (radar + camera fusion)",
                "Actuator output (brake system, steering)",
                "Driver override (steering torque, accelerator pedal)",
                "Vehicle dynamics interface (ESP, EPS)",
            ],
            "interfaces": [
                "CAN bus (250 kbps, powertrain)",
                "Ethernet (1 Gbps, ADAS domain)",
                "FlexRay (diagnostic)",
                "LIN bus (comfort systems)",
            ],
        }

        # Hazard analysis 危险分析
        hazard_list = [h.to_dict() for h in self.hazards]

        # Summary 摘要
        total = len(self.hazards)
        asil_counts = {asil.name: 0 for asil in ASIL}
        for h in self.hazards:
            asil_counts[h.asil.name] += 1

        return {
            "analysis_type": "HARA",
            "standard": "ISO 26262-3:2018",
            "item_definition": item_definition,
            "hazards": hazard_list,
            "summary": {
                "total_hazards": total,
                "asil_d": asil_counts.get("ASIL_D", 0),
                "asil_c": asil_counts.get("ASIL_C", 0),
                "asil_b": asil_counts.get("ASIL_B", 0),
                "asil_a": asil_counts.get("ASIL_A", 0),
                "qm": asil_counts.get("QM", 0),
            },
        }


# =============================================================================
# HARA Example HARA 示例
# =============================================================================

def run_aeb_hara_example() -> dict:
    """Run HARA on the AEB (Autonomous Emergency Braking) function.
    对 AEB（自主紧急制动）功能执行 HARA。"""
    print("=" * 70)
    print("Nonull — HARA Example HARA 示例")
    print("=" * 70)
    print("\nItem Definition 项目定义:")
    print("  Function 功能: AEB (Autonomous Emergency Braking)")
    print("  Description 描述: System that automatically applies brakes")
    print("  when an imminent collision is detected")
    print("  当检测到即将发生碰撞时自动应用制动")

    # Initialize HARA analyzer 初始化 HARA 分析器
    analyzer = HARAAnalyzer(
        function_name="Autonomous Emergency Braking (AEB)",
        system_description=(
            "AEB system that uses radar and camera fusion to detect "
            "potential collisions and automatically applies the vehicle brakes "
            "to avoid or mitigate the impact."
        ),
    )

    # Add hazards 添加危险
    analyzer.add_hazard(Hazard(
        hazard_id="H-001",
        hazard="Unintended braking at highway speed",
        situation="Vehicle traveling at 110 km/h, no obstacle ahead",
        severity=Severity.S3,
        exposure=Exposure.E3,
        controllability=Controllability.C3,
        safety_goal="AEB shall not apply brakes exceeding 0.2g when no collision is predicted",
        safety_goal_asil=ASIL.ASIL_D,
    ))

    analyzer.add_hazard(Hazard(
        hazard_id="H-002",
        hazard="Failure to brake when collision imminent",
        situation="Vehicle approaching stationary vehicle at 80 km/h",
        severity=Severity.S3,
        exposure=Exposure.E2,
        controllability=Controllability.C3,
        safety_goal="AEB shall detect obstacles >50m ahead and initiate braking >1.5s before TTC",
        safety_goal_asil=ASIL.ASIL_C,
    ))

    analyzer.add_hazard(Hazard(
        hazard_id="H-003",
        hazard="Partial braking due to sensor degradation",
        situation="Radar sensor covered by snow, reduced detection range",
        severity=Severity.S2,
        exposure=Exposure.E2,
        controllability=Controllability.C2,
        safety_goal="AEB shall degrade gracefully: reduce max speed or warn driver when sensor confidence < 90%",
        safety_goal_asil=ASIL.ASIL_B,
    ))

    analyzer.add_hazard(Hazard(
        hazard_id="H-004",
        hazard="Delayed braking due to computational overload",
        situation="Perception stack overloaded, processing latency >300ms",
        severity=Severity.S2,
        exposure=Exposure.E1,
        controllability=Controllability.C2,
        safety_goal="AEB shall complete sensor-to-actuator path within 150ms (FTTI compliant)",
        safety_goal_asil=ASIL.ASIL_B,
    ))

    analyzer.add_hazard(Hazard(
        hazard_id="H-005",
        hazard="Brake release during active braking due to communication fault",
        situation="CAN bus transient fault, brake command lost",
        severity=Severity.S3,
        exposure=Exposure.E1,
        controllability=Controllability.C2,
        safety_goal="AEB shall maintain braking force for minimum 500ms after communication loss (fail-safe)",
        safety_goal_asil=ASIL.ASIL_C,
    ))

    analyzer.add_hazard(Hazard(
        hazard_id="H-006",
        hazard="False detection of obstacle causing unnecessary braking",
        situation="Bridge shadow misidentified as stationary obstacle",
        severity=Severity.S2,
        exposure=Exposure.E3,
        controllability=Controllability.C2,
        safety_goal="AEB shall require dual-sensor confirmation before initiating braking >0.3g",
        safety_goal_asil=ASIL.ASIL_B,
    ))

    # Perform analysis 执行分析
    result = analyzer.analyze()

    # Print results 打印结果
    print(f"\n{'=' * 70}")
    print("HARA Results HARA 结果")
    print(f"{'=' * 70}")

    print(f"\nAnalysis Type 分析类型: {result['analysis_type']}")
    print(f"Standard 标准: {result['standard']}")

    print(f"\nHazard Summary 危险摘要:")
    summary = result["summary"]
    print(f"  Total Hazards 总危险数: {summary['total_hazards']}")
    print(f"  ASIL D: {summary['asil_d']}  [最高安全等级 / Highest safety level]")
    print(f"  ASIL C: {summary['asil_c']}")
    print(f"  ASIL B: {summary['asil_b']}")
    print(f"  ASIL A: {summary['asil_a']}")
    print(f"  QM:     {summary['qm']}")

    print(f"\nDetailed Hazard List 详细危险列表:")
    for hazard in result["hazards"]:
        print(f"\n  Hazard {hazard['id']}:")
        print(f"    Description: {hazard['hazard']}")
        print(f"    Situation: {hazard['situation']}")
        print(f"    S={hazard['severity_value']} "
              f"E={hazard['exposure_value']} "
              f"C={hazard['controllability_value']} "
              f"=> ASIL {hazard['asil']}")
        print(f"    Safety Goal: {hazard['safety_goal']['description']}")
        print(f"    Safety Goal ASIL: {hazard['safety_goal']['asil']}")

    return result


def generate_safety_report(result: dict) -> str:
    """Generate a safety analysis summary report.
    生成安全分析摘要报告。

    Args:
        result: HARA 分析结果 / HARA analysis result

    Returns:
        str: 报告文本 / Report text
    """
    summary = result["summary"]
    report = []

    report.append("=" * 60)
    report.append("AEB Safety Analysis Report 安全分析报告")
    report.append("=" * 60)
    report.append("")
    report.append(f"Function 功能: AEB (Autonomous Emergency Braking)")
    report.append(f"Analysis 分析: HARA per ISO 26262-3:2018")
    report.append(f"Hazards Identified 识别危险: {summary['total_hazards']}")
    report.append("")
    report.append("ASIL Distribution ASIL 分布:")
    report.append(f"  ASIL D: {summary['asil_d']} — Highest safety requirements")
    report.append(f"  ASIL C: {summary['asil_c']} — High safety requirements")
    report.append(f"  ASIL B: {summary['asil_b']} — Moderate safety requirements")
    report.append(f"  ASIL A: {summary['asil_a']} — Low safety requirements")
    report.append(f"  QM:     {summary['qm']}     — Quality management only")
    report.append("")
    report.append("Conclusion 结论:")
    if summary["asil_d"] > 0:
        report.append("  ASIL D elements identified — requires systematic rigor")
        report.append("  发现 ASIL D 元素 — 需要系统性严格开发")
    else:
        report.append("  No ASIL D elements — standard safety approach sufficient")
        report.append("  无 ASIL D 元素 — 标准安全方法足够")
    report.append("")
    report.append("=" * 60)

    return "\n".join(report)


# =============================================================================
# Main 主程序
# =============================================================================

if __name__ == "__main__":
    print(r"""
    ╔══════════════════════════════════════════════════════════╗
    ║           Nonull 智驾智能体                       ║
    ║           Safety Analysis 安全分析                        ║
    ║           HARA Example HARA 示例                        ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    result = run_aeb_hara_example()

    print(f"\n{'=' * 70}")
    report = generate_safety_report(result)
    print(f"\n{report}")

    # Export to JSON 导出为 JSON
    output_path = os.path.join(os.path.dirname(__file__), "hara_result.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n  Result exported to 结果已导出到: {output_path}")

    print("\nSafety analysis complete! 安全分析完成！")
    print("\nKey Takeaways 关键要点:")
    print("  1. AEB has 3 ASIL D and C hazards requiring highest rigor")
    print("     AEB 有 3 个 ASIL D 和 C 级别的危险，需要最高严格度")
    print("  2. Dual-sensor confirmation reduces false positives")
    print("     双传感器确认减少误报")
    print("  3. FTTI compliance (150ms) is critical for AEB effectiveness")
    print("     FTTI 合规性（150ms）对 AEB 有效性至关重要")
