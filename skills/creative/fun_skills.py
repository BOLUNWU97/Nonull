"""
Fun / creative skills / 创意技能
"""
from __future__ import annotations
from typing import Any, Dict
from skills.base import BaseSkill, SkillMetadata, SkillCategory

DAD_JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "What do you call a fake noodle? An impasta!",
    "Why did the scarecrow win an award? He was outstanding in his field!",
    "I told my wife she was drawing her eyebrows too high. She looked surprised.",
    "What do you call a fish wearing a bowtie? So-fish-ticated!",
    "Why don't scientists trust atoms? They make up everything!",
    "What do you call a bear with no teeth? A gummy bear!",
    "I would tell you a UDP joke, but I'm not sure you'd get it.",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
    "What's the best thing about Switzerland? I don't know, but the flag is a big plus.",
]

RANDOM_FACTS = [
    "Octopuses have three hearts!",
    "Honey never spoils. Archaeologists found 3000-year-old honey still edible.",
    "A day on Venus is longer than a year on Venus.",
    "Bananas are berries, but strawberries aren't.",
    "The Eiffel Tower can be 15 cm taller during summer (metal expands).",
    "Wombat poop is cube-shaped.",
    "A group of flamingos is called a 'flamboyance'.",
    "The shortest war in history lasted 38 minutes (Britain vs Zanzibar, 1896).",
    "Cleopatra lived closer to the moon landing than to the building of the Great Pyramid.",
    "There are more trees on Earth than stars in the Milky Way.",
]


class DadJokeSkill(BaseSkill):
    """Returns a random dad joke."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="dad_joke",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Returns a random dad joke. Great for icebreakers!",
            tags=["fun", "joke", "icebreaker"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        pass

    def _execute_impl(self, context):
        import hashlib
        seed = context.get("seed", "")
        jokes = DAD_JOKES[:]
        if seed:
            idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(jokes)
        else:
            import random
            idx = random.randint(0, len(jokes) - 1)
        return {"joke": jokes[idx], "total_inventory": len(jokes)}


class RandomFactSkill(BaseSkill):
    """Returns an interesting random fact."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="random_fact",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Returns an interesting random fact about science, history, or nature.",
            tags=["fun", "trivia", "education"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        pass

    def _execute_impl(self, context):
        import hashlib
        seed = context.get("seed", "")
        facts = RANDOM_FACTS[:]
        if seed:
            idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(facts)
        else:
            import random
            idx = random.randint(0, len(facts) - 1)
        return {"fact": facts[idx], "total_inventory": len(facts)}


class DecisionHelperSkill(BaseSkill):
    """Generates a pro/con list for a decision."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="decision_helper",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Generate a structured pro/con list to help make a decision.",
            tags=["productivity", "decision", "thinking"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("decision"):
            raise ValueError("'decision' is required")

    def _execute_impl(self, context):
        decision = context["decision"]
        return {
            "decision": decision,
            "template": f"Pros and Cons of: {decision}\n\nPros:\n1. \n2. \n3.\n\nCons:\n1. \n2. \n3.\n\nFill in the blanks with specific pros and cons for your situation."
        }
