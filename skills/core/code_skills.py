"""
Programming utilities / 编程辅助技能
"""
from __future__ import annotations
import re
from typing import Any, Dict
from skills.base import BaseSkill, SkillMetadata, SkillCategory


class RegexBuilderSkill(BaseSkill):
    """Test a regex against a string. Returns matches and groups."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="regex_tester",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Test a regular expression against a string. Returns all matches.",
            tags=["regex", "text", "programming"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("pattern"):
            raise ValueError("'pattern' is required")
        if not isinstance(context.get("text", ""), str):
            raise ValueError("'text' must be a string")

    def _execute_impl(self, context):
        pattern = context["pattern"]
        text = context["text"]
        flags_str = context.get("flags", "")
        flag = 0
        if "i" in flags_str: flag |= re.IGNORECASE
        if "m" in flags_str: flag |= re.MULTILINE
        if "s" in flags_str: flag |= re.DOTALL
        try:
            compiled = re.compile(pattern, flag)
        except re.error as e:
            return {"error": f"Invalid regex: {e}", "matches": []}
        matches = [{"match": m.group(0), "start": m.start(), "end": m.end(), "groups": m.groups()} for m in compiled.finditer(text)]
        return {"match_count": len(matches), "matches": matches}


class JsonSchemaGeneratorSkill(BaseSkill):
    """Generate a Pydantic BaseModel from a JSON schema dict."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="json_schema_generator",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Generate a Pydantic BaseModel class definition from a JSON schema dict.",
            tags=["json", "schema", "pydantic", "codegen"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not isinstance(context.get("schema", {}), dict):
            raise ValueError("'schema' must be a dict")

    def _execute_impl(self, context):
        schema = context["schema"]
        title = schema.get("title", "GeneratedModel")
        props = schema.get("properties", {})
        required = schema.get("required", [])

        lines = ["from pydantic import BaseModel", "", f"class {title}(BaseModel):"]
        if not props:
            lines.append("    pass")
        else:
            for name, spec in props.items():
                ptype = self._map_type(spec)
                default = "" if name in required else " = None"
                lines.append(f"    {name}: {ptype}{default}")
        return {"python_code": "\n".join(lines), "class_name": title}

    def _map_type(self, spec: dict) -> str:
        t = spec.get("type", "string")
        if t == "integer": return "int"
        if t == "number": return "float"
        if t == "boolean": return "bool"
        if t == "array": return "list"
        if t == "object": return "dict"
        return "str"


class CodeCounterSkill(BaseSkill):
    """Count lines of code, comments, blanks in source code."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="code_counter",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Count lines, comment lines, and blank lines in source code.",
            tags=["code", "statistics", "metrics"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("code"):
            raise ValueError("'code' is required")

    def _execute_impl(self, context):
        code = context["code"]
        language = context.get("language", "python")
        lines = code.split("\n")
        total = len(lines)
        blanks = sum(1 for l in lines if not l.strip())

        if language == "python":
            comment_pattern = re.compile(r"^\s*#")
            in_block = False
            comments = 0
            for line in lines:
                stripped = line.strip()
                if in_block:
                    comments += 1
                    if "*/" in stripped: in_block = False
                elif stripped.startswith('"""') or stripped.startswith("'''"):
                    comments += 1
                    if stripped.count('"""') == 1 or stripped.count("'''") == 1:
                        in_block = True
                elif comment_pattern.match(line):
                    comments += 1
        else:
            comments = sum(1 for l in lines if l.strip().startswith("//"))

        return {
            "total_lines": total,
            "blank_lines": blanks,
            "comment_lines": comments,
            "code_lines": total - blanks - comments,
            "language": language,
        }
