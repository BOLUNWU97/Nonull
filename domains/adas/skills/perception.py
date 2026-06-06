"""
Perception Skills - 感知技能

自动驾驶感知模块的分析、评估与优化。
Analysis, evaluation, and optimization of autonomous driving perception modules.
"""

from __future__ import annotations

import re
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

# 传感器类型常量 / Sensor type constants
SENSOR_TYPES = {
    "lidar": ["velodyne", "hesai", "robosense", "ouster", "livox"],
    "camera": ["mono", "stereo", "fisheye", "surround_view", "thermal"],
    "radar": ["mmwave", "ultrasonic", "4d_imaging"],
    "ultrasonic": ["parking_sensor"],
    "imu": ["gps_ins", "gyroscope", "accelerometer"],
}


# =============================================================================
# 传感器分析技能 / Sensor Analysis Skill
# =============================================================================


class SensorAnalysisSkill(BaseSkill):
    """
    传感器数据分析技能。
    LiDAR/Camera/Radar data review and analysis.

    分析内容 / Analysis:
        - 传感器配置合理性 / Sensor configuration validation
        - 数据质量评估 / Data quality assessment
        - 视野覆盖分析 / Field-of-view coverage analysis
        - 传感器融合策略 / Sensor fusion strategy review
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="sensor_analysis",
            version="1.0.0",
            category=SkillCategory.PERCEPTION,
            description="传感器数据分析：LiDAR/Camera/Radar 配置与数据质量审查",
            author="Nonull",
            tags=["perception", "sensor", "lidar", "camera", "radar", "fusion"],
            input_schema={
                "type": "object",
                "properties": {
                    "sensor_config": {
                        "type": "object",
                        "description": "传感器配置信息 / Sensor configuration",
                    },
                    "data_sample": {
                        "type": "object",
                        "description": "传感器数据样本（可选）",
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["coverage", "quality", "calibration", "full"],
                    },
                },
                "required": ["sensor_config"],
            },
            safety_level=3,
        )

    def _validate_input(self, context: Dict[str, Any]) -> None:
        if not context.get("sensor_config"):
            raise SkillValidationError("'sensor_config' is required")

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config: Dict = context["sensor_config"]
        data: Optional[Dict] = context.get("data_sample")
        analysis_type: str = context.get("analysis_type", "full")

        result: Dict[str, Any] = {
            "sensor_summary": {},
            "findings": [],
            "recommendations": [],
            "warnings": [],
            "scores": {},
        }

        sensors = config.get("sensors", [])
        if not sensors:
            # 支持单传感器配置 / Support single sensor config
            if "type" in config:
                sensors = [config]

        for sensor in sensors:
            sensor_type = sensor.get("type", "unknown").lower()
            result["sensor_summary"][sensor.get("name", "unnamed")] = \
                self._analyze_sensor(sensor, analysis_type)

        # 融合分析 / Fusion analysis
        if len(sensors) > 1:
            fusion_findings = self._analyze_fusion(sensors)
            result["findings"].extend(fusion_findings)

        # 覆盖分析 / Coverage analysis
        if analysis_type in ("coverage", "full"):
            coverage = self._analyze_coverage(sensors)
            result["coverage_analysis"] = coverage
            result["scores"]["coverage"] = coverage.get("score", 0)

        # 总体评分 / Overall score
        result["scores"]["overall"] = self._calculate_overall_score(result)

        return result

    def _analyze_sensor(self, sensor: Dict, mode: str) -> Dict[str, Any]:
        """分析单个传感器 / Analyze a single sensor."""
        sensor_type = sensor.get("type", "unknown")
        name = sensor.get("name", f"{sensor_type}_1")
        findings = []

        # 检查必要参数 / Check required parameters
        required_params = {
            "lidar": ["channels", "range", "fov_h", "fov_v", "update_rate"],
            "camera": ["resolution", "fov", "fps", "pixel_format"],
            "radar": ["range", "fov_h", "fov_v", "update_rate", "max_objects"],
        }

        needs = required_params.get(sensor_type, [])
        missing = [p for p in needs if p not in sensor]
        if missing:
            findings.append({
                "severity": "warning",
                "message": f"缺少关键参数: {', '.join(missing)}",
                "suggestion": "请补充完整传感器配置参数",
            })

        # 参数合理性检查 / Parameter validity checks
        checks = {
            "lidar": [
                (sensor.get("channels", 0) < 16, "激光雷达线数 < 16，点云密度可能不足"),
                (sensor.get("range", 0) > 300, "探测距离 > 300m，需确认实际性能"),
                (sensor.get("update_rate", 0) < 5, "更新率 < 5Hz，实时性不足"),
            ],
            "camera": [
                (sensor.get("fps", 0) < 15, "帧率 < 15fps，高速场景可能丢帧"),
                (sensor.get("resolution", "").lower() in ("720p", "480p"),
                 "分辨率较低，远距离目标检测受限"),
            ],
            "radar": [
                (sensor.get("max_objects", 0) < 64, "最大跟踪目标数 < 64，密集场景可能不足"),
                (sensor.get("range", 0) < 150, "探测距离 < 150m，高速场景受限"),
            ],
        }

        for condition, msg in checks.get(sensor_type, []):
            if condition:
                findings.append({
                    "severity": "warning",
                    "message": msg,
                })

        return {
            "name": name,
            "type": sensor_type,
            "status": "ok" if not any(f["severity"] == "critical" for f in findings) else "warning",
            "findings": findings,
            "params_available": len(needs) - len(missing),
            "params_total": len(needs),
        }

    def _analyze_fusion(self, sensors: List[Dict]) -> List[Dict]:
        """分析传感器融合策略 / Analyze sensor fusion strategy."""
        findings = []
        types = set(s.get("type", "").lower() for s in sensors)

        if "lidar" not in types and "radar" not in types:
            findings.append({
                "severity": "critical",
                "type": "FUSION_NO_3D",
                "message": "缺少 LiDAR/Radar 3D传感器，120km/h以上安全性受限",
                "suggestion": "建议至少配置一个3D传感器",
            })

        if "camera" not in types:
            findings.append({
                "severity": "critical",
                "type": "FUSION_NO_CAMERA",
                "message": "缺少摄像头，无法进行交通标志/车道线识别",
                "suggestion": "建议至少配置一个前视摄像头",
            })

        # 时间同步检查 / Temporal synchronization
        rates = []
        for s in sensors:
            rate = s.get("update_rate", 0) or s.get("fps", 0)
            if rate > 0:
                rates.append((s.get("name", "unknown"), rate))

        if len(rates) > 1:
            rate_values = [r[1] for r in rates]
            max_rate = max(rate_values)
            min_rate = min(rate_values)
            if max_rate / min_rate > 5:
                findings.append({
                    "severity": "warning",
                    "type": "FUSION_ASYNC",
                    "message": "传感器更新率差异较大，需要时间同步机制",
                    "suggestion": "使用插值或硬件同步 / Use interpolation or HW sync",
                    "details": {r[0]: r[1] for r in rates},
                })

        return findings

    def _analyze_coverage(self, sensors: List[Dict]) -> Dict[str, Any]:
        """分析传感器视野覆盖 / Analyze sensor field-of-view coverage."""
        coverage_zones = {
            "front": {"min": -30, "max": 30},
            "front_wide": {"min": -60, "max": 60},
            "side_left": {"min": -120, "max": -30},
            "side_right": {"min": 30, "max": 120},
            "rear": {"min": 150, "max": -150},
        }

        covered = set()
        total_zones = len(coverage_zones)

        for sensor in sensors:
            fov = sensor.get("fov", 0) or sensor.get("fov_h", 0)
            if fov <= 0:
                continue

            yaw = sensor.get("yaw", 0) or sensor.get("mounting_yaw", 0)
            fov_min = yaw - fov / 2
            fov_max = yaw + fov / 2

            for zone_name, zone in coverage_zones.items():
                z_min, z_max = zone["min"], zone["max"]
                # 简单重叠检测 / Simple overlap detection
                if fov_min < z_max and fov_max > z_min:
                    covered.add(zone_name)

        uncovered = total_zones - len(covered)
        score = max(0, (len(covered) / total_zones) * 100)

        return {
            "zones_covered": sorted(covered),
            "zones_total": total_zones,
            "zones_uncovered": total_zones - len(covered),
            "score": score,
            "recommendation": "覆盖良好" if score >= 80 else "建议增加传感器填补盲区",
        }

    def _calculate_overall_score(self, result: Dict) -> float:
        """计算总体评分 / Calculate overall score."""
        score = 100.0
        for finding in result.get("findings", []):
            if finding.get("severity") == "critical":
                score -= 20
            elif finding.get("severity") == "warning":
                score -= 10
        return max(0, score)


# =============================================================================
# 感知模型审查技能 / Perception Model Review Skill
# =============================================================================


class PerceptionModelReviewSkill(BaseSkill):
    """
    ML感知模型评估技能。
    ML model evaluation for perception tasks.

    评估内容 / Evaluation:
        - 模型架构选型 / Architecture selection
        - 性能指标评估 / Performance metrics
        - 数据集适配性 / Dataset suitability
        - 部署可行性 / Deployment feasibility
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="perception_model_review",
            version="1.0.0",
            category=SkillCategory.PERCEPTION,
            description="感知模型评估：目标检测/分割/跟踪模型的性能与部署分析",
            author="Nonull",
            tags=["perception", "model", "ml", "deep-learning", "evaluation"],
            input_schema={
                "type": "object",
                "properties": {
                    "task_type": {
                        "type": "string",
                        "enum": ["detection", "segmentation", "tracking", "depth"],
                    },
                    "model_config": {"type": "object"},
                    "metrics": {"type": "object"},
                    "hardware_profile": {"type": "object"},
                },
                "required": ["task_type", "model_config"],
            },
            safety_level=3,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        task: str = context["task_type"]
        model: Dict = context["model_config"]
        metrics: Optional[Dict] = context.get("metrics")
        hardware: Optional[Dict] = context.get("hardware_profile")
        model_name: str = model.get("name", "unnamed_model")

        review_result: Dict[str, Any] = {
            "model_name": model_name,
            "task_type": task,
            "architecture_review": self._review_architecture(task, model),
            "metric_evaluation": self._evaluate_metrics(task, metrics),
            "deployment_analysis": self._analyze_deployment(model, hardware),
            "recommendations": [],
            "overall_score": 0.0,
        }

        suggestions = []
        scores = []

        arch = review_result["architecture_review"]
        if arch.get("score") is not None:
            scores.append(arch["score"])
        if arch.get("suggestions"):
            suggestions.extend(arch["suggestions"])

        eval_res = review_result["metric_evaluation"]
        if eval_res.get("score") is not None:
            scores.append(eval_res["score"])
        if eval_res.get("suggestions"):
            suggestions.extend(eval_res["suggestions"])

        dep = review_result["deployment_analysis"]
        if dep.get("score") is not None:
            scores.append(dep["score"])
        if dep.get("suggestions"):
            suggestions.extend(dep["suggestions"])

        review_result["recommendations"] = suggestions[:5]
        review_result["overall_score"] = (
            sum(scores) / len(scores) if scores else 0.0
        )

        return review_result

    def _review_architecture(self, task: str, model: Dict) -> Dict[str, Any]:
        """审查模型架构 / Review model architecture."""
        findings = []
        arch = model.get("architecture", "").lower()
        backbone = model.get("backbone", "").lower()
        params_m = model.get("parameters_m", 0)
        flops_g = model.get("flops_g", 0)

        # 检测任务推荐架构 / Recommended architectures
        task_archs = {
            "detection": ["yolo", "faster-rcnn", "dino", "rt-detr", "deformable-detr"],
            "segmentation": ["unet", "deeplab", "segformer", "mask2former", "bisenet"],
            "tracking": ["sort", "botsort", "bytetrack", "deep-sort", "fairmot"],
            "depth": ["monodepth2", "midas", "depth-anything", "crestereo"],
        }

        recommended = task_archs.get(task, [])
        if arch and not any(r in arch for r in recommended):
            findings.append({
                "severity": "warning",
                "message": f"架构 '{arch}' 在{task}任务中不常见，建议参考: {', '.join(recommended[:3])}",
            })

        # 参数规模检查 / Parameter size check
        if params_m > 0:
            if params_m > 100:
                findings.append({
                    "severity": "warning",
                    "message": f"参数量 {params_m}M 较大，可能影响推理速度",
                    "suggestion": "考虑使用轻量化架构或模型剪枝",
                })
            elif params_m < 1 and task != "tracking":
                findings.append({
                    "severity": "info",
                    "message": f"参数量 {params_m}M 较小，确认精度是否满足要求",
                })

        # 实时性评估 / Real-time assessment
        score = 70
        if params_m < 50 and flops_g < 100:
            score = 90
        elif params_m < 100 and flops_g < 200:
            score = 75

        return {
            "architecture": arch or "unknown",
            "backbone": backbone or "unknown",
            "parameters_m": params_m,
            "flops_g": flops_g,
            "findings": findings,
            "score": score,
            "suggestions": [f["message"] for f in findings],
        }

    def _evaluate_metrics(
        self, task: str, metrics: Optional[Dict]
    ) -> Dict[str, Any]:
        """评估模型指标 / Evaluate model metrics."""
        if not metrics:
            return {"score": 50, "suggestions": ["提供模型指标以进行详细评估"]}

        findings = []
        score = 60

        # 检测 / Detection metrics
        if task == "detection":
            map_val = metrics.get("mAP", 0)
            if map_val:
                if map_val < 0.5:
                    findings.append(f"mAP={map_val:.3f} 较低，需改进模型精度")
                elif map_val > 0.85:
                    score += 20
                score += min(30, map_val * 30)

            ap50 = metrics.get("AP50", 0)
            if ap50 and ap50 > 0.9:
                score += 10

            recall = metrics.get("Recall", 0)
            if recall and recall < 0.85:
                findings.append(f"召回率 {recall:.3f} 偏低，增加漏检风险")

        # 分割 / Segmentation metrics
        elif task == "segmentation":
            miou = metrics.get("mIoU", 0)
            if miou:
                score += min(30, miou * 35)
                if miou < 0.6:
                    findings.append(f"mIoU={miou:.3f} 较低，建议使用更强的骨干网络")

        # FPS 检查 / FPS check
        fps = metrics.get("FPS", 0)
        if fps:
            fps_target = metrics.get("target_fps", 30)
            if fps < fps_target:
                findings.append(
                    f"FPS={fps} < 目标{fps_target}，无法满足实时性要求"
                )
                score -= 15
            else:
                score += 10

        return {
            "metrics": metrics,
            "findings": findings,
            "score": min(100, max(0, score)),
            "suggestions": findings,
        }

    def _analyze_deployment(
        self, model: Dict, hardware: Optional[Dict]
    ) -> Dict[str, Any]:
        """分析部署可行性 / Analyze deployment feasibility."""
        findings = []
        score = 70

        if hardware:
            compute = hardware.get("compute", 0)  # TOPS
            memory = hardware.get("memory_mb", 0)  # MB
            flops_g = model.get("flops_g", 0)

            if compute > 0 and flops_g > 0:
                utilization = (flops_g * 1000) / (compute * 1e3)  # rough estimate
                if utilization > 0.8:
                    findings.append(f"计算资源利用率高 ({utilization:.0%})，建议优化")
                    score -= 15
                else:
                    score += 10

            if memory > 0:
                model_memory = model.get("parameters_m", 0) * 4  # 4 bytes/param -> MB
                if model_memory > memory * 0.7:
                    findings.append(f"模型内存需求 ({model_memory:.0f}MB) 超过可用内存70%")
                    score -= 20
        else:
            findings.append("未提供硬件配置信息，部署分析基于默认假设")

        return {
            "hardware": hardware or {"info": "not provided"},
            "findings": findings,
            "score": max(0, score),
            "suggestions": findings,
        }


# =============================================================================
# 传感器标定技能 / Sensor Calibration Skill
# =============================================================================


class SensorCalibrationSkill(BaseSkill):
    """
    传感器标定参数审查技能。
    Sensor calibration parameter review.

    审查内容 / Review:
        - 内参合理性 / Intrinsic parameter validity
        - 外参一致性 / Extrinsic parameter consistency
        - 标定精度评估 / Calibration accuracy evaluation
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="sensor_calibration",
            version="1.0.0",
            category=SkillCategory.PERCEPTION,
            description="传感器标定审查：内外参合理性及标定精度评估",
            author="Nonull",
            tags=["perception", "calibration", "sensor", "intrinsics", "extrinsics"],
            input_schema={
                "type": "object",
                "properties": {
                    "calibration_data": {"type": "object"},
                    "sensor_type": {"type": "string"},
                },
                "required": ["calibration_data", "sensor_type"],
            },
            safety_level=3,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        calib: Dict = context["calibration_data"]
        sensor_type: str = context["sensor_type"].lower()

        calib_result: Dict[str, Any] = {
            "sensor_type": sensor_type,
            "calibration_valid": False,
            "intrinsic_check": {},
            "extrinsic_check": {},
            "issues": [],
            "score": 0.0,
        }

        # 内参检查 / Intrinsic check
        intrinsics = calib.get("intrinsics", {})
        calib_result["intrinsic_check"] = self._check_intrinsics(
            sensor_type, intrinsics
        )

        # 外参检查 / Extrinsic check
        extrinsics = calib.get("extrinsics", {})
        calib_result["extrinsic_check"] = self._check_extrinsics(
            sensor_type, extrinsics
        )

        # 汇总问题 / Aggregate issues
        all_issues = (
            calib_result["intrinsic_check"].get("issues", [])
            + calib_result["extrinsic_check"].get("issues", [])
        )
        calib_result["issues"] = all_issues
        calib_result["calibration_valid"] = len(
            [i for i in all_issues if i.get("severity") == "critical"]
        ) == 0
        calib_result["score"] = self._compute_calibration_score(all_issues)

        return calib_result

    def _check_intrinsics(
        self, sensor_type: str, intrinsics: Dict
    ) -> Dict[str, Any]:
        """检查内参 / Check intrinsic parameters."""
        issues = []

        if sensor_type == "camera":
            fx = intrinsics.get("fx", 0)
            fy = intrinsics.get("fy", 0)
            cx = intrinsics.get("cx", 0)
            cy = intrinsics.get("cy", 0)
            width = intrinsics.get("width", 0)
            height = intrinsics.get("height", 0)
            distortion = intrinsics.get("distortion", [])

            if fx <= 0 or fy <= 0:
                issues.append({
                    "severity": "critical",
                    "message": "焦距 fx/fy 无效，需要重新标定",
                })
            if cx <= 0 or cy <= 0:
                issues.append({
                    "severity": "critical",
                    "message": "主点 cx/cy 无效，需要重新标定",
                })
            if len(distortion) != 5 and len(distortion) != 8:
                issues.append({
                    "severity": "warning",
                    "message": f"畸变系数数量异常 ({len(distortion)})，预期 5 (OpenCV) 或 8",
                })
            # 畸变系数异常检测 / Abnormal distortion
            if distortion and any(abs(d) > 1.0 for d in distortion[:4]):
                issues.append({
                    "severity": "warning",
                    "message": "畸变系数偏大，可能存在标定误差",
                })

        return {"parameters": intrinsics, "issues": issues}

    def _check_extrinsics(
        self, sensor_type: str, extrinsics: Dict
    ) -> Dict[str, Any]:
        """检查外参 / Check extrinsic parameters."""
        issues = []

        translation = extrinsics.get("translation", [])
        rotation = extrinsics.get("rotation", [])

        if translation and len(translation) == 3:
            if all(abs(t) < 0.001 for t in translation):
                issues.append({
                    "severity": "info",
                    "message": "平移向量接近零，确认是否与参考系重合",
                })

        if rotation and len(rotation) == 9:
            # 旋转矩阵正交性检查 / Rotation matrix orthogonality check
            import math
            det = (
                rotation[0] * (rotation[4] * rotation[8] - rotation[5] * rotation[7])
                - rotation[1] * (rotation[3] * rotation[8] - rotation[5] * rotation[6])
                + rotation[2] * (rotation[3] * rotation[7] - rotation[4] * rotation[6])
            )
            if abs(abs(det) - 1.0) > 0.01:
                issues.append({
                    "severity": "critical",
                    "message": f"旋转矩阵行列式={det:.4f}，不是有效的旋转矩阵",
                })

        return {"parameters": extrinsics, "issues": issues}

    def _compute_calibration_score(self, issues: List[Dict]) -> float:
        """计算标定评分 / Compute calibration score."""
        score = 100.0
        for issue in issues:
            sev = issue.get("severity", "info")
            if sev == "critical":
                score -= 25
            elif sev == "warning":
                score -= 10
            elif sev == "info":
                score -= 2
        return max(0, score)


# =============================================================================
# 目标检测审查技能 / Object Detection Review Skill
# =============================================================================


class ObjectDetectionReviewSkill(BaseSkill):
    """
    目标检测结果分析技能。
    Object detection result analysis for autonomous driving.

    分析内容 / Analysis:
        - 检测性能评估 / Detection performance evaluation
        - 误报/漏报分析 / False positive/negative analysis
        - 远距离检测能力 / Long-range detection capability
        - 小目标检测分析 / Small object detection analysis
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="object_detection_review",
            version="1.0.0",
            category=SkillCategory.PERCEPTION,
            description="目标检测结果分析：性能评估与误报/漏报分析",
            author="Nonull",
            tags=["perception", "detection", "object", "false-positive", "evaluation"],
            input_schema={
                "type": "object",
                "properties": {
                    "detection_results": {"type": "array"},
                    "ground_truth": {"type": "array"},
                    "config": {"type": "object"},
                },
                "required": ["detection_results"],
            },
            safety_level=3,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        detections: List = context.get("detection_results", [])
        ground_truth: List = context.get("ground_truth", [])
        config: Dict = context.get("config", {})

        review_result: Dict[str, Any] = {
            "total_detections": len(detections),
            "total_ground_truth": len(ground_truth),
            "performance_metrics": self._compute_metrics(detections, ground_truth),
            "error_analysis": self._analyze_errors(detections, ground_truth),
            "range_analysis": self._analyze_by_range(detections, ground_truth),
            "recommendations": [],
            "overall_quality": "",
        }

        metrics = review_result["performance_metrics"]
        precision = metrics.get("precision", 0)
        recall = metrics.get("recall", 0)
        mAP = metrics.get("mAP", 0)

        recommendations = []
        if recall < 0.9:
            recommendations.append("召回率偏低：检查模型阈值或增加训练难例")
        if precision < 0.9:
            recommendations.append("精确率偏低：检查误报模式，考虑后处理过滤")
        if mAP < 0.7:
            recommendations.append("mAP偏低：需重新训练或更换骨干网络")

        if not recommendations:
            recommendations.append("检测性能良好")

        review_result["recommendations"] = recommendations
        review_result["overall_quality"] = (
            "优秀" if min(precision, recall) >= 0.95
            else "良好" if min(precision, recall) >= 0.85
            else "需改进"
        )

        return review_result

    def _compute_metrics(
        self, detections: List, ground_truth: List
    ) -> Dict[str, Any]:
        """计算检测指标 / Compute detection metrics."""
        tp = sum(1 for d in detections if d.get("is_true_positive", False))
        fp = sum(1 for d in detections if not d.get("is_true_positive", False))
        fn = len(ground_truth) - tp if ground_truth else 0

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        confidences = [d.get("confidence", 0) for d in detections if d.get("is_true_positive")]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0

        return {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "mAP": round(context.get("mAP", precision), 4),
            "average_confidence": round(avg_conf, 4),
        }

    def _analyze_errors(
        self, detections: List, ground_truth: List
    ) -> Dict[str, Any]:
        """分析错误模式 / Analyze error patterns."""
        error_analysis = {
            "fp_analysis": {"total_fp": 0, "by_category": {}},
            "fn_analysis": {"total_fn": 0, "by_category": {}},
        }

        fps = [d for d in detections if not d.get("is_true_positive")]
        error_analysis["fp_analysis"]["total_fp"] = len(fps)

        for fp in fps:
            cat = fp.get("category", "unknown")
            if cat not in error_analysis["fp_analysis"]["by_category"]:
                error_analysis["fp_analysis"]["by_category"][cat] = 0
            error_analysis["fp_analysis"]["by_category"][cat] += 1

        if ground_truth:
            detected_ids = set(
                d.get("match_id") for d in detections
                if d.get("is_true_positive") and d.get("match_id") is not None
            )
            for gt in ground_truth:
                gt_id = gt.get("id", gt.get("object_id"))
                if gt_id is not None and gt_id not in detected_ids:
                    error_analysis["fn_analysis"]["total_fn"] += 1
                    cat = gt.get("category", "unknown")
                    if cat not in error_analysis["fn_analysis"]["by_category"]:
                        error_analysis["fn_analysis"]["by_category"][cat] = 0
                    error_analysis["fn_analysis"]["by_category"][cat] += 1

        return error_analysis

    def _analyze_by_range(
        self, detections: List, ground_truth: List
    ) -> Dict[str, Any]:
        """按距离分析检测性能 / Analyze performance by range."""
        range_bins = {
            "close": {"max": 30, "tp": 0, "total": 0},
            "medium": {"max": 60, "tp": 0, "total": 0},
            "far": {"max": 100, "tp": 0, "total": 0},
            "extreme": {"max": float("inf"), "tp": 0, "total": 0},
        }

        for d in detections:
            dist = d.get("distance", 0) or abs(
                d.get("position", [0])[0] if isinstance(d.get("position"), list) else 0
            )
            for bin_name, bin_def in range_bins.items():
                if dist <= bin_def["max"]:
                    bin_def["total"] += 1
                    if d.get("is_true_positive"):
                        bin_def["tp"] += 1
                    break

        return {
            bin_name: {
                "detections": bin_def["total"],
                "true_positives": bin_def["tp"],
                "accuracy": round(
                    bin_def["tp"] / bin_def["total"] * 100, 1
                ) if bin_def["total"] > 0 else 0,
            }
            for bin_name, bin_def in range_bins.items()
        }
