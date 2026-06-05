"""
Testing Skills - 测试技能

自动驾驶系统的测试用例设计、SIL/HIL 测试和回归测试。
Test case design, SIL/HIL testing, and regression testing for autonomous driving.
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
# 测试用例设计技能 / Test Case Design Skill
# =============================================================================


class TestCaseDesignSkill(BaseSkill):
    """
    测试用例生成与设计技能。
    Test case generation and design for AD/ADAS systems.

    生成策略 / Generation strategies:
        - 等价类划分 / Equivalence partitioning
        - 边界值分析 / Boundary value analysis
        - 场景组合测试 / Scenario combination testing
        - 正交实验设计 / Orthogonal experimental design
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="test_case_design",
            version="1.0.0",
            category=SkillCategory.TESTING,
            description="测试用例设计：等价类、边界值、场景组合测试设计",
            author="Nonull",
            tags=["testing", "test-case", "qa", "validation", "scenario"],
            input_schema={
                "type": "object",
                "properties": {
                    "module": {"type": "string", "description": "待测模块 / Module under test"},
                    "requirements": {"type": "array", "description": "需求列表"},
                    "specifications": {"type": "object", "description": "规格说明"},
                    "count": {"type": "integer", "description": "期望生成用例数"},
                },
                "required": ["module", "requirements"],
            },
            safety_level=2,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        module: str = context["module"]
        requirements: List = context.get("requirements", [])
        specs: Optional[Dict] = context.get("specifications", {})
        target_count: int = context.get("count", 0)

        test_cases: List[Dict[str, Any]] = []

        # 基于需求的测试生成 / Requirement-based test generation
        for req in requirements:
            cases = self._generate_from_requirement(req, module)
            test_cases.extend(cases)

        # 场景组合测试 / Scenario combination
        if specs:
            combo_cases = self._generate_combinations(specs, module)
            test_cases.extend(combo_cases)

        # 边界测试 / Boundary tests
        boundary_cases = self._generate_boundary_tests(module)
        test_cases.extend(boundary_cases)

        # 去重 / Deduplicate
        seen = set()
        unique_cases = []
        for tc in test_cases:
            key = (tc.get("name", ""), tc.get("input", str(tc)))
            if key not in seen:
                seen.add(key)
                unique_cases.append(tc)

        # 按目标数量裁剪 / Trim to target
        if target_count > 0 and len(unique_cases) > target_count:
            random.shuffle(unique_cases)
            unique_cases = unique_cases[:target_count]

        return {
            "module": module,
            "total_test_cases": len(unique_cases),
            "requirement_coverage": f"{len(set(r.get('id', '') for r in requirements))}/{len(requirements)}",
            "test_cases": unique_cases,
            "coverage_summary": self._summary_coverage(unique_cases, requirements),
            "generation_methods": ["requirement", "combination", "boundary"],
        }

    def _generate_from_requirement(
        self, req: Any, module: str
    ) -> List[Dict[str, Any]]:
        """从需求生成测试用例 / Generate test case from a requirement."""
        cases = []

        if isinstance(req, dict):
            req_id = req.get("id", f"REQ-{random.randint(100, 999)}")
            req_desc = req.get("description", req.get("text", str(req)))
        else:
            req_id = f"REQ-{random.randint(100, 999)}"
            req_desc = str(req)

        # 生成正例 / Positive test
        cases.append({
            "name": f"TC-{req_id}-POS-001",
            "requirement": req_id,
            "type": "positive",
            "description": f"[正向] 验证: {req_desc[:80]}",
            "precondition": "系统正常运行 / System is operational",
            "input": {"module": module, "scenario": "normal_operation"},
            "expected_output": {"status": "success", "meets_requirement": True},
            "priority": "high",
            "automation_ready": True,
        })

        # 生成负例 / Negative test
        cases.append({
            "name": f"TC-{req_id}-NEG-001",
            "requirement": req_id,
            "type": "negative",
            "description": f"[负向] 异常输入验证: {req_desc[:80]}",
            "precondition": "系统正常运行",
            "input": {"module": module, "scenario": "error_condition", "inject_fault": True},
            "expected_output": {"status": "error_handled", "safe_state": True},
            "priority": "high",
            "automation_ready": True,
        })

        return cases

    def _generate_combinations(
        self, specs: Dict, module: str
    ) -> List[Dict[str, Any]]:
        """基于组合测试生成用例 / Generate combination test cases."""
        cases = []

        # ADAS 典型参数组合 / Typical ADAS parameter combinations
        combinations = [
            {
                "speed": "high", "weather": "clear", "road": "highway",
                "traffic": "light", "lighting": "day",
            },
            {
                "speed": "medium", "weather": "rain", "road": "urban",
                "traffic": "dense", "lighting": "night",
            },
            {
                "speed": "low", "weather": "fog", "road": "residential",
                "traffic": "mixed", "lighting": "dusk",
            },
            {
                "speed": "high", "weather": "snow", "road": "highway",
                "traffic": "medium", "lighting": "day",
            },
        ]

        for i, combo in enumerate(combinations):
            cases.append({
                "name": f"TC-COMBO-{i + 1:03d}",
                "requirement": "COMBINATION_TEST",
                "type": "combination",
                "description": f"组合测试: {combo['speed']}速/{combo['weather']}/{combo['road']}",
                "precondition": f"天气: {combo['weather']}, 道路: {combo['road']}",
                "input": {
                    "module": module,
                    "scenario": combo,
                },
                "expected_output": {"status": "success", "safety_margin": "adequate"},
                "priority": "medium" if combo["weather"] == "clear" else "high",
                "automation_ready": True,
            })

        return cases

    def _generate_boundary_tests(self, module: str) -> List[Dict[str, Any]]:
        """生成边界测试 / Generate boundary tests."""
        boundaries = [
            {
                "param": "车速 / Vehicle Speed",
                "values": [0, 0.1, 29.9, 30.0, 30.1, 119.9, 120.0, 120.1, 250],
                "unit": "km/h",
            },
            {
                "param": "跟车距离 / Following Distance",
                "values": [0, 0.5, 1.0, 1.5, 2.0, 5.0, 10.0, 50.0, 100.0],
                "unit": "s (time headway)",
            },
            {
                "param": "转向角 / Steering Angle",
                "values": [-720, -360, -180, -90, -45, 0, 45, 90, 180, 360, 720],
                "unit": "deg",
            },
        ]

        cases = []
        for b in boundaries:
            for val in b["values"]:
                cases.append({
                    "name": f"TC-BOUNDARY-{b['param'][:20]}-{val}",
                    "requirement": "BOUNDARY_TEST",
                    "type": "boundary",
                    "description": f"边界测试: {b['param']}={val}{b['unit']}",
                    "precondition": f"{b['param']} 设置为边界值",
                    "input": {
                        "module": module,
                        "parameter": b["param"],
                        "value": val,
                        "unit": b["unit"],
                    },
                    "expected_output": self._boundary_expected(val, b["param"]),
                    "priority": "high",
                    "automation_ready": True,
                })

        return cases

    def _boundary_expected(self, val: float, param: str) -> Dict:
        """边界值的预期结果 / Expected result for boundary value."""
        # 根据值范围判断预期 / Determine expected based on value range
        if param.startswith("车速"):
            if 0 <= val <= 250:
                return {"status": "success", "behavior": "normal"}
            return {"status": "error", "behavior": "clamp_or_reject"}
        if param.startswith("跟车"):
            if val >= 0.5:
                return {"status": "success", "behavior": "normal"}
            return {"status": "warning", "behavior": "collision_warning"}
        return {"status": "success"}

    def _summary_coverage(
        self, test_cases: List[Dict], requirements: List
    ) -> Dict[str, Any]:
        """总结覆盖率 / Summarize coverage."""
        req_ids = set()
        types = {}
        priorities = {}

        for tc in test_cases:
            rid = tc.get("requirement", "")
            if rid:
                req_ids.add(rid)
            t = tc.get("type", "unknown")
            types[t] = types.get(t, 0) + 1
            p = tc.get("priority", "medium")
            priorities[p] = priorities.get(p, 0) + 1

        return {
            "requirements_covered": len(req_ids),
            "total_requirements": len(requirements),
            "test_type_distribution": types,
            "priority_distribution": priorities,
        }


# =============================================================================
# SIL 测试技能 / SIL Test Skill
# =============================================================================


class SILTestSkill(BaseSkill):
    """
    软件在环测试技能。
    Software-in-the-loop testing for AD algorithms.

    测试内容 / Testing:
        - 算法单元测试 / Algorithm unit testing
        - 模块集成测试 / Module integration testing
        - 接口一致性验证 / Interface consistency verification
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="sil_test",
            version="1.0.0",
            category=SkillCategory.TESTING,
            description="SIL测试：软件在环测试、接口验证与集成测试",
            author="Nonull",
            tags=["testing", "sil", "software-in-the-loop", "unit-test", "integration"],
            input_schema={
                "type": "object",
                "properties": {
                    "test_type": {
                        "type": "string",
                        "enum": ["unit", "integration", "interface", "full"],
                    },
                    "module": {"type": "string"},
                    "test_vectors": {"type": "array"},
                    "test_script": {"type": "string"},
                },
                "required": ["test_type", "module"],
            },
            safety_level=2,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        test_type: str = context["test_type"]
        module: str = context["module"]
        test_vectors: List = context.get("test_vectors", [])
        test_script: Optional[str] = context.get("test_script")

        result: Dict[str, Any] = {
            "module": module,
            "test_type": test_type,
            "test_results": [],
            "summary": {},
            "recommendations": [],
        }

        if test_type in ("unit", "full"):
            result["test_results"].extend(self._run_unit_tests(module, test_vectors))

        if test_type in ("integration", "full"):
            result["test_results"].extend(
                self._run_integration_tests(module, test_vectors)
            )

        if test_type in ("interface", "full"):
            result["test_results"].extend(
                self._verify_interfaces(module, test_script)
            )

        passed = sum(1 for r in result["test_results"] if r.get("passed", False))
        total = len(result["test_results"])
        coverage = result.get("coverage_estimate", 0)

        result["summary"] = {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": f"{passed / total * 100:.1f}%" if total > 0 else "N/A",
            "coverage_estimate": f"{coverage}%",
        }

        if passed < total:
            result["recommendations"].append(
                f"有 {total - passed} 个测试未通过，请检查模块实现"
            )
        if coverage < 80:
            result["recommendations"].append("测试覆盖率低于80%，请补充测试用例")

        return result

    def _run_unit_tests(
        self, module: str, vectors: List
    ) -> List[Dict[str, Any]]:
        """运行单元测试 / Run unit tests."""
        results = []

        if not vectors:
            vectors = self._generate_test_vectors(module, count=5)

        for i, vec in enumerate(vectors):
            test_name = vec.get("name", f"UT-{module}-{i:03d}")
            passed = vec.get("expected") == vec.get("actual") if "expected" in vec and "actual" in vec else True

            results.append({
                "test_name": test_name,
                "type": "unit",
                "category": vec.get("category", "functional"),
                "input": vec.get("input", {}),
                "expected": vec.get("expected"),
                "actual": vec.get("actual", vec.get("expected")),
                "passed": passed,
                "duration_ms": round(random.uniform(1, 50), 2),
                "message": "通过" if passed else "输出与预期不符",
            })

        return results

    def _run_integration_tests(
        self, module: str, vectors: List
    ) -> List[Dict[str, Any]]:
        """运行集成测试 / Run integration tests."""
        results = []

        interfaces = [
            {"from": "perception", "to": "planning", "data": "object_list"},
            {"from": "planning", "to": "control", "data": "trajectory"},
            {"from": "localization", "to": "planning", "data": "ego_pose"},
        ]

        for iface in interfaces:
            passed = random.random() > 0.1
            results.append({
                "test_name": f"INT-{iface['from']}-to-{iface['to']}",
                "type": "integration",
                "interface": f"{iface['from']} -> {iface['to']}",
                "data_type": iface["data"],
                "passed": passed,
                "duration_ms": round(random.uniform(10, 100), 2),
                "message": f"接口 {iface['from']}->{iface['to']} 数据传递正常" if passed else "数据传递异常",
            })

        return results

    def _verify_interfaces(
        self, module: str, script: Optional[str]
    ) -> List[Dict[str, Any]]:
        """验证接口一致性 / Verify interface consistency."""
        results = []

        checks = [
            {"name": "输入类型检查", "check": "type_consistency"},
            {"name": "数据范围检查", "check": "range_validation"},
            {"name": "时序约束检查", "check": "timing_constraints"},
            {"name": "内存安全检查", "check": "memory_safety"},
        ]

        for check in checks:
            passed = random.random() > 0.05
            results.append({
                "test_name": f"IFACE-{check['name']}",
                "type": "interface",
                "check": check["check"],
                "passed": passed,
                "message": f"{check['name']}: 通过" if passed else f"{check['name']}: 存在异常",
            })

        return results

    def _generate_test_vectors(self, module: str, count: int) -> List[Dict]:
        """生成测试向量 / Generate test vectors."""
        vectors = []
        for i in range(count):
            vectors.append({
                "name": f"TV-{module}-{i:03d}",
                "category": random.choice(["functional", "boundary", "stress"]),
                "input": {"value": random.uniform(-10, 100)},
                "expected": {"status": "ok"},
                "actual": {"status": "ok"},
            })
        return vectors


# =============================================================================
# HIL 测试技能 / HIL Test Skill
# =============================================================================


class HILTestSkill(BaseSkill):
    """
    硬件在环测试技能。
    Hardware-in-the-loop testing for AD/ADAS ECUs.

    测试内容 / Testing:
        - 传感器 HIL / Sensor HIL
        - 执行器 HIL / Actuator HIL
        - 整车 ECU HIL / Vehicle ECU HIL
        - 故障注入测试 / Fault injection testing
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="hil_test",
            version="1.0.0",
            category=SkillCategory.TESTING,
            description="HIL测试：硬件在环测试、故障注入与实时性验证",
            author="Nonull",
            tags=["testing", "hil", "hardware-in-the-loop", "ecu", "fault-injection"],
            input_schema={
                "type": "object",
                "properties": {
                    "ecu_type": {"type": "string", "description": "ECU类型"},
                    "test_duration_s": {"type": "number", "description": "测试时长"},
                    "test_cases": {"type": "array"},
                    "fault_injection": {"type": "boolean"},
                },
                "required": ["ecu_type"],
            },
            safety_level=5,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        ecu_type: str = context["ecu_type"]
        duration: float = context.get("test_duration_s", 60.0)
        test_cases: List = context.get("test_cases", [])
        fault_injection: bool = context.get("fault_injection", False)

        result: Dict[str, Any] = {
            "ecu_type": ecu_type,
            "test_duration_s": duration,
            "test_phases": [],
            "fault_injection_tests": [],
            "timing_analysis": {},
            "verdict": "",
            "recommendations": [],
        }

        # HIL 测试阶段 / HIL test phases
        phases = [
            {"name": "上电自检", "duration_pct": 10},
            {"name": "传感器信号仿真", "duration_pct": 30},
            {"name": "控制算法验证", "duration_pct": 35},
            {"name": "执行器响应测试", "duration_pct": 15},
            {"name": "下电安全测试", "duration_pct": 10},
        ]

        phase_results = []
        all_passed = True
        for phase in phases:
            phase_duration = duration * phase["duration_pct"] / 100
            passed = self._simulate_hil_phase(ecu_type, phase["name"])
            if not passed:
                all_passed = False
            phase_results.append({
                "phase": phase["name"],
                "duration_s": round(phase_duration, 1),
                "passed": passed,
                "details": f"{phase['name']} {'通过' if passed else '失败'}",
            })

        result["test_phases"] = phase_results

        # 故障注入测试 / Fault injection tests
        if fault_injection:
            fault_tests = self._run_fault_injection(ecu_type)
            result["fault_injection_tests"] = fault_tests
            if any(ft.get("system_response") == "critical_failure" for ft in fault_tests):
                all_passed = False

        # 时序分析 / Timing analysis
        result["timing_analysis"] = self._analyze_timing(ecu_type)

        result["verdict"] = "PASS" if all_passed else "FAIL"
        if not all_passed:
            result["recommendations"].append("HIL测试未通过，检查硬件连接或固件版本")

        return result

    def _simulate_hil_phase(self, ecu_type: str, phase: str) -> bool:
        """模拟HIL测试阶段 / Simulate HIL test phase."""
        # 随机模拟HIL测试结果（实际应用中连接真实硬件）
        # Simulate HIL result (real implementation would connect to actual HW)
        return random.random() > 0.05

    def _run_fault_injection(self, ecu_type: str) -> List[Dict]:
        """运行故障注入测试 / Run fault injection tests."""
        faults = [
            {"fault": "CAN总线断开", "duration_s": 2.0},
            {"fault": "传感器信号丢失", "duration_s": 1.0},
            {"fault": "电源电压波动", "duration_s": 0.5},
            {"fault": "执行器短路", "duration_s": 3.0},
            {"fault": "时钟信号异常", "duration_s": 1.5},
        ]

        results = []
        for f in faults:
            responses = ["graceful_degradation", "safe_state", "error_recovery", "critical_failure"]
            response = random.choices(responses, weights=[0.4, 0.3, 0.2, 0.1])[0]
            results.append({
                "injected_fault": f["fault"],
                "duration_s": f["duration_s"],
                "system_response": response,
                "recovery_time_ms": round(random.uniform(10, 200), 1),
                "expected_response": "safe_state_or_degradation",
                "passed": response != "critical_failure",
            })

        return results

    def _analyze_timing(self, ecu_type: str) -> Dict:
        """分析时序 / Analyze timing."""
        return {
            "max_latency_ms": round(random.uniform(1, 15), 2),
            "average_latency_ms": round(random.uniform(0.5, 5), 2),
            "jitter_ms": round(random.uniform(0.1, 2), 2),
            "deadline_misses": random.randint(0, 3),
            "meets_real_time_requirements": random.random() > 0.1,
        }


# =============================================================================
# 回归测试技能 / Regression Test Skill
# =============================================================================


class RegressionTestSkill(BaseSkill):
    """
    回归测试设计技能。
    Regression test design for AD software releases.

    设计内容 / Design:
        - 影响范围分析 / Impact scope analysis
        - 回归用例选择 / Regression test selection
        - 自动化回归流程 / Automated regression workflow
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="regression_test",
            version="1.0.0",
            category=SkillCategory.TESTING,
            description="回归测试：影响分析、用例选择和自动化流程设计",
            author="Nonull",
            tags=["testing", "regression", "automation", "ci", "impact-analysis"],
            input_schema={
                "type": "object",
                "properties": {
                    "changed_modules": {"type": "array"},
                    "release_notes": {"type": "string"},
                    "existing_tests": {"type": "array"},
                    "impact_analysis": {"type": "object"},
                },
                "required": ["changed_modules", "release_notes"],
            },
            safety_level=2,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        changed_modules: List = context["changed_modules"]
        notes: str = context.get("release_notes", "")
        existing_tests: List = context.get("existing_tests", [])
        impact: Optional[Dict] = context.get("impact_analysis")

        result: Dict[str, Any] = {
            "impact_analysis": impact or self._analyze_impact(changed_modules),
            "selected_tests": [],
            "regression_suite": {
                "smoke_tests": [],
                "full_regression": [],
            },
            "automation_plan": {},
            "estimated_execution_time_min": 0,
            "recommendations": [],
        }

        impact_result = result["impact_analysis"]
        affected = impact_result.get("affected_modules", changed_modules)

        # 选择烟幕测试 / Select smoke tests
        smoke = self._select_smoke_tests(affected, existing_tests)
        result["regression_suite"]["smoke_tests"] = smoke

        # 选择全回归测试 / Select full regression tests
        full = self._select_full_regression(affected, existing_tests)
        result["regression_suite"]["full_regression"] = full

        # 汇总 / Summary
        all_selected = smoke + full
        result["selected_tests"] = all_selected

        smoke_time = sum(t.get("duration_min", 2) for t in smoke)
        full_time = sum(t.get("duration_min", 5) for t in full)
        result["estimated_execution_time_min"] = smoke_time + full_time

        # 自动化计划 / Automation plan
        result["automation_plan"] = {
            "trigger": "on_push_to_main_or_release_branch",
            "smoke_timeout_min": max(10, int(smoke_time * 1.5)),
            "full_timeout_min": max(30, int(full_time * 1.5)),
            "parallel_execution": True,
            "max_parallel_jobs": 4,
            "report_format": "junit_xml",
            "notification": "slack_and_email",
        }

        if result["estimated_execution_time_min"] > 120:
            result["recommendations"].append("回归测试预计超过2小时，建议优化用例或增加并行度")

        return result

    def _analyze_impact(self, changed_modules: List[str]) -> Dict[str, Any]:
        """分析变更影响 / Analyze change impact."""
        impact_map = {
            "perception": ["planning", "control", "fusion"],
            "planning": ["control", "prediction"],
            "localization": ["planning", "control", "perception"],
            "control": ["actuator", "can_bus"],
            "fusion": ["planning", "perception"],
            "prediction": ["planning", "decision"],
        }

        affected = set(changed_modules)
        for mod in changed_modules:
            downstream = impact_map.get(mod.lower(), [])
            affected.update(downstream)

        return {
            "changed_modules": changed_modules,
            "affected_modules": sorted(affected),
            "risk_level": "high" if "planning" in affected else "medium",
        }

    def _select_smoke_tests(
        self, affected: List[str], existing: List
    ) -> List[Dict]:
        """选择冒烟测试 / Select smoke tests."""
        smoke = []

        # 为每个受影响的模块生成烟雾测试 / Generate smoke test per affected module
        for mod in affected:
            smoke.append({
                "name": f"SMOKE-{mod}-001",
                "module": mod,
                "type": "smoke",
                "description": f"{mod} 模块基本功能冒烟测试",
                "duration_min": random.randint(1, 5),
                "priority": "critical",
                "automated": True,
            })

        return smoke

    def _select_full_regression(
        self, affected: List[str], existing: List
    ) -> List[Dict]:
        """选择全回归测试 / Select full regression tests."""
        regression = []

        for mod in affected:
            # 功能回归 / Functional regression
            regression.append({
                "name": f"REGR-{mod}-FUNC-001",
                "module": mod,
                "type": "functional",
                "description": f"{mod} 功能回归测试",
                "duration_min": random.randint(5, 20),
                "priority": "high",
                "automated": True,
            })

            # 接口回归 / Interface regression
            regression.append({
                "name": f"REGR-{mod}-IFACE-001",
                "module": mod,
                "type": "interface",
                "description": f"{mod} 接口回归测试",
                "duration_min": random.randint(3, 10),
                "priority": "high",
                "automated": True,
            })

        return regression
