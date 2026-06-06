"""
人格编排器 — 统合 Nonull 的独特人格、场景思维、安全指标记录、副驾提醒
Persona Orchestrator — Unifies Nonull's unique persona, scenario thinking, safety metrics tracking, and co-pilot features
"""

from enum import Enum
from typing import Optional

# P15: 领域抽象 / Domain abstraction.
# The persona orchestrator is a CORE module (not ADAS-specific) — it composes
# a persona, a scenario engine, a safety-metrics system, and a co-pilot. The
# concrete classes it composes used to live in `persona/`, which has been
# refactored: ADAS-specific bits now live in `domains/adas/`, and the safety
# metrics moved into `core/` because they are domain-agnostic.
from domains.adas.personas import DrivingPersona, PersonaType
from domains.adas.scenarios import ScenarioEngine
from domains.adas.copilot import CoPilot
from core.safety_metrics import SafetyBadgeSystem


class PersonaOrchestrator:
    """人格编排器 — Nonull 的"灵魂"

    把所有特色功能统合在一起：
    - 驾驶人格：三种性格切换
    - 场景思维：自动关联驾驶场景
    - 安全指标记录：安全操作指标
    - 副驾模式：主动提醒风险
    """

    def __init__(self, persona_type: PersonaType = PersonaType.VETERAN):
        self.persona_type = persona_type
        self.persona = DrivingPersona.for_type(persona_type)
        self.scenarios = ScenarioEngine()
        self.badges = SafetyBadgeSystem()
        self.copilot = CoPilot(persona_type)

    # ═══ 人格相关 ═══

    def switch_persona(self, persona_type: PersonaType) -> str:
        """切换驾驶人格"""
        self.persona_type = persona_type
        self.persona = DrivingPersona.for_type(persona_type)
        # Rebuild co-pilot so its default rules match the new persona
        self.copilot = CoPilot(persona_type)
        return f"已切换到「{self.persona.get_name()}」模式"

    def get_current_persona(self) -> dict:
        """获取当前人格信息"""
        return {
            "type": self.persona.persona_type.value,
            "name": self.persona.get_name(),
            "style": self.persona.get_style(),
            "phrase": self.persona.get_signature_phrase(),
        }

    def list_personas(self) -> list:
        """列出所有可用人格"""
        return [
            {
                "type": p.value,
                "name": DrivingPersona.for_type(p).get_name(),
                "desc": DrivingPersona.for_type(p).get_description(),
            }
            for p in PersonaType
        ]

    # ═══ 场景思维 ═══

    def analyze_task(self, task: str) -> dict:
        """分析任务，自动关联驾驶场景"""
        scenario_analysis = self.scenarios.analyze_task_scenarios(task)
        persona_style = self.persona.apply_to_analysis(scenario_analysis)
        return {
            "task": task,
            "related_scenarios": scenario_analysis,
            "persona_lens": persona_style,
        }

    def check_scenario_coverage(self, test_cases: list) -> dict:
        """检查场景测试覆盖率"""
        return self.scenarios.analyze_scenario_coverage(test_cases)

    # ═══ 安全指标 ═══

    def record_interaction(self, context: dict) -> dict:
        """记录一次交互，统计安全指标"""
        metric = self.badges.evaluate_interaction(context)
        new_level = self.badges.check_and_record()
        return {
            "metric": metric,
            "level": new_level,
            "total_levels": len(self.badges.get_achieved_levels()),
        }

    def get_scorecard(self) -> dict:
        """获取安全成绩单"""
        return self.badges.get_scorecard()

    # ═══ 副驾模式 ═══

    def proactive_scan(self, context: dict) -> list:
        """主动扫描风险"""
        return self.copilot.scan_context(context)

    def get_daily_brief(self) -> str:
        """生成每日简报"""
        return self.copilot.get_daily_brief()

    # ═══ 综合 ═══

    def get_full_status(self) -> dict:
        """获取完整状态"""
        return {
            "persona": self.get_current_persona(),
            "metrics": self.get_scorecard(),
            "stats": {
                "total_interactions": self.badges.total_interactions,
                "safety_metric_avg": self.badges.average_score,
            },
        }
