"""
Nonull - 智驾智能体 技能系统
Nonull - Autonomous Driving AI Agent Skill System

本包提供了完整的技能系统，用于自动驾驶领域的智能体任务执行。
This package provides a complete skill system for autonomous driving agent tasks.

技能分类 / Skill Categories:
    - code:         代码审查与优化 (Code Review & Optimization)
    - perception:   感知算法分析 (Perception Algorithm Analysis)
    - planning:     规划算法评估 (Planning Algorithm Evaluation)
    - testing:      测试用例设计与执行 (Test Case Design & Execution)
    - safety:       功能安全分析 (Functional Safety Analysis)
    - simulation:   仿真场景与测试 (Simulation & Scenario Testing)
    - data:         数据流水线与日志分析 (Data Pipeline & Log Analysis)
    - research:     学术研究与前沿跟踪 (Academic Research & SOTA Tracking)
    - devops:       CI/CD与部署运维 (CI/CD & Deployment)

使用示例 / Usage Example:
    from skills.registry import SkillRegistry

    registry = SkillRegistry()
    registry.auto_discover()
    skill = registry.get_skill("code_review")
    result = skill.execute(context={"code": "..."})
"""

from skills.base import (
    SkillMetadata,
    BaseSkill,
    SkillResult,
    SkillCategory,
    SkillException,
)
from skills.registry import SkillRegistry, SkillComposition
from skills.code_skills import (
    CodeReviewSkill,
    CodeOptimizationSkill,
    RefactoringSkill,
    BugDetectionSkill,
)
from skills.perception_skills import (
    SensorAnalysisSkill,
    PerceptionModelReviewSkill,
    SensorCalibrationSkill,
    ObjectDetectionReviewSkill,
)
from skills.planning_skills import (
    RoutePlanningSkill,
    BehaviorPlanningSkill,
    TrajectoryOptimizationSkill,
)
from skills.testing_skills import (
    TestCaseDesignSkill,
    SILTestSkill,
    HILTestSkill,
    RegressionTestSkill,
)
from skills.safety_skills import (
    HazardAnalysisSkill,
    FMEASkill,
    ISO26262CheckSkill,
    SafetyCaseSkill,
)
from skills.simulation_skills import (
    ScenarioGenerationSkill,
    CARLARunnerSkill,
    EdgeCaseSkill,
)
from skills.data_skills import (
    LogAnalysisSkill,
    DataPipelineReviewSkill,
    AnnotationsQCSkill,
)
from skills.research_skills import (
    PaperAnalysisSkill,
    SOTATrackingSkill,
    AlgorithmComparisonSkill,
)
from skills.devops_skills import (
    CICDSkill,
    DeploymentSkill,
    MonitoringSkill,
)

__all__ = [
    # Base
    "SkillMetadata",
    "BaseSkill",
    "SkillResult",
    "SkillCategory",
    "SkillException",
    # Registry
    "SkillRegistry",
    "SkillComposition",
    # Code Skills
    "CodeReviewSkill",
    "CodeOptimizationSkill",
    "RefactoringSkill",
    "BugDetectionSkill",
    # Perception Skills
    "SensorAnalysisSkill",
    "PerceptionModelReviewSkill",
    "SensorCalibrationSkill",
    "ObjectDetectionReviewSkill",
    # Planning Skills
    "RoutePlanningSkill",
    "BehaviorPlanningSkill",
    "TrajectoryOptimizationSkill",
    # Testing Skills
    "TestCaseDesignSkill",
    "SILTestSkill",
    "HILTestSkill",
    "RegressionTestSkill",
    # Safety Skills
    "HazardAnalysisSkill",
    "FMEASkill",
    "ISO26262CheckSkill",
    "SafetyCaseSkill",
    # Simulation Skills
    "ScenarioGenerationSkill",
    "CARLARunnerSkill",
    "EdgeCaseSkill",
    # Data Skills
    "LogAnalysisSkill",
    "DataPipelineReviewSkill",
    "AnnotationsQCSkill",
    # Research Skills
    "PaperAnalysisSkill",
    "SOTATrackingSkill",
    "AlgorithmComparisonSkill",
    # DevOps Skills
    "CICDSkill",
    "DeploymentSkill",
    "MonitoringSkill",
]

__version__ = "1.0.0"
__author__ = "Nonull Team"
