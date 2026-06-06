"""
Productivity skills / 效率工具
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List
from skills.base import BaseSkill, SkillMetadata, SkillCategory


class PomodoroSkill(BaseSkill):
    """Suggest a Pomodoro schedule for a list of tasks."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="pomodoro_schedule",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Generate a Pomodoro-style work schedule for a list of tasks.",
            tags=["productivity", "pomodoro", "scheduling", "time-management"],
            author="Nonull Team",
            safety_level=1,
        )

    POMODORO_MINUTES = 25
    BREAK_MINUTES = 5
    LONG_BREAK_MINUTES = 15

    def _validate_input(self, context):
        if not isinstance(context.get("tasks"), list):
            raise ValueError("'tasks' must be a list")

    def _execute_impl(self, context):
        tasks = context["tasks"]
        estimate_minutes = context.get("estimate_minutes", 1)

        schedule = []
        cycle = 0
        for i, task in enumerate(tasks):
            pomodoros = max(1, estimate_minutes // self.POMODORO_MINUTES)
            schedule.append({
                "task": task,
                "pomodoro_count": pomodoros,
                "estimated_minutes": pomodoros * self.POMODORO_MINUTES,
            })
        return {
            "tasks": schedule,
            "total_pomodoros": sum(s["pomodoro_count"] for s in schedule),
            "total_minutes": sum(s["estimated_minutes"] for s in schedule),
            "structure": "25 min work → 5 min break (4 cycles) → 15 min long break",
        }


class EisenhowerMatrixSkill(BaseSkill):
    """Categorize tasks into an Eisenhower matrix (urgent/important quadrants)."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="eisenhower_matrix",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Categorize a list of tasks into an Eisenhower urgent/important matrix.",
            tags=["productivity", "prioritization", "eisenhower", "task-management"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not isinstance(context.get("tasks"), list):
            raise ValueError("'tasks' must be a list")

    def _execute_impl(self, context):
        tasks = context["tasks"]
        # Each task should have: name, urgent (bool), important (bool)
        matrix = {
            "do_first": [],      # urgent + important
            "schedule": [],      # not urgent + important
            "delegate": [],      # urgent + not important
            "eliminate": [],     # not urgent + not important
        }
        for task in tasks:
            # Accept either a dict or a plain string for each task entry.
            # String tasks get the default "neither urgent nor important"
            # treatment, which routes them to the ``eliminate`` bucket.
            if isinstance(task, dict):
                name = task.get("name", str(task))
                urgent = bool(task.get("urgent", False))
                important = bool(task.get("important", False))
            else:
                name = str(task)
                urgent = False
                important = False
            if urgent and important:
                matrix["do_first"].append(name)
            elif important and not urgent:
                matrix["schedule"].append(name)
            elif urgent and not important:
                matrix["delegate"].append(name)
            else:
                matrix["eliminate"].append(name)
        return matrix
