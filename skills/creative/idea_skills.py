"""
Creative ideation skills / 创意激发的技能
"""
from __future__ import annotations
import random
from typing import Any, Dict, List
from skills.base import BaseSkill, SkillMetadata, SkillCategory


class BrainstormSkill(BaseSkill):
    """Generate creative ideas on a topic using established brainstorming techniques."""

    BRAINSTORM_TECHNIQUES = [
        "SCAMPER (Substitute, Combine, Adapt, Modify, Put to other use, Eliminate, Reverse)",
        "Six Thinking Hats (fact, emotion, caution, optimism, creativity, process)",
        "Worst Possible Idea (deliberately brainstorm bad ideas, then flip them)",
        "Random Word Association (associate random words with the topic)",
        "Analogical Thinking (find analogies in unrelated domains)",
        "Reversal (state the opposite of what you want)",
        "First Principles (break down to fundamentals, rebuild from scratch)",
    ]

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="brainstorm",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Generate creative ideas on a topic using established brainstorming techniques.",
            tags=["creativity", "ideation", "brainstorm"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("topic"):
            raise ValueError("'topic' is required")

    def _execute_impl(self, context):
        topic = context["topic"]
        count = min(context.get("count", 5), 20)
        techniques = random.sample(self.BRAINSTORM_TECHNIQUES, min(3, len(self.BRAINSTORM_TECHNIQUES)))

        return {
            "topic": topic,
            "techniques_used": techniques,
            "ideas": [
                f"[{t}] Idea {i+1} for '{topic}': " + self._generate_idea_prompt(topic, t)
                for i in range(count)
                for t in [techniques[i % len(techniques)]]
            ],
            "count": count,
        }

    def _generate_idea_prompt(self, topic, technique):
        prompts = {
            "SCAMPER (Substitute, Combine, Adapt, Modify, Put to other use, Eliminate, Reverse)": f"Apply each of the 7 SCAMPER verbs to '{topic}'",
            "Six Thinking Hats (fact, emotion, caution, optimism, creativity, process)": f"Consider '{topic}' from each of the 6 thinking-hat perspectives",
            "Worst Possible Idea (deliberately brainstorm bad ideas, then flip them)": f"Brainstorm the WORST possible approach to '{topic}', then flip",
            "Random Word Association (associate random words with the topic)": f"Pick 3 random words and connect each to '{topic}'",
            "Analogical Thinking (find analogies in unrelated domains)": f"Find 3 unrelated domains that share structure with '{topic}'",
            "Reversal (state the opposite of what you want)": f"What's the opposite of what you want for '{topic}'? Then work backwards",
            "First Principles (break down to fundamentals, rebuild from scratch)": f"What are the fundamental truths of '{topic}'? Rebuild from there",
        }
        return prompts.get(technique, f"Think creatively about '{topic}'")


class MetaphorGeneratorSkill(BaseSkill):
    """Generate metaphors and analogies to explain a concept."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="metaphor_generator",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Generate metaphors and analogies to explain an abstract concept.",
            tags=["creativity", "metaphor", "explanation", "writing"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("concept"):
            raise ValueError("'concept' is required")

    def _execute_impl(self, context):
        concept = context["concept"]
        domain = context.get("domain", "")
        templates = [
            f"{concept} is like ___ because both ___",
            f"Think of {concept} as a ___ that ___",
            f"{concept} behaves like ___ in a ___",
            f"Just as ___ navigates ___, {concept} navigates ___",
        ]
        return {
            "concept": concept,
            "domain": domain,
            "metaphor_templates": templates,
            "instruction": f"Fill in the blanks for '{concept}'{f' in the {domain} domain' if domain else ''}. Be creative but accurate.",
        }


class StoryPlotGeneratorSkill(BaseSkill):
    """Generate story plots using classic narrative structures."""

    PLOT_STRUCTURES = {
        "three_act": "Setup → Confrontation → Resolution",
        "hero_journey": "Call to Adventure → Crossing Threshold → Trials → Return",
        "freytag": "Exposition → Rising Action → Climax → Falling Action → Denouement",
        "kishōtenketsu": "Introduction → Development → Twist → Conclusion",
    }

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="story_plot",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Generate a story plot skeleton using classic narrative structures.",
            tags=["creativity", "writing", "story", "narrative"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("premise"):
            raise ValueError("'premise' required")

    def _execute_impl(self, context):
        premise = context["premise"]
        structure = context.get("structure", "three_act")
        if structure not in self.PLOT_STRUCTURES:
            structure = "three_act"
        return {
            "premise": premise,
            "structure": structure,
            "beats": self.PLOT_STRUCTURES[structure].split(" → "),
            "instruction": f"Expand each beat of the '{structure}' structure for the premise: {premise}",
        }
