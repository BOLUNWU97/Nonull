"""
Translation / language skills / 翻译相关技能
"""
from __future__ import annotations
import re
from typing import Any, Dict
from skills.base import BaseSkill, SkillMetadata, SkillCategory


class LanguageDetectorSkill(BaseSkill):
    """Naive language detection based on Unicode character ranges.

    Returns one of: 'en', 'zh', 'ja', 'ko', 'ru', 'ar', 'other'.
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="language_detector",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Heuristic language detection from Unicode character ranges. DEMO: not a real detector.",
            tags=["language", "i18n", "nlp"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not isinstance(context.get("text", ""), str):
            raise ValueError("'text' must be a string")

    def _execute_impl(self, context):
        text = context["text"]
        if not text.strip():
            return {"language": "unknown", "confidence": 0.0}

        # Count chars in different Unicode ranges
        cjk = len(re.findall(r"[一-鿿぀-ゟ゠-ヿ가-힯]", text))
        latin = len(re.findall(r"[a-zA-Z]", text))
        cyrillic = len(re.findall(r"[Ѐ-ӿ]", text))
        arabic = len(re.findall(r"[؀-ۿ]", text))

        total = max(len(text.strip()), 1)
        ratios = {"zh": cjk, "latin": latin, "cyrillic": cyrillic, "arabic": arabic}
        primary = max(ratios, key=ratios.get)
        confidence = ratios[primary] / total

        if primary == "latin" and confidence > 0.5: lang = "en"
        elif primary == "zh" and confidence > 0.1: lang = "zh"
        elif primary == "cyrillic" and confidence > 0.3: lang = "ru"
        elif primary == "arabic" and confidence > 0.3: lang = "ar"
        else: lang = "other"
        return {"language": lang, "confidence": round(confidence, 3), "char_distribution": ratios}


class TranslationPromptSkill(BaseSkill):
    """Generate a translation prompt template for the LLM."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="translation_prompt",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Generate a translation prompt template (the LLM does the actual translation).",
            tags=["translation", "i18n", "prompt"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("text"):
            raise ValueError("'text' is required")
        if not context.get("target_lang"):
            raise ValueError("'target_lang' is required")

    def _execute_impl(self, context):
        text = context["text"]
        target = context["target_lang"]
        source = context.get("source_lang", "auto-detect")
        preserve = context.get("preserve_formatting", True)
        glossary = context.get("glossary", {})

        glossary_str = "\n".join(f'  - "{k}" → "{v}"' for k, v in glossary.items())

        prompt = f"""Translate the following text from {source} to {target}.
{"Preserve the original formatting (markdown, code blocks, etc.)." if preserve else "Plain text translation is fine."}
{f"Use this glossary for specific terms:" + chr(10) + glossary_str if glossary else ""}

Text to translate:
---
{text}
---

Provide ONLY the translation, no explanations."""
        return {"prompt": prompt, "target_language": target, "source_language": source}
