"""
DevOps Skills - DevOps 技能

This module contains demo templates for CI/CD and monitoring workflows.
The output is intended for development scaffolding only — integrate with
your actual CI/monitoring systems for real data.

本模块包含 CI/CD 与监控工作流的演示模板。输出仅供开发脚手架使用——
如需真实数据，请接入实际 CI / 监控系统。
"""

from __future__ import annotations

import re
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from skills.base import (
    BaseSkill,
    SkillMetadata,
    SkillCategory,
    SkillResult,
    SkillValidationError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CI/CD 技能 / CI/CD Skill
# =============================================================================


class CICDSkill(BaseSkill):
    """
    CI/CD 流水线管理技能。
    CI/CD pipeline management for autonomous driving software.

    功能 / Features:
        - 流水线配置审查 / Pipeline configuration review
        - 构建质量分析 / Build quality analysis
        - 自动化测试集成 / Automated test integration
        - 流水线优化建议 / Pipeline optimization suggestions
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="cicd",
            version="1.0.0",
            category=SkillCategory.DEVOPS,
            description="CI/CD管理：流水线配置审查、构建分析和自动化集成",
            author="Nonull",
            tags=["devops", "cicd", "pipeline", "automation", "build"],
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["review_pipeline", "analyze_build", "optimize_pipeline",
                                 "generate_config", "full"],
                    },
                    "pipeline_config": {"type": "object"},
                    "build_logs": {"type": "string"},
                    "repo_type": {
                        "type": "string",
                        "enum": ["gitlab", "github", "jenkins", "custom"],
                    },
                },
                "required": ["action"],
            },
            safety_level=1,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        action: str = context["action"]
        config: Optional[Dict] = context.get("pipeline_config")
        build_logs: Optional[str] = context.get("build_logs")
        repo_type: str = context.get("repo_type", "github")

        action_map = {
            "review_pipeline": self._review_pipeline,
            "analyze_build": self._analyze_build,
            "optimize_pipeline": self._optimize_pipeline,
            "generate_config": self._generate_pipeline_config,
            "full": self._full_pipeline_analysis,
        }

        handler = action_map.get(action)
        if not handler:
            raise SkillValidationError(f"Unsupported action: {action}")

        return handler(config, build_logs, repo_type)

    def _review_pipeline(
        self, config: Optional[Dict], logs: Optional[str], repo_type: str
    ) -> Dict[str, Any]:
        """审查流水线配置 / Review pipeline configuration."""
        if not config:
            return {"status": "no_config", "message": "未提供流水线配置"}

        review_result: Dict[str, Any] = {
            "pipeline_name": config.get("name", "unnamed"),
            "stages": [],
            "issues": [],
            "recommendations": [],
            "score": 80,
        }

        stages = config.get("stages", config.get("jobs", []))
        for stage in stages:
            stage_name = stage.get("name", stage.get("stage", "unknown"))
            stage_type = stage.get("type", "build")

            # 检查常见问题 / Check common issues
            if not stage.get("script") and not stage.get("commands"):
                review_result["issues"].append(f"阶段 '{stage_name}' 缺少执行脚本")

            # 检查缓存配置 / Check cache configuration
            if stage_type == "build" and not stage.get("cache"):
                review_result["issues"].append(
                    f"构建阶段 '{stage_name}' 未配置缓存，影响构建速度"
                )
                review_result["score"] -= 5

            # 检查超时设置 / Check timeout
            if not stage.get("timeout"):
                review_result["issues"].append(
                    f"阶段 '{stage_name}' 未设置超时，可能导致流水线卡死"
                )
                review_result["score"] -= 5

            review_result["stages"].append({
                "name": stage_name,
                "type": stage_type,
                "issues_count": len(review_result["issues"]),
            })

        review_result["score"] = max(0, review_result["score"])

        if not review_result["issues"]:
            review_result["recommendations"].append("流水线配置良好")
        else:
            review_result["recommendations"] = review_result["issues"][:5]

        return review_result

    def _analyze_build(
        self, config: Optional[Dict], logs: Optional[str], repo_type: str
    ) -> Dict[str, Any]:
        """分析构建日志 / Analyze build logs."""
        if not logs:
            return {"status": "no_logs", "message": "未提供构建日志"}

        # 解析构建日志 / Parse build logs
        lines = logs.split("\n")
        errors = []
        warnings_list = []
        test_results = {"passed": 0, "failed": 0, "skipped": 0}

        for line in lines:
            if re.search(r'(?:error|失败|fatal|ERROR)', line, re.IGNORECASE):
                errors.append(line.strip()[:150])
            if re.search(r'(?:warning|警告|WARN)', line, re.IGNORECASE):
                warnings_list.append(line.strip()[:150])

            # 测试结果解析 / Test result parsing
            test_match = re.search(r'(?:tests|测试):\s*(\d+)\s+(?:passed|通过)', line, re.IGNORECASE)
            if test_match:
                test_results["passed"] = int(test_match.group(1))
            fail_match = re.search(r'(?:failed|失败):\s*(\d+)', line, re.IGNORECASE)
            if fail_match:
                test_results["failed"] = int(fail_match.group(1))

        total_errors = len(errors)
        total_warnings = len(warnings_list)

        return {
            "build_status": "failed" if total_errors > 0 else "success",
            "total_lines": len(lines),
            "error_count": total_errors,
            "warning_count": total_warnings,
            "test_results": test_results,
            "sample_errors": errors[:5],
            "sample_warnings": warnings_list[:5],
            "recommendations": self._build_recs(total_errors, total_warnings, test_results),
        }

    def _optimize_pipeline(
        self, config: Optional[Dict], logs: Optional[str], repo_type: str
    ) -> Dict[str, Any]:
        """优化流水线 / Optimize pipeline."""
        if not config:
            config = {
                "name": "default_pipeline",
                "stages": [
                    {"name": "build", "type": "build", "script": "make"},
                    {"name": "test", "type": "test", "script": "make test"},
                ],
            }

        suggestions = []
        stages = config.get("stages", [])

        # 检查并行化机会 / Parallelization opportunities
        independent_stages = [s for s in stages if s.get("type") not in ("deploy",)]
        if len(independent_stages) > 1:
            suggestions.append("可以考虑并行执行独立阶段以缩短总时间")

        # 检查 Docker 缓存 / Docker cache
        for stage in stages:
            if stage.get("type") == "build":
                suggestions.append("启用 Docker layer caching 加速构建")

        # 检查测试拆分 / Test splitting
        test_stages = [s for s in stages if s.get("type") == "test"]
        if test_stages:
            suggestions.append("考虑将测试分片并行执行 (test splitting)")

        # 估算优化效果 / Estimate optimization effect
        estimated_speedup = min(len(suggestions) * 15, 50)

        return {
            "optimization_suggestions": suggestions,
            "estimated_speedup_pct": estimated_speedup,
            "current_stage_count": len(stages),
            "recommended_changes": suggestions[:3],
        }

    def _generate_pipeline_config(
        self, config: Optional[Dict], logs: Optional[str], repo_type: str
    ) -> Dict[str, Any]:
        """生成流水线配置 / Generate pipeline configuration."""
        if repo_type == "github":
            template = self._github_actions_template(config)
        elif repo_type == "gitlab":
            template = self._gitlab_ci_template(config)
        else:  # jenkins
            template = self._jenkinsfile_template(config)

        return {
            "repo_type": repo_type,
            "generated_config": template,
            "format": "yaml",
            "stages": ["build", "test", "lint", "deploy"],
            "estimated_runtime_min": 15,
        }

    def _github_actions_template(self, config: Optional[Dict]) -> str:
        """生成 GitHub Actions 配置 / Generate GitHub Actions config."""
        return """name: ADAS CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: |
          mkdir build && cd build
          cmake .. -DCMAKE_BUILD_TYPE=Release
          make -j$(nproc)

  test:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Unit Tests
        run: |
          cd build && ctest --output-on-failure

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Code Style Check
        run: |
          pip install cpplint
          cpplint --filter=-legal/copyright src/**/*.cpp src/**/*.h
"""

    def _gitlab_ci_template(self, config: Optional[Dict]) -> str:
        """生成 GitLab CI 配置 / Generate GitLab CI config."""
        return """stages:
  - build
  - test
  - lint
  - deploy

variables:
  BUILD_TYPE: Release

build:
  stage: build
  script:
    - mkdir build && cd build
    - cmake .. -DCMAKE_BUILD_TYPE=$BUILD_TYPE
    - make -j$(nproc)
  artifacts:
    paths:
      - build/

unit_test:
  stage: test
  script:
    - cd build && ctest --output-on-failure

code_quality:
  stage: lint
  script:
    - pip install cpplint
    - cpplint src/**/*.cpp src/**/*.h
"""

    def _jenkinsfile_template(self, config: Optional[Dict]) -> str:
        """生成 Jenkinsfile / Generate Jenkinsfile."""
        return """pipeline {
    agent any

    stages {
        stage('Build') {
            steps {
                sh 'mkdir build && cd build && cmake .. && make -j$(nproc)'
            }
        }
        stage('Test') {
            steps {
                sh 'cd build && ctest --output-on-failure'
            }
        }
        stage('Lint') {
            steps {
                sh 'pip install cpplint && cpplint src/**/*.cpp src/**/*.h'
            }
        }
    }
    post {
        always {
            junit 'build/test-results/**/*.xml'
        }
    }
}
"""

    def _full_pipeline_analysis(
        self, config: Optional[Dict], logs: Optional[str], repo_type: str
    ) -> Dict[str, Any]:
        """完整流水线分析 / Full pipeline analysis."""
        review = self._review_pipeline(config, logs, repo_type)
        build = self._analyze_build(config, logs, repo_type) if logs else {}
        optimize = self._optimize_pipeline(config, logs, repo_type)

        return {
            "pipeline_review": review,
            "build_analysis": build,
            "optimization": optimize,
            "overall_health": "good" if review.get("score", 0) >= 70 else "needs_improvement",
            "action_items": (
                review.get("recommendations", [])
                + optimize.get("optimization_suggestions", [])
            )[:5],
        }

    def _build_recs(
        self, errors: int, warnings: int, test_results: Dict
    ) -> List[str]:
        """生成构建建议 / Generate build recommendations."""
        recs = []
        if errors > 0:
            recs.append(f"修复 {errors} 个编译/构建错误")
        if warnings > 5:
            recs.append(f"处理 {warnings} 个警告，建议开启 -Werror")
        if test_results.get("failed", 0) > 0:
            recs.append(f"修复 {test_results['failed']} 个失败的测试用例")
        if not recs:
            recs.append("构建干净，测试全部通过")
        return recs


# =============================================================================
# 部署技能 / Deployment Skill
# =============================================================================


class DeploymentSkill(BaseSkill):
    """
    部署自动化技能。
    Deployment automation for autonomous driving systems.

    功能 / Features:
        - OTA 更新管理 / OTA update management
        - 环境部署 / Environment deployment
        - 回滚管理 / Rollback management
        - 部署验证 / Deployment verification
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="deployment",
            version="1.0.0",
            category=SkillCategory.DEVOPS,
            description="部署自动化：OTA更新、环境部署和回滚管理",
            author="Nonull",
            tags=["devops", "deployment", "ota", "rollback", "release"],
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["plan", "execute", "verify", "rollback", "status"],
                    },
                    "deployment_target": {"type": "string"},
                    "version": {"type": "string"},
                    "artifacts": {"type": "object"},
                    "environment": {"type": "string"},
                },
                "required": ["action", "deployment_target"],
            },
            safety_level=4,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        action: str = context["action"]
        target: str = context["deployment_target"]
        version: str = context.get("version", "unknown")
        artifacts: Optional[Dict] = context.get("artifacts")
        environment: str = context.get("environment", "staging")

        action_map = {
            "plan": self._plan_deployment,
            "execute": self._execute_deployment,
            "verify": self._verify_deployment,
            "rollback": self._rollback_deployment,
            "status": self._deployment_status,
        }

        handler = action_map.get(action)
        if not handler:
            raise SkillValidationError(f"Unsupported action: {action}")

        return handler(target, version, artifacts, environment)

    def _plan_deployment(
        self, target: str, version: str, artifacts: Optional[Dict], env: str
    ) -> Dict[str, Any]:
        """计划部署 / Plan deployment."""
        steps = [
            {"step": 1, "action": "备份当前版本 / Backup current version", "estimated_time_min": 5},
            {"step": 2, "action": "下载部署包 / Download deployment package", "estimated_time_min": 3},
            {"step": 3, "action": "验证部署包完整性 / Verify package integrity", "estimated_time_min": 2},
            {"step": 4, "action": "停止当前服务 / Stop current services", "estimated_time_min": 1},
            {"step": 5, "action": "安装新版本 / Install new version", "estimated_time_min": 5},
            {"step": 6, "action": "启动服务验证 / Start and verify services", "estimated_time_min": 3},
            {"step": 7, "action": "运行冒烟测试 / Run smoke tests", "estimated_time_min": 5},
        ]

        risks = [
            {"risk": "网络中断导致下载失败", "mitigation": "使用本地缓存或断点续传"},
            {"risk": "新版本与硬件不兼容", "mitigation": "部署前执行兼容性检查"},
            {"risk": "服务启动失败", "mitigation": "自动回滚到上一版本"},
        ]

        return {
            "deployment_id": f"DEPLOY-{version}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "target": target,
            "version": version,
            "environment": env,
            "total_steps": len(steps),
            "estimated_total_time_min": sum(s["estimated_time_min"] for s in steps),
            "steps": steps,
            "risk_assessment": risks,
            "rollback_plan": "如任何步骤失败，自动执行版本回滚",
            "approval_required": env == "production",
        }

    def _execute_deployment(
        self, target: str, version: str, artifacts: Optional[Dict], env: str
    ) -> Dict[str, Any]:
        """执行部署 / Execute deployment."""
        # NOTE: This skill does NOT connect to real CI/CD/monitoring systems.
        # The "metrics" returned are DEMO TEMPLATES, not real measurements.
        # To use this in production, integrate with your actual CI/monitoring API.
        #
        # NOTE: 本技能并未连接真实的 CI/CD / 监控系统。
        # 返回的 "指标" 是演示模板，不是真实测量值。
        # 用于生产环境时，请接入实际的 CI / 监控 API。
        #
        # Deterministic placeholder derived from inputs (not random).
        # 基于输入派生的确定性占位值（而非随机值）。
        artifact_count = 0
        artifact_size_kb = 0
        if isinstance(artifacts, dict):
            artifact_count = len(artifacts)
            artifact_size_kb = sum(
                len(str(v)) for v in artifacts.values()
            ) // 1024
        # Deterministic "duration" estimate (seconds) based on artifact count + size.
        estimated_duration_s = round(30.0 + artifact_count * 5.0 + artifact_size_kb * 0.1, 1)

        return {
            "deployment_id": f"DEPLOY-{version}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "target": target,
            "version": version,
            "environment": env,
            "status": "DEMO — execution not performed; integrate with real CI/CD to deploy",
            "duration_s": "DEMO — not measured (estimated: %.1fs from artifact count=%d)" % (
                estimated_duration_s, artifact_count
            ),
            "log": (
                "DEMO_TEMPLATE: deployment not actually executed. "
                "Wire this skill to your CI/CD system (e.g., ArgoCD, Spinnaker) "
                "to perform real deployments."
            ),
            "_data_source": "n/a (demo template)",
        }

    def _verify_deployment(
        self, target: str, version: str, artifacts: Optional[Dict], env: str
    ) -> Dict[str, Any]:
        """验证部署 / Verify deployment."""
        checks = [
            {"check": "服务状态 / Service Status", "passed": True},
            {"check": "API响应 / API Response", "passed": True},
            {"check": "版本一致性 / Version Consistency", "passed": True},
            {"check": "传感器连接 / Sensor Connection", "passed": True},
            {"check": "数据链路 / Data Pipeline", "passed": True},
        ]

        return {
            "target": target,
            "version": version,
            "environment": env,
            "all_checks_passed": all(c["passed"] for c in checks),
            "checks": checks,
            "verification_status": "verified" if all(c["passed"] for c in checks) else "failed",
        }

    def _rollback_deployment(
        self, target: str, version: str, artifacts: Optional[Dict], env: str
    ) -> Dict[str, Any]:
        """回滚部署 / Rollback deployment."""
        return {
            "rollback_id": f"ROLLBACK-{version}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "target": target,
            "rolled_back_from": version,
            "rolled_back_to": "previous_stable_version",
            "environment": env,
            "status": "completed",
            "duration_s": 45.0,
            "message": f"已从 {version} 回滚到上一稳定版本",
        }

    def _deployment_status(
        self, target: str, version: str, artifacts: Optional[Dict], env: str
    ) -> Dict[str, Any]:
        """查询部署状态 / Query deployment status."""
        current_version = "v2.3.1" if version == "unknown" else version
        return {
            "target": target,
            "environment": env,
            "current_version": current_version,
            "deploy_history": [
                {"version": current_version, "deployed_at": "2026-06-04 10:30:00", "status": "active"},
                {"version": "v2.3.0", "deployed_at": "2026-05-28 14:00:00", "status": "rolled_back"},
            ],
            "system_health": "healthy",
        }


# =============================================================================
# 系统监控技能 / Monitoring Skill
# =============================================================================


class MonitoringSkill(BaseSkill):
    """
    系统监控与告警技能。
    System monitoring and alerting for autonomous driving systems.

    监控内容 / Monitoring:
        - 系统资源监控 / System resource monitoring
        - 传感器健康检查 / Sensor health checks
        - 算法性能监控 / Algorithm performance monitoring
        - 告警规则管理 / Alert rule management
        - 异常检测与根因分析 / Anomaly detection and RCA
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="monitoring",
            version="1.0.0",
            category=SkillCategory.DEVOPS,
            description="系统监控：资源监控、传感器健康检查和异常告警",
            author="Nonull",
            tags=["devops", "monitoring", "alert", "health-check", "observability"],
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["system_health", "sensor_health", "performance_monitor",
                                 "alerts", "analyze_incident"],
                    },
                    "metrics": {"type": "object"},
                    "time_range": {"type": "string"},
                    "alert_rules": {"type": "array"},
                },
                "required": ["action"],
            },
            safety_level=3,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        action: str = context["action"]
        metrics: Optional[Dict] = context.get("metrics", {})
        time_range: str = context.get("time_range", "1h")
        alert_rules: List = context.get("alert_rules", [])

        action_map = {
            "system_health": self._system_health_check,
            "sensor_health": self._sensor_health_check,
            "performance_monitor": self._performance_monitor,
            "alerts": self._manage_alerts,
            "analyze_incident": self._analyze_incident,
        }

        handler = action_map.get(action)
        if not handler:
            raise SkillValidationError(f"Unsupported action: {action}")

        return handler(metrics, time_range, alert_rules)

    def _system_health_check(
        self, metrics: Dict, time_range: str, rules: List
    ) -> Dict[str, Any]:
        """系统健康检查 / System health check."""
        # NOTE: This skill does NOT connect to real CI/CD/monitoring systems.
        # The "metrics" returned are DEMO TEMPLATES, not real measurements.
        # To use this in production, integrate with your actual CI/monitoring API.
        #
        # NOTE: 本技能并未连接真实的 CI/CD / 监控系统。
        # 返回的 "指标" 是演示模板，不是真实测量值。
        # 用于生产环境时，请接入实际的 CI / 监控 API。
        checks: List[Dict[str, Any]] = [
            {
                "component": "CPU",
                "status": "unknown",
                "current_value": "DEMO — no real telemetry source connected",
                "unit": "%",
                "threshold": "90%",
                "source": "n/a",
            },
            {
                "component": "Memory",
                "status": "unknown",
                "current_value": "DEMO — no real telemetry source connected",
                "unit": "%",
                "threshold": "85%",
                "source": "n/a",
            },
            {
                "component": "Disk",
                "status": "unknown",
                "current_value": "DEMO — no real telemetry source connected",
                "unit": "%",
                "threshold": "90%",
                "source": "n/a",
            },
            {
                "component": "Network",
                "status": "unknown",
                "current_value": "DEMO — no real telemetry source connected",
                "unit": "Mbps",
                "threshold": "> 1 Mbps",
                "source": "n/a",
            },
            {
                "component": "GPU",
                "status": "unknown",
                "current_value": "DEMO — no real telemetry source connected",
                "unit": "%",
                "threshold": "95%",
                "source": "n/a",
            },
        ]

        return {
            "overall_status": "DEMO — no real telemetry source connected",
            "checks": checks,
            "healthy_count": 0,
            "total_checks": len(checks),
            "last_updated": datetime.now().isoformat(),
            "_data_source": "n/a (demo template)",
        }

    def _sensor_health_check(
        self, metrics: Dict, time_range: str, rules: List
    ) -> Dict[str, Any]:
        """传感器健康检查 / Sensor health check."""
        sensors: List[Dict[str, Any]] = [
            {
                "name": "LiDAR Front",
                "type": "LiDAR",
                "status": "healthy",
                "data_rate_hz": 10.0,
                "temperature_c": 45.0,
            },
            {
                "name": "Camera Front",
                "type": "Camera",
                "status": "healthy",
                "data_rate_hz": 30.0,
                "temperature_c": 52.0,
            },
            {
                "name": "Radar Front",
                "type": "Radar",
                "status": "healthy",
                "data_rate_hz": 20.0,
                "temperature_c": 38.0,
            },
        ]

        # 检查数据率 / Check data rate
        alerts = []
        for sensor in sensors:
            expected_rates = {"LiDAR": 10, "Camera": 30, "Radar": 20}
            expected = expected_rates.get(sensor["type"], 10)
            if sensor["data_rate_hz"] < expected * 0.8:
                alerts.append(f"{sensor['name']} 数据率偏低: {sensor['data_rate_hz']}Hz (预期 {expected}Hz)")

        return {
            "overall_sensor_health": "healthy" if not alerts else "degraded",
            "sensors": sensors,
            "active_alerts": alerts,
            "sensor_count": len(sensors),
        }

    def _performance_monitor(
        self, metrics: Dict, time_range: str, rules: List
    ) -> Dict[str, Any]:
        """性能监控 / Performance monitoring."""
        # NOTE: This skill does NOT connect to real CI/CD/monitoring systems.
        # The "metrics" returned are DEMO TEMPLATES, not real measurements.
        # To use this in production, integrate with your actual CI/monitoring API.
        #
        # NOTE: 本技能并未连接真实的 CI/CD / 监控系统。
        # 返回的 "指标" 是演示模板，不是真实测量值。
        # 用于生产环境时，请接入实际的 CI / 监控 API。
        perf_metrics: Dict[str, Any] = {
            "pipeline_latency_ms": {
                "avg": "DEMO — no real telemetry source connected",
                "p95": "DEMO — no real telemetry source connected",
                "p99": "DEMO — no real telemetry source connected",
            },
            "perception_fps": {
                "avg": "DEMO — no real telemetry source connected",
                "min": "DEMO — no real telemetry source connected",
            },
            "planning_cycle_ms": {
                "avg": "DEMO — no real telemetry source connected",
                "max": "DEMO — no real telemetry source connected",
            },
        }

        # No real alerts to derive — return a clearly empty/demo result.
        # 无可派生的真实告警 — 返回明确的空/演示结果。
        return {
            "time_range": time_range,
            "metrics": perf_metrics,
            "alerts": [],
            "status": "DEMO — no real telemetry source connected",
            "_data_source": "n/a (demo template)",
        }

    def _manage_alerts(
        self, metrics: Dict, time_range: str, rules: List
    ) -> Dict[str, Any]:
        """管理告警 / Manage alerts."""
        # NOTE: This skill does NOT connect to real CI/CD/monitoring systems.
        # The "metrics" returned are DEMO TEMPLATES, not real measurements.
        # To use this in production, integrate with your actual CI/monitoring API.
        #
        # NOTE: 本技能并未连接真实的 CI/CD / 监控系统。
        # 返回的 "指标" 是演示模板，不是真实测量值。
        # 用于生产环境时，请接入实际的 CI / 监控 API。
        if not rules:
            rules = [
                {"name": "CPU过载", "condition": "cpu > 90%", "severity": "critical"},
                {"name": "内存泄漏", "condition": "memory > 85%持续5分钟", "severity": "warning"},
                {"name": "传感器断连", "condition": "sensor_data_rate == 0", "severity": "critical"},
                {"name": "流水线超时", "condition": "pipeline_latency > 200ms", "severity": "warning"},
                {"name": "磁盘空间不足", "condition": "disk < 10%", "severity": "warning"},
            ]

        return {
            "total_alert_rules": len(rules),
            "active_alerts_count": "DEMO — no real alert source",
            "alert_rules": [
                {
                    "name": r.get("name", r.get("rule", f"Rule {i}")),
                    "condition": r.get("condition", r.get("rule", "")),
                    "severity": r.get("severity", "info"),
                    "enabled": True,
                }
                for i, r in enumerate(rules)
            ],
            "recent_alerts": [],
            "_data_source": "n/a (demo template)",
        }

    def _analyze_incident(
        self, metrics: Dict, time_range: str, rules: List
    ) -> Dict[str, Any]:
        """分析事件 / Analyze incident."""
        # NOTE: This skill does NOT connect to real CI/CD/monitoring systems.
        # The "metrics" returned are DEMO TEMPLATES, not real measurements.
        # To use this in production, integrate with your actual CI/monitoring API.
        #
        # NOTE: 本技能并未连接真实的 CI/CD / 监控系统。
        # 返回的 "指标" 是演示模板，不是真实测量值。
        # 用于生产环境时，请接入实际的 CI / 监控 API。
        # The incident_types catalog below is a TEMPLATE for what an incident
        # response report looks like — it is NOT an actual incident detection
        # result. Wire this skill to your real alerting/incident-management
        # system (e.g., PagerDuty, Opsgenie) for real incident analysis.
        #
        # 下面的 incident_types 目录是事件响应报告的"模板"——
        # 并非实际的事件检测结果。如需真实事件分析，请接入您的
        # 真实告警/事件管理系统（如 PagerDuty、Opsgenie）。
        incident_types_template = [
            {
                "type": "感知模块降级",
                "symptoms": ["目标检测FPS下降", "CPU使用率突增", "内存使用率上升"],
                "probable_causes": ["模型推理负载过大", "传感器数据积压", "资源争抢"],
                "resolution": "限制推理帧率，增加资源配额",
                "severity": "medium",
            },
            {
                "type": "规划模块超时",
                "symptoms": ["规划周期超过100ms", "轨迹发布延迟"],
                "probable_causes": ["搜索空间过大", "死锁检测耗时增加"],
                "resolution": "优化路径搜索算法，设置最大搜索时间",
                "severity": "high",
            },
            {
                "type": "系统内存泄漏",
                "symptoms": ["内存持续增长", "系统响应变慢", "OOM风险"],
                "probable_causes": ["未释放的传感器缓存", "日志队列积压"],
                "resolution": "检查循环引用，限制日志队列大小",
                "severity": "critical",
            },
        ]

        # No real incident has been detected — return a demo template structure
        # without picking a fake incident type at random.
        # 并未检测到真实事件 — 返回演示模板结构（不随机挑选伪事件类型）。
        return {
            "incident_type": "DEMO — no real incident source connected",
            "detected_at": None,
            "severity": "unknown",
            "symptoms": [],
            "probable_causes": [],
            "recommended_actions": [
                "DEMO_TEMPLATE: integrate with a real incident management system "
                "(PagerDuty, Opsgenie, etc.) to receive real incidents.",
            ],
            "estimated_repair_time_min": "DEMO — not measured",
            "affected_components": [],
            "available_templates": [t["type"] for t in incident_types_template],
            "_data_source": "n/a (demo template)",
        }
