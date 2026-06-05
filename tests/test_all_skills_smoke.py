"""Smoke test: every registered skill can be activated and executed with a sample input.

This is the P11 final smoke test. For each of the 31 skills, this test:
1. Activates the skill
2. Calls execute() with a representative sample input (a sensible default per skill category)
3. Verifies the result is a SkillResult with success=True or success=False (some skills are designed to fail on bad input)
4. Checks that no exception escapes

If a skill consistently crashes on any input, the test fails. This is the
broad-net regression check that protects the public skill surface.

NOTE: The test does NOT verify that the skill produces correct output (semantic
correctness is per-skill). It only verifies that the skill can be activated,
executed, and returns a SkillResult without raising.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import pytest

# Ensure project root is importable when running pytest from any CWD.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.registry import SkillRegistry
from skills.base import BaseSkill, SkillResult


# Per-skill sample inputs. Most skills just need a generic context dict.
# These were tailored to match each skill's ``_validate_input`` / ``_execute_impl``
# contract discovered by reading the actual implementation in skills/*.py.
SAMPLE_INPUTS: Dict[str, Dict[str, Any]] = {
    # ------------------ code (4) ------------------
    "code_review": {
        "code": "def f():\n    return 42\n",
        "language": "python",
        "strictness": "medium",
    },
    "code_optimization": {
        "code": "def f():\n    return [x*2 for x in range(10)]\n",
        "language": "python",
    },
    "refactoring": {
        "code": "def f(x):\n    return x*2\n",
        "language": "python",
    },
    "bug_detection": {
        "code": "def f(x):\n    return x/0  # possible div by zero\n",
        "language": "python",
    },
    # ------------------ safety (4) ------------------
    "haras_analysis": {
        "system_description": "ADAS perception + planning stack",
        "functions": ["perception", "planning", "control"],
    },
    "fmea": {
        "system_elements": [
            {"name": "FrontCamera", "type": "sensor"},
            {"name": "PlannerECU", "type": "controller"},
        ],
        "analysis_type": "full",
    },
    "iso26262_check": {
        "project_phase": "concept",
        "asil_level": "ASIL_B",
        "documents": {"item_definition": "v1.0", "HARA report": "draft"},
    },
    "safety_case": {
        "system_name": "TestADStack",
        "safety_goals": [
            {"goal": "Avoid unintended acceleration", "ASIL": "ASIL_D"}
        ],
        "evidence_items": [
            {"type": "verification_report", "description": "demo", "status": "available"}
        ],
    },
    # ------------------ perception (4) ------------------
    "sensor_analysis": {
        "sensor_config": {
            "sensors": [
                {
                    "name": "FrontCamera",
                    "type": "camera",
                    "resolution": "1920x1080",
                    "fov": 120,
                    "fps": 30,
                    "pixel_format": "RGB",
                }
            ]
        },
        "analysis_type": "full",
    },
    "perception_model_review": {
        "task_type": "detection",
        "model_config": {
            "name": "YOLOv8-Test",
            "architecture": "yolo",
            "backbone": "cspdarknet",
            "parameters_m": 25.0,
            "flops_g": 50.0,
        },
    },
    "sensor_calibration": {
        "calibration_data": {
            "intrinsics": {
                "fx": 1200.0, "fy": 1200.0,
                "cx": 960.0, "cy": 540.0,
                "width": 1920, "height": 1080,
                "distortion": [0.1, -0.05, 0.0, 0.0, 0.02],
            },
            "extrinsics": {
                "translation": [0.0, 0.0, 1.5],
                "rotation": [1, 0, 0, 0, 1, 0, 0, 0, 1],
            },
        },
        "sensor_type": "camera",
    },
    "object_detection_review": {
        "detection_results": [
            {"is_true_positive": True, "confidence": 0.92, "distance": 25.0, "category": "car"},
            {"is_true_positive": False, "confidence": 0.30, "distance": 15.0, "category": "pedestrian"},
        ],
        "ground_truth": [
            {"id": "g1", "category": "car"},
        ],
    },
    # ------------------ planning (3) ------------------
    "route_planning": {
        "waypoints": [[0, 0, 0], [10, 0, 0], [20, 5, 0.2], [30, 5, 0.2]],
        "vehicle_state": {"width_m": 2.0, "min_turn_radius_m": 5.0},
        "constraints": {"road_width_m": 7.0, "safety_margin_m": 2.0},
    },
    "behavior_planning": {
        "scenario": {
            "type": "highway",
            "agents": [
                {"position": [0, 0], "heading": 0.0},
                {"position": [20, 1.5], "heading": 0.0},
            ],
            "speed_limit": 30.0,
            "weather": "clear",
            "road_type": "highway",
        },
        "predictions": [],
        "decision_logic": {"type": "lane_keep", "target_velocity": 25.0, "behavior": "lane_keep"},
    },
    "trajectory_optimization": {
        "trajectory": [
            [0.0, 0.0, 0.0, 10.0, 0.0],
            [1.0, 10.0, 0.0, 10.0, 0.0],
            [2.0, 20.0, 0.0, 10.0, 0.0],
            [3.0, 30.0, 0.0, 10.0, 0.0],
        ],
        "obstacles": [],
        "vehicle_params": {"max_acceleration_mps2": 3.0, "max_deceleration_mps2": -5.0, "max_speed_mps": 50.0},
    },
    # ------------------ testing (4) ------------------
    "test_case_design": {
        "module": "AEBController",
        "requirements": [
            {"id": "REQ-001", "description": "Activate AEB when TTC < 1.5s"},
            {"id": "REQ-002", "description": "Limit decel to 0.6g on dry road"},
        ],
        "count": 4,
    },
    "sil_test": {
        "test_type": "unit",
        "module": "perception_fusion",
        "test_vectors": [
            {"name": "TV-1", "input": {"value": 1.0}, "expected": {"status": "ok"}, "actual": {"status": "ok"}},
        ],
    },
    "hil_test": {
        "ecu_type": "AEB_ECU",
        "test_duration_s": 30.0,
        "fault_injection": False,
    },
    "regression_test": {
        "changed_modules": ["perception", "planning"],
        "release_notes": "Refactored fusion pipeline; bumped planner cost function.",
    },
    # ------------------ simulation (3) ------------------
    "scenario_generation": {
        "scenario_type": "highway",
        "parameters": {},
        "count": 3,
        "format": "openx",
    },
    "carla_runner": {
        "action": "launch",
        "simulation_params": {"version": "0.9.15", "map": "Town01", "fps": 20},
    },
    "edge_case": {
        "target_module": "perception",
        "method": "knowledge",
        "count": 3,
    },
    # ------------------ data (3) ------------------
    "log_analysis": {
        "log_data": "2026-06-05 10:00:00 INFO perception - frame processed\n2026-06-05 10:00:01 ERROR planning - timeout\n",
        "log_format": "text",
        "analysis_type": "full",
    },
    "data_pipeline_review": {
        "pipeline_config": {
            "name": "ros-bag-ingest",
            "stages": [
                {"name": "ingest", "type": "ingestion", "source": "s3://bags"},
                {"name": "transform", "type": "transformation", "transformations": ["crop"]},
                {"name": "validate", "type": "validation", "rules": ["schema"]},
            ],
        },
        "data_samples": [
            {"frame_id": "f1", "ts": 1.0, "objects": [1, 2, 3]},
        ],
    },
    "annotations_qc": {
        "annotations": [
            {"bbox": [0, 0, 10, 10], "category": "car", "confidence": 0.99},
            {"bbox": [20, 20, 40, 40], "category": "pedestrian", "confidence": 0.85},
        ],
        "task_type": "detection",
    },
    # ------------------ research (3) ------------------
    "paper_analysis": {
        "paper_content": (
            "Title: BEVFusion for Multi-Modal 3D Object Detection\n"
            "Author: Liu et al.\n"
            "Abstract: We propose BEVFusion, a unified framework for multi-modal\n"
            "3D object detection. We achieve state-of-the-art results on nuScenes.\n"
        ),
        "analysis_depth": "standard",
        "research_area": "perception",
    },
    "sota_tracking": {
        "tracking_tasks": ["detection", "tracking"],
        "benchmark": "all",
        "timeframe": "quarter",
        "max_results": 3,
    },
    "algorithm_comparison": {
        "algorithms": ["BEVFusion", "PointPillars", "CenterPoint"],
        "comparison_dimensions": ["performance", "efficiency", "robustness"],
    },
    # ------------------ devops (3) ------------------
    "cicd": {
        "action": "review_pipeline",
        "pipeline_config": {
            "name": "ad-ci",
            "stages": [
                {"name": "build", "type": "build", "script": "make", "cache": True, "timeout": 600},
                {"name": "test", "type": "test", "script": "make test", "timeout": 1200},
            ],
        },
        "repo_type": "github",
    },
    "deployment": {
        "action": "plan",
        "deployment_target": "vehicle-fleet-canary",
        "version": "v2.4.0",
        "environment": "staging",
    },
    "monitoring": {
        "action": "system_health",
        "metrics": {},
        "time_range": "1h",
        "alert_rules": [],
    },
}


# A few skills need to be skipped: they are placeholders that require real
# external services (e.g. a live CARLA instance) to do anything meaningful.
# The SAMPLE_INPUTS above are already "safe" for the regular code path, so
# the skip list should normally be empty. We keep the mechanism in place for
# future skills that need real hardware / network.
SKIP_SKILLS: Dict[str, str] = {
    # "carla_runner": "needs real CARLA simulator (external dependency)",
    # "hil_test": "needs real HIL hardware",
}


def get_all_skill_names() -> List[str]:
    """Return the names of all skills in the registry after auto-discover."""
    registry = SkillRegistry()
    registry.auto_discover()
    return [s.metadata.name for s in registry.get_all_skills()]


@pytest.fixture(scope="module")
def registry() -> SkillRegistry:
    """A single registry instance for the whole smoke test module."""
    reg = SkillRegistry()
    reg.auto_discover()
    return reg


def test_auto_discover_loads_at_least_30_skills(registry):
    """We expect 31 skills across 9 categories."""
    loaded = registry.get_all_skills()
    assert len(loaded) >= 30, (
        f"Only {len(loaded)} skills auto-discovered. "
        f"Expected at least 30. Names: {[s.metadata.name for s in loaded]}"
    )


def _all_skill_ids_for_parametrize() -> List[str]:
    """Return the parametrize id list, with skip markers handled."""
    reg = SkillRegistry()
    reg.auto_discover()
    return [s.metadata.name for s in reg.get_all_skills()]


@pytest.mark.parametrize("skill_name", _all_skill_ids_for_parametrize())
def test_skill_activates_and_executes_without_crashing(registry, skill_name):
    """For each registered skill, call activate() and execute() with a sample input.

    The skill should not raise. It may return success=True (most cases) or
    success=False (if the sample input is intentionally bad).
    """
    if skill_name in SKIP_SKILLS:
        pytest.skip(SKIP_SKILLS[skill_name])

    skill = registry.get_skill(skill_name)
    assert skill is not None, f"get_skill({skill_name!r}) returned None"

    # ``get_skill`` already auto-activates on lazy instantiation, but call
    # activate() explicitly so we exercise the documented lifecycle.
    skill.activate()

    sample_input = SAMPLE_INPUTS.get(skill_name, {})

    try:
        result = skill.execute(sample_input)
    except Exception as e:
        pytest.fail(
            f"Skill {skill_name!r} crashed on sample input. "
            f"Error: {type(e).__name__}: {e}. "
            f"Input was: {sample_input!r}"
        )

    assert isinstance(result, SkillResult), (
        f"Skill {skill_name!r} returned {type(result).__name__} instead of SkillResult"
    )
    assert isinstance(result.success, bool), (
        f"Skill {skill_name!r} returned non-boolean success: {result.success!r}"
    )

    skill.deactivate()


def test_all_skills_have_required_metadata(registry):
    """Every skill must have non-empty name, version, description, and category."""
    for skill in registry.get_all_skills():
        meta = skill.metadata
        assert meta.name and isinstance(meta.name, str), f"Empty name in {meta}"
        assert meta.version and isinstance(meta.version, str), f"Empty version in {meta.name}"
        assert meta.description and isinstance(meta.description, str), f"Empty description in {meta.name}"
        assert meta.category is not None, f"Missing category in {meta.name}"


def test_no_duplicate_skill_names(registry):
    """No two registered skills can have the same name (registry invariant)."""
    names = [s.metadata.name for s in registry.get_all_skills()]
    duplicates = set([n for n in names if names.count(n) > 1])
    assert not duplicates, f"Duplicate skill names: {duplicates}"


def test_skill_input_inventory_is_complete(registry):
    """Every discovered skill either has a SAMPLE_INPUTS entry or is in SKIP_SKILLS.

    If this test fails, the developer forgot to add a sample input for a new
    skill (or to skip it). Either is a legitimate action; the test exists to
    make the omission visible.
    """
    missing_inputs: List[str] = []
    for skill in registry.get_all_skills():
        name = skill.metadata.name
        if name in SKIP_SKILLS:
            continue
        if name not in SAMPLE_INPUTS:
            missing_inputs.append(name)
    assert not missing_inputs, (
        f"Skills discovered that have no SAMPLE_INPUTS entry and are not skipped: "
        f"{missing_inputs}. Add a SAMPLE_INPUTS entry or a SKIP_SKILLS entry."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
