"""
Nonull - Skill System (backward-compat shim)
============================================

P15 NOTE — Domain Abstraction Refactor
--------------------------------------
The ADAS-specific skills have been **moved** to ``domains/adas/skills/``::

    skills/perception_skills.py  ->  domains/adas/skills/perception.py
    skills/planning_skills.py    ->  domains/adas/skills/planning.py
    skills/safety_skills.py      ->  domains/adas/skills/safety.py
    skills/simulation_skills.py  ->  domains/adas/skills/simulation.py

Generic skills (code/data/devops/research/testing) still live under
``skills/`` because they are domain-agnostic.

This module remains so that older code (and ``tests/test_all_skills_smoke.py``,
which enumerates skills by name from the registry) keeps working. All
moved symbols are re-exported **lazily** via ``__getattr__`` so that
``import skills`` doesn't force the full ADAS skills import chain.

The ``SkillRegistry.auto_discover()`` mechanism is unchanged — it
discovers whatever ``BaseSkill`` subclasses it can import, and that
includes the new ``domains.adas.skills.*`` modules.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Eagerly re-export the base + registry + the *generic* (non-ADAS) skills.
# Those files still live under skills/ and can be imported directly.
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
from skills.testing_skills import (
    TestCaseDesignSkill,
    SILTestSkill,
    HILTestSkill,
    RegressionTestSkill,
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
# General-purpose (domain-agnostic) skills / 通用技能 — P16
# These live under skills/core/ and are eagerly importable because they have
# no heavy external dependencies beyond the stdlib + httpx (already pinned).
from skills.core.web_skills import (
    WebFetchSkill,
    WebSearchSkill,
    LinkExtractorSkill,
)
from skills.core.data_skills import (
    JsonFormatterSkill,
    CsvParserSkill,
    TextStatisticsSkill,
    DiffSkill,
)
from skills.core.code_skills import (
    RegexBuilderSkill,
    JsonSchemaGeneratorSkill,
    CodeCounterSkill,
)
from skills.core.documentation_skills import (
    MarkdownToHtmlSkill,
    ReadmeSkeletonSkill,
    DocstringGeneratorSkill,
)
from skills.core.translation_skills import (
    LanguageDetectorSkill,
    TranslationPromptSkill,
)
from skills.core.utilities_skills import (
    UuidGeneratorSkill,
    HashSkill,
    TimestampSkill,
    Base64Skill,
)
# Multimodal skills (images / PDFs / audio) — P18
# 多模态技能（图像 / PDF / 音频）—— P18
from skills.multimodal.image_skills import (
    ImageInfoSkill,
    ImageResizeSkill,
    ImageBase64Skill,
)
from skills.multimodal.pdf_skills import (
    PdfInfoSkill,
    PdfExtractTextSkill,
)
from skills.multimodal.audio_skills import (
    AudioInfoSkill,
    AudioTranscribeStubSkill,
)
# Creative / moonshot skills / 创意技能 — P20
from skills.creative.idea_skills import (
    BrainstormSkill,
    MetaphorGeneratorSkill,
    StoryPlotGeneratorSkill,
)
from skills.creative.productivity_skills import (
    PomodoroSkill,
    EisenhowerMatrixSkill,
)
from skills.creative.learning_skills import (
    FlashcardGeneratorSkill,
    QuizGeneratorSkill,
    SpacedRepetitionScheduleSkill,
)
# Sandboxed code execution backends / 沙箱化代码执行后端 — P16
# Re-exported here so callers can ``from skills import CodeRunnerSkill``
# and so that ``SkillRegistry.auto_discover`` finds the inner ``BaseSkill``
# subclass via the ``skills.execution`` module namespace.
from skills.execution import (
    CodeRunnerSkill,
    ExecutionBackend,
    get_backend,
)
from skills.execution.inline import InlineBackend
from skills.execution.subprocess_backend import SubprocessBackend
from skills.execution.docker_backend import DockerBackend
from skills.execution.http_backend import HTTPBackend


# ---------------------------------------------------------------------------
# Lazy re-exports for ADAS-specific skills (P15)
# ---------------------------------------------------------------------------

_SKILLS_TO_CANONICAL: Dict[str, tuple] = {
    # perception
    "SensorAnalysisSkill":         ("domains.adas.skills.perception", "SensorAnalysisSkill"),
    "PerceptionModelReviewSkill":  ("domains.adas.skills.perception", "PerceptionModelReviewSkill"),
    "SensorCalibrationSkill":      ("domains.adas.skills.perception", "SensorCalibrationSkill"),
    "ObjectDetectionReviewSkill":  ("domains.adas.skills.perception", "ObjectDetectionReviewSkill"),

    # planning
    "RoutePlanningSkill":          ("domains.adas.skills.planning",   "RoutePlanningSkill"),
    "BehaviorPlanningSkill":       ("domains.adas.skills.planning",   "BehaviorPlanningSkill"),
    "TrajectoryOptimizationSkill": ("domains.adas.skills.planning",   "TrajectoryOptimizationSkill"),

    # safety
    "HazardAnalysisSkill":         ("domains.adas.skills.safety",     "HazardAnalysisSkill"),
    "FMEASkill":                   ("domains.adas.skills.safety",     "FMEASkill"),
    "ISO26262CheckSkill":          ("domains.adas.skills.safety",     "ISO26262CheckSkill"),
    "SafetyCaseSkill":             ("domains.adas.skills.safety",     "SafetyCaseSkill"),

    # simulation
    "ScenarioGenerationSkill":     ("domains.adas.skills.simulation", "ScenarioGenerationSkill"),
    "CARLARunnerSkill":            ("domains.adas.skills.simulation", "CARLARunnerSkill"),
    "EdgeCaseSkill":               ("domains.adas.skills.simulation", "EdgeCaseSkill"),
}


def __getattr__(name: str) -> Any:
    """PEP 562 lazy attribute access for the moved ADAS skill classes."""
    if name in _SKILLS_TO_CANONICAL:
        module_name, attr = _SKILLS_TO_CANONICAL[name]
        import importlib
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            raise ImportError(
                f"skills.{name} could not be loaded from {module_name!r}: {e}. "
                f"The new canonical home is {module_name!r}."
            ) from e
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'skills' has no attribute {name!r}")


def __dir__() -> List[str]:
    return sorted(list(globals().keys()) + list(_SKILLS_TO_CANONICAL.keys()))


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
    # General-purpose skills (skills/core/) / 通用技能 — P16
    "WebFetchSkill",
    "WebSearchSkill",
    "LinkExtractorSkill",
    "JsonFormatterSkill",
    "CsvParserSkill",
    "TextStatisticsSkill",
    "DiffSkill",
    "RegexBuilderSkill",
    "JsonSchemaGeneratorSkill",
    "CodeCounterSkill",
    "MarkdownToHtmlSkill",
    "ReadmeSkeletonSkill",
    "DocstringGeneratorSkill",
    "LanguageDetectorSkill",
    "TranslationPromptSkill",
    "UuidGeneratorSkill",
    "HashSkill",
    "TimestampSkill",
    "Base64Skill",
    # Multimodal skills (skills/multimodal/) — P18 / 多模态技能
    "ImageInfoSkill",
    "ImageResizeSkill",
    "ImageBase64Skill",
    "PdfInfoSkill",
    "PdfExtractTextSkill",
    "AudioInfoSkill",
    "AudioTranscribeStubSkill",
    # Creative / moonshot skills (skills/creative/) — P20 / 创意技能
    "BrainstormSkill",
    "MetaphorGeneratorSkill",
    "StoryPlotGeneratorSkill",
    "PomodoroSkill",
    "EisenhowerMatrixSkill",
    "FlashcardGeneratorSkill",
    "QuizGeneratorSkill",
    "SpacedRepetitionScheduleSkill",
    # Sandboxed code execution backends — P16 / 沙箱化代码执行
    "CodeRunnerSkill",
    "ExecutionBackend",
    "get_backend",
    "InlineBackend",
    "SubprocessBackend",
    "DockerBackend",
    "HTTPBackend",
]

__version__ = "1.0.0"
__author__ = "Nonull Team"
