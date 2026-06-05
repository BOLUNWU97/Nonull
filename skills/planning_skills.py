"""
Planning Skills - 规划决策技能

自动驾驶路径规划、行为预测和轨迹优化分析。
Path planning, behavior prediction, and trajectory optimization for autonomous driving.
"""

from __future__ import annotations

import math
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
# 路径规划审查技能 / Route Planning Skill
# =============================================================================


class RoutePlanningSkill(BaseSkill):
    """
    路径规划算法审查技能。
    Route planning algorithm review for autonomous driving.

    审查内容 / Review:
        - 路径完整性 / Path completeness
        - 安全约束验证 / Safety constraint validation
        - 平滑性分析 / Smoothness analysis
        - 实时性评估 / Real-time performance evaluation
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="route_planning",
            version="1.0.0",
            category=SkillCategory.PLANNING,
            description="路径规划审查：评估路径的安全性、平滑性和实时性",
            author="Nonull",
            tags=["planning", "route", "path", "navigation", "global"],
            input_schema={
                "type": "object",
                "properties": {
                    "waypoints": {
                        "type": "array",
                        "description": "路径点列表 [(x,y) or (x,y,theta)]",
                    },
                    "map_data": {
                        "type": "object",
                        "description": "地图数据（可选）",
                    },
                    "vehicle_state": {
                        "type": "object",
                        "description": "车辆状态信息",
                    },
                    "constraints": {
                        "type": "object",
                        "description": "约束条件",
                    },
                },
                "required": ["waypoints"],
            },
            safety_level=4,
        )

    def _validate_input(self, context: Dict[str, Any]) -> None:
        if not context.get("waypoints"):
            raise SkillValidationError("'waypoints' is required")
        if len(context["waypoints"]) < 2:
            raise SkillValidationError("至少需要2个路径点 / At least 2 waypoints required")

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        waypoints: List = context["waypoints"]
        vehicle: Optional[Dict] = context.get("vehicle_state", {})
        constraints: Optional[Dict] = context.get("constraints", {})
        map_data: Optional[Dict] = context.get("map_data")

        # 提取坐标 / Extract coordinates
        pts = self._parse_waypoints(waypoints)

        result: Dict[str, Any] = {
            "waypoint_count": len(pts),
            "route_length_m": self._compute_path_length(pts),
            "safety_analysis": self._safety_check(pts, constraints, vehicle),
            "smoothness_analysis": self._smoothness_analysis(pts),
            "feasibility_analysis": self._feasibility_check(pts, vehicle, constraints),
            "recommendations": [],
            "overall_score": 0.0,
        }

        # 汇总评分 / Aggregate score
        safety_score = result["safety_analysis"].get("score", 50)
        smooth_score = result["smoothness_analysis"].get("score", 50)
        feasibility_score = result["feasibility_analysis"].get("score", 50)

        result["overall_score"] = round(
            0.5 * safety_score + 0.3 * smooth_score + 0.2 * feasibility_score, 2
        )

        # 生成建议 / Generate recommendations
        recs = []
        if safety_score < 70:
            recs.append("安全评分偏低，请检查路径与障碍物的距离")
        if smooth_score < 60:
            recs.append("路径平滑度不足，建议增加插值点或使用样条曲线")
        if feasibility_score < 60:
            recs.append("路径可行性低，检查曲率是否满足车辆最小转弯半径")
        if not recs:
            recs.append("路径规划基本合理")

        result["recommendations"] = recs

        return result

    def _parse_waypoints(self, waypoints: List) -> List[Tuple[float, float, float]]:
        """解析路径点格式 / Parse waypoint format."""
        pts = []
        for wp in waypoints:
            if isinstance(wp, (list, tuple)):
                x, y = float(wp[0]), float(wp[1])
                theta = float(wp[2]) if len(wp) > 2 else 0.0
                pts.append((x, y, theta))
            elif isinstance(wp, dict):
                x = float(wp.get("x", wp.get("lat", 0)))
                y = float(wp.get("y", wp.get("lon", 0)))
                theta = float(wp.get("theta", wp.get("yaw", 0)))
                pts.append((x, y, theta))
        return pts

    def _compute_path_length(self, pts: List[Tuple[float, float, float]]) -> float:
        """计算路径总长度 / Compute total path length."""
        total = 0.0
        for i in range(1, len(pts)):
            dx = pts[i][0] - pts[i - 1][0]
            dy = pts[i][1] - pts[i - 1][1]
            total += math.sqrt(dx * dx + dy * dy)
        return round(total, 2)

    def _safety_check(
        self,
        pts: List[Tuple[float, float, float]],
        constraints: Optional[Dict],
        vehicle: Optional[Dict],
    ) -> Dict[str, Any]:
        """安全检查 / Safety check."""
        findings = []
        score = 80
        safety_margin = (constraints or {}).get("safety_margin_m", 2.0)
        vehicle_width = (vehicle or {}).get("width_m", 2.0)
        road_width = (constraints or {}).get("road_width_m", 7.0)

        # 检查路径是否超出道路宽度 / Check if path exceeds road width
        if road_width > 0 and vehicle_width > 0:
            lateral_clearance = road_width - vehicle_width
            if lateral_clearance < 1.0:
                findings.append(f"横向通过空间 {lateral_clearance:.2f}m 不足")
                score -= 20

        # 检查路径点聚簇 / Check for waypoint clusters
        for i in range(1, len(pts)):
            dx = pts[i][0] - pts[i - 1][0]
            dy = pts[i][1] - pts[i - 1][1]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.01 and i not in (0, len(pts) - 1):
                findings.append(f"路径点 #{i} 和 #{i - 1} 几乎重合")
                score -= 5
                break

        return {
            "score": max(0, score),
            "clearance_check": {"road_width_m": road_width, "vehicle_width_m": vehicle_width},
            "findings": findings,
        }

    def _smoothness_analysis(
        self, pts: List[Tuple[float, float, float]]
    ) -> Dict[str, Any]:
        """平滑度分析 / Smoothness analysis."""
        findings = []
        total_curvature = 0.0
        max_curvature = 0.0
        sharp_turns = 0

        for i in range(1, len(pts) - 1):
            # 三点曲率计算 / Three-point curvature
            x1, y1 = pts[i - 1][0], pts[i - 1][1]
            x2, y2 = pts[i][0], pts[i][1]
            x3, y3 = pts[i + 1][0], pts[i + 1][1]

            v1 = (x2 - x1, y2 - y1)
            v2 = (x3 - x2, y3 - y2)

            len1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2)
            len2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2)

            if len1 > 0 and len2 > 0:
                cross = v1[0] * v2[1] - v1[1] * v2[0]
                dot = v1[0] * v2[0] + v1[1] * v2[1]
                curvature = abs(cross) / (len1 * len2)
                total_curvature += curvature

                if curvature > 0.2:  # 大约 11 度转角 / ~11 degree turn
                    sharp_turns += 1
                    if curvature > max_curvature:
                        max_curvature = curvature

        if sharp_turns > 2:
            findings.append(f"存在 {sharp_turns} 个急转弯")
        if max_curvature > 0.5:
            findings.append(f"最大曲率 {max_curvature:.3f} 较大")

        avg_curvature = total_curvature / max(1, len(pts) - 2)
        score = 90 if avg_curvature < 0.05 else 70 if avg_curvature < 0.15 else 50

        return {
            "score": score,
            "average_curvature": round(avg_curvature, 4),
            "max_curvature": round(max_curvature, 4),
            "sharp_turns": sharp_turns,
            "findings": findings,
        }

    def _feasibility_check(
        self,
        pts: List[Tuple[float, float, float]],
        vehicle: Optional[Dict],
        constraints: Optional[Dict],
    ) -> Dict[str, Any]:
        """可行性检查 / Feasibility check."""
        findings = []
        min_turn_radius = (vehicle or {}).get("min_turn_radius_m", 5.0)
        max_accel = (vehicle or {}).get("max_acceleration_mps2", 3.0)
        score = 80

        if min_turn_radius > 0 and len(pts) >= 3:
            for i in range(1, len(pts) - 1):
                x1, y1 = pts[i - 1][0], pts[i - 1][1]
                x2, y2 = pts[i][0], pts[i][1]
                x3, y3 = pts[i + 1][0], pts[i + 1][1]

                len1 = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                len2 = math.sqrt((x3 - x2) ** 2 + (y3 - y2) ** 2)

                if len1 > 0 and len2 > 0:
                    cross = abs((x2 - x1) * (y3 - y2) - (y2 - y1) * (x3 - x2))
                    curvature = cross / (len1 * len2)
                    if curvature > 0:
                        radius = 1.0 / curvature
                        if radius < min_turn_radius:
                            findings.append(
                                f"路径点 #{i}: 转弯半径 {radius:.2f}m < "
                                f"最小转弯半径 {min_turn_radius}m"
                            )
                            score -= 15

        if findings:
            score = max(0, score)

        return {
            "score": score,
            "min_turn_radius_m": min_turn_radius,
            "findings": findings,
        }


# =============================================================================
# 行为规划技能 / Behavior Planning Skill
# =============================================================================


class BehaviorPlanningSkill(BaseSkill):
    """
    行为预测与决策规划分析技能。
    Behavior prediction and decision planning analysis.

    分析内容 / Analysis:
        - 行为预测模型评估 / Behavior prediction model evaluation
        - 决策逻辑一致性 / Decision logic consistency
        - 交互行为分析 / Interactive behavior analysis
        - 异常行为检测 / Anomalous behavior detection
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="behavior_planning",
            version="1.0.0",
            category=SkillCategory.PLANNING,
            description="行为规划分析：行为预测、决策逻辑与交互行为评估",
            author="Nonull",
            tags=["planning", "behavior", "prediction", "decision", "interaction"],
            input_schema={
                "type": "object",
                "properties": {
                    "scenario": {"type": "object"},
                    "predictions": {"type": "array"},
                    "decision_logic": {"type": "object"},
                    "history": {"type": "array"},
                },
                "required": ["scenario"],
            },
            safety_level=4,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        scenario: Dict = context.get("scenario", {})
        predictions: List = context.get("predictions", [])
        decisions: Optional[Dict] = context.get("decision_logic")
        history: List = context.get("history", [])

        result: Dict[str, Any] = {
            "scenario_type": scenario.get("type", "unknown"),
            "complexity_level": "",
            "prediction_review": self._review_predictions(predictions, scenario),
            "decision_review": self._review_decisions(decisions, scenario),
            "interaction_analysis": self._analyze_interactions(scenario),
            "safety_concerns": [],
            "recommendations": [],
            "overall_risk": "low",
        }

        # 场景复杂度评估 / Scenario complexity
        complexity = self._assess_complexity(scenario)
        result["complexity_level"] = complexity

        # 风险分析 / Risk analysis
        concerns = []
        if complexity in ("high", "critical"):
            concerns.append("场景复杂度高，建议降速或接管")

        pred_review = result["prediction_review"]
        if pred_review.get("uncertain_agents", 0) > 2:
            concerns.append(f"有 {pred_review['uncertain_agents']} 个不确定性高的交通参与者")
            result["overall_risk"] = "medium"

        dec_review = result["decision_review"]
        if not dec_review.get("safe", True):
            concerns.append("决策逻辑存在安全隐患")
            result["overall_risk"] = "high"

        result["safety_concerns"] = concerns
        result["recommendations"] = self._generate_recommendations(result)

        return result

    def _review_predictions(
        self, predictions: List, scenario: Dict
    ) -> Dict[str, Any]:
        """审查预测结果 / Review prediction results."""
        uncertain_count = 0
        low_confidence = 0
        total = len(predictions)

        for pred in predictions:
            confidence = pred.get("confidence", 0)
            if confidence < 0.5:
                low_confidence += 1
            if pred.get("uncertainty", 1.0) > 0.7:
                uncertain_count += 1

            # 检查预测轨迹是否合理 / Check trajectory plausibility
            trajectory = pred.get("trajectory", [])
            if len(trajectory) >= 2:
                for i in range(1, len(trajectory)):
                    dx = trajectory[i][0] - trajectory[i - 1][0]
                    dy = trajectory[i][1] - trajectory[i - 1][1]
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist > 50:  # 单步超过50米不合理 / Unrealistic step
                        low_confidence += 1
                        break

        return {
            "total_predictions": total,
            "uncertain_agents": uncertain_count,
            "low_confidence_predictions": low_confidence,
            "prediction_horizon_s": scenario.get("prediction_horizon", 5),
        }

    def _review_decisions(
        self, decisions: Optional[Dict], scenario: Dict
    ) -> Dict[str, Any]:
        """审查决策逻辑 / Review decision logic."""
        if not decisions:
            return {"safe": True, "warnings": ["No decision logic provided"]}

        findings = []
        safe = True

        decision_type = decisions.get("type", "unknown")
        velocity = decisions.get("target_velocity", 0)
        scenario_speed_limit = scenario.get("speed_limit", 0)

        if scenario_speed_limit > 0 and velocity > scenario_speed_limit * 1.1:
            findings.append(f"目标速度 {velocity:.1f}m/s 超过限速 {scenario_speed_limit:.1f}m/s")
            safe = False

        # 检查行为一致性 / Behavior consistency
        behavior = decisions.get("behavior", "")
        if behavior == "lane_change" and not decisions.get("has_gap", False):
            findings.append("变道决策缺少安全间隙检查")
            safe = False

        if behavior == "overtake":
            oncoming = decisions.get("oncoming_traffic", False)
            if oncoming:
                findings.append("对向有来车时超车，风险较高")
                safe = False

        return {
            "safe": safe,
            "decision_type": decision_type,
            "findings": findings,
            "warnings": findings if not safe else [],
        }

    def _analyze_interactions(self, scenario: Dict) -> Dict[str, Any]:
        """分析交互行为 / Analyze interactions."""
        agents = scenario.get("agents", [])
        interaction_zones = 0
        conflicting_flows = 0

        for i, a1 in enumerate(agents):
            for j, a2 in enumerate(agents):
                if i >= j:
                    continue
                # 简单距离检查 / Simple distance check
                p1 = a1.get("position", [0, 0])
                p2 = a2.get("position", [0, 0])
                dist = math.sqrt(
                    (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2
                ) if len(p1) == 2 and len(p2) == 2 else float("inf")

                if dist < 20:
                    interaction_zones += 1
                    if a1.get("heading", 0) and a2.get("heading", 0):
                        heading_diff = abs(a1["heading"] - a2["heading"])
                        if heading_diff > math.pi / 4:
                            conflicting_flows += 1

        return {
            "agent_count": len(agents),
            "interaction_zones": interaction_zones,
            "conflicting_flows": conflicting_flows,
            "complexity_score": min(interaction_zones + conflicting_flows, 10),
        }

    def _assess_complexity(self, scenario: Dict) -> str:
        """评估场景复杂度 / Assess scenario complexity."""
        agents = scenario.get("agents", [])
        n_agents = len(agents)
        speed_limit = scenario.get("speed_limit", 0)
        weather = scenario.get("weather", "clear")
        road_type = scenario.get("road_type", "highway")

        score = 0
        if n_agents > 10:
            score += 3
        elif n_agents > 5:
            score += 2
        elif n_agents > 3:
            score += 1

        if speed_limit > 30:  # > 108 km/h
            score += 2
        elif speed_limit > 20:
            score += 1

        if weather in ("rain", "snow", "fog"):
            score += 2

        if road_type == "intersection":
            score += 2
        elif road_type == "urban":
            score += 1

        if score >= 6:
            return "critical"
        elif score >= 4:
            return "high"
        elif score >= 2:
            return "medium"
        return "low"

    def _generate_recommendations(self, result: Dict) -> List[str]:
        """生成建议 / Generate recommendations."""
        recs = []
        risk = result.get("overall_risk", "low")
        if risk == "high":
            recs.append("建议驾驶员接管 / Suggest driver take over")
        elif risk == "medium":
            recs.append("降低车速，增加跟车距离")

        concerns = result.get("safety_concerns", [])
        recs.extend(concerns[:3])

        if not recs:
            recs.append("行为规划合理，继续监控")
        return recs


# =============================================================================
# 轨迹优化技能 / Trajectory Optimization Skill
# =============================================================================


class TrajectoryOptimizationSkill(BaseSkill):
    """
    轨迹优化与评估技能。
    Trajectory evaluation and optimization for autonomous driving.

    评估内容 / Evaluation:
        - 运动学可行性 / Kinematic feasibility
        - 舒适性评估 / Comfort assessment
        - 障碍物避让 / Obstacle avoidance
        - 时间最优性 / Time optimality
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="trajectory_optimization",
            version="1.0.0",
            category=SkillCategory.PLANNING,
            description="轨迹优化评估：运动学可行性、舒适性与最优性分析",
            author="Nonull",
            tags=["planning", "trajectory", "optimization", "comfort", "kinematic"],
            input_schema={
                "type": "object",
                "properties": {
                    "trajectory": {"type": "array", "description": "轨迹点列表 [(t, x, y, v, a)]"},
                    "obstacles": {"type": "array", "description": "障碍物信息"},
                    "vehicle_params": {"type": "object", "description": "车辆参数"},
                    "optimization_weights": {"type": "object"},
                },
                "required": ["trajectory"],
            },
            safety_level=4,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        trajectory: List = context.get("trajectory", [])
        obstacles: List = context.get("obstacles", [])
        vehicle_params: Dict = context.get("vehicle_params", {})
        weights: Dict = context.get("optimization_weights", {})

        traj = self._parse_trajectory(trajectory)

        comfort = self._assess_comfort(traj)
        kinematic = self._check_kinematic_feasibility(traj, vehicle_params)
        collision = self._check_collision(traj, obstacles)
        optimality = self._assess_optimality(traj, weights)

        score = (
            0.25 * comfort.get("score", 50)
            + 0.25 * kinematic.get("score", 50)
            + 0.35 * collision.get("score", 50)
            + 0.15 * optimality.get("score", 50)
        )

        return {
            "trajectory_length": len(traj),
            "duration_s": traj[-1][0] - traj[0][0] if len(traj) >= 2 else 0,
            "comfort_assessment": comfort,
            "kinematic_feasibility": kinematic,
            "collision_check": collision,
            "optimality_assessment": optimality,
            "overall_score": round(score, 2),
            "recommendations": self._merge_recommendations(
                comfort, kinematic, collision, optimality
            ),
        }

    def _parse_trajectory(
        self, trajectory: List
    ) -> List[Tuple[float, float, float, float, float]]:
        """解析轨迹点 / Parse trajectory points."""
        parsed = []
        for pt in trajectory:
            if isinstance(pt, (list, tuple)):
                t = float(pt[0])
                x = float(pt[1]) if len(pt) > 1 else 0.0
                y = float(pt[2]) if len(pt) > 2 else 0.0
                v = float(pt[3]) if len(pt) > 3 else 0.0
                a = float(pt[4]) if len(pt) > 4 else 0.0
                parsed.append((t, x, y, v, a))
            elif isinstance(pt, dict):
                parsed.append((
                    float(pt.get("t", pt.get("time", 0))),
                    float(pt.get("x", 0)),
                    float(pt.get("y", 0)),
                    float(pt.get("v", pt.get("velocity", 0))),
                    float(pt.get("a", pt.get("acceleration", 0))),
                ))
        return parsed

    def _assess_comfort(
        self, traj: List[Tuple[float, float, float, float, float]]
    ) -> Dict[str, Any]:
        """舒适性评估 / Comfort assessment."""
        findings = []
        max_jerk = 0.0
        max_lateral_accel = 0.0
        jerk_violations = 0

        for i in range(2, len(traj)):
            dt1 = traj[i - 1][0] - traj[i - 2][0]
            dt2 = traj[i][0] - traj[i - 1][0]
            if dt1 > 0 and dt2 > 0:
                jerk = abs((traj[i][4] - traj[i - 1][4]) / dt2 - (traj[i - 1][4] - traj[i - 2][4]) / dt1) / ((dt1 + dt2) / 2)
                max_jerk = max(max_jerk, jerk)
                if jerk > 2.0:  #  jerk > 2 m/s^3 不舒服 / Uncomfortable
                    jerk_violations += 1

            # 横向加速度估算 / Lateral acceleration estimation
            if i < len(traj) - 1:
                dx = traj[i][1] - traj[i - 1][1]
                dy = traj[i][2] - traj[i - 1][2]
                v = traj[i][3]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 0 and v > 0:
                    curvature = abs(dx * (traj[i + 1][2] - traj[i][2]) - dy * (traj[i + 1][1] - traj[i][1])) / (dist ** 3)
                    lat_accel = v * v * curvature
                    max_lateral_accel = max(max_lateral_accel, lat_accel)

        if max_jerk > 2.0:
            findings.append(f"最大加加速度 {max_jerk:.2f}m/s^3 超过舒适阈值")
        if jerk_violations > 3:
            findings.append(f"有 {jerk_violations} 处加加速度超限")
        if max_lateral_accel > 3.0:
            findings.append(f"最大横向加速度 {max_lateral_accel:.2f}m/s^2 偏大")

        score = 90
        score -= min(30, max_jerk * 5)
        score -= min(20, jerk_violations * 3)
        score -= min(20, max_lateral_accel * 3)
        score = max(0, score)

        return {
            "score": score,
            "max_jerk_mps3": round(max_jerk, 3),
            "max_lateral_accel_mps2": round(max_lateral_accel, 3),
            "jerk_violations": jerk_violations,
            "findings": findings,
        }

    def _check_kinematic_feasibility(
        self,
        traj: List[Tuple[float, float, float, float, float]],
        vehicle_params: Dict,
    ) -> Dict[str, Any]:
        """运动学可行性检查 / Kinematic feasibility check."""
        findings = []
        max_accel = vehicle_params.get("max_acceleration_mps2", 5.0)
        max_decel = vehicle_params.get("max_deceleration_mps2", -5.0)
        max_speed = vehicle_params.get("max_speed_mps", 50.0)
        score = 80

        for i, pt in enumerate(traj):
            v, a = pt[3], pt[4]
            if v > max_speed * 1.05:
                findings.append(f"点 #{i}: 速度 {v:.1f}m/s 超过最大速度 {max_speed:.1f}m/s")
                score -= 15
            if a > max_accel:
                findings.append(f"点 #{i}: 加速度 {a:.2f}m/s^2 超过最大值")
                score -= 10
            if a < max_decel:
                findings.append(f"点 #{i}: 减速度 {a:.2f}m/s^2 超过极限")
                score -= 10

        return {"score": max(0, score), "findings": findings}

    def _check_collision(
        self,
        traj: List[Tuple[float, float, float, float, float]],
        obstacles: List,
    ) -> Dict[str, Any]:
        """碰撞检测 / Collision check."""
        findings = []
        min_distance = float("inf")
        near_misses = 0

        for obs in obstacles:
            ox = obs.get("x", obs.get("position", [0])[0])
            oy = obs.get("y", obs.get("position", [0, 0])[1])
            oradius = obs.get("radius", obs.get("width", 2.0)) / 2

            for pt in traj:
                dx = pt[1] - ox
                dy = pt[2] - oy
                dist = math.sqrt(dx * dx + dy * dy) - oradius
                min_distance = min(min_distance, dist)
                if dist < 1.0:
                    near_misses += 1
                    if dist < 0.1:
                        findings.append(f"与障碍物碰撞风险: 距离 {dist:.3f}m")

        if min_distance < 0.5:
            findings.append(f"最小距离 {min_distance:.2f}m，存在碰撞风险")
        elif min_distance > 5.0:
            findings.append("碰撞风险低")

        score = 80 if findings else 100
        if near_misses > 5:
            score -= 20

        return {
            "score": max(0, score),
            "min_distance_m": round(min_distance, 2),
            "near_misses": near_misses,
            "findings": findings or ["无碰撞风险"],
        }

    def _assess_optimality(
        self,
        traj: List[Tuple[float, float, float, float, float]],
        weights: Dict,
    ) -> Dict[str, Any]:
        """最优性评估 / Optimality assessment."""
        w_time = weights.get("time", 1.0)
        w_energy = weights.get("energy", 0.5)
        w_comfort = weights.get("comfort", 0.8)

        if len(traj) < 2:
            return {"score": 50, "findings": ["轨迹点太少"]}

        total_time = traj[-1][0] - traj[0][0]
        total_energy = sum(abs(pt[4]) * abs(pt[3]) for pt in traj) if total_time > 0 else 0

        cost = w_time * total_time + w_energy * total_energy * 0.01
        score = max(0, 100 - cost * 2)

        return {
            "score": round(score, 2),
            "total_time_s": round(total_time, 2),
            "energy_cost": round(total_energy, 2),
            "cost": round(cost, 2),
            "findings": [] if score >= 60 else ["轨迹成本较高，可考虑优化"],
        }

    def _merge_recommendations(self, *assessments: Dict) -> List[str]:
        """合并建议 / Merge recommendations."""
        recs = []
        for assess in assessments:
            recs.extend(assess.get("findings", []))
        return recs[:5]
