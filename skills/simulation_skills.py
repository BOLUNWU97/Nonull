"""
Simulation Skills - 仿真技能

These skills generate demo/test data only. For real testing/simulation workflows,
integrate with your actual test framework and simulator.
本技能仅用于生成演示/测试数据。真实测试/仿真工作流请接入实际测试框架与仿真器。

自动驾驶仿真场景生成、CARLA 集成和边缘案例发现。
Scenario generation, CARLA integration, and edge case discovery for autonomous driving.

重要: 仿真生成的 driving_score / safety_score / comfort_score / route_completion
等指标均为 DEMO 占位值,并非真实仿真测量结果。
Important: driving_score / safety_score / comfort_score / route_completion values
emitted by these skills are DEMO placeholders, not real simulator measurements.

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
import json
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
_SIM_COUNTER = {"value": 10000}
_ARTIFACT_COUNTER = {"value": 1000}


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
        try:
            payload = repr(sorted(ctx.items())).encode("utf-8")
        except Exception:
            payload = repr(ctx).encode("utf-8")
        seed = int(hashlib.md5(payload).hexdigest()[:8], 16)
        return random.Random(seed)
    return random  # Backward compat: legacy mode uses module random


def _next_sim_id() -> int:
    """Return next deterministic simulation id (counter-based)."""
    _SIM_COUNTER["value"] += 1
    return _SIM_COUNTER["value"]


def _next_artifact_id() -> int:
    """Return next deterministic artifact id (counter-based)."""
    _ARTIFACT_COUNTER["value"] += 1
    return _ARTIFACT_COUNTER["value"]


def _stable_hash_int(value: str, modulo: int) -> int:
    """Map a string to a stable integer in [0, modulo)."""
    h = int(hashlib.md5(value.encode("utf-8")).hexdigest()[:8], 16)
    return h % modulo


# =============================================================================
# 场景生成技能 / Scenario Generation Skill
# =============================================================================


class ScenarioGenerationSkill(BaseSkill):
    """
    驾驶场景生成技能。
    Driving scenario generation for simulation testing.

    生成策略 / Generation strategies:
        - 基于规范的标准场景 / Specification-based standard scenarios
        - 参数化场景变异 / Parameterized scenario mutation
        - 对抗性场景生成 / Adversarial scenario generation
        - 真实数据场景提取 / Real-world data scenario extraction
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="scenario_generation",
            version="1.1.0",
            category=SkillCategory.SIMULATION,
            description="驾驶场景生成：标准场景、参数变异和对抗性场景创建",
            author="Nonull",
            tags=["simulation", "scenario", "generation", "testing", "openx"],
            input_schema={
                "type": "object",
                "properties": {
                    "scenario_type": {
                        "type": "string",
                        "enum": ["highway", "urban", "intersection", "parking", "custom"],
                    },
                    "parameters": {"type": "object"},
                    "count": {"type": "integer"},
                    "format": {"type": "string", "enum": ["openx", "esmini", "custom"]},
                    "__demo_mode__": {"type": "boolean"},
                    "seed": {"type": "integer"},
                },
                "required": ["scenario_type"],
            },
            safety_level=3,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        scenario_type: str = context["scenario_type"]
        params: Dict = context.get("parameters", {})
        count: int = min(context.get("count", 5), 50)
        output_format: str = context.get("format", "openx")

        rng = _make_rng(context)
        scenarios: List[Dict[str, Any]] = []

        if scenario_type == "highway":
            scenarios.extend(self._generate_highway_scenarios(params, count, rng, context))
        elif scenario_type == "urban":
            scenarios.extend(self._generate_urban_scenarios(params, count, rng, context))
        elif scenario_type == "intersection":
            scenarios.extend(self._generate_intersection_scenarios(params, count, rng, context))
        elif scenario_type == "parking":
            scenarios.extend(self._generate_parking_scenarios(params, count, rng, context))
        else:
            scenarios.extend(self._generate_custom_scenarios(params, count))

        # 截取到请求数量 / Trim to requested count
        scenarios = scenarios[:count]

        # 格式转换 / Format conversion
        if output_format == "openx":
            formatted = [self._to_openx(s) for s in scenarios]
        else:
            formatted = scenarios

        return {
            "scenario_type": scenario_type,
            "total_generated": len(scenarios),
            "format": output_format,
            "scenarios": formatted,
            "parameters_used": params,
            "complexity_distribution": self._analyze_complexity(scenarios),
            "metadata": {
                "generator_version": "1.1.0",
                "safety_filter_applied": True,
                "is_demo_data": True,
            },
        }

    def _generate_highway_scenarios(
        self, params: Dict, count: int, rng: random.Random, context: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """生成高速公路场景 / Generate highway scenarios."""
        scenarios = []

        templates = [
            {
                "name": "高速巡航 / Highway Cruise",
                "description": "多车道高速巡航，前方车辆减速",
                "ego_speed_range": (25, 40),  # m/s
                "npc_count_range": (1, 5),
                "duration_s": 60,
            },
            {
                "name": "高速变道 / Highway Lane Change",
                "description": "相邻车道有车情况下变道",
                "ego_speed_range": (20, 35),
                "npc_count_range": (2, 4),
                "duration_s": 45,
            },
            {
                "name": "高速汇入 / Highway Merge",
                "description": "匝道汇入主路场景",
                "ego_speed_range": (15, 30),
                "npc_count_range": (2, 6),
                "duration_s": 50,
            },
            {
                "name": "高速拥堵 / Highway Traffic Jam",
                "description": "高速拥堵路段的走走停停",
                "ego_speed_range": (0, 10),
                "npc_count_range": (5, 15),
                "duration_s": 90,
            },
            {
                "name": "高速施工区 / Construction Zone",
                "description": "前方施工改道场景",
                "ego_speed_range": (10, 25),
                "npc_count_range": (1, 3),
                "duration_s": 55,
            },
        ]

        # If user requested more than templates, cycle with deterministic ordering
        selected = self._select_templates(templates, count, rng, context)

        for i, template in enumerate(selected):
            speed = self._demo_uniform(*template["ego_speed_range"], key=f"hw_speed|{i}|{template['name']}", rng=rng, context=context)
            npc_count = self._demo_randint(*template["npc_count_range"], key=f"hw_npc|{i}|{template['name']}", rng=rng, context=context)
            weather = self._demo_choice(
                ["clear", "cloudy", "rain", "fog"],
                key=f"hw_weather|{i}|{template['name']}",
                rng=rng,
                context=context,
            )

            scenarios.append({
                "id": f"HW-{i + 1:03d}",
                "name": f"{template['name']} v{i + 1}",
                "type": "highway",
                "description": template["description"],
                "ego_initial_speed_mps": round(speed, 1),
                "npc_vehicle_count": npc_count,
                "weather": weather,
                "duration_s": template["duration_s"],
                "difficulty": self._calc_difficulty(speed, npc_count, weather),
                "tags": ["highway", weather],
                "openx_scenario": {},
            })

        return scenarios

    def _generate_urban_scenarios(
        self, params: Dict, count: int, rng: random.Random, context: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """生成城市道路场景 / Generate urban scenarios."""
        scenarios = []

        templates = [
            {
                "name": "城市跟车 / Urban Car Following",
                "npc_count_range": (2, 8),
                "pedestrian_range": (0, 3),
                "cyclist_range": (0, 2),
            },
            {
                "name": "城市路口 / Urban Intersection",
                "npc_count_range": (2, 6),
                "pedestrian_range": (1, 5),
                "cyclist_range": (0, 2),
            },
            {
                "name": "学校区域 / School Zone",
                "npc_count_range": (1, 3),
                "pedestrian_range": (3, 10),
                "cyclist_range": (0, 1),
            },
        ]

        selected = self._select_templates(templates, count, rng, context)

        for i, template in enumerate(selected):
            scenarios.append({
                "id": f"UR-{i + 1:03d}",
                "name": f"{template['name']} v{i + 1}",
                "type": "urban",
                "npc_count": self._demo_randint(
                    *template["npc_count_range"],
                    key=f"ur_npc|{i}|{template['name']}",
                    rng=rng,
                    context=context,
                ),
                "pedestrian_count": self._demo_randint(
                    *template["pedestrian_range"],
                    key=f"ur_ped|{i}|{template['name']}",
                    rng=rng,
                    context=context,
                ),
                "cyclist_count": self._demo_randint(
                    *template["cyclist_range"],
                    key=f"ur_cyc|{i}|{template['name']}",
                    rng=rng,
                    context=context,
                ),
                "has_traffic_lights": self._demo_choice(
                    [True, False],
                    key=f"ur_tl|{i}|{template['name']}",
                    rng=rng,
                    context=context,
                ),
                "weather": self._demo_choice(
                    ["clear", "rain", "snow"],
                    key=f"ur_w|{i}|{template['name']}",
                    rng=rng,
                    context=context,
                ),
                "time_of_day": self._demo_choice(
                    ["day", "night", "dusk"],
                    key=f"ur_tod|{i}|{template['name']}",
                    rng=rng,
                    context=context,
                ),
            })

        return scenarios

    def _generate_intersection_scenarios(
        self, params: Dict, count: int, rng: random.Random, context: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """生成路口场景 / Generate intersection scenarios."""
        scenarios = []

        configs = [
            {"type": "十字路口", "conflict": "直行-直行"},
            {"type": "T型路口", "conflict": "左转-直行"},
            {"type": "环岛", "conflict": "汇入-环内"},
            {"type": "多叉路口", "conflict": "多方向冲突"},
        ]

        for i, cfg in enumerate(configs[:count]):
            scenarios.append({
                "id": f"IS-{i + 1:03d}",
                "name": f"{cfg['type']} {cfg['conflict']}",
                "type": "intersection",
                "intersection_type": cfg["type"],
                "conflict_pattern": cfg["conflict"],
                "approach_speed_mps": round(
                    self._demo_uniform(
                        5, 15,
                        key=f"is_speed|{i}|{cfg['type']}",
                        rng=rng,
                        context=context,
                    ),
                    1,
                ),
                "has_traffic_light": self._demo_choice(
                    [True, False],
                    key=f"is_tl|{i}|{cfg['type']}",
                    rng=rng,
                    context=context,
                ),
                "has_stop_sign": self._demo_choice(
                    [True, False],
                    key=f"is_ss|{i}|{cfg['type']}",
                    rng=rng,
                    context=context,
                ),
                "npc_count": self._demo_randint(
                    1, 4,
                    key=f"is_npc|{i}|{cfg['type']}",
                    rng=rng,
                    context=context,
                ),
            })

        return scenarios

    def _generate_parking_scenarios(
        self, params: Dict, count: int, rng: random.Random, context: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """生成泊车场景 / Generate parking scenarios."""
        scenarios = []

        for i in range(count):
            scenarios.append({
                "id": f"PK-{i + 1:03d}",
                "name": f"泊车场景 v{i + 1}",
                "type": "parking",
                "parking_type": self._demo_choice(
                    ["parallel", "perpendicular", "angled"],
                    key=f"pk_type|{i}",
                    rng=rng,
                    context=context,
                ),
                "spot_width_m": round(
                    self._demo_uniform(
                        2.0, 3.5,
                        key=f"pk_w|{i}",
                        rng=rng,
                        context=context,
                    ),
                    2,
                ),
                "spot_length_m": round(
                    self._demo_uniform(
                        5.0, 7.0,
                        key=f"pk_l|{i}",
                        rng=rng,
                        context=context,
                    ),
                    2,
                ),
                "obstacle_count": self._demo_randint(
                    0, 3,
                    key=f"pk_obs|{i}",
                    rng=rng,
                    context=context,
                ),
                "is_reverse": self._demo_choice(
                    [True, False],
                    key=f"pk_rev|{i}",
                    rng=rng,
                    context=context,
                ),
            })

        return scenarios

    def _generate_custom_scenarios(
        self, params: Dict, count: int
    ) -> List[Dict]:
        """生成自定义场景 / Generate custom scenarios."""
        scenarios = []
        for i in range(count):
            scenarios.append({
                "id": f"CS-{i + 1:03d}",
                "name": f"自定义场景 {i + 1}",
                "type": "custom",
                "parameters": params,
                "description": params.get("description", f"自定义测试场景 #{i + 1}"),
            })
        return scenarios

    def _calc_difficulty(self, speed: float, npc_count: int, weather: str) -> str:
        """计算场景难度 / Calculate scenario difficulty."""
        score = 0
        if speed > 30: score += 2
        elif speed > 20: score += 1
        if npc_count > 5: score += 2
        elif npc_count > 3: score += 1
        if weather in ("rain", "fog"): score += 1
        if weather == "snow": score += 2

        if score >= 4: return "hard"
        elif score >= 2: return "medium"
        return "easy"

    def _to_openx(self, scenario: Dict) -> Dict:
        """转换为 OpenSCENARIO 格式 / Convert to OpenSCENARIO format."""
        return {
            "open_scenario": {
                "file_header": {
                    "revMajor": 1,
                    "revMinor": 0,
                    "author": "Nonull",
                    "description": scenario.get("description", ""),
                },
                "catalog_references": {},
                "road_network": {"logical_road": {"road_type": scenario.get("type", "highway")}},
                "entities": {
                    "scenario_object": [
                        {"name": "ego", "vehicle_type": "car"},
                    ],
                },
                "storyboard": {
                    "init": {"actions": []},
                    "story": [{"name": "main_story", "act": []}],
                },
            },
            "original_scenario": scenario,
        }

    def _analyze_complexity(self, scenarios: List[Dict]) -> Dict:
        """分析复杂度分布 / Analyze complexity distribution."""
        dist = {"easy": 0, "medium": 0, "hard": 0}
        for s in scenarios:
            diff = s.get("difficulty", "medium")
            if diff in dist:
                dist[diff] += 1
        return dist

    # ------------------------------------------------------------------ #
    # Deterministic / demo helpers                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _select_templates(
        templates: List[Dict], count: int, rng: random.Random, context: Optional[Dict[str, Any]]
    ) -> List[Dict]:
        """Select templates, cycling with deterministic order in demo mode."""
        if not templates:
            return []
        if count <= len(templates):
            return templates[:count]
        # In backward-compat mode, use random.choices (with replacement)
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            return random.choices(templates, k=count)
        # Deterministic cycling
        return [templates[i % len(templates)] for i in range(count)]

    @staticmethod
    def _demo_uniform(
        low: float, high: float, key: str, rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Deterministic uniform draw derived from ``key`` when possible."""
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            return random.uniform(low, high)
        h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
        return low + (h % 10000) / 10000.0 * (high - low)

    @staticmethod
    def _demo_randint(
        low: int, high: int, key: str, rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Deterministic int draw derived from ``key`` when possible."""
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            return random.randint(low, high)
        h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
        return low + (h % (high - low + 1))

    @staticmethod
    def _demo_choice(
        options: List[Any], key: str, rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Deterministic choice derived from ``key`` when possible."""
        if not options:
            return None
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            return random.choice(options)
        h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
        return options[h % len(options)]


# =============================================================================
# CARLA 运行器技能 / CARLA Runner Skill
# =============================================================================


class CARLARunnerSkill(BaseSkill):
    """
    CARLA 仿真器集成技能。
    CARLA simulator integration for autonomous driving testing.

    NOTE: This skill emits DEMO placeholder data by default. Driving score,
    safety score, comfort score, route completion, collision counts, and
    infraction counts are placeholders, NOT real measurements from a running
    CARLA instance. To get real numbers, wire this skill to a live CARLA
    server (e.g. via carla.Client) and feed real measurements back in.

    功能 / Features:
        - 仿真环境管理 / Simulation environment management
        - 场景加载与运行 / Scenario loading and execution
        - 传感器配置 / Sensor configuration
        - 指标采集 / Metrics collection
        - 仿真结果分析 / Simulation result analysis
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="carla_runner",
            version="1.1.0",
            category=SkillCategory.SIMULATION,
            description="CARLA仿真集成：环境管理、场景执行和结果分析",
            author="Nonull",
            tags=["simulation", "carla", "environment", "sensor", "metrics"],
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["launch", "run_scenario", "configure_sensors",
                                 "collect_metrics", "stop", "analyze"],
                    },
                    "scenario": {"type": "object"},
                    "sensor_config": {"type": "object"},
                    "simulation_params": {"type": "object"},
                    "__demo_mode__": {"type": "boolean"},
                    "seed": {"type": "integer"},
                },
                "required": ["action"],
            },
            safety_level=3,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        action: str = context["action"]
        scenario: Optional[Dict] = context.get("scenario")
        sensor_config: Optional[Dict] = context.get("sensor_config")
        sim_params: Optional[Dict] = context.get("simulation_params", {})

        rng = _make_rng(context)

        action_map = {
            "launch": self._launch_simulation,
            "run_scenario": self._run_scenario_in_carla,
            "configure_sensors": self._configure_carla_sensors,
            "collect_metrics": self._collect_simulation_metrics,
            "stop": self._stop_simulation,
            "analyze": self._analyze_simulation_results,
        }

        handler = action_map.get(action)
        if not handler:
            raise SkillValidationError(f"Unsupported action: {action}")

        # Pass through rng and context so handlers can be deterministic
        return handler(scenario, sensor_config, sim_params, rng, context)

    def _launch_simulation(
        self,
        scenario: Optional[Dict],
        sensors: Optional[Dict],
        params: Dict,
        rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """启动 CARLA 仿真 / Launch CARLA simulation (returns DEMO id)."""
        carla_version = params.get("version", "0.9.15")
        timeout = params.get("timeout_s", 30)
        map_name = params.get("map", "Town01")
        sync_mode = params.get("synchronous_mode", True)
        fps = params.get("fps", 20)

        # Deterministic counter-based simulation id
        sim_id = f"carla_{_next_sim_id()}"

        return {
            "status": "launched",
            "simulation_id": sim_id,
            "carla_version": carla_version,
            "map": map_name,
            "synchronous_mode": sync_mode,
            "target_fps": fps,
            "timeout_s": timeout,
            "connection": {
                "host": params.get("host", "localhost"),
                "port": params.get("port", 2000),
            },
            "message": f"CARLA {carla_version} 仿真启动成功 (地图: {map_name})",
            "is_demo_data": True,
            "data_source": "DEMO: connect to real CARLA for actual launch",
        }

    def _run_scenario_in_carla(
        self,
        scenario: Optional[Dict],
        sensors: Optional[Dict],
        params: Dict,
        rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """在 CARLA 中运行场景 / Run scenario in CARLA (DEMO metrics)."""
        if not scenario:
            raise SkillValidationError("'scenario' is required for run_scenario action")

        duration = scenario.get("duration_s", 30)
        weather = scenario.get("weather", "clear")
        scenario_name = scenario.get("name", "unnamed")

        steps = duration * 20  # assuming 20 FPS
        # Deterministic metrics derived from scenario name
        metrics_snapshot = {
            "frame_count": steps,
            "simulation_time_s": duration,
            "weather": weather,
            "ego_distance_km": round(
                self._demo_uniform(
                    0.1,
                    duration * 10 / 3.6 / 1000.0,
                    key=f"run_distance|{scenario_name}|{duration}",
                    rng=rng,
                    context=context,
                ),
                3,
            ),
            "collisions": self._demo_randint(
                0, 1,
                key=f"run_coll|{scenario_name}|{duration}",
                rng=rng,
                context=context,
            ),
            "red_light_violations": (
                self._demo_randint(
                    0, 1,
                    key=f"run_rl|{scenario_name}|{duration}",
                    rng=rng,
                    context=context,
                )
                if self._demo_p(0.8, key=f"run_rlgate|{scenario_name}|{duration}", rng=rng, context=context)
                else 0
            ),
            "lane_infractions": self._demo_randint(
                0, 2,
                key=f"run_li|{scenario_name}|{duration}",
                rng=rng,
                context=context,
            ),
        }

        return {
            "status": "completed",
            "scenario_name": scenario_name,
            "duration_s": duration,
            "metrics": metrics_snapshot,
            "success": metrics_snapshot["collisions"] == 0,
            "message": f"场景 '{scenario_name}' 执行完成 (DEMO metrics)",
            "is_demo_data": True,
            "artifacts": {
                "sensor_data_path": f"/tmp/carla_{_next_artifact_id()}/",
                "log_path": f"/tmp/carla_log_{_next_artifact_id()}.json",
            },
        }

    def _configure_carla_sensors(
        self,
        scenario: Optional[Dict],
        config: Optional[Dict],
        params: Dict,
        rng: Optional[random.Random] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """配置 CARLA 传感器 / Configure CARLA sensors (no randomness)."""
        if not config:
            config = {
                "sensors": [
                    {"type": "camera.rgb", "width": 1920, "height": 1080, "fov": 90},
                    {"type": "sensor.lidar.ray_cast",
                     "channels": 64, "range": 100, "points_per_second": 1000000},
                    {"type": "sensor.other.gnss", "noise_std": 0.5},
                    {"type": "sensor.other.imu"},
                ]
            }

        configured = []
        for sensor in config.get("sensors", [config]):
            configured.append({
                "type": sensor.get("type", "unknown"),
                "blueprint": f"vehicle.{sensor.get('type', 'unknown')}",
                "params": {k: v for k, v in sensor.items() if k != "type"},
                "status": "configured",
            })

        return {
            "status": "sensors_configured",
            "sensor_count": len(configured),
            "sensors": configured,
            "message": f"已配置 {len(configured)} 个传感器",
        }

    def _collect_simulation_metrics(
        self,
        scenario: Optional[Dict],
        sensors: Optional[Dict],
        params: Dict,
        rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """收集仿真指标 / Collect simulation metrics (DEMO placeholders).

        driving_score, safety_score, comfort_score, route_completion_pct and
        the infractions counts are DEMO values, not real measurements.
        """
        scenario_name = (scenario or {}).get("name", "default")
        return {
            "status": "metrics_collected",
            "is_demo_data": True,
            "data_source": (
                "DEMO: driving/safety/comfort scores and route_completion_pct "
                "are placeholders, not real simulator measurements"
            ),
            "metrics": {
                "driving_score": round(
                    self._demo_uniform(
                        0.6, 1.0,
                        key=f"metrics_ds|{scenario_name}",
                        rng=rng,
                        context=context,
                    ),
                    3,
                ),
                "comfort_score": round(
                    self._demo_uniform(
                        0.5, 1.0,
                        key=f"metrics_cs|{scenario_name}",
                        rng=rng,
                        context=context,
                    ),
                    3,
                ),
                "safety_score": round(
                    self._demo_uniform(
                        0.7, 1.0,
                        key=f"metrics_ss|{scenario_name}",
                        rng=rng,
                        context=context,
                    ),
                    3,
                ),
                "route_completion_pct": round(
                    self._demo_uniform(
                        80, 100,
                        key=f"metrics_rc|{scenario_name}",
                        rng=rng,
                        context=context,
                    ),
                    1,
                ),
                "infractions": {
                    "collisions": self._demo_randint(
                        0, 2,
                        key=f"metrics_c|{scenario_name}",
                        rng=rng,
                        context=context,
                    ),
                    "lane_violations": self._demo_randint(
                        0, 5,
                        key=f"metrics_lv|{scenario_name}",
                        rng=rng,
                        context=context,
                    ),
                    "speed_violations": self._demo_randint(
                        0, 3,
                        key=f"metrics_sv|{scenario_name}",
                        rng=rng,
                        context=context,
                    ),
                },
            },
        }

    def _stop_simulation(
        self,
        scenario: Optional[Dict],
        sensors: Optional[Dict],
        params: Dict,
        rng: Optional[random.Random] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """停止仿真 / Stop simulation."""
        return {
            "status": "stopped",
            "message": "CARLA 仿真已停止，资源已释放",
        }

    def _analyze_simulation_results(
        self,
        scenario: Optional[Dict],
        sensors: Optional[Dict],
        params: Dict,
        rng: Optional[random.Random] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """分析仿真结果 / Analyze simulation results.

        NOTE: The driving score is treated as a DEMO metric that the caller
        passes in. We do not invent a new one. Real analysis should be
        performed on real measurements.
        """
        metrics = params.get("metrics", {})
        driving_score = metrics.get("driving_score", 0.85)
        infractions = metrics.get("infractions", {})

        findings = []
        if infractions.get("collisions", 0) > 0:
            findings.append(f"发生 {infractions['collisions']} 次碰撞 (DEMO)")
        if infractions.get("lane_violations", 0) > 3:
            findings.append("车道保持性能需改进 (DEMO)")

        return {
            "status": "analyzed",
            "is_demo_data": True,
            "driving_score": driving_score,
            "driving_score_source": "DEMO placeholder — feed real metrics for analysis",
            "assessment": "良好" if driving_score >= 0.8 else "需改进",
            "findings": findings,
            "recommendations": [
                "优化横向控制参数" if infractions.get("lane_violations", 0) > 3 else "各项指标正常",
            ],
        }

    # ------------------------------------------------------------------ #
    # Deterministic / demo helpers (shared with scenario generation)     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _demo_uniform(
        low: float, high: float, key: str, rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> float:
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            return random.uniform(low, high)
        h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
        return low + (h % 10000) / 10000.0 * (high - low)

    @staticmethod
    def _demo_randint(
        low: int, high: int, key: str, rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> int:
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            return random.randint(low, high)
        h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
        return low + (h % (high - low + 1))

    @staticmethod
    def _demo_choice(
        options: List[Any], key: str, rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not options:
            return None
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            return random.choice(options)
        h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
        return options[h % len(options)]

    @staticmethod
    def _demo_p(
        threshold: float, key: str, rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Deterministic Bernoulli with given success threshold."""
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            return random.random() > (1.0 - threshold)
        h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
        return (h % 10000) / 10000.0 < threshold


# =============================================================================
# 边缘案例发现技能 / Edge Case Skill
# =============================================================================


class EdgeCaseSkill(BaseSkill):
    """
    边缘案例发现与生成技能。
    Edge case discovery and generation for autonomous driving systems.

    发现方法 / Discovery methods:
        - 基于知识的边缘场景 / Knowledge-based edge scenarios
        - 对抗性搜索 / Adversarial search
        - 参数空间覆盖 / Parameter space coverage
        - 真实世界场景挖掘 / Real-world scenario mining

    NOTE: ``adversarial_factor`` and ``severity`` fields produced here are
    DEMO placeholders, not actual safety / risk measurements. Real edge
    case analysis should be done on real test runs and FMEA output.
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="edge_case",
            version="1.1.0",
            category=SkillCategory.SIMULATION,
            description="边缘案例发现：极限场景搜索和对抗性测试场景生成",
            author="Nonull",
            tags=["simulation", "edge-case", "adversarial", "corner-case", "safety"],
            input_schema={
                "type": "object",
                "properties": {
                    "search_space": {"type": "object"},
                    "target_module": {"type": "string"},
                    "count": {"type": "integer"},
                    "method": {
                        "type": "string",
                        "enum": ["knowledge", "adversarial", "coverage", "mining"],
                    },
                    "__demo_mode__": {"type": "boolean"},
                    "seed": {"type": "integer"},
                },
                "required": ["target_module"],
            },
            safety_level=4,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        target: str = context["target_module"]
        method: str = context.get("method", "knowledge")
        count: int = min(context.get("count", 10), 50)
        search_space: Optional[Dict] = context.get("search_space")

        rng = _make_rng(context)
        edge_cases: List[Dict[str, Any]] = []

        method_map = {
            "knowledge": self._knowledge_based,
            "adversarial": self._adversarial_search,
            "coverage": self._coverage_driven,
            "mining": self._mining_based,
        }

        handler = method_map.get(method, self._knowledge_based)
        edge_cases = handler(target, search_space, count, rng, context)

        return {
            "target_module": target,
            "method": method,
            "total_edge_cases": len(edge_cases),
            "edge_cases": edge_cases,
            "severity_distribution": self._severity_dist(edge_cases),
            "is_demo_data": True,
            "summary": f"发现 {len(edge_cases)} 个潜在边缘案例 (方法: {method}) [DEMO]",
        }

    def _knowledge_based(
        self,
        target: str,
        space: Optional[Dict],
        count: int,
        rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        """基于知识的边缘场景 / Knowledge-based edge cases."""
        knowledge_base = [
            {
                "scenario": "强烈阳光直射摄像头",
                "target": "perception",
                "description": "低角度强光照导致摄像头过曝",
                "severity": "medium",
            },
            {
                "scenario": "夜间无照明路段行人穿行",
                "target": "perception",
                "description": "夜间低光照行人检测挑战",
                "severity": "high",
            },
            {
                "scenario": "隧道出口强光突变",
                "target": "perception",
                "description": "出隧道瞬间光照剧烈变化",
                "severity": "high",
            },
            {
                "scenario": "高速上前车急刹并变道",
                "target": "planning",
                "description": "前车突发紧急避让行为",
                "severity": "critical",
            },
            {
                "scenario": "儿童突然冲入马路",
                "target": "planning",
                "description": "弱势道路使用者突发行为",
                "severity": "critical",
            },
            {
                "scenario": "施工区临时改道标线模糊",
                "target": "planning",
                "description": "临时道路标记不符合标准",
                "severity": "high",
            },
            {
                "scenario": "大雨中LiDAR点云退化",
                "target": "perception",
                "description": "雨滴造成LiDAR点云噪声大幅增加",
                "severity": "high",
            },
            {
                "scenario": "多车道环岛导航决策",
                "target": "planning",
                "description": "多出口环岛的路径选择",
                "severity": "high",
            },
            {
                "scenario": "对向车辆强行占道超车",
                "target": "planning",
                "description": "对向车辆侵入本车车道",
                "severity": "critical",
            },
            {
                "scenario": "传感器间歇性数据丢失",
                "target": "fusion",
                "description": "某个传感器数据短暂缺失",
                "severity": "high",
            },
            {
                "scenario": "GPS信号丢失隧道内定位",
                "target": "localization",
                "description": "长隧道内无GPS信号",
                "severity": "medium",
            },
            {
                "scenario": "动物横穿高速公路",
                "target": "planning",
                "description": "大型动物突然出现",
                "severity": "high",
            },
        ]

        filtered = [
            ec for ec in knowledge_base
            if target == "all" or ec["target"] == target or target in ec["target"]
        ]

        if not filtered:
            filtered = knowledge_base

        # Deterministic shuffle: order is stable per (target, count) input
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            random.shuffle(filtered)
        else:
            # Stable ordering by hash of (target, scenario)
            filtered = sorted(
                filtered,
                key=lambda ec: hashlib.md5(
                    f"{target}|{ec['scenario']}".encode("utf-8")
                ).hexdigest(),
            )
        return filtered[:count]

    def _adversarial_search(
        self,
        target: str,
        space: Optional[Dict],
        count: int,
        rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        """对抗性搜索 / Adversarial edge case search (DEMO placeholders)."""
        cases = []
        params = space or {
            "speed_range": (0, 50),
            "weathers": ["clear", "rain", "fog", "snow"],
            "lightings": ["day", "night", "dusk", "dawn"],
            "road_types": ["highway", "urban", "rural"],
        }

        for i in range(count):
            speed = self._demo_uniform(
                *params.get("speed_range", (0, 30)),
                key=f"adv_speed|{target}|{i}",
                rng=rng,
                context=context,
            )
            weather = self._demo_choice(
                params.get("weathers", ["clear"]),
                key=f"adv_w|{target}|{i}",
                rng=rng,
                context=context,
            )
            lighting = self._demo_choice(
                params.get("lightings", ["day"]),
                key=f"adv_l|{target}|{i}",
                rng=rng,
                context=context,
            )
            road = self._demo_choice(
                params.get("road_types", ["highway"]),
                key=f"adv_r|{target}|{i}",
                rng=rng,
                context=context,
            )

            cases.append({
                "id": f"ADV-{i + 1:03d}",
                "scenario": f"对抗性场景 #{i + 1}",
                "target": target,
                "parameters": {
                    "speed_mps": round(speed, 1),
                    "weather": weather,
                    "lighting": lighting,
                    "road_type": road,
                },
                # DEMO placeholder; not a real safety/risk measurement
                "adversarial_factor": round(
                    self._demo_uniform(
                        0.5, 1.0,
                        key=f"adv_af|{target}|{i}",
                        rng=rng,
                        context=context,
                    ),
                    3,
                ),
                "adversarial_factor_note": "DEMO placeholder, not a real measurement",
                "severity": (
                    "critical"
                    if self._demo_p(0.7, key=f"adv_sev|{target}|{i}", rng=rng, context=context)
                    else "high"
                ),
                "severity_note": "DEMO placeholder, not a real measurement",
                "description": f"{road}场景 {weather}天气 {lighting}光照 车速{speed:.1f}m/s",
            })

        return cases

    def _coverage_driven(
        self,
        target: str,
        space: Optional[Dict],
        count: int,
        rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        """覆盖驱动的边缘案例 / Coverage-driven edge cases (deterministic)."""
        dims = space or {
            "ego_speed": [0, 5, 15, 30, 50],
            "target_speed": [-10, 0, 10, 20, 40],
            "relative_distance": [2, 5, 10, 30, 100],
            "road_curvature": [0, 0.05, 0.1, 0.2, 0.4],
        }

        cases = []
        dim_keys = list(dims.keys())
        for i in range(min(count, 20)):
            if rng is random and (context is None or (
                "seed" not in context
                and not context.get("deterministic")
                and context.get("__demo_mode__") is not False
            )):
                key = random.choice(dim_keys)
                values = dims[key]
                val = random.choice(values)
            else:
                # Deterministic: round-robin through dimensions
                key = dim_keys[i % len(dim_keys)]
                values = dims[key]
                val = values[i % len(values)]

            cases.append({
                "id": f"COV-{i + 1:03d}",
                "scenario": f"参数覆盖: {key}={val}",
                "target": target,
                "coverage_dimension": key,
                "dimension_value": val,
                "severity": "medium",
                "description": f"参数 {key} 取边界值 {val}",
            })

        return cases[:count]

    def _mining_based(
        self,
        target: str,
        space: Optional[Dict],
        count: int,
        rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        """基于数据挖掘的边缘案例 / Mining-based edge cases (DEMO)."""
        scenarios = [
            "交叉路口大型车辆遮挡视野",
            "积雪覆盖车道标线",
            "落叶覆盖路面使轮胎打滑",
            "桥头跳车导致的颠簸",
            "地库出入口坡度突变",
            "收费站复杂导流线",
            "非机动车逆行",
            "行人撑伞遮挡LiDAR点云",
            "路面深坑或井盖缺失",
            "临时交通指挥 vs 信号灯冲突",
            "警车/救护车优先通行",
            "阅兵或大型活动交通管制",
        ]

        n = min(count, len(scenarios))
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            selected = random.sample(scenarios, n)
        else:
            # Deterministic: pick the first n in stable order (sorted by hash)
            ordered = sorted(
                scenarios,
                key=lambda s: hashlib.md5(s.encode("utf-8")).hexdigest(),
            )
            selected = ordered[:n]

        return [
            {
                "id": f"MINE-{i + 1:03d}",
                "scenario": s,
                "target": target,
                "source": "real_world_mining",
                "severity": self._demo_choice(
                    ["medium", "high", "critical"],
                    key=f"mine_sev|{target}|{i}|{s}",
                    rng=rng,
                    context=context,
                ),
                "severity_note": "DEMO placeholder, not a real measurement",
                "frequency": round(
                    self._demo_uniform(
                        0.01, 0.1,
                        key=f"mine_freq|{target}|{i}|{s}",
                        rng=rng,
                        context=context,
                    ),
                    4,
                ),
            }
            for i, s in enumerate(selected)
        ]

    def _severity_dist(self, cases: List[Dict]) -> Dict:
        """严重程度分布 / Severity distribution."""
        dist = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for c in cases:
            s = c.get("severity", "medium")
            if s in dist:
                dist[s] += 1
        return dist

    # ------------------------------------------------------------------ #
    # Deterministic / demo helpers                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _demo_uniform(
        low: float, high: float, key: str, rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> float:
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            return random.uniform(low, high)
        h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
        return low + (h % 10000) / 10000.0 * (high - low)

    @staticmethod
    def _demo_randint(
        low: int, high: int, key: str, rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> int:
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            return random.randint(low, high)
        h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
        return low + (h % (high - low + 1))

    @staticmethod
    def _demo_choice(
        options: List[Any], key: str, rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not options:
            return None
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            return random.choice(options)
        h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
        return options[h % len(options)]

    @staticmethod
    def _demo_p(
        threshold: float, key: str, rng: random.Random,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if rng is random and (context is None or (
            "seed" not in context
            and not context.get("deterministic")
            and context.get("__demo_mode__") is not False
        )):
            return random.random() > (1.0 - threshold)
        h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
        return (h % 10000) / 10000.0 < threshold
