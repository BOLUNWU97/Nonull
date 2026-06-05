"""
人格编排器 — 统合 Nonull 的独特人格、场景思维、安全徽章、副驾提醒
Persona Orchestrator — Unifies Nonull's unique persona, scenario thinking, safety badges, and co-pilot features
"""

from enum import Enum
from typing import Optional
from .driving_persona import DrivingPersona, PersonaType
from .scenario_engine import ScenarioEngine
from .safety_badge import SafetyBadgeSystem
from .co_pilot import CoPilot


class PersonaOrchestrator:
    """人格编排器 — Nonull 的"灵魂"

    把所有特色功能统合在一起：
    - 驾驶人格：三种性格切换
    - 场景思维：自动关联驾驶场景
    - 安全徽章：游戏化安全评分
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

    # ═══ 安全徽章 ═══

    def record_interaction(self, context: dict) -> dict:
        """记录一次交互，评估安全评分"""
        score = self.badges.evaluate_interaction(context)
        new_level = self.badges.check_and_record()
        return {
            "score": score,
            "new_level": new_level,
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
            "badges": self.get_scorecard(),
            "stats": {
                "total_interactions": self.badges.total_interactions,
                "safety_score_avg": self.badges.average_score,
            },
        }
