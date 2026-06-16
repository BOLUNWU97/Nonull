"""
Translation / language skills / 翻译相关技能
"""
from __future__ import annotations
import re
from typing import Any, Dict
from skills.base import BaseSkill, SkillMetadata, SkillCategory
from skills.core.lang_detect import detect_language


class LanguageDetectorSkill(BaseSkill):
    """Zero-dependency language detection.

    Script-based detection for non-Latin (zh/ja/ko/ru/ar/el/th/he via Unicode
    ranges + kana/hangul disambiguation), and n-gram/stopword fingerprinting for
    Latin-script languages (en/de/fr/es/pt/it/nl). No external deps.
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="language_detector",
            version="0.2.0",
            category=SkillCategory.GENERAL,
            description="Detect text language: script-based for CJK/Cyrillic/Arabic/etc, "
                        "stopword+diacritic fingerprinting for Latin languages. Zero-dependency.",
            tags=["language", "i18n", "nlp"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not isinstance(context.get("text", ""), str):
            raise ValueError("'text' must be a string")

    def _execute_impl(self, context):
        text = context["text"]
        result = detect_language(text)
        # 兼容旧返回字段 char_distribution (映射到 scripts)
        result["char_distribution"] = result.get("scripts", {})
        return result


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
