"""
Data Skills - 数据处理技能

自动驾驶日志分析、数据流水线审查和标注质量控制。
Driving log analysis, data pipeline review, and annotation quality control.
"""

from __future__ import annotations

import re
import json
import math
import logging
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter

from skills.base import (
    BaseSkill,
    SkillMetadata,
    SkillCategory,
    SkillResult,
    SkillValidationError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 日志分析技能 / Log Analysis Skill
# =============================================================================


class LogAnalysisSkill(BaseSkill):
    """
    驾驶日志分析技能。
    Driving log analysis for autonomous driving systems.

    分析内容 / Analysis:
        - 日志级别统计 / Log level statistics
        - 错误模式识别 / Error pattern recognition
        - 时间序列分析 / Time-series analysis
        - 异常检测 / Anomaly detection
        - 性能瓶颈定位 / Performance bottleneck identification
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="log_analysis",
            version="1.0.0",
            category=SkillCategory.DATA,
            description="驾驶日志分析：错误模式识别、异常检测和性能瓶颈定位",
            author="Nonull",
            tags=["data", "log", "analysis", "anomaly", "debug"],
            input_schema={
                "type": "object",
                "properties": {
                    "log_data": {"type": "string"},
                    "log_format": {
                        "type": "string",
                        "enum": ["text", "json", "bag", "csv"],
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["error", "performance", "anomaly", "timeline", "full"],
                    },
                    "time_range": {"type": "object"},
                    "filters": {"type": "object"},
                },
                "required": ["log_data", "log_format"],
            },
            safety_level=2,
        )

    def _validate_input(self, context: Dict[str, Any]) -> None:
        if not context.get("log_data"):
            raise SkillValidationError("'log_data' is required")

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        log_data: str = context["log_data"]
        log_format: str = context["log_format"]
        analysis_type: str = context.get("analysis_type", "full")
        time_range: Optional[Dict] = context.get("time_range")
        filters: Optional[Dict] = context.get("filters", {})

        # 解析日志 / Parse logs
        if log_format == "json":
            entries = self._parse_json_logs(log_data)
        elif log_format == "csv":
            entries = self._parse_csv_logs(log_data)
        else:  # text / bag
            entries = self._parse_text_logs(log_data)

        # 应用过滤器 / Apply filters
        if filters:
            entries = self._apply_filters(entries, filters)

        # 时间范围过滤 / Time range filter
        if time_range:
            entries = self._filter_by_time(entries, time_range)

        result: Dict[str, Any] = {
            "total_entries": len(entries),
            "time_span_s": 0,
            "log_level_stats": {},
            "module_stats": {},
            "findings": [],
            "recommendations": [],
        }

        if not entries:
            return {
                **result,
                "warning": "未找到匹配的日志条目 / No matching log entries found",
            }

        # 时间跨度 / Time span
        timestamps = [e.get("timestamp", 0) for e in entries if e.get("timestamp")]
        if timestamps:
            result["time_span_s"] = round(max(timestamps) - min(timestamps), 2)

        # 执行分析 / Execute analysis
        if analysis_type in ("error", "full"):
            result["log_level_stats"] = self._level_stats(entries)
            result["error_analysis"] = self._error_pattern_analysis(entries)

        if analysis_type in ("performance", "full"):
            result["performance_analysis"] = self._performance_analysis(entries)

        if analysis_type in ("anomaly", "full"):
            result["anomaly_detection"] = self._detect_anomalies(entries)

        if analysis_type in ("timeline", "full"):
            result["timeline"] = self._build_timeline(entries)

        result["module_stats"] = self._module_stats(entries)
        result["recommendations"] = self._generate_log_recommendations(result)

        return result

    def _parse_json_logs(self, data: str) -> List[Dict]:
        """解析 JSON 格式日志 / Parse JSON format logs."""
        entries = []
        for line in data.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append({
                    "timestamp": entry.get("timestamp", entry.get("time", 0)),
                    "level": entry.get("level", entry.get("severity", "INFO")).upper(),
                    "module": entry.get("module", entry.get("logger", "unknown")),
                    "message": entry.get("message", entry.get("msg", "")),
                    "thread": entry.get("thread", ""),
                    "extra": {k: v for k, v in entry.items()
                              if k not in ("timestamp", "level", "module", "message", "thread")},
                })
            except (json.JSONDecodeError, ValueError):
                continue
        return entries

    def _parse_csv_logs(self, data: str) -> List[Dict]:
        """解析 CSV 格式日志 / Parse CSV format logs."""
        entries = []
        lines = data.strip().split("\n")
        if not lines:
            return entries
        headers = [h.strip().lower() for h in lines[0].split(",")]
        for line in lines[1:]:
            if not line.strip():
                continue
            values = line.split(",")
            entry = dict(zip(headers, values))
            entries.append({
                "timestamp": float(entry.get("timestamp", entry.get("time", 0))),
                "level": entry.get("level", "INFO").upper(),
                "module": entry.get("module", entry.get("logger", "unknown")),
                "message": entry.get("message", entry.get("msg", "")),
            })
        return entries

    def _parse_text_logs(self, data: str) -> List[Dict]:
        """解析文本格式日志 / Parse text format logs."""
        entries = []
        patterns = [
            r"\[?(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})\]?\s+"
            r"\[?(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL|WARN|FATAL)\]?\s+"
            r"\[?(?P<module>\w+)\]?\s*[-:]\s*(?P<message>.*)",
            r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*[|:]\s*"
            r"(?P<module>\w+)\s*[|:]\s*(?P<message>.*)",
        ]

        for line in data.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            for pattern in patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    entries.append({
                        "timestamp": match.group("timestamp"),
                        "level": match.group("level").upper(),
                        "module": match.group("module").lower(),
                        "message": match.group("message").strip(),
                    })
                    break
            else:
                # 无法解析的行作为 raw 条目 / Unparsable lines as raw
                if len(line) > 20:
                    entries.append({
                        "timestamp": 0,
                        "level": "RAW",
                        "module": "unknown",
                        "message": line[:200],
                    })

        return entries

    def _apply_filters(self, entries: List[Dict], filters: Dict) -> List[Dict]:
        """应用过滤器 / Apply filters."""
        filtered = list(entries)
        if "level" in filters:
            levels = [l.upper() for l in (filters["level"] if isinstance(filters["level"], list) else [filters["level"]])]
            filtered = [e for e in filtered if e.get("level") in levels]
        if "module" in filters:
            modules = filters["module"] if isinstance(filters["module"], list) else [filters["module"]]
            filtered = [e for e in filtered if e.get("module") in modules]
        if "keyword" in filters:
            kw = filters["keyword"].lower()
            filtered = [e for e in filtered if kw in e.get("message", "").lower()]
        return filtered

    def _filter_by_time(self, entries: List[Dict], time_range: Dict) -> List[Dict]:
        """按时间范围过滤 / Filter by time range."""
        t_start = time_range.get("start", 0)
        t_end = time_range.get("end", float("inf"))
        return [
            e for e in entries
            if t_start <= e.get("timestamp", 0) <= t_end
        ]

    def _level_stats(self, entries: List[Dict]) -> Dict[str, int]:
        """日志级别统计 / Log level statistics."""
        counts = Counter(e.get("level", "UNKNOWN") for e in entries)
        return dict(counts)

    def _error_pattern_analysis(self, entries: List[Dict]) -> Dict[str, Any]:
        """错误模式分析 / Error pattern analysis."""
        errors = [e for e in entries if e.get("level") in ("ERROR", "CRITICAL", "FATAL")]
        if not errors:
            return {"total_errors": 0, "patterns": [], "error_rate": 0}

        # 错误消息聚类 / Error message clustering
        error_msgs = [e["message"] for e in errors if e.get("message")]
        error_groups = Counter()
        for msg in error_msgs:
            # 使用前80字符作为分组key / Use first 80 chars as group key
            key = msg[:80]
            error_groups[key] += 1

        top_patterns = error_groups.most_common(10)

        return {
            "total_errors": len(errors),
            "error_rate": round(len(errors) / len(entries) * 100, 2) if entries else 0,
            "unique_error_patterns": len(error_groups),
            "patterns": [
                {"message": msg[:100], "count": count, "percentage": round(count / len(errors) * 100, 1)}
                for msg, count in top_patterns
            ],
        }

    def _performance_analysis(self, entries: List[Dict]) -> Dict[str, Any]:
        """性能分析 / Performance analysis."""
        perf_entries = [
            e for e in entries
            if any(kw in e.get("message", "").lower()
                   for kw in ["ms", "latency", "fps", "duration", "timeout", "hz"])
        ]

        timings = []
        for e in perf_entries:
            # 提取数值 / Extract numerical values
            nums = re.findall(r'(\d+\.?\d*)\s*ms', e.get("message", ""))
            timings.extend(float(n) for n in nums)

        return {
            "performance_related_entries": len(perf_entries),
            "max_latency_ms": max(timings) if timings else None,
            "avg_latency_ms": round(sum(timings) / len(timings), 2) if timings else None,
            "timing_samples": len(timings),
        }

    def _detect_anomalies(self, entries: List[Dict]) -> List[Dict]:
        """异常检测 / Anomaly detection."""
        anomalies = []

        # 错误突增检测 / Error burst detection
        error_entries = [e for e in entries if e.get("level") == "ERROR"]
        if len(error_entries) > len(entries) * 0.3:
            anomalies.append({
                "type": "ERROR_BURST",
                "severity": "high",
                "message": f"错误日志占比 {len(error_entries) / len(entries) * 100:.1f}%，超过30%阈值",
            })

        # 重复错误检测 / Repeated error detection
        msg_counter = Counter(e.get("message", "") for e in error_entries)
        for msg, count in msg_counter.most_common(3):
            if count > 10:
                anomalies.append({
                    "type": "REPEATED_ERROR",
                    "severity": "medium",
                    "message": f"错误消息重复 {count} 次: {msg[:80]}",
                })

        return anomalies

    def _build_timeline(self, entries: List[Dict]) -> Dict[str, Any]:
        """构建时间线 / Build timeline."""
        return {
            "start_time": entries[0].get("timestamp", "N/A") if entries else "N/A",
            "end_time": entries[-1].get("timestamp", "N/A") if entries else "N/A",
            "key_events": [
                {
                    "time": e.get("timestamp"),
                    "level": e.get("level"),
                    "module": e.get("module"),
                    "message": e.get("message", "")[:100],
                }
                for e in entries
                if e.get("level") in ("ERROR", "CRITICAL", "WARNING")
            ][:20],
        }

    def _module_stats(self, entries: List[Dict]) -> Dict[str, Any]:
        """模块统计 / Module statistics."""
        module_entries = Counter(e.get("module", "unknown") for e in entries)
        module_errors = Counter(
            e.get("module", "unknown") for e in entries
            if e.get("level") in ("ERROR", "CRITICAL")
        )

        return {
            "module_counts": dict(module_entries.most_common(10)),
            "module_error_counts": dict(module_errors.most_common(10)),
        }

    def _generate_log_recommendations(self, result: Dict) -> List[str]:
        """生成建议 / Generate recommendations."""
        recs = []
        error_analysis = result.get("error_analysis", {})
        if error_analysis.get("error_rate", 0) > 10:
            recs.append(f"错误率 {error_analysis['error_rate']}% 较高，建议重点排查")
        anomalies = result.get("anomaly_detection", [])
        for a in anomalies:
            if a.get("severity") == "high":
                recs.append(f"发现严重异常: {a['message']}")
        return recs


# =============================================================================
# 数据流水线审查技能 / Data Pipeline Review Skill
# =============================================================================


class DataPipelineReviewSkill(BaseSkill):
    """
    数据流水线审查技能。
    Data pipeline review for autonomous driving data processing.

    审查内容 / Review:
        - 数据处理流程 / Data processing workflow
        - 数据质量检查 / Data quality checks
        - 吞吐量评估 / Throughput assessment
        - 延迟分析 / Latency analysis
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="data_pipeline_review",
            version="1.0.0",
            category=SkillCategory.DATA,
            description="数据流水线审查：处理流程、数据质量和性能评估",
            author="Nonull",
            tags=["data", "pipeline", "etl", "throughput", "quality"],
            input_schema={
                "type": "object",
                "properties": {
                    "pipeline_config": {"type": "object"},
                    "data_samples": {"type": "array"},
                    "performance_metrics": {"type": "object"},
                },
                "required": ["pipeline_config"],
            },
            safety_level=1,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config: Dict = context.get("pipeline_config", {})
        samples: List = context.get("data_samples", [])
        perf: Optional[Dict] = context.get("performance_metrics")

        review_result: Dict[str, Any] = {
            "pipeline_name": config.get("name", "unnamed_pipeline"),
            "stages": [],
            "quality_assessment": {},
            "performance_assessment": {},
            "bottlenecks": [],
            "recommendations": [],
            "overall_score": 0.0,
        }

        stages = config.get("stages", [])
        for stage in stages:
            stage_review = self._review_stage(stage, perf)
            review_result["stages"].append(stage_review)
            if stage_review.get("is_bottleneck"):
                review_result["bottlenecks"].append(stage_review["name"])

        review_result["quality_assessment"] = self._assess_data_quality(samples)
        review_result["performance_assessment"] = self._assess_performance(
            config, perf
        )

        # 总体评分 / Overall score
        stage_scores = [s.get("score", 50) for s in review_result["stages"] if s.get("score") is not None]
        quality_score = review_result["quality_assessment"].get("score", 50)
        perf_score = review_result["performance_assessment"].get("score", 50)

        all_scores = stage_scores + [quality_score, perf_score]
        review_result["overall_score"] = round(
            sum(all_scores) / len(all_scores), 2
        ) if all_scores else 50.0

        return review_result

    def _review_stage(self, stage: Dict, perf: Optional[Dict]) -> Dict:
        """审查流水线阶段 / Review a pipeline stage."""
        name = stage.get("name", "unknown")
        stage_type = stage.get("type", "process")

        findings = []
        score = 80

        # 检查必要配置 / Check required config
        if stage_type == "ingestion":
            if not stage.get("source"):
                findings.append("数据源未配置")
                score -= 20
        elif stage_type == "transformation":
            if not stage.get("transformations"):
                findings.append("转换规则列表为空")
                score -= 10
        elif stage_type == "validation":
            if not stage.get("rules"):
                findings.append("验证规则未配置")
                score -= 15
        elif stage_type == "export":
            if not stage.get("destination"):
                findings.append("数据导出目标未配置")
                score -= 20

        # 性能检查 / Performance checks
        if perf and name in perf:
            stage_perf = perf[name]
            if stage_perf.get("latency_ms", 0) > 1000:
                findings.append(f"阶段延迟 {stage_perf['latency_ms']}ms 偏高")
                score -= 10

        return {
            "name": name,
            "type": stage_type,
            "score": max(0, score),
            "findings": findings,
            "is_bottleneck": score < 60,
        }

    def _assess_data_quality(self, samples: List) -> Dict[str, Any]:
        """评估数据质量 / Assess data quality."""
        if not samples:
            return {"score": 50, "issues": ["无数据样本可评估"]}

        issues = []
        missing_fields = 0
        total_fields = 0

        for sample in samples:
            if isinstance(sample, dict):
                for key, value in sample.items():
                    total_fields += 1
                    if value is None or (isinstance(value, str) and not value.strip()):
                        missing_fields += 1

        completeness = (
            (total_fields - missing_fields) / total_fields * 100
            if total_fields > 0 else 100
        )
        if completeness < 80:
            issues.append(f"数据完整度 {completeness:.1f}% 偏低")

        score = min(100, completeness)

        return {
            "score": round(score, 2),
            "samples_checked": len(samples),
            "completeness_pct": round(completeness, 2),
            "issues": issues,
        }

    def _assess_performance(
        self, config: Dict, perf: Optional[Dict]
    ) -> Dict[str, Any]:
        """评估性能 / Assess performance."""
        if not perf:
            return {"score": 50, "message": "无性能数据", "throughput_mbps": None}

        total_latency = sum(
            stage.get("latency_ms", 0) for stage in perf.values()
        ) if isinstance(perf, dict) else 0
        throughput = perf.get("throughput_mbps") if isinstance(perf, dict) else None

        score = 80
        if total_latency > 5000:
            score -= 20
        if throughput and throughput < 10:
            score -= 15

        return {
            "score": score,
            "total_latency_ms": total_latency,
            "throughput_mbps": throughput,
            "message": f"延迟 {total_latency}ms, 吞吐 {throughput or 'N/A'} Mbps",
        }


# =============================================================================
# 标注质量控制技能 / Annotations QC Skill
# =============================================================================


class AnnotationsQCSkill(BaseSkill):
    """
    标注质量控制技能。
    Annotation quality control for autonomous driving datasets.

    检查内容 / Checks:
        - 标注完整性 / Annotation completeness
        - 标注一致性 / Annotation consistency
        - 标注精度 / Annotation accuracy
        - 边界质量 / Boundary quality
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="annotations_qc",
            version="1.0.0",
            category=SkillCategory.DATA,
            description="标注质量控制：完整性、一致性和精度检查",
            author="Nonull",
            tags=["data", "annotation", "quality-control", "dataset", "label"],
            input_schema={
                "type": "object",
                "properties": {
                    "annotations": {"type": "array"},
                    "task_type": {
                        "type": "string",
                        "enum": ["detection", "tracking", "segmentation", "classification"],
                    },
                    "qc_thresholds": {"type": "object"},
                },
                "required": ["annotations", "task_type"],
            },
            safety_level=1,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        annotations: List = context.get("annotations", [])
        task_type: str = context["task_type"]
        thresholds: Dict = context.get("qc_thresholds", {})

        if not annotations:
            return {
                "total_annotations": 0,
                "qc_passed": False,
                "issues": ["无标注数据 / No annotation data"],
                "quality_score": 0,
            }

        # 各维度检查 / Multi-dimensional checks
        completeness = self._check_completeness(annotations, task_type)
        consistency = self._check_consistency(annotations, task_type)
        accuracy = self._check_accuracy(annotations, task_type)

        all_issues = (
            completeness.get("issues", [])
            + consistency.get("issues", [])
            + accuracy.get("issues", [])
        )

        # 总评分 / Total score
        quality_score = round(
            0.3 * completeness.get("score", 50)
            + 0.35 * consistency.get("score", 50)
            + 0.35 * accuracy.get("score", 50),
            2,
        )

        pass_threshold = thresholds.get("pass_threshold", 80)
        qc_passed = quality_score >= pass_threshold

        return {
            "task_type": task_type,
            "total_annotations": len(annotations),
            "quality_score": quality_score,
            "qc_passed": qc_passed,
            "dimension_scores": {
                "completeness": completeness.get("score", 0),
                "consistency": consistency.get("score", 0),
                "accuracy": accuracy.get("score", 0),
            },
            "issues": all_issues,
            "summary": f"质量评分 {quality_score}/100 - {'通过' if qc_passed else '未通过'}",
            "recommendations": self._generate_qc_recommendations(all_issues),
        }

    def _check_completeness(
        self, annotations: List, task_type: str
    ) -> Dict[str, Any]:
        """检查标注完整性 / Check annotation completeness."""
        issues = []
        missing_fields = 0
        total = len(annotations)

        required_fields = {
            "detection": ["bbox", "category"],
            "tracking": ["bbox", "category", "track_id"],
            "segmentation": ["segmentation", "category"],
            "classification": ["category"],
        }

        fields = required_fields.get(task_type, ["category"])

        for ann in annotations:
            if isinstance(ann, dict):
                for field in fields:
                    if field not in ann or ann[field] is None:
                        missing_fields += 1

        completeness_score = max(
            0, 100 - (missing_fields / max(1, total * len(fields))) * 100
        )

        if missing_fields > 0:
            issues.append(f"缺少 {missing_fields} 个必要字段")

        return {"score": round(completeness_score, 2), "issues": issues}

    def _check_consistency(
        self, annotations: List, task_type: str
    ) -> Dict[str, Any]:
        """检查标注一致性 / Check annotation consistency."""
        issues = []
        inconsistencies = 0

        # 分类标签一致性 / Category label consistency
        categories = []
        for ann in annotations:
            if isinstance(ann, dict):
                cat = ann.get("category")
                if cat:
                    categories.append(cat)

        if categories:
            cat_counts = Counter(categories)
            # 检查未知类别 / Check unknown categories
            standard_cats = {
                "car", "truck", "bus", "pedestrian", "cyclist",
                "motorcycle", "traffic_light", "traffic_sign", "unknown",
            }
            for cat in cat_counts:
                if cat.lower() not in standard_cats:
                    inconsistencies += 1
                    issues.append(f"非标准类别: {cat}")

        # 尺寸一致性 / Size consistency
        for ann in annotations:
            if isinstance(ann, dict):
                bbox = ann.get("bbox", [])
                if len(bbox) == 4:
                    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    if w <= 0 or h <= 0:
                        inconsistencies += 1
                        issues.append(f"无效边界框: width={w}, height={h}")

        consistency_score = max(
            0, 100 - inconsistencies * 10
        )

        return {"score": round(consistency_score, 2), "issues": issues}

    def _check_accuracy(
        self, annotations: List, task_type: str
    ) -> Dict[str, Any]:
        """检查标注精度 / Check annotation accuracy."""
        issues = []
        total_checks = 0
        failed_checks = 0

        for ann in annotations:
            if not isinstance(ann, dict):
                continue

            # 检查坐标有效性 / Coordinate validity
            bbox = ann.get("bbox", [])
            if len(bbox) == 4:
                total_checks += 1
                x1, y1, x2, y2 = bbox
                if x2 <= x1 or y2 <= y1:
                    failed_checks += 1

            # 检查分割掩码 / Segmentation mask check
            seg = ann.get("segmentation", [])
            if seg:
                total_checks += 1
                if isinstance(seg, list) and len(seg) < 6:
                    failed_checks += 1
                    issues.append("分割多边形点数不足 (< 3)")

            # 检查类别置信度 / Category confidence check
            conf = ann.get("confidence", 1.0)
            total_checks += 1
            if conf <= 0 or conf > 1:
                failed_checks += 1
                issues.append(f"置信度超出范围: {conf}")

        accuracy_score = (
            max(0, 100 - (failed_checks / max(1, total_checks)) * 100)
            if total_checks > 0 else 100
        )

        return {"score": round(accuracy_score, 2), "issues": issues}

    def _generate_qc_recommendations(self, issues: List) -> List[str]:
        """生成建议 / Generate recommendations."""
        if not issues:
            return ["标注质量良好 / Annotation quality is good"]
        return issues[:5]
