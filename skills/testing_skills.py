"""
Testing Skills - 测试技能

These skills generate demo/test data only. For real testing/simulation workflows,
integrate with your actual test framework and simulator.
本技能仅用于生成演示/测试数据。真实测试/仿真工作流请接入实际测试框架与仿真器。

自动驾驶系统的测试用例设计、SIL/HIL 测试和回归测试。
Test case design, SIL/HIL testing, and regression testing for autonomous driving.

重要: 这些技能生成的测试通过率、延迟、响应时间等指标都是 DEMO 模拟值。
Important: Pass rates, latencies, and response times emitted by these skills are
DEMO simulated values, not real measurements.

To control behavior, the execution context may include:
    {
        "__demo_mode__": True,    # Use random data (default for backward compat)
        "seed": 42,               # Optional: reproducible random
        "deterministic": True,    # Optional: derive values from inputs (no random)
    }
"""

from __future__ import annotations

import hashlib
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


# Module-level ID counters (deterministic by default)
_REQ_COUNTER = {"value": 100}
_TEST_VECTOR_COUNTER = {"value": 0}
_FAULT_COUNTER = {"value": 0}


def _make_rng(context: Optional[Dict[str, Any]]) -> random.Random:
    """Build a per-call RNG based on context flags.

    Behavior:
        - If ``seed`` is provided in the context, use a Random(seed) instance
          for reproducible randomness.
        - If ``__demo_mode__`` is False OR ``deterministic`` is True, return a
          Random instance seeded from a hash of the context so the same
          inputs always produce the same outputs.
        - Otherwise (default / legacy), use the global random module for
          backwards compatibility.
    """
    ctx = context or {}
    if "seed" in ctx:
        try:
            return random.Random(ctx["seed"])
        except (TypeError, ValueError):
            pass
    if ctx.get("deterministic") or ctx.get("__demo_mode__") is False:
        # Hash context to a stable seed
        try:
            payload = repr(sorted(ctx.items())).encode("utf-8")
        except Exception:
            payload = repr(ctx).encode("utf-8")
        seed = int(hashlib.md5(payload).hexdigest()[:8], 16)
        return random.Random(seed)
    return random  # Use module-level random for backward compat


def _next_id(counter: Dict[str, int], rng: random.Random) -> int:
    """Return a deterministic ID derived from a counter (or RNG fallback)."""
    counter["value"] += 1
    return counter["value"]


def _stable_hash_int(value: str, modulo: int) -> int:
    """Map a string to a stable integer in [0, modulo)."""
    h = int(hashlib.md5(value.encode("utf-8")).hexdigest()[:8], 16)
    return h % modulo


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
            version="1.1.0",
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
                    "__demo_mode__": {"type": "boolean", "description": "DEMO mode flag"},
                    "seed": {"type": "integer", "description": "Optional seed"},
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

        rng = _make_rng(context)

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
            # Deterministic shuffle: use the RNG derived from context
            rng.shuffle(unique_cases)
            unique_cases = unique_cases[:target_count]

        return {
            "module": module,
            "total_test_cases": len(unique_cases),
            "requirement_coverage": f"{len(set(r.get('id', '') for r in requirements))}/{len(requirements)}",
            "test_cases": unique_cases,
            "coverage_summary": self._summary_coverage(unique_cases, requirements),
            "generation_methods": ["requirement", "combination", "boundary"],
            "is_demo_data": True,
        }

    def _generate_from_requirement(
        self, req: Any, module: str
    ) -> List[Dict[str, Any]]:
        """从需求生成测试用例 / Generate test case from a requirement."""
        cases = []

        if isinstance(req, dict):
            # Deterministic: use the user-supplied id, or a stable hash-derived id
            req_id = req.get("id")
            if not req_id:
                req_id = f"REQ-{_stable_hash_int(req.get('description', str(req)), 900) + 100}"
            req_desc = req.get("description", req.get("text", str(req)))
        else:
            # Deterministic fallback for string requirements
            req_id = f"REQ-{_stable_hash_int(str(req), 900) + 100}"
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

    NOTE: Pass/fail results produced by this skill are DEMO placeholders,
    not real measurements. Wire it to your real test framework (pytest, gtest,
    etc.) for actual validation. Pass ``__demo_mode__=False`` or a numeric
    ``seed`` to make the placeholders deterministic.

    测试内容 / Testing:
        - 算法单元测试 / Algorithm unit testing
        - 模块集成测试 / Module integration testing
        - 接口一致性验证 / Interface consistency verification
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="sil_test",
            version="1.1.0",
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
                    "__demo_mode__": {"type": "boolean"},
                    "seed": {"type": "integer"},
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

        rng = _make_rng(context)

        result: Dict[str, Any] = {
            "module": module,
            "test_type": test_type,
            "test_results": [],
            "summary": {},
            "recommendations": [],
            "is_demo_data": True,
            "data_source": "DEMO: replace with real test framework output",
        }

        if test_type in ("unit", "full"):
            result["test_results"].extend(
                self._run_unit_tests(module, test_vectors, rng)
            )

        if test_type in ("integration", "full"):
            result["test_results"].extend(
                self._run_integration_tests(module, test_vectors, rng)
            )

        if test_type in ("interface", "full"):
            result["test_results"].extend(
                self._verify_interfaces(module, test_script, rng)
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
                f"有 {total - passed} 个测试未通过，请检查模块实现 (DEMO占位结果)"
            )
        if coverage < 80:
            result["recommendations"].append("测试覆盖率低于80%，请补充测试用例")

        return result

    def _run_unit_tests(
        self, module: str, vectors: List, rng: random.Random
    ) -> List[Dict[str, Any]]:
        """运行单元测试 / Run unit tests."""
        results = []

        if not vectors:
            vectors = self._generate_test_vectors(module, count=5, rng=rng)

        for i, vec in enumerate(vectors):
            test_name = vec.get("name", f"UT-{module}-{i:03d}")
            # Only declare passed when both expected and actual are present and match.
            passed = (
                vec.get("expected") == vec.get("actual")
                if "expected" in vec and "actual" in vec
                else None  # unknown — not fabricated
            )
            # If passed is unknown, derive a deterministic DEMO placeholder
            # based on the input vector. Same vector => same outcome.
            if passed is None:
                passed = self._demo_pass(vec, "unit", rng)

            # Duration is derived from input size (deterministic) instead of random
            input_size = self._estimate_input_size(vec.get("input", {}))
            duration_ms = round(1.0 + math.log1p(input_size) * 5.0, 2)

            results.append({
                "test_name": test_name,
                "type": "unit",
                "category": vec.get("category", "functional"),
                "input": vec.get("input", {}),
                "expected": vec.get("expected"),
                "actual": vec.get("actual", vec.get("expected")),
                "passed": passed,
                "duration_ms": duration_ms,
                "message": "通过" if passed else "输出与预期不符",
            })

        return results

    def _run_integration_tests(
        self, module: str, vectors: List, rng: random.Random
    ) -> List[Dict[str, Any]]:
        """运行集成测试 / Run integration tests."""
        results = []

        interfaces = [
            {"from": "perception", "to": "planning", "data": "object_list"},
            {"from": "planning", "to": "control", "data": "trajectory"},
            {"from": "localization", "to": "planning", "data": "ego_pose"},
        ]

        for iface in interfaces:
            iface_key = f"{iface['from']}->{iface['to']}"
            # Deterministic DEMO pass/fail: derived from interface key, not random
            passed = self._demo_pass({"iface": iface_key, "type": "integration"}, "integration", rng)
            # Duration derived from data_type complexity (deterministic)
            base_ms = self._complexity_ms(iface["data"])
            duration_ms = round(base_ms, 2)

            results.append({
                "test_name": f"INT-{iface['from']}-to-{iface['to']}",
                "type": "integration",
                "interface": f"{iface['from']} -> {iface['to']}",
                "data_type": iface["data"],
                "passed": passed,
                "duration_ms": duration_ms,
                "message": (
                    f"接口 {iface['from']}->{iface['to']} 数据传递正常"
                    if passed
                    else "数据传递异常"
                ),
            })

        return results

    def _verify_interfaces(
        self, module: str, script: Optional[str], rng: random.Random
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
            # Deterministic DEMO pass/fail: derived from check name
            passed = self._demo_pass(check, "interface", rng)
            results.append({
                "test_name": f"IFACE-{check['name']}",
                "type": "interface",
                "check": check["check"],
                "passed": passed,
                "message": f"{check['name']}: 通过" if passed else f"{check['name']}: 存在异常",
            })

        return results

    def _generate_test_vectors(
        self, module: str, count: int, rng: random.Random
    ) -> List[Dict]:
        """生成测试向量 / Generate test vectors.

        Categories and input values are derived deterministically from the
        index. The same ``(module, count, seed)`` always produces the same
        vectors.
        """
        categories = ["functional", "boundary", "stress"]
        vectors = []
        for i in range(count):
            # Deterministic selection: alternate through categories
            category = categories[i % len(categories)]
            # Deterministic value: scaled by index, not random
            value = -10.0 + (i * (110.0 / max(count, 1)))
            vectors.append({
                "name": f"TV-{module}-{i:03d}",
                "category": category,
                "input": {"value": round(value, 3)},
                "expected": {"status": "ok"},
                "actual": {"status": "ok"},
            })
        return vectors

    @staticmethod
    def _estimate_input_size(obj: Any) -> int:
        """Estimate the size of an input for deterministic duration derivation."""
        try:
            return len(repr(obj))
        except Exception:
            return 16

    @staticmethod
    def _complexity_ms(data_type: str) -> float:
        """Map a data type name to a base DEMO duration in ms (deterministic)."""
        mapping = {
            "object_list": 50.0,
            "trajectory": 75.0,
            "ego_pose": 25.0,
        }
        return mapping.get(data_type, 30.0)

    def _demo_pass(self, vec: Dict[str, Any], test_kind: str, rng: random.Random) -> bool:
        """Derive a deterministic DEMO pass/fail from the input.

        Real test outcomes MUST come from a real test framework. This method
        exists only so that smoke tests and demos are reproducible.
        """
        if rng is random:
            # Backward-compat: legacy non-deterministic mode kept on demand
            return random.random() > 0.1
        # Deterministic: hash the test vector to get a stable 0..1 value
        key = f"{test_kind}|{repr(sorted(vec.items()))}"
        h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
        # Use a default 90% pass rate; the same vector always gets the same outcome
        return (h % 100) < 90


# =============================================================================
# HIL 测试技能 / HIL Test Skill
# =============================================================================


class HILTestSkill(BaseSkill):
    """
    硬件在环测试技能。
    Hardware-in-the-loop testing for AD/ADAS ECUs.

    NOTE: This skill emits DEMO placeholder data. It does not connect to real
    HIL hardware. For real HIL testing, integrate with your dSPACE / Vector /
    National Instruments stack and feed the results back into this skill via
    its context.

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
            version="1.1.0",
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
                    "__demo_mode__": {"type": "boolean"},
                    "seed": {"type": "integer"},
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

        rng = _make_rng(context)

        result: Dict[str, Any] = {
            "ecu_type": ecu_type,
            "test_duration_s": duration,
            "test_phases": [],
            "fault_injection_tests": [],
            "timing_analysis": {},
            "verdict": "",
            "recommendations": [],
            "is_demo_data": True,
            "data_source": "DEMO: replace with real HIL hardware output",
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
            # Deterministic pass derived from (ecu_type, phase) and RNG
            passed = self._simulate_hil_phase(ecu_type, phase["name"], rng)
            if not passed:
                all_passed = False
            phase_results.append({
                "phase": phase["name"],
                "duration_s": round(phase_duration, 1),
                "passed": passed,
                "details": f"{phase['name']} {'通过' if passed else '失败'} (DEMO占位)",
            })

        result["test_phases"] = phase_results

        # 故障注入测试 / Fault injection tests
        if fault_injection:
            fault_tests = self._run_fault_injection(ecu_type, rng)
            result["fault_injection_tests"] = fault_tests
            if any(ft.get("system_response") == "critical_failure" for ft in fault_tests):
                all_passed = False

        # 时序分析 / Timing analysis — deterministic from ecu_type
        result["timing_analysis"] = self._analyze_timing(ecu_type, rng)

        result["verdict"] = "PASS" if all_passed else "FAIL"
        if not all_passed:
            result["recommendations"].append("HIL测试未通过 (DEMO)，请接入真实HIL硬件获取真实结论")

        return result

    def _simulate_hil_phase(
        self, ecu_type: str, phase: str, rng: random.Random
    ) -> bool:
        """模拟HIL测试阶段 / Simulate HIL test phase (DEMO).

        Real implementations must connect to actual HIL hardware. This
        placeholder produces a stable outcome based on (ecu_type, phase).
        """
        if rng is random:
            return random.random() > 0.05
        # Deterministic: hash (ecu_type, phase) to a stable outcome
        key = f"hil_phase|{ecu_type}|{phase}"
        h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
        return (h % 100) >= 5  # ~95% pass rate, but stable per phase

    def _run_fault_injection(
        self, ecu_type: str, rng: random.Random
    ) -> List[Dict]:
        """运行故障注入测试 / Run fault injection tests (DEMO)."""
        faults = [
            {"fault": "CAN总线断开", "duration_s": 2.0},
            {"fault": "传感器信号丢失", "duration_s": 1.0},
            {"fault": "电源电压波动", "duration_s": 0.5},
            {"fault": "执行器短路", "duration_s": 3.0},
            {"fault": "时钟信号异常", "duration_s": 1.5},
        ]

        responses = ["graceful_degradation", "safe_state", "error_recovery", "critical_failure"]

        results = []
        for f in faults:
            # Deterministic response based on fault name and ecu_type
            response = self._demo_fault_response(ecu_type, f["fault"], responses, rng)
            results.append({
                "injected_fault": f["fault"],
                "duration_s": f["duration_s"],
                "system_response": response,
                "recovery_time_ms": round(self._demo_recovery_ms(ecu_type, f["fault"]), 1),
                "expected_response": "safe_state_or_degradation",
                "passed": response != "critical_failure",
            })

        return results

    def _analyze_timing(self, ecu_type: str, rng: random.Random) -> Dict:
        """分析时序 / Analyze timing (DEMO).

        Values are stable per ecu_type. Real HIL timing should come from
        oscilloscope / ECU trace data.
        """
        if rng is random:
            return {
                "max_latency_ms": round(random.uniform(1, 15), 2),
                "average_latency_ms": round(random.uniform(0.5, 5), 2),
                "jitter_ms": round(random.uniform(0.1, 2), 2),
                "deadline_misses": random.randint(0, 3),
                "meets_real_time_requirements": random.random() > 0.1,
            }
        # Deterministic per ecu_type
        h = int(hashlib.md5(f"timing|{ecu_type}".encode("utf-8")).hexdigest(), 16)
        max_lat = 1.0 + (h % 1400) / 100.0          # 1.0 .. 15.0
        avg_lat = 0.5 + ((h >> 8) % 450) / 100.0    # 0.5 .. 5.0
        jitter = 0.1 + ((h >> 16) % 190) / 100.0    # 0.1 .. 2.0
        misses = (h >> 24) % 4
        meets = ((h >> 32) % 10) != 0
        return {
            "max_latency_ms": round(max_lat, 2),
            "average_latency_ms": round(avg_lat, 2),
            "jitter_ms": round(jitter, 2),
            "deadline_misses": misses,
            "meets_real_time_requirements": meets,
        }

    def _demo_fault_response(
        self,
        ecu_type: str,
        fault: str,
        responses: List[str],
        rng: random.Random,
    ) -> str:
        """Derive a deterministic fault response from (ecu_type, fault)."""
        if rng is random:
            return random.choices(responses, weights=[0.4, 0.3, 0.2, 0.1])[0]
        h = int(hashlib.md5(f"fault|{ecu_type}|{fault}".encode("utf-8")).hexdigest()[:8], 16)
        weights = [0.4, 0.3, 0.2, 0.1]
        total = sum(weights)
        target = (h % 1000) / 1000.0 * total
        cumulative = 0.0
        for resp, w in zip(responses, weights):
            cumulative += w
            if target < cumulative:
                return resp
        return responses[-1]

    def _demo_recovery_ms(self, ecu_type: str, fault: str) -> float:
        """Deterministic recovery time in ms derived from (ecu_type, fault)."""
        h = int(hashlib.md5(f"recovery|{ecu_type}|{fault}".encode("utf-8")).hexdigest()[:8], 16)
        return 10.0 + (h % 19000) / 100.0  # 10.0 .. 200.0


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
            version="1.1.0",
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
                    "__demo_mode__": {"type": "boolean"},
                    "seed": {"type": "integer"},
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

        # We pass context through so durations can be deterministic when seeded
        rng = _make_rng(context)

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
            "is_demo_data": True,
        }

        impact_result = result["impact_analysis"]
        affected = impact_result.get("affected_modules", changed_modules)

        # 选择烟幕测试 / Select smoke tests
        smoke = self._select_smoke_tests(affected, rng, context)
        result["regression_suite"]["smoke_tests"] = smoke

        # 选择全回归测试 / Select full regression tests
        full = self._select_full_regression(affected, rng, context)
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
        self,
        affected: List[str],
        rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        """选择冒烟测试 / Select smoke tests.

        Duration is derived deterministically from the module name unless
        ``__demo_mode__`` is left at its backward-compatible default (random).
        """
        smoke = []

        for idx, mod in enumerate(affected):
            duration = self._demo_duration_min(mod, idx, 1, 5, rng, context)
            smoke.append({
                "name": f"SMOKE-{mod}-001",
                "module": mod,
                "type": "smoke",
                "description": f"{mod} 模块基本功能冒烟测试",
                "duration_min": duration,
                "priority": "critical",
                "automated": True,
            })

        return smoke

    def _select_full_regression(
        self,
        affected: List[str],
        rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        """选择全回归测试 / Select full regression tests (deterministic)."""
        regression = []

        for idx, mod in enumerate(affected):
            # Functional regression
            func_dur = self._demo_duration_min(mod, idx, 5, 20, rng, context, kind="func")
            regression.append({
                "name": f"REGR-{mod}-FUNC-001",
                "module": mod,
                "type": "functional",
                "description": f"{mod} 功能回归测试",
                "duration_min": func_dur,
                "priority": "high",
                "automated": True,
            })

            # Interface regression
            iface_dur = self._demo_duration_min(mod, idx, 3, 10, rng, context, kind="iface")
            regression.append({
                "name": f"REGR-{mod}-IFACE-001",
                "module": mod,
                "type": "interface",
                "description": f"{mod} 接口回归测试",
                "duration_min": iface_dur,
                "priority": "high",
                "automated": True,
            })

        return regression

    def _demo_duration_min(
        self,
        mod: str,
        idx: int,
        low: int,
        high: int,
        rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
        kind: str = "smoke",
    ) -> int:
        """Derive a deterministic integer duration in [low, high] for a module.

        Backward-compat: if the legacy module-level random is being used
        (no seed, no deterministic, demo_mode unset) we keep the previous
        random behavior so existing callers see the same output distribution.
        """
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            return random.randint(low, high)
        h = int(hashlib.md5(f"dur|{kind}|{mod}|{idx}".encode("utf-8")).hexdigest()[:8], 16)
        return low + (h % (high - low + 1))
