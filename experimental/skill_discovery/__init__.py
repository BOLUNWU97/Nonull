"""
Skill Discovery (Experimental)
==============================

Watches the agent's conversation history and proposes new skills based on
patterns in user requests. When the same kind of task is requested 3+ times,
a skill suggestion is generated.

This is a research prototype. The "discovered skills" are NOT auto-registered;
they must be reviewed and approved by a human before being added.
"""
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SkillProposal:
    """A proposed new skill, generated from observed usage patterns."""
    name: str
    description: str
    rationale: str  # why this skill should exist
    example_uses: List[str]  # sample user requests that triggered this proposal
    suggested_implementation: str  # rough pseudocode or template
    confidence: float  # 0.0-1.0, based on frequency and consistency

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "rationale": self.rationale,
            "example_uses": self.example_uses,
            "suggested_implementation": self.suggested_implementation,
            "confidence": self.confidence,
        }


class SkillDiscoveryEngine:
    """Watches task history and proposes new skills."""

    def __init__(self, min_frequency: int = 3):
        self.min_frequency = min_frequency
        self._task_history: List[str] = []

    def record_task(self, task: str) -> None:
        """Record a task that the agent was asked to perform."""
        if task and isinstance(task, str):
            self._task_history.append(task)

    def find_repeating_patterns(self) -> List[SkillProposal]:
        """Find patterns that repeat >= min_frequency times and propose a skill for each."""
        # Extract "intent" via simple keyword extraction
        intents = []
        for task in self._task_history:
            intent = self._extract_intent(task)
            if intent:
                intents.append(intent)

        # Count frequencies
        intent_counts = Counter(intents)
        proposals = []
        for intent, count in intent_counts.items():
            if count >= self.min_frequency:
                proposal = self._build_proposal(intent, count)
                proposals.append(proposal)
        return sorted(proposals, key=lambda p: p.confidence, reverse=True)

    def _extract_intent(self, task: str) -> Optional[str]:
        """Extract a coarse intent signature from a user request."""
        task_lower = task.lower()
        # Match against existing skill keywords
        keywords = {
            "code_review": ["review", "code", "bug", "lint"],
            "data_analysis": ["analyze", "data", "csv", "json", "statistics"],
            "web_search": ["search", "find online", "google"],
            "translation": ["translate", "翻译"],
            "summarization": ["summarize", "tldr", "summary"],
            "explanation": ["explain", "what is", "how does"],
            "formatting": ["format", "json", "indent", "prettify"],
            "comparison": ["compare", "versus", "vs", "difference"],
        }
        for intent, kws in keywords.items():
            if any(kw in task_lower for kw in kws):
                return intent
        return None

    def _build_proposal(self, intent: str, count: int) -> SkillProposal:
        """Build a SkillProposal from an observed intent."""
        descriptions = {
            "code_review": "Review code for bugs, style, and best practices.",
            "data_analysis": "Analyze tabular/JSON data and produce statistics or insights.",
            "web_search": "Search the web and return relevant results.",
            "translation": "Translate text between languages.",
            "summarization": "Produce a summary of long text.",
            "explanation": "Explain a concept in clear terms.",
            "formatting": "Format code or data (JSON, indent, prettify).",
            "comparison": "Compare two or more items and explain differences.",
        }
        template = '''from skills.base import BaseSkill, SkillMetadata, SkillCategory

class {class_name}Skill(BaseSkill):
    @property
    def metadata(self):
        return SkillMetadata(
            name="{name}",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="{description}",
            tags=[],
        )

    def _validate_input(self, context):
        # TODO: add validation
        pass

    def _execute_impl(self, context):
        # TODO: implement
        return {{}}
'''
        return SkillProposal(
            name=f"custom_{intent}",
            description=descriptions.get(intent, f"Custom skill for {intent}"),
            rationale=f"User requested {intent} {count} times. Consider creating a dedicated skill.",
            example_uses=[t for t in self._task_history if self._extract_intent(t) == intent][:3],
            suggested_implementation=template.format(
                class_name=intent.title().replace("_", ""),
                name=f"custom_{intent}",
                description=descriptions.get(intent, f"Custom skill for {intent}"),
            ),
            confidence=min(1.0, count / 10.0),
        )

    def clear_history(self) -> None:
        self._task_history = []
