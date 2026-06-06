"""
智驾/ADAS 领域包 / ADAS Domain Package
======================================

可插拔的智驾领域。包含：
- 36 个 ADAS 驾驶场景
- 三种驾驶人格（保守派/运动派/老司机）
- 副驾 CoPilot 模式
- ADAS 相关技能（感知/规划/HARA/仿真）

This is a built-in domain. To disable it, see DomainRegistry.deactivate('adas').
"""
from typing import List

from domains import DomainPackage, DomainMetadata

# Re-export main classes for convenience
from domains.adas.scenarios import ScenarioEngine, get_engine
from domains.adas.personas import (
    DrivingPersona,
    PersonaType,
    AnalysisFocus,
    ConservativePersona,
    SportyPersona,
    VeteranPersona,
    get_persona,
)
from domains.adas.copilot import (
    AlertSeverity,
    Alert,
    TelemetryContext,
    AlertRule,
    CoPilot,
)


class ADASDomain:
    """ADAS/智驾 领域 — built-in default domain.

    The actual skill registration is deferred to P16. For now this
    class is a thin metadata + activation wrapper: it advertises the
    ADAS domain to the DomainRegistry and exposes its public API.
    """

    @property
    def metadata(self) -> DomainMetadata:
        return DomainMetadata(
            name="adas",
            display_name="智驾 / ADAS",
            description=(
                "Autonomous driving domain. 36 SAE J3016 scenarios, "
                "three driving personas, CoPilot mode, and ADAS-specific "
                "skills (perception/planning/HARA/simulation)."
            ),
            safety_profile="advisory",  # ADVISORY per CLAUDE.md
            requires_disclaimers=[
                "智驾领域：所有 ASIL/SOTIF/ISO 26262 引用均为模板参考，不构成合规认证。",
                "ADAS domain: all ASIL/SOTIF/ISO 26262 references are "
                "template references, NOT compliance certification.",
            ],
        )

    def register(self, registry) -> None:
        """Register ADAS skills with the main skill registry.

        In P16, ``registry`` will be wired to a real SkillRegistry so that
        ``register_skill`` actually adds the ADAS skills. For now this
        method is a stub that consumes the default ``register_skill``
        no-op shim on DomainRegistry.
        """
        # Imported here to avoid a hard dependency at module import time;
        # the ADAS skill modules are sizeable and we don't want a circular
        # import between the ADAS domain package and the skill registry.
        try:
            from domains.adas.skills.safety import (
                HazardAnalysisSkill,
                FMEASkill,
                ISO26262CheckSkill,
                SafetyCaseSkill,
            )
            from domains.adas.skills.simulation import (
                ScenarioGenerationSkill,
                CARLARunnerSkill,
                EdgeCaseSkill,
            )
            from domains.adas.skills.perception import (
                SensorAnalysisSkill,
                PerceptionModelReviewSkill,
                ObjectDetectionReviewSkill,
                SensorCalibrationSkill,
            )
            from domains.adas.skills.planning import (
                RoutePlanningSkill,
                BehaviorPlanningSkill,
                TrajectoryOptimizationSkill,
            )
        except ImportError:
            # If the ADAS skill modules can't be imported for any reason,
            # don't crash the domain activation — just log a warning via
            # the registry's no-op shim.
            return

        # Domain-side hookup: a future P16 change will pass a real
        # SkillRegistry in as ``registry``, with a working
        # ``register_skill`` method. For now we just iterate and call
        # the registry's hook. The default DomainRegistry.register_skill
        # is a no-op, so this is a safe placeholder.
        for skill in (
            HazardAnalysisSkill,
            FMEASkill,
            ISO26262CheckSkill,
            SafetyCaseSkill,
            ScenarioGenerationSkill,
            CARLARunnerSkill,
            EdgeCaseSkill,
            SensorAnalysisSkill,
            PerceptionModelReviewSkill,
            ObjectDetectionReviewSkill,
            SensorCalibrationSkill,
            RoutePlanningSkill,
            BehaviorPlanningSkill,
            TrajectoryOptimizationSkill,
        ):
            registry.register_skill(skill)

        # Personas and scenarios are registered by their own subsystems
        # at a later stage (not in this method).

    def get_safety_disclaimers(self) -> List[str]:
        return list(self.metadata.requires_disclaimers)


__all__ = [
    "ADASDomain",
    # Personas
    "DrivingPersona",
    "PersonaType",
    "AnalysisFocus",
    "ConservativePersona",
    "SportyPersona",
    "VeteranPersona",
    "get_persona",
    # Scenarios
    "ScenarioEngine",
    "get_engine",
    # CoPilot
    "AlertSeverity",
    "Alert",
    "TelemetryContext",
    "AlertRule",
    "CoPilot",
]
