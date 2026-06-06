"""Tests for the creative / moonshot skills in skills/creative/ and the i18n module.

P20 — i18n + Advanced Creative Features.
"""
from __future__ import annotations

import os
import sys

import pytest

# Ensure project root is importable when running pytest from any CWD.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.base import BaseSkill, SkillResult
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


def _activate(skill: BaseSkill) -> BaseSkill:
    skill.activate()
    return skill


# =============================================================================
# Idea / creativity skills
# =============================================================================


class TestBrainstormSkill:
    def test_generates_ideas(self):
        skill = _activate(BrainstormSkill())
        result = skill.execute({"topic": "smart home for elderly", "count": 3})
        assert result.success
        assert result.data["topic"] == "smart home for elderly"
        assert result.data["count"] == 3
        assert len(result.data["ideas"]) == 3
        # Each idea must mention the topic
        for idea in result.data["ideas"]:
            assert "smart home for elderly" in idea

    def test_default_count(self):
        skill = _activate(BrainstormSkill())
        result = skill.execute({"topic": "X"})
        assert result.success
        assert result.data["count"] == 5  # default

    def test_caps_count_at_20(self):
        skill = _activate(BrainstormSkill())
        result = skill.execute({"topic": "X", "count": 100})
        assert result.success
        assert result.data["count"] == 20  # capped

    def test_techniques_picked(self):
        skill = _activate(BrainstormSkill())
        result = skill.execute({"topic": "X"})
        assert result.success
        assert len(result.data["techniques_used"]) == 3

    def test_requires_topic(self):
        skill = _activate(BrainstormSkill())
        result = skill.execute({})
        assert not result.success
        assert "topic" in result.error.lower()


class TestMetaphorGeneratorSkill:
    def test_generates_templates(self):
        skill = _activate(MetaphorGeneratorSkill())
        result = skill.execute({"concept": "neural network", "domain": "biology"})
        assert result.success
        assert result.data["concept"] == "neural network"
        assert result.data["domain"] == "biology"
        assert len(result.data["metaphor_templates"]) >= 1
        assert "neural network" in result.data["instruction"]
        assert "biology" in result.data["instruction"]

    def test_works_without_domain(self):
        skill = _activate(MetaphorGeneratorSkill())
        result = skill.execute({"concept": "time"})
        assert result.success
        assert result.data["domain"] == ""
        assert "time" in result.data["instruction"]

    def test_requires_concept(self):
        skill = _activate(MetaphorGeneratorSkill())
        result = skill.execute({})
        assert not result.success


class TestStoryPlotGeneratorSkill:
    def test_default_three_act(self):
        skill = _activate(StoryPlotGeneratorSkill())
        result = skill.execute({"premise": "A robot becomes sentient"})
        assert result.success
        assert result.data["structure"] == "three_act"
        assert len(result.data["beats"]) == 3

    def test_hero_journey(self):
        skill = _activate(StoryPlotGeneratorSkill())
        result = skill.execute({
            "premise": "A young mage must save the kingdom",
            "structure": "hero_journey",
        })
        assert result.success
        assert result.data["structure"] == "hero_journey"
        assert "Call to Adventure" in result.data["beats"][0]

    def test_freytag(self):
        skill = _activate(StoryPlotGeneratorSkill())
        result = skill.execute({"premise": "X", "structure": "freytag"})
        assert result.success
        assert len(result.data["beats"]) == 5  # exposition → denouement

    def test_kishotenketsu(self):
        skill = _activate(StoryPlotGeneratorSkill())
        result = skill.execute({"premise": "X", "structure": "kishōtenketsu"})
        assert result.success
        assert len(result.data["beats"]) == 4

    def test_invalid_structure_falls_back(self):
        skill = _activate(StoryPlotGeneratorSkill())
        result = skill.execute({"premise": "X", "structure": "nonexistent"})
        assert result.success
        assert result.data["structure"] == "three_act"

    def test_requires_premise(self):
        skill = _activate(StoryPlotGeneratorSkill())
        result = skill.execute({})
        assert not result.success


# =============================================================================
# Productivity skills
# =============================================================================


class TestPomodoroSkill:
    def test_generates_schedule(self):
        skill = _activate(PomodoroSkill())
        result = skill.execute({
            "tasks": ["Write report", "Review code"],
            "estimate_minutes": 50,
        })
        assert result.success
        assert len(result.data["tasks"]) == 2
        # 50 min / 25 min/pomodoro = 2 pomodoros
        assert result.data["tasks"][0]["pomodoro_count"] == 2
        assert result.data["total_pomodoros"] == 4
        assert "25 min work" in result.data["structure"]

    def test_minimum_one_pomodoro_per_task(self):
        skill = _activate(PomodoroSkill())
        result = skill.execute({"tasks": ["Tiny task"], "estimate_minutes": 5})
        assert result.success
        assert result.data["tasks"][0]["pomodoro_count"] == 1

    def test_requires_tasks_list(self):
        skill = _activate(PomodoroSkill())
        result = skill.execute({"tasks": "not a list"})
        assert not result.success


class TestEisenhowerMatrixSkill:
    def test_categorizes_tasks(self):
        skill = _activate(EisenhowerMatrixSkill())
        result = skill.execute({
            "tasks": [
                {"name": "Fix production bug", "urgent": True, "important": True},
                {"name": "Plan next quarter", "urgent": False, "important": True},
                {"name": "Answer email", "urgent": True, "important": False},
                {"name": "Browse social media", "urgent": False, "important": False},
            ]
        })
        assert result.success
        assert "Fix production bug" in result.data["do_first"]
        assert "Plan next quarter" in result.data["schedule"]
        assert "Answer email" in result.data["delegate"]
        assert "Browse social media" in result.data["eliminate"]

    def test_handles_string_tasks(self):
        skill = _activate(EisenhowerMatrixSkill())
        result = skill.execute({"tasks": ["task1", "task2"]})
        assert result.success
        # Default: not urgent, not important → eliminate
        assert "task1" in result.data["eliminate"]
        assert "task2" in result.data["eliminate"]

    def test_requires_tasks_list(self):
        skill = _activate(EisenhowerMatrixSkill())
        result = skill.execute({})
        assert not result.success


# =============================================================================
# Learning skills
# =============================================================================


class TestFlashcardGeneratorSkill:
    def test_generates_prompt(self):
        skill = _activate(FlashcardGeneratorSkill())
        text = "Photosynthesis converts CO2 and H2O into glucose using sunlight."
        result = skill.execute({"text": text, "count": 10})
        assert result.success
        assert result.data["card_count"] == 10
        assert result.data["text_length"] == len(text)
        assert "Photosynthesis" in result.data["instruction"]
        assert "Q:" in result.data["instruction"]

    def test_default_count(self):
        skill = _activate(FlashcardGeneratorSkill())
        result = skill.execute({"text": "Some text"})
        assert result.success
        assert result.data["card_count"] == 5

    def test_validates_count_range(self):
        skill = _activate(FlashcardGeneratorSkill())
        # count = 0 fails
        result = skill.execute({"text": "X", "count": 0})
        assert not result.success
        # count = 100 fails
        result = skill.execute({"text": "X", "count": 100})
        assert not result.success

    def test_requires_text(self):
        skill = _activate(FlashcardGeneratorSkill())
        result = skill.execute({})
        assert not result.success


class TestQuizGeneratorSkill:
    def test_generates_prompt(self):
        skill = _activate(QuizcardGeneratorSkill() if False else QuizGeneratorSkill())
        result = skill.execute({
            "text": "The mitochondria is the powerhouse of the cell.",
            "num_questions": 5,
        })
        assert result.success
        assert result.data["num_questions"] == 5
        assert "mitochondria" in result.data["instruction"]
        assert "A)" in result.data["instruction"]
        assert "ANSWER:" in result.data["instruction"]

    def test_default_count(self):
        skill = _activate(QuizGeneratorSkill())
        result = skill.execute({"text": "X"})
        assert result.success
        assert result.data["num_questions"] == 5

    def test_validates_num_questions(self):
        skill = _activate(QuizGeneratorSkill())
        result = skill.execute({"text": "X", "num_questions": 0})
        assert not result.success
        result = skill.execute({"text": "X", "num_questions": 50})
        assert not result.success

    def test_requires_text(self):
        skill = _activate(QuizGeneratorSkill())
        result = skill.execute({})
        assert not result.success


class TestSpacedRepetitionScheduleSkill:
    def test_generates_schedule(self):
        skill = _activate(SpacedRepetitionScheduleSkill())
        result = skill.execute({"items": ["item1", "item2", "item3"]})
        assert result.success
        assert len(result.data["items"]) == 3
        assert result.data["method"] == "Leitner box"
        # Each item has the standard 7-day review intervals
        assert result.data["items"][0]["review_intervals_days"] == [1, 3, 7, 14, 30, 60, 120]

    def test_total_days(self):
        skill = _activate(SpacedRepetitionScheduleSkill())
        result = skill.execute({"items": ["x"]})
        assert result.success
        assert result.data["items"][0]["estimated_total_days"] == sum([1, 3, 7, 14, 30, 60, 120])

    def test_requires_items_list(self):
        skill = _activate(SpacedRepetitionScheduleSkill())
        result = skill.execute({})
        assert not result.success


# =============================================================================
# Registry integration: all 8 new creative skills must be auto-discoverable.
# =============================================================================


class TestCreativeSkillsRegistry:
    """All 8 new creative skills should auto-discover via the registry."""

    EXPECTED_SKILLS = [
        "brainstorm",
        "metaphor_generator",
        "story_plot",
        "pomodoro_schedule",
        "eisenhower_matrix",
        "flashcard_generator",
        "quiz_generator",
        "spaced_repetition",
    ]

    def test_all_creative_skills_discoverable(self):
        from skills.registry import SkillRegistry
        reg = SkillRegistry()
        reg.auto_discover()
        names = {s.metadata.name for s in reg.get_all_skills()}
        missing = set(self.EXPECTED_SKILLS) - names
        assert not missing, (
            f"Missing creative skills: {missing}. "
            f"Discovered: {sorted(names)}"
        )

    def test_all_creative_skills_in_general_category(self):
        from skills.registry import SkillRegistry
        from skills.base import SkillCategory
        reg = SkillRegistry()
        reg.auto_discover()
        for name in self.EXPECTED_SKILLS:
            skill = reg.get_skill(name)
            assert skill is not None
            assert skill.metadata.category == SkillCategory.GENERAL, (
                f"Skill {name!r} has category {skill.metadata.category.value}, "
                f"expected 'general'"
            )


# =============================================================================
# i18n tests
# =============================================================================


class TestI18N:
    """Tests for the i18n module."""

    def test_english_default(self):
        from i18n import t
        assert t("welcome") == "Nonull — Universal AI Agent"
        assert t("agent_disabled") == (
            "(Agent mode disabled — set NONULL_LLM_API_KEY to enable)"
        )

    def test_chinese_translation(self):
        from i18n import t
        assert t("welcome", lang="zh") == "Nonull — 通用 AI 智能体"
        assert t("agent_disabled", lang="zh") == (
            "（智能体模式未启用 — 设置 NONULL_LLM_API_KEY 启用）"
        )

    def test_format_substitution(self):
        from i18n import t
        # English
        assert t("skills_loaded", n=5) == "5 skills loaded"
        # Chinese
        assert t("skills_loaded", lang="zh", n=5) == "已加载 5 个技能"
        # Domain active
        assert t("domain_active", name="perception") == "Active domain: perception"
        assert t("domain_active", lang="zh", name="感知") == "当前领域: 感知"

    def test_falls_back_to_english_for_unknown_lang(self):
        from i18n import t
        assert t("welcome", lang="fr") == "Nonull — Universal AI Agent"

    def test_returns_key_for_unknown_key(self):
        from i18n import t
        assert t("nonexistent_key") == "nonexistent_key"

    def test_set_lang_persists(self):
        from i18n import set_lang, t
        set_lang("zh")
        try:
            assert t("welcome") == "Nonull — 通用 AI 智能体"
        finally:
            set_lang("en")  # restore

    def test_set_lang_ignores_unknown(self):
        from i18n import set_lang, t
        set_lang("klingon")
        # Should NOT change the language
        assert t("welcome") == "Nonull — Universal AI Agent"

    def test_i18n_class_directly(self):
        from i18n import I18N
        i18n = I18N(default_lang="zh")
        assert i18n.t("welcome") == "Nonull — 通用 AI 智能体"
        i18n.set_lang("en")
        assert i18n.t("welcome") == "Nonull — Universal AI Agent"

    def test_i18n_falls_back_for_missing_lang(self):
        from i18n import I18N
        i18n = I18N(default_lang="klingon")  # unknown
        assert i18n.default_lang == "en"  # fallback
        assert i18n.t("welcome") == "Nonull — Universal AI Agent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
