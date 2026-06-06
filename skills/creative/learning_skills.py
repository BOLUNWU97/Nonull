"""
Learning / education skills / 学习辅助技能
"""
from __future__ import annotations
from typing import Any, Dict, List
from skills.base import BaseSkill, SkillMetadata, SkillCategory


class FlashcardGeneratorSkill(BaseSkill):
    """Generate flashcards from text content."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="flashcard_generator",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Generate Q&A flashcards from a text passage.",
            tags=["learning", "flashcards", "education", "anki"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("text"):
            raise ValueError("'text' is required")
        if not (1 <= context.get("count", 5) <= 50):
            raise ValueError("'count' must be 1-50")

    def _execute_impl(self, context):
        text = context["text"]
        count = context.get("count", 5)
        return {
            "text_length": len(text),
            "card_count": count,
            "instruction": (
                f"Generate {count} high-quality Q&A flashcards from the following text. "
                f"Each flashcard should test a key concept. Format: Q: ... A: ...\n\n"
                f"Text:\n{text}"
            ),
        }


class QuizGeneratorSkill(BaseSkill):
    """Generate a multiple-choice quiz from content."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="quiz_generator",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Generate a multiple-choice quiz from text content.",
            tags=["learning", "quiz", "education", "assessment"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("text"):
            raise ValueError("'text' is required")
        if not (1 <= context.get("num_questions", 5) <= 30):
            raise ValueError("'num_questions' must be 1-30")

    def _execute_impl(self, context):
        text = context["text"]
        n = context.get("num_questions", 5)
        return {
            "num_questions": n,
            "instruction": (
                f"Generate {n} multiple-choice questions from the following text. "
                f"Each question: 1 correct + 3 plausible distractors. "
                f"Format: Q: ... A) ... B) ... C) ... D) ... ANSWER: X\n\n"
                f"Text:\n{text}"
            ),
        }


class SpacedRepetitionScheduleSkill(BaseSkill):
    """Generate a spaced-repetition review schedule (Leitner system style)."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="spaced_repetition",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Generate a spaced-repetition review schedule for a list of items.",
            tags=["learning", "spaced-repetition", "memory", "education"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not isinstance(context.get("items"), list):
            raise ValueError("'items' must be a list")

    def _execute_impl(self, context):
        items = context["items"]
        # Leitner box schedule: each box reviewed at increasing intervals
        intervals = [1, 3, 7, 14, 30, 60, 120]  # days

        schedule = []
        for i, item in enumerate(items):
            schedule.append({
                "item": item,
                "review_intervals_days": intervals,
                "estimated_total_days": sum(intervals),
            })
        return {
            "items": schedule,
            "method": "Leitner box",
            "intervals": intervals,
        }
