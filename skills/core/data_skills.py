"""
Data utilities / 数据处理通用技能
"""
from __future__ import annotations
import csv
import io
import json
import re
from difflib import unified_diff
from typing import Any, Dict, List
from skills.base import BaseSkill, SkillMetadata, SkillCategory


class JsonFormatterSkill(BaseSkill):
    """Pretty-print, validate, or minify JSON."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="json_formatter",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Format, validate, or minify JSON. Operations: 'pretty', 'minify', 'validate'.",
            tags=["json", "format", "data"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("json_str"):
            raise ValueError("'json_str' is required")
        op = context.get("operation", "pretty")
        if op not in ("pretty", "minify", "validate"):
            raise ValueError(f"operation must be pretty|minify|validate, got {op!r}")

    def _execute_impl(self, context):
        json_str = context["json_str"]
        op = context.get("operation", "pretty")
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return {"valid": False, "error": str(e), "operation": op}

        result = {"valid": True, "operation": op}
        if op == "pretty":
            result["output"] = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
        elif op == "minify":
            result["output"] = json.dumps(data, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
        elif op == "validate":
            result["output"] = json.dumps(data, ensure_ascii=False, sort_keys=True)[:200]  # preview
        return result


class CsvParserSkill(BaseSkill):
    """Parse CSV string to list of dicts."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="csv_parser",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Parse a CSV string to a list of row dicts.",
            tags=["csv", "parse", "data"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("csv_str"):
            raise ValueError("'csv_str' is required")

    def _execute_impl(self, context):
        csv_str = context["csv_str"]
        delimiter = context.get("delimiter", ",")
        try:
            reader = csv.DictReader(io.StringIO(csv_str), delimiter=delimiter)
            rows = list(reader)
        except Exception as e:
            return {"error": str(e), "rows": []}
        return {
            "row_count": len(rows),
            "rows": rows,
            "columns": list(rows[0].keys()) if rows else [],
        }


class TextStatisticsSkill(BaseSkill):
    """Count characters, words, lines, sentences in text."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="text_statistics",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Compute basic statistics on text: chars, words, lines, sentences, paragraphs.",
            tags=["text", "statistics", "nlp"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not isinstance(context.get("text", ""), str):
            raise ValueError("'text' must be a string")

    def _execute_impl(self, context):
        text = context["text"]
        chars = len(text)
        chars_no_ws = len(re.sub(r"\s+", "", text))
        words = len(text.split())
        lines = text.count("\n") + (1 if text else 0)
        sentences = len(re.findall(r"[.!?。！？]+", text))
        paragraphs = len([p for p in text.split("\n\n") if p.strip()])
        return {
            "chars": chars,
            "chars_no_whitespace": chars_no_ws,
            "words": words,
            "lines": lines,
            "sentences": sentences,
            "paragraphs": paragraphs,
        }


class DiffSkill(BaseSkill):
    """Compute a line-by-line diff between two strings."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="diff",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Compute a unified diff between two text strings.",
            tags=["diff", "text", "compare"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not isinstance(context.get("a", ""), str) or not isinstance(context.get("b", ""), str):
            raise ValueError("'a' and 'b' must both be strings")

    def _execute_impl(self, context):
        a_lines = context["a"].splitlines(keepends=True)
        b_lines = context["b"].splitlines(keepends=True)
        diff = list(unified_diff(a_lines, b_lines, fromfile="a", tofile="b", lineterm=""))
        return {
            "diff": "\n".join(diff),
            "change_count": sum(1 for line in diff if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))),
        }
