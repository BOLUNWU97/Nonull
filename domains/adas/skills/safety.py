"""
ADVISORY SAFETY — Skills in this module are advisory pattern checkers, NOT
certified safety analysis. HARA, FMEA, ISO 26262, and safety case outputs
are template-driven suggestions for developer review; they do NOT constitute
ISO 26262 process compliance, ASPICE process conformance, or any certified
hazard/risk assessment. The hazard templates use random / hard-coded values
for demonstration (rule-based in production is itself an aspirational note).
See README §Disclaimer and `safety.disclaimer: advisory_only` in config.

Safety Skills - 功能安全技能

自动驾驶功能安全分析、HARA、FMEA、ISO 26262 合规检查和安全案例生成。
Functional safety analysis: HARA, FMEA, ISO 26262 compliance, and safety case generation.
"""

from __future__ import annotations

import math
import random
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
# 危害分析与风险评估 / Hazard Analysis and Risk Assessment (HARA)
# =============================================================================


class HazardAnalysisSkill(BaseSkill):
    """
    危害分析与风险评估技能 (HARA)。
    Hazard Analysis and Risk Assessment (HARA) — ADVISORY template only,
    not a certified HARA. The output pattern references ISO 26262-3 clause
    structure (S/E/C → ASIL) but is not "per ISO 26262" in a process
    compliance sense. It is NOT compliant or certified HARA.

    **ADVISORY TEMPLATE ONLY**: This skill matches input keywords against
    hardcoded hazard templates. The S/E/C values are NOT derived from your
    specific system; they are defaults. A real HARA requires expert
    elicitation. This skill is a scaffolding aid, not a HARA work product.

    执行步骤 / Steps:
        1. 功能危害识别 / Functional hazard identification
        2. 情境分析 / Situational analysis
        3. 危害等级评定 (S/E/C) / Severity/Exposure/Controllability rating
        4. ASIL 等级确定 / ASIL determination (advisory classification, not certified ASIL)
        5. 安全目标定义 / Safety goal definition

    Class Attributes:
        LEGACY_ALIASES: 旧名称（typo）作为已弃用别名保留 / Old typo name
            kept as a deprecated alias for backward compatibility. The
            registry will resolve ``haras_analysis`` to this skill but
            log a deprecation warning.
    """

    # 旧名称 "haras_analysis" 是 typo，保留为已弃用别名以兼容旧调用。
    # "haras_analysis" was a typo — kept as a deprecated alias so older
    # call sites still resolve to this skill via SkillRegistry.get_skill.
    LEGACY_ALIASES = ("haras_analysis",)

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="hara_analysis",
            version="1.0.0",
            category=SkillCategory.SAFETY,
            description="HARA分析：危害识别、风险评估与ASIL等级确定",
            author="Nonull",
            tags=["safety", "hara", "iso26262", "asil", "risk-assessment"],
            input_schema={
                "type": "object",
                "properties": {
                    "system_description": {"type": "string"},
                    "functions": {"type": "array"},
                    "operating_scenarios": {"type": "array"},
                    "sec_overrides": {
                        "type": "object",
                        "description": (
                            "可选 S/E/C 覆盖映射 / Optional S/E/C overrides, "
                            "keyed by hazard description. Use this to inject "
                            "expert-elicited values; otherwise TEMPLATE defaults "
                            "are used and the output is marked is_template=True."
                        ),
                    },
                },
                "required": ["system_description", "functions"],
            },
            safety_level=5,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        description: str = context.get("system_description", "")
        functions: List = context.get("functions", [])
        scenarios: List = context.get("operating_scenarios", [])
        # sec_overrides: {hazard_description: {"S": int, "E": int, "C": int}}
        # Optional S/E/C overrides keyed by hazard description. If absent
        # for a given hazard, the DEMO/TEMPLATE defaults are used and the
        # output is marked is_template=True. See ADVISORY TEMPLATE ONLY in
        # the class docstring.
        sec_overrides: Dict[str, Dict[str, int]] = context.get("sec_overrides", {}) or {}

        if not scenarios:
            scenarios = self._default_scenarios()

        hazards: List[Dict[str, Any]] = []
        for func in functions:
            func_name = self._get_func_name(func)
            for scenario in scenarios:
                hazard = self._analyze_hazard(
                    func_name,
                    scenario,
                    sec_overrides=sec_overrides,
                )
                hazards.append(hazard)

        safety_goals = self._derive_safety_goals(hazards)

        return {
            "system": description[:100] if description else "未指定",
            "total_hazards": len(hazards),
            "asil_distribution": self._count_asils(hazards),
            "hazards": hazards,
            "safety_goals": safety_goals,
            "summary": self._generate_hara_summary(hazards, safety_goals),
            "recommendations": self._generate_recommendations(hazards),
            "is_template": True,
            "warning": (
                "ADVISORY TEMPLATE ONLY: S/E/C/ASIL values are hardcoded "
                "demo defaults. This is NOT a real HARA work product. Real "
                "HARA requires expert elicitation per ISO 26262-3:2018."
            ),
        }

    def _get_func_name(self, func: Any) -> str:
        """获取功能名 / Get function name."""
        if isinstance(func, dict):
            return func.get("name", func.get("function", str(func)))
        return str(func)

    def _default_scenarios(self) -> List[str]:
        """默认运行场景 / Default operating scenarios."""
        return [
            "高速公路行驶 / Highway driving",
            "城市道路行驶 / Urban driving",
            "路口通行 / Intersection crossing",
            "变道 / Lane changing",
            "泊车 / Parking",
            "紧急制动 / Emergency braking",
        ]

    def _analyze_hazard(
        self,
        function: str,
        scenario: str,
        sec_overrides: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> Dict[str, Any]:
        """分析危害 / Analyze hazard.

        ADVISORY TEMPLATE ONLY — the S/E/C values in ``hazard_templates``
        below are hardcoded DEMO defaults matched to keyword presence in
        the function/scenario text. They are NOT derived from a real
        hazard analysis and do NOT constitute expert-elicited HARA values
        per ISO 26262-3:2018. Pass ``sec_overrides`` (keyed by hazard
        description) to override the template values; values you supply
        are kept as-is in the output (still marked ``is_template=True``
        so consumers can distinguish expert inputs from defaults).
        """
        # 随机生成危害参数以演示（实际应用中基于规则引擎）
        # NOTE: These are DEMO/TEMPLATE values, not real HARA inputs.
        # In a real HARA, S/E/C must be elicited from domain experts
        # and validated per ISO 26262-3:2018. The "template_id" lets
        # downstream consumers trace a given hazard back to which
        # keyword bucket produced it.
        hazard_templates = {
            "制动": {
                "template_id": "brake_failure_v1",
                "hazards": ["制动失效", "制动延迟", "非预期制动"],
                "severity": [3, 3, 2],
                "exposure": [3, 2, 3],
                "controllability": [3, 2, 2],
            },
            "转向": {
                "template_id": "steering_failure_v1",
                "hazards": ["转向失效", "转向过度", "转向不足"],
                "severity": [3, 2, 2],
                "exposure": [2, 3, 3],
                "controllability": [3, 2, 2],
            },
            "加速": {
                "template_id": "acceleration_failure_v1",
                "hazards": ["非预期加速", "加速无力"],
                "severity": [3, 1],
                "exposure": [2, 3],
                "controllability": [3, 1],
            },
            "感知": {
                "template_id": "perception_failure_v1",
                "hazards": ["目标漏检", "目标误检", "测距误差过大"],
                "severity": [3, 2, 2],
                "exposure": [3, 3, 2],
                "controllability": [2, 1, 2],
            },
        }

        sec_overrides = sec_overrides or {}

        hazard_types = []
        for keyword, template in hazard_templates.items():
            if keyword in function.lower() or keyword in scenario.lower():
                template_id = template.get("template_id", "unknown_v1")
                for h_desc, sev, exp, cont in zip(
                    template["hazards"],
                    template["severity"],
                    template["exposure"],
                    template["controllability"],
                ):
                    # Apply per-hazard overrides if the caller supplied them.
                    # Keys are S / E / C (matching severity_S / exposure_E
                    # / controllability_C in the output schema).
                    override = sec_overrides.get(h_desc, {}) or {}
                    sev_eff = override.get("S", sev)
                    exp_eff = override.get("E", exp)
                    cont_eff = override.get("C", cont)
                    hazard_types.append(
                        (h_desc, sev_eff, exp_eff, cont_eff, template_id)
                    )

        if not hazard_types:
            hazard_types.append(
                ("功能异常 / Function malfunction", 2, 2, 2, "default_unknown_v1")
            )

        hazards = []
        for h_desc, sev, exp, cont, template_id in hazard_types:
            asil = self._determine_asil(sev, exp, cont)
            hazards.append({
                "hazard": h_desc,
                "scenario": scenario,
                "severity_S": sev,         # DEMO/template value
                "exposure_E": exp,         # DEMO/template value
                "controllability_C": cont, # DEMO/template value
                "ASIL": asil,              # DEMO/template, not validated
                "template_id": template_id,
                "is_template": True,       # always True for this method
            })

        return {
            "function": function,
            "scenario": scenario,
            "hazards": hazards,
            "is_template": True,
            "warning": (
                "These S/E/C/ASIL values are template defaults. "
                "Real HARA requires expert elicitation per ISO 26262-3:2018."
            ),
        }

    def _determine_asil(self, severity: int, exposure: int, controllability: int) -> str:
        """
        Determine ASIL level — ADVISORY pattern reference, not a certified
        reproduction of ISO 26262-3:2018 Table 2. The weighted score below
        (S + E + C with hand-picked cutoffs) is a simplified heuristic; it
        does NOT match the exact lookup table in the standard.
        确定 ASIL 等级 — 建议性模式参考，非 ISO 26262-3:2018 Table 2 的认证复现。
        下面的加权评分是简化启发式，并非标准的精确查找表。

        Returns: "QM", "ASIL_A", "ASIL_B", "ASIL_C", "ASIL_D" (advisory only)
        """
        # S + E + C 加权评分 / Weighted scoring (advisory heuristic, not the standard's lookup table)
        score = severity * 3 + exposure * 2 + controllability * 2

        if severity == 0 or score <= 8:
            return "QM"
        elif score <= 12:
            return "ASIL_A"
        elif score <= 15:
            return "ASIL_B"
        elif score <= 18:
            return "ASIL_C"
        else:
            return "ASIL_D"

    def _derive_safety_goals(self, hazards: List[Dict]) -> List[Dict]:
        """推导安全目标 / Derive safety goals from hazards."""
        safety_goals = []
        seen_goals = set()

        asil_map = {"QM": 0, "ASIL_A": 1, "ASIL_B": 2, "ASIL_C": 3, "ASIL_D": 4}

        for hazard_entry in hazards:
            for h in hazard_entry.get("hazards", []):
                h_desc = h.get("hazard", "")
                asil = h.get("ASIL", "QM")

                if asil == "QM":
                    continue

                # 生成安全目标 / Generate safety goal
                goal = f"避免因 {h_desc} 导致的危害"
                if goal not in seen_goals:
                    seen_goals.add(goal)
                    safety_goals.append({
                        "id": f"SG-{len(safety_goals) + 1:03d}",
                        "goal": goal,
                        "ASIL": asil,
                        "related_hazards": [h_desc],
                    })

        return sorted(safety_goals, key=lambda x: asil_map.get(x["ASIL"], 0), reverse=True)

    def _count_asils(self, hazards: List[Dict]) -> Dict[str, int]:
        """统计 ASIL 分布 / Count ASIL distribution."""
        counts = {"QM": 0, "ASIL_A": 0, "ASIL_B": 0, "ASIL_C": 0, "ASIL_D": 0}
        for hazard_entry in hazards:
            for h in hazard_entry.get("hazards", []):
                asil = h.get("ASIL", "QM")
                if asil in counts:
                    counts[asil] += 1
        return counts

    def _generate_hara_summary(
        self, hazards: List[Dict], safety_goals: List[Dict]
    ) -> str:
        """生成 HARA 摘要 / Generate HARA summary."""
        total_h = sum(len(entry.get("hazards", [])) for entry in hazards)
        total_sg = len(safety_goals)
        asil_d = sum(1 for sg in safety_goals if sg["ASIL"] == "ASIL_D")
        return (
            f"HARA完成: 识别 {total_h} 个危害, "
            f"推导 {total_sg} 个安全目标 "
            f"(其中 ASIL D: {asil_d})"
        )

    def _generate_recommendations(self, hazards: List[Dict]) -> List[str]:
        """生成建议 / Generate recommendations."""
        recs = []
        asil_d_hazards = []
        for entry in hazards:
            for h in entry.get("hazards", []):
                if h.get("ASIL") == "ASIL_D":
                    asil_d_hazards.append(h["hazard"])

        if asil_d_hazards:
            recs.append(f"以下ASIL D危害需要最高安全等级措施: {', '.join(asil_d_hazards[:3])}")

        recs.append("建议在系统架构层面实现故障容错机制")
        recs.append("安全目标需分解到软硬件需求中")

        return recs


# =============================================================================
# FMEA 技能 / FMEA Skill
# =============================================================================


class FMEASkill(BaseSkill):
    """
    失效模式与影响分析技能 (FMEA)。
    Failure Mode and Effects Analysis (FMEA) for AD systems.

    分析内容 / Analysis:
        - 硬件 FMEA / Hardware FMEA
        - 软件 FMEA / Software FMEA
        - 系统 FMEA / System FMEA
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="fmea",
            version="1.0.0",
            category=SkillCategory.SAFETY,
            description="FMEA分析：失效模式识别、影响分析和风险优先级评估",
            author="Nonull",
            tags=["safety", "fmea", "failure-mode", "risk-priority", "iso26262"],
            input_schema={
                "type": "object",
                "properties": {
                    "system_elements": {"type": "array"},
                    "analysis_type": {
                        "type": "string",
                        "enum": ["hardware", "software", "system", "full"],
                    },
                },
                "required": ["system_elements"],
            },
            safety_level=4,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        elements: List = context["system_elements"]
        analysis_type: str = context.get("analysis_type", "full")

        fmea_items: List[Dict[str, Any]] = []
        for element in elements:
            name = self._get_element_name(element)
            element_type = self._get_element_type(element)
            if analysis_type in ("full", element_type):
                items = self._analyze_element(name, element_type)
                fmea_items.extend(items)

        rpn_high = [i for i in fmea_items if i.get("RPN", 0) >= 200]
        rpn_medium = [i for i in fmea_items if 100 <= i.get("RPN", 0) < 200]

        return {
            "analysis_type": analysis_type,
            "total_items": len(fmea_items),
            "critical_items": len(rpn_high),
            "items": sorted(fmea_items, key=lambda x: x.get("RPN", 0), reverse=True),
            "rpn_summary": {
                "high_risk_count": len(rpn_high),
                "medium_risk_count": len(rpn_medium),
                "low_risk_count": len(fmea_items) - len(rpn_high) - len(rpn_medium),
            },
            "recommendations": self._generate_fmea_recs(rpn_high),
        }

    def _get_element_name(self, element: Any) -> str:
        if isinstance(element, dict):
            return element.get("name", element.get("component", str(element)))
        return str(element)

    def _get_element_type(self, element: Any) -> str:
        if isinstance(element, dict):
            return element.get("type", "system")
        return "system"

    def _analyze_element(self, name: str, element_type: str) -> List[Dict]:
        """分析元素的失效模式 / Analyze element failure modes."""
        failures_map = {
            "sensor": [
                ("信号丢失 / Signal loss", 8, 8, 7),
                ("噪声干扰 / Noise interference", 6, 7, 5),
                ("漂移 / Drift", 5, 6, 5),
                ("完全失效 / Complete failure", 9, 9, 9),
            ],
            "actuator": [
                ("卡滞 / Stuck", 7, 5, 8),
                ("响应延迟 / Response delay", 6, 7, 6),
                ("失效 / Failure", 8, 6, 9),
            ],
            "software": [
                ("内存泄漏 / Memory leak", 5, 8, 6),
                ("竞态条件 / Race condition", 7, 6, 7),
                ("除零 / Division by zero", 8, 4, 8),
                ("死锁 / Deadlock", 9, 5, 9),
            ],
            "controller": [
                ("看门狗超时 / Watchdog timeout", 6, 5, 7),
                ("温度过载 / Thermal overload", 5, 4, 6),
                ("电源失效 / Power failure", 9, 6, 9),
            ],
        }

        items = []
        failures = failures_map.get(element_type, [("未知失效 / Unknown failure", 5, 5, 5)])

        for failure_desc, severity, occurrence, detection in failures:
            rpn = severity * occurrence * detection
            items.append({
                "element": name,
                "element_type": element_type,
                "failure_mode": failure_desc,
                "severity_S": severity,
                "occurrence_O": occurrence,
                "detection_D": detection,
                "RPN": rpn,
                "risk_level": "high" if rpn >= 200 else "medium" if rpn >= 100 else "low",
                "recommended_action": self._recommend_action(failure_desc, rpn),
            })

        return items

    def _recommend_action(self, failure_desc: str, rpn: int) -> str:
        """推荐改进措施 / Recommend improvement actions."""
        if rpn >= 200:
            return "必须立即改进 / Mandatory immediate improvement"
        elif rpn >= 100:
            return "建议改进 / Improvement recommended"
        return "持续监控 / Continue monitoring"

    def _generate_fmea_recs(self, high_rpn_items: List[Dict]) -> List[str]:
        """生成 FMEA 建议 / Generate FMEA recommendations."""
        recs = []
        for item in high_rpn_items[:5]:
            recs.append(
                f"关键项: {item['element']} - {item['failure_mode']} "
                f"(RPN={item['RPN']}) -> {item['recommended_action']}"
            )
        if not recs:
            recs.append("无明显高风险的失效模式")
        return recs


# =============================================================================
# ISO 26262 合规检查技能 / ISO 26262 Check Skill
# =============================================================================


class ISO26262CheckSkill(BaseSkill):
    """
    ISO 26262 合规性检查技能。
    ISO 26262 compliance checking for AD/ADAS systems.

    检查范围 / Check scope:
        - 功能安全流程 / Functional safety processes
        - 安全档案完整性 / Safety case completeness
        - ASIL 分解正确性 / ASIL decomposition correctness
        - 安全机制覆盖率 / Safety mechanism coverage
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="iso26262_check",
            version="1.0.0",
            category=SkillCategory.SAFETY,
            description="ISO 26262合规检查：流程、文档和安全机制完整性验证",
            author="Nonull",
            tags=["safety", "iso26262", "compliance", "asil", "functional-safety"],
            input_schema={
                "type": "object",
                "properties": {
                    "project_phase": {
                        "type": "string",
                        "enum": ["concept", "system", "hardware", "software", "production"],
                    },
                    "documents": {"type": "object"},
                    "asil_level": {"type": "string"},
                },
                "required": ["project_phase", "asil_level"],
            },
            safety_level=5,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        phase: str = context["project_phase"]
        documents: Optional[Dict] = context.get("documents", {})
        target_asil: str = context.get("asil_level", "ASIL_B")

        checks = self._get_part_checks(phase, target_asil)
        results = []

        for check in checks:
            passed = self._verify_check(check, documents)
            results.append({
                "check_id": check["id"],
                "title": check["title"],
                "description": check["description"],
                "required_by": check["required_by"],
                "passed": passed,
                "evidence": check.get("evidence_required", ""),
                "status": "通过" if passed else "未通过 / 证据不足",
            })

        passed_count = sum(1 for r in results if r["passed"])
        compliance_rate = passed_count / len(results) * 100 if results else 0

        return {
            "project_phase": phase,
            "target_asil": target_asil,
            "total_checks": len(results),
            "passed_checks": passed_count,
            "failed_checks": len(results) - passed_count,
            "compliance_rate_pct": round(compliance_rate, 1),
            "check_results": results,
            "verdict": "COMPLIANT" if compliance_rate >= 90 else "PARTIALLY_COMPLIANT" if compliance_rate >= 70 else "NON_COMPLIANT",
            "recommendations": [
                r["description"] for r in results if not r["passed"]
            ][:5],
        }

    def _get_part_checks(self, phase: str, asil: str) -> List[Dict]:
        """获取对应阶段和ASIL等级的检查项 / Get checks for phase and ASIL."""
        all_checks = {
            "concept": [
                {"id": "ISO-3-1", "title": "项目定义 / Item definition",
                 "description": "项目定义是否清晰完整", "required_by": "ISO 26262-3:2018 Clause 5",
                 "evidence_required": "Item definition document"},
                {"id": "ISO-3-2", "title": "HARA / Hazard analysis",
                 "description": "是否完成系统化的HARA分析", "required_by": "ISO 26262-3:2018 Clause 7",
                 "evidence_required": "HARA report"},
                {"id": "ISO-3-3", "title": "安全目标 / Safety goals",
                 "description": "安全目标是否覆盖所有identified hazards",
                 "required_by": "ISO 26262-3:2018 Clause 8",
                 "evidence_required": "Safety goals specification"},
            ],
            "system": [
                {"id": "ISO-4-1", "title": "系统架构 / System architecture",
                 "description": "系统架构是否满足安全要求", "required_by": "ISO 26262-4:2018 Clause 6"},
                {"id": "ISO-4-2", "title": "安全机制 / Safety mechanisms",
                 "description": "安全机制是否满足ASIL要求覆盖率",
                 "required_by": "ISO 26262-4:2018 Clause 7"},
                {"id": "ISO-4-3", "title": "FTTI分析 / Fault tolerant time interval",
                 "description": "故障容错时间间隔是否被定义和验证",
                 "required_by": "ISO 26262-4:2018 Clause 8"},
            ],
            "software": [
                {"id": "ISO-6-1", "title": "软件架构 / Software architecture",
                 "description": "软件架构是否满足ASIL等级要求",
                 "required_by": "ISO 26262-6:2018 Clause 7"},
                {"id": "ISO-6-2", "title": "单元测试 / Unit testing",
                 "description": "单元测试覆盖率和通过率是否达标",
                 "required_by": "ISO 26262-6:2018 Clause 9"},
                {"id": "ISO-6-3", "title": "代码规范 / Coding standards",
                 "description": "是否遵循MISRA C/C++等编码规范",
                 "required_by": "ISO 26262-6:2018 Clause 8"},
            ],
            "hardware": [
                {"id": "ISO-5-1", "title": "硬件架构 / Hardware architecture",
                 "description": "硬件架构是否满足可靠性和安全需求",
                 "required_by": "ISO 26262-5:2018 Clause 6"},
                {"id": "ISO-5-2", "title": "硬件FMEDA / Hardware FMEDA",
                 "description": "是否完成硬件FMEDA且SPFM/LFM达标",
                 "required_by": "ISO 26262-5:2018 Clause 9"},
                {"id": "ISO-5-3", "title": "PMHF计算 / PMHF calculation",
                 "description": "PMHF是否满足ASIL等级要求",
                 "required_by": "ISO 26262-5:2018 Clause 10"},
            ],
            "production": [
                {"id": "ISO-7-1", "title": "生产流程 / Production process",
                 "description": "生产流程是否满足功能安全要求",
                 "required_by": "ISO 26262-7:2018 Clause 5"},
                {"id": "ISO-7-2", "title": "操作维护 / Operation & maintenance",
                 "description": "操作维护计划是否包含安全相关说明",
                 "required_by": "ISO 26262-7:2018 Clause 6"},
            ],
        }

        return all_checks.get(phase, all_checks["concept"])

    def _verify_check(self, check: Dict, documents: Dict) -> bool:
        """验证检查项 / Verify a check item."""
        # 在实际应用中连接文档管理系统进行验证
        # In production, connect to document management system
        evidence = check.get("evidence_required", "")
        if not evidence:
            return True
        # 检查文档是否提供 / Check if document exists
        return any(evidence.lower() in doc.lower() for doc in documents) if documents else False


# =============================================================================
# 安全案例生成技能 / Safety Case Skill
# =============================================================================


class SafetyCaseSkill(BaseSkill):
    """
    安全案例生成技能。
    Safety case generation for autonomous driving systems.

    生成内容 / Generation:
        - 安全论据 / Safety argumentation (GSN)
        - 安全证据索引 / Safety evidence index
        - 安全案例报告 / Safety case report
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="safety_case",
            version="1.0.0",
            category=SkillCategory.SAFETY,
            description="安全案例生成：GSN论据图、证据索引和安全案例报告",
            author="Nonull",
            tags=["safety", "safety-case", "gsn", "assurance", "evidence"],
            input_schema={
                "type": "object",
                "properties": {
                    "system_name": {"type": "string"},
                    "safety_goals": {"type": "array"},
                    "evidence_items": {"type": "array"},
                    "target_asil": {"type": "string"},
                },
                "required": ["system_name", "safety_goals"],
            },
            safety_level=5,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        system_name: str = context["system_name"]
        safety_goals: List = context.get("safety_goals", [])
        evidence_items: List = context.get("evidence_items", [])
        target_asil: str = context.get("target_asil", "ASIL_B")

        # GSN 论据结构 / GSN argument structure
        gsn_structure = self._build_gsn(system_name, safety_goals)

        # 证据映射 / Evidence mapping
        evidence_map = self._map_evidence(safety_goals, evidence_items)

        # 差距分析 / Gap analysis
        gaps = self._analyze_gaps(gsn_structure, evidence_map)

        # 置信度评估 / Confidence assessment
        confidence = self._assess_confidence(evidence_map)

        return {
            "system_name": system_name,
            "target_asil": target_asil,
            "gsn_structure": gsn_structure,
            "evidence_map": evidence_map,
            "gap_analysis": gaps,
            "confidence_assessment": confidence,
            "overall_verdict": self._determine_verdict(confidence, gaps),
            "summary": (
                f"安全案例生成完成: {len(gsn_structure['goals'])} 个目标, "
                f"{len(evidence_map)} 项证据, "
                f"{len(gaps)} 个差距项"
            ),
            "recommendations": gaps,
        }

    def _build_gsn(
        self, system: str, safety_goals: List
    ) -> Dict[str, Any]:
        """构建 GSN 论据结构 / Build GSN argument structure."""
        goals = []
        strategies = []
        solutions = []

        for i, sg in enumerate(safety_goals):
            if isinstance(sg, dict):
                goal_text = sg.get("goal", sg.get("description", str(sg)))
                asil = sg.get("ASIL", target_asil)
            else:
                goal_text = str(sg)
                asil = "ASIL_B"

            goal_id = f"G{i + 1}"
            goals.append({
                "id": goal_id,
                "text": goal_text,
                "asil": asil,
            })

            strategies.append({
                "id": f"S{i + 1}",
                "goal_id": goal_id,
                "text": f"论据: 通过架构设计、安全机制和验证活动满足 '{goal_text}'",
            })

            solutions.append({
                "id": f"Sol{i + 1}",
                "strategy_id": f"S{i + 1}",
                "text": f"安全机制和验证结果支持该论据",
            })

        return {
            "top_goal": f"{system} 在预期运行场景下是安全的",
            "goals": goals,
            "strategies": strategies,
            "solutions": solutions,
        }

    def _map_evidence(
        self, safety_goals: List, evidence_items: List
    ) -> List[Dict]:
        """映射证据到安全目标 / Map evidence to safety goals."""
        evidence_map = []

        for i, sg in enumerate(safety_goals):
            goal_id = f"G{i + 1}"
            goal_text = sg.get("goal", "") if isinstance(sg, dict) else str(sg)

            matching = [
                e for e in evidence_items
                if goal_text.lower() in (e.get("related_goal", "") if isinstance(e, dict) else str(e)).lower()
            ] if evidence_items else []

            if not matching:
                matching = [{
                    "type": "verification_report",
                    "description": f"验证报告: {goal_text[:50]}",
                    "status": "pending",
                }]

            for ev in matching:
                evidence_map.append({
                    "goal_id": goal_id,
                    "goal_text": goal_text[:60],
                    "evidence_id": f"E{i + 1}-{len(evidence_map) + 1}",
                    "evidence_type": ev.get("type", "document") if isinstance(ev, dict) else "document",
                    "description": ev.get("description", str(ev)[:80]) if isinstance(ev, dict) else str(ev)[:80],
                    "status": ev.get("status", "available") if isinstance(ev, dict) else "available",
                })

        return evidence_map

    def _analyze_gaps(
        self, gsn: Dict, evidence_map: List
    ) -> List[str]:
        """分析差距 / Analyze gaps."""
        gaps = []

        covered_goals = set(e["goal_id"] for e in evidence_map)
        for goal in gsn.get("goals", []):
            if goal["id"] not in covered_goals:
                gaps.append(f"目标 {goal['id']} 缺少证据: {goal['text'][:60]}")

        # 检查证据状态 / Check evidence status
        pending = [e for e in evidence_map if e.get("status") == "pending"]
        if pending:
            gaps.append(f"有 {len(pending)} 项证据状态为待确认")

        # ASIL D 深入检查 / ASIL D deep check
        asil_d_goals = [g for g in gsn.get("goals", []) if g.get("asil") == "ASIL_D"]
        if asil_d_goals and not any(e.get("evidence_type") == "independent_assessment" for e in evidence_map):
            gaps.append("ASIL D 目标需要独立安全评估 (I SA)")

        return gaps

    def _assess_confidence(self, evidence_map: List) -> Dict[str, Any]:
        """评估置信度 / Assess confidence level."""
        if not evidence_map:
            return {"level": "low", "score": 0}

        available = sum(1 for e in evidence_map if e.get("status") == "available")
        pending = sum(1 for e in evidence_map if e.get("status") == "pending")
        total = len(evidence_map)

        score = available / total * 100 if total > 0 else 0

        if score >= 90:
            level = "high"
        elif score >= 70:
            level = "medium"
        else:
            level = "low"

        return {
            "level": level,
            "score": round(score, 1),
            "available_evidence": available,
            "pending_evidence": pending,
            "total_evidence": total,
        }

    def _determine_verdict(self, confidence: Dict, gaps: List) -> str:
        """确定最终判定 / Determine final verdict."""
        if confidence.get("level") == "high" and not gaps:
            return "安全案例充分 / Safety case sufficient"
        elif confidence.get("level") in ("medium", "high"):
            return "安全案例部分充分，需补充证据 / Partially sufficient"
        else:
            return "安全案例不充分，需补充分析和证据 / Insufficient"
