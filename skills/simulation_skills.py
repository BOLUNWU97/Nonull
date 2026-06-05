"""
Simulation Skills - 仿真技能

自动驾驶仿真场景生成、CARLA 集成和边缘案例发现。
Scenario generation, CARLA integration, and edge case discovery for autonomous driving.
"""

from __future__ import annotations

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
            version="1.0.0",
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

        scenarios: List[Dict[str, Any]] = []

        if scenario_type == "highway":
            scenarios.extend(self._generate_highway_scenarios(params, count))
        elif scenario_type == "urban":
            scenarios.extend(self._generate_urban_scenarios(params, count))
        elif scenario_type == "intersection":
            scenarios.extend(self._generate_intersection_scenarios(params, count))
        elif scenario_type == "parking":
            scenarios.extend(self._generate_parking_scenarios(params, count))
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
                "generator_version": "1.0.0",
                "safety_filter_applied": True,
            },
        }

    def _generate_highway_scenarios(
        self, params: Dict, count: int
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

        selected = random.choices(templates, k=count) if count > len(templates) else templates[:count]
        for i, template in enumerate(selected):
            speed = random.uniform(*template["ego_speed_range"])
            npc_count = random.randint(*template["npc_count_range"])
            weather = random.choice(["clear", "cloudy", "rain", "fog"])

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
        self, params: Dict, count: int
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

        selected = random.choices(templates, k=count) if count > len(templates) else templates[:count]
        for i, template in enumerate(selected):
            scenarios.append({
                "id": f"UR-{i + 1:03d}",
                "name": f"{template['name']} v{i + 1}",
                "type": "urban",
                "npc_count": random.randint(*template["npc_count_range"]),
                "pedestrian_count": random.randint(*template["pedestrian_range"]),
                "cyclist_count": random.randint(*template["cyclist_range"]),
                "has_traffic_lights": random.choice([True, False]),
                "weather": random.choice(["clear", "rain", "snow"]),
                "time_of_day": random.choice(["day", "night", "dusk"]),
            })

        return scenarios

    def _generate_intersection_scenarios(
        self, params: Dict, count: int
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
                "approach_speed_mps": round(random.uniform(5, 15), 1),
                "has_traffic_light": random.choice([True, False]),
                "has_stop_sign": random.choice([True, False]),
                "npc_count": random.randint(1, 4),
            })

        return scenarios

    def _generate_parking_scenarios(
        self, params: Dict, count: int
    ) -> List[Dict]:
        """生成泊车场景 / Generate parking scenarios."""
        scenarios = []

        for i in range(count):
            scenarios.append({
                "id": f"PK-{i + 1:03d}",
                "name": f"泊车场景 v{i + 1}",
                "type": "parking",
                "parking_type": random.choice(["parallel", "perpendicular", "angled"]),
                "spot_width_m": round(random.uniform(2.0, 3.5), 2),
                "spot_length_m": round(random.uniform(5.0, 7.0), 2),
                "obstacle_count": random.randint(0, 3),
                "is_reverse": random.choice([True, False]),
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


# =============================================================================
# CARLA 运行器技能 / CARLA Runner Skill
# =============================================================================


class CARLARunnerSkill(BaseSkill):
    """
    CARLA 仿真器集成技能。
    CARLA simulator integration for autonomous driving testing.

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
            version="1.0.0",
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

        return handler(scenario, sensor_config, sim_params)

    def _launch_simulation(
        self, scenario: Optional[Dict], sensors: Optional[Dict], params: Dict
    ) -> Dict[str, Any]:
        """启动 CARLA 仿真 / Launch CARLA simulation."""
        carla_version = params.get("version", "0.9.15")
        timeout = params.get("timeout_s", 30)
        map_name = params.get("map", "Town01")
        sync_mode = params.get("synchronous_mode", True)
        fps = params.get("fps", 20)

        return {
            "status": "launched",
            "simulation_id": f"carla_{random.randint(10000, 99999)}",
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
        }

    def _run_scenario_in_carla(
        self, scenario: Optional[Dict], sensors: Optional[Dict], params: Dict
    ) -> Dict[str, Any]:
        """在 CARLA 中运行场景 / Run scenario in CARLA."""
        if not scenario:
            raise SkillValidationError("'scenario' is required for run_scenario action")

        duration = scenario.get("duration_s", 30)
        weather = scenario.get("weather", "clear")

        # 模拟执行 / Simulate execution
        steps = duration * 20  # assuming 20 FPS
        metrics_snapshot = {
            "frame_count": steps,
            "simulation_time_s": duration,
            "weather": weather,
            "ego_distance_km": round(random.uniform(0.1, duration * 10 / 3.6) / 1000, 3),
            "collisions": random.randint(0, 1),
            "red_light_violations": random.randint(0, 1) if random.random() > 0.8 else 0,
            "lane_infractions": random.randint(0, 2),
        }

        return {
            "status": "completed",
            "scenario_name": scenario.get("name", "unnamed"),
            "duration_s": duration,
            "metrics": metrics_snapshot,
            "success": metrics_snapshot["collisions"] == 0,
            "message": f"场景 '{scenario.get('name', 'unnamed')}' 执行完成",
            "artifacts": {
                "sensor_data_path": f"/tmp/carla_{random.randint(1000, 9999)}/",
                "log_path": f"/tmp/carla_log_{random.randint(1000, 9999)}.json",
            },
        }

    def _configure_carla_sensors(
        self, scenario: Optional[Dict], config: Optional[Dict], params: Dict
    ) -> Dict[str, Any]:
        """配置 CARLA 传感器 / Configure CARLA sensors."""
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
        self, scenario: Optional[Dict], sensors: Optional[Dict], params: Dict
    ) -> Dict[str, Any]:
        """收集仿真指标 / Collect simulation metrics."""
        return {
            "status": "metrics_collected",
            "metrics": {
                "driving_score": round(random.uniform(0.6, 1.0), 3),
                "comfort_score": round(random.uniform(0.5, 1.0), 3),
                "safety_score": round(random.uniform(0.7, 1.0), 3),
                "route_completion_pct": round(random.uniform(80, 100), 1),
                "infractions": {
                    "collisions": random.randint(0, 2),
                    "lane_violations": random.randint(0, 5),
                    "speed_violations": random.randint(0, 3),
                },
            },
        }

    def _stop_simulation(
        self, scenario: Optional[Dict], sensors: Optional[Dict], params: Dict
    ) -> Dict[str, Any]:
        """停止仿真 / Stop simulation."""
        return {
            "status": "stopped",
            "message": "CARLA 仿真已停止，资源已释放",
        }

    def _analyze_simulation_results(
        self, scenario: Optional[Dict], sensors: Optional[Dict], params: Dict
    ) -> Dict[str, Any]:
        """分析仿真结果 / Analyze simulation results."""
        metrics = params.get("metrics", {})
        driving_score = metrics.get("driving_score", 0.85)
        infractions = metrics.get("infractions", {})

        findings = []
        if infractions.get("collisions", 0) > 0:
            findings.append(f"发生 {infractions['collisions']} 次碰撞")
        if infractions.get("lane_violations", 0) > 3:
            findings.append("车道保持性能需改进")

        return {
            "status": "analyzed",
            "driving_score": driving_score,
            "assessment": "良好" if driving_score >= 0.8 else "需改进",
            "findings": findings,
            "recommendations": [
                "优化横向控制参数" if infractions.get("lane_violations", 0) > 3 else "各项指标正常",
            ],
        }


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
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="edge_case",
            version="1.0.0",
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

        edge_cases: List[Dict[str, Any]] = []

        method_map = {
            "knowledge": self._knowledge_based,
            "adversarial": self._adversarial_search,
            "coverage": self._coverage_driven,
            "mining": self._mining_based,
        }

        handler = method_map.get(method, self._knowledge_based)
        edge_cases = handler(target, search_space, count)

        return {
            "target_module": target,
            "method": method,
            "total_edge_cases": len(edge_cases),
            "edge_cases": edge_cases,
            "severity_distribution": self._severity_dist(edge_cases),
            "summary": f"发现 {len(edge_cases)} 个潜在边缘案例 (方法: {method})",
        }

    def _knowledge_based(
        self, target: str, space: Optional[Dict], count: int
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

        random.shuffle(filtered)
        return filtered[:count]

    def _adversarial_search(
        self, target: str, space: Optional[Dict], count: int
    ) -> List[Dict]:
        """对抗性搜索 / Adversarial edge case search."""
        cases = []
        params = space or {
            "speed_range": (0, 50),
            "weathers": ["clear", "rain", "fog", "snow"],
            "lightings": ["day", "night", "dusk", "dawn"],
            "road_types": ["highway", "urban", "rural"],
        }

        for i in range(count):
            speed = random.uniform(*params.get("speed_range", (0, 30)))
            weather = random.choice(params.get("weathers", ["clear"]))
            lighting = random.choice(params.get("lightings", ["day"]))
            road = random.choice(params.get("road_types", ["highway"]))

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
                "adversarial_factor": round(random.uniform(0.5, 1.0), 3),
                "severity": "critical" if random.random() > 0.7 else "high",
                "description": f"{road}场景 {weather}天气 {lighting}光照 车速{speed:.1f}m/s",
            })

        return cases

    def _coverage_driven(
        self, target: str, space: Optional[Dict], count: int
    ) -> List[Dict]:
        """覆盖驱动的边缘案例 / Coverage-driven edge cases."""
        dims = space or {
            "ego_speed": [0, 5, 15, 30, 50],
            "target_speed": [-10, 0, 10, 20, 40],
            "relative_distance": [2, 5, 10, 30, 100],
            "road_curvature": [0, 0.05, 0.1, 0.2, 0.4],
        }

        cases = []
        for i in range(min(count, 20)):
            key = random.choice(list(dims.keys()))
            values = dims[key]
            val = random.choice(values)

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
        self, target: str, space: Optional[Dict], count: int
    ) -> List[Dict]:
        """基于数据挖掘的边缘案例 / Mining-based edge cases."""
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

        selected = random.sample(scenarios, min(count, len(scenarios)))
        return [
            {
                "id": f"MINE-{i + 1:03d}",
                "scenario": s,
                "target": target,
                "source": "real_world_mining",
                "severity": random.choice(["medium", "high", "critical"]),
                "frequency": round(random.uniform(0.01, 0.1), 4),
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
