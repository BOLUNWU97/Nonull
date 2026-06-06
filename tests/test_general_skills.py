"""Tests for the 19 general-purpose skills under skills/core/.

These skills are domain-agnostic and work for ANY task. They cover web,
data, code, documentation, translation, and utility operations.
"""
from __future__ import annotations

import os
import sys

import pytest

# Ensure project root is importable when running pytest from any CWD.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.base import BaseSkill, SkillResult
from skills.core.web_skills import (
    WebFetchSkill,
    WebSearchSkill,
    LinkExtractorSkill,
)
from skills.core.data_skills import (
    JsonFormatterSkill,
    CsvParserSkill,
    TextStatisticsSkill,
    DiffSkill,
)
from skills.core.code_skills import (
    RegexBuilderSkill,
    JsonSchemaGeneratorSkill,
    CodeCounterSkill,
)
from skills.core.documentation_skills import (
    MarkdownToHtmlSkill,
    ReadmeSkeletonSkill,
    DocstringGeneratorSkill,
)
from skills.core.translation_skills import (
    LanguageDetectorSkill,
    TranslationPromptSkill,
)
from skills.core.utilities_skills import (
    UuidGeneratorSkill,
    HashSkill,
    TimestampSkill,
    Base64Skill,
)


def _activate(skill: BaseSkill) -> BaseSkill:
    skill.activate()
    return skill


# =============================================================================
# Web skills
# =============================================================================


class TestWebSearchSkill:
    """WebSearchSkill is a stub that returns a clear demo warning."""

    def test_search_returns_demo_warning(self):
        skill = _activate(WebSearchSkill())
        result = skill.execute({"query": "test query"})
        assert result.success
        assert result.data["query"] == "test query"
        assert result.data["results"] == []
        assert "DEMO PLACEHOLDER" in result.data["warning"]

    def test_search_validates_query(self):
        skill = _activate(WebSearchSkill())
        result = skill.execute({})
        assert not result.success
        assert "query" in result.error.lower()


class TestLinkExtractorSkill:
    def test_extracts_deduped_links(self):
        skill = _activate(LinkExtractorSkill())
        html = '<a href="https://a.com">A</a> <a href="/b">B</a> <a href="https://a.com">A2</a>'
        result = skill.execute({"content": html})
        assert result.success
        # Deduplicated, order preserved
        assert result.data["link_count"] == 2
        assert result.data["links"] == ["https://a.com", "/b"]

    def test_validates_content(self):
        skill = _activate(LinkExtractorSkill())
        result = skill.execute({"content": ""})
        assert not result.success


# =============================================================================
# Data skills
# =============================================================================


class TestJsonFormatterSkill:
    def test_pretty(self):
        skill = _activate(JsonFormatterSkill())
        result = skill.execute({"json_str": '{"b":1,"a":2}', "operation": "pretty"})
        assert result.success
        assert result.data["valid"] is True
        assert result.data["output"] == '{\n  "a": 2,\n  "b": 1\n}'

    def test_minify(self):
        skill = _activate(JsonFormatterSkill())
        result = skill.execute({"json_str": '{ "a":  1 }', "operation": "minify"})
        assert result.success
        assert result.data["output"] == '{"a":1}'

    def test_validate_invalid(self):
        skill = _activate(JsonFormatterSkill())
        result = skill.execute({"json_str": "not json", "operation": "validate"})
        assert result.success  # The skill succeeds but reports invalid
        assert result.data["valid"] is False
        assert "error" in result.data

    def test_invalid_operation_rejected(self):
        skill = _activate(JsonFormatterSkill())
        result = skill.execute({"json_str": "{}", "operation": "explode"})
        assert not result.success


class TestCsvParserSkill:
    def test_parse_basic_csv(self):
        skill = _activate(CsvParserSkill())
        csv_str = "name,age\nAlice,30\nBob,25\n"
        result = skill.execute({"csv_str": csv_str})
        assert result.success
        assert result.data["row_count"] == 2
        assert result.data["columns"] == ["name", "age"]
        assert result.data["rows"][0] == {"name": "Alice", "age": "30"}

    def test_custom_delimiter(self):
        skill = _activate(CsvParserSkill())
        result = skill.execute({"csv_str": "a|b\n1|2\n", "delimiter": "|"})
        assert result.success
        assert result.data["rows"][0] == {"a": "1", "b": "2"}


class TestTextStatisticsSkill:
    def test_basic_counts(self):
        skill = _activate(TextStatisticsSkill())
        text = "Hello world.\nThis is a test.\n\nAnother paragraph."
        result = skill.execute({"text": text})
        assert result.success
        stats = result.data
        assert stats["words"] == 8  # Hello world This is a test Another paragraph
        assert stats["sentences"] >= 2
        assert stats["paragraphs"] == 2
        assert stats["chars"] == len(text)
        assert stats["chars_no_whitespace"] < stats["chars"]

    def test_empty_text(self):
        skill = _activate(TextStatisticsSkill())
        result = skill.execute({"text": ""})
        assert result.success
        assert result.data["words"] == 0
        assert result.data["paragraphs"] == 0


class TestDiffSkill:
    def test_detects_changes(self):
        skill = _activate(DiffSkill())
        result = skill.execute({"a": "line1\nline2\nline3\n", "b": "line1\nline2-modified\nline3\n"})
        assert result.success
        assert result.data["change_count"] >= 1
        assert "line2-modified" in result.data["diff"]

    def test_identical_inputs(self):
        skill = _activate(DiffSkill())
        result = skill.execute({"a": "same\n", "b": "same\n"})
        assert result.success
        assert result.data["change_count"] == 0


# =============================================================================
# Code skills
# =============================================================================


class TestRegexBuilderSkill:
    def test_finds_matches(self):
        skill = _activate(RegexBuilderSkill())
        result = skill.execute({"pattern": r"\d+", "text": "abc 123 def 456"})
        assert result.success
        assert result.data["match_count"] == 2
        assert result.data["matches"][0]["match"] == "123"
        assert result.data["matches"][0]["start"] == 4

    def test_case_insensitive_flag(self):
        skill = _activate(RegexBuilderSkill())
        result = skill.execute({"pattern": "hello", "text": "Hello world", "flags": "i"})
        assert result.success
        assert result.data["match_count"] == 1

    def test_invalid_regex(self):
        skill = _activate(RegexBuilderSkill())
        result = skill.execute({"pattern": "[invalid", "text": "anything"})
        assert result.success  # Skill itself succeeds, returns error in data
        assert "error" in result.data


class TestJsonSchemaGeneratorSkill:
    def test_generates_model(self):
        skill = _activate(JsonSchemaGeneratorSkill())
        schema = {
            "title": "User",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "active": {"type": "boolean"},
            },
            "required": ["id"],
        }
        result = skill.execute({"schema": schema})
        assert result.success
        code = result.data["python_code"]
        assert "class User(BaseModel)" in code
        assert "id: int" in code
        assert "name: str = None" in code
        assert "active: bool = None" in code

    def test_empty_schema(self):
        skill = _activate(JsonSchemaGeneratorSkill())
        result = skill.execute({"schema": {}})
        assert result.success
        assert "class GeneratedModel" in result.data["python_code"]


class TestCodeCounterSkill:
    def test_python_counts(self):
        skill = _activate(CodeCounterSkill())
        code = "# comment\n\ndef f():\n    pass\n# another comment\n"
        result = skill.execute({"code": code, "language": "python"})
        assert result.success
        assert result.data["language"] == "python"
        assert result.data["total_lines"] == 6
        assert result.data["blank_lines"] >= 1
        assert result.data["comment_lines"] == 2
        assert result.data["code_lines"] >= 1

    def test_cpp_counts(self):
        skill = _activate(CodeCounterSkill())
        code = "// cpp comment\nint main() { return 0; }\n"
        result = skill.execute({"code": code, "language": "cpp"})
        assert result.success
        assert result.data["comment_lines"] == 1


# =============================================================================
# Documentation skills
# =============================================================================


class TestMarkdownToHtmlSkill:
    def test_basic_conversion(self):
        skill = _activate(MarkdownToHtmlSkill())
        md = "# Title\n\nThis is **bold** and *italic* with `code`."
        result = skill.execute({"markdown": md})
        assert result.success
        html = result.data["html"]
        assert "<h1>Title</h1>" in html
        assert "<strong>bold</strong>" in html
        assert "<em>italic</em>" in html
        assert "<code>code</code>" in html

    def test_link_conversion(self):
        skill = _activate(MarkdownToHtmlSkill())
        result = skill.execute({"markdown": "[Nonull](https://nonull.io)"})
        assert result.success
        assert '<a href="https://nonull.io">Nonull</a>' in result.data["html"]


class TestReadmeSkeletonSkill:
    def test_generates_readme(self):
        skill = _activate(ReadmeSkeletonSkill())
        result = skill.execute({"project_name": "MyTool", "description": "A great tool."})
        assert result.success
        assert result.data["filename"] == "README.md"
        assert "# MyTool" in result.data["readme"]
        assert "A great tool." in result.data["readme"]
        assert "## Installation" in result.data["readme"]

    def test_requires_name(self):
        skill = _activate(ReadmeSkeletonSkill())
        result = skill.execute({})
        assert not result.success


class TestDocstringGeneratorSkill:
    def test_generates_docstring(self):
        skill = _activate(ReadmeSkeletonSkill())
        result = skill.execute({
            "project_name": "test",
        })  # sanity: skeleton works
        assert result.success

        # Now the real docstring skill
        skill = _activate(DocstringGeneratorSkill())
        result = skill.execute({
            "signature": "def add(a: int, b: int) -> int:",
        })
        assert result.success
        assert "def add" in result.data["docstring"]
        assert "Args:" in result.data["docstring"]
        assert "Returns:" in result.data["docstring"]


# =============================================================================
# Translation skills
# =============================================================================


class TestLanguageDetectorSkill:
    def test_detects_english(self):
        skill = _activate(LanguageDetectorSkill())
        result = skill.execute({"text": "The quick brown fox jumps over the lazy dog"})
        assert result.success
        assert result.data["language"] == "en"

    def test_detects_chinese(self):
        skill = _activate(LanguageDetectorSkill())
        result = skill.execute({"text": "你好世界，这是一个测试"})
        assert result.success
        assert result.data["language"] == "zh"

    def test_empty_text(self):
        skill = _activate(LanguageDetectorSkill())
        result = skill.execute({"text": "   "})
        assert result.success
        assert result.data["language"] == "unknown"


class TestTranslationPromptSkill:
    def test_generates_prompt(self):
        skill = _activate(TranslationPromptSkill())
        result = skill.execute({
            "text": "Hello world",
            "target_lang": "zh",
            "source_lang": "en",
        })
        assert result.success
        prompt = result.data["prompt"]
        assert "from en to zh" in prompt
        assert "Hello world" in prompt

    def test_includes_glossary(self):
        skill = _activate(TranslationPromptSkill())
        result = skill.execute({
            "text": "API",
            "target_lang": "zh",
            "glossary": {"API": "接口"},
        })
        assert result.success
        assert "API" in result.data["prompt"]
        assert "接口" in result.data["prompt"]


# =============================================================================
# Utility skills
# =============================================================================


class TestUuidGeneratorSkill:
    def test_generates_uuid_v4(self):
        skill = _activate(UuidGeneratorSkill())
        result = skill.execute({"count": 3})
        assert result.success
        assert result.data["count"] == 3
        assert len(result.data["uuids"]) == 3
        for u in result.data["uuids"]:
            # v4 uuid has 4 in the 13th position (after the 2nd dash)
            assert u[14] == "4"

    def test_validates_count_range(self):
        skill = _activate(UuidGeneratorSkill())
        result = skill.execute({"count": 0})
        assert not result.success
        result = skill.execute({"count": 1001})
        assert not result.success

    def test_uuid_uniqueness(self):
        skill = _activate(UuidGeneratorSkill())
        result = skill.execute({"count": 100})
        uuids = result.data["uuids"]
        assert len(set(uuids)) == 100, "UUIDs should be unique"


class TestHashSkill:
    def test_sha256(self):
        skill = _activate(HashSkill())
        result = skill.execute({"text": "hello", "algorithm": "sha256"})
        assert result.success
        assert result.data["algorithm"] == "sha256"
        assert result.data["hash"] == (
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )

    def test_md5(self):
        skill = _activate(HashSkill())
        result = skill.execute({"text": "hello", "algorithm": "md5"})
        assert result.success
        assert result.data["hash"] == "5d41402abc4b2a76b9719d911017c592"

    def test_invalid_algorithm(self):
        skill = _activate(HashSkill())
        result = skill.execute({"text": "x", "algorithm": "ripemd"})
        assert not result.success


class TestTimestampSkill:
    def test_returns_iso_format(self):
        skill = _activate(TimestampSkill())
        result = skill.execute({})
        assert result.success
        assert "T" in result.data["iso"]
        assert isinstance(result.data["unix"], int)
        assert result.data["utc"] is True

    def test_local_time(self):
        skill = _activate(TimestampSkill())
        result = skill.execute({"utc": False})
        assert result.success
        assert result.data["utc"] is False


class TestBase64Skill:
    def test_encode_decode_roundtrip(self):
        skill = _activate(Base64Skill())
        enc = skill.execute({"text": "hello world", "operation": "encode"})
        assert enc.success
        encoded = enc.data["output"]

        dec = skill.execute({"text": encoded, "operation": "decode"})
        assert dec.success
        assert dec.data["output"] == "hello world"

    def test_invalid_decode(self):
        skill = _activate(Base64Skill())
        result = skill.execute({"text": "@@@not-base64@@@", "operation": "decode"})
        # Either succeeds with error in data, or fails — both acceptable
        if result.success:
            assert "error" in result.data
        else:
            assert result.error is not None


# =============================================================================
# Registry integration: all 19 skills must be auto-discoverable.
# =============================================================================


class TestGeneralSkillsRegistry:
    """All 19 new general-purpose skills should auto-discover via the registry."""

    EXPECTED_SKILLS = [
        "web_fetch", "web_search", "link_extractor",
        "json_formatter", "csv_parser", "text_statistics", "diff",
        "regex_tester", "json_schema_generator", "code_counter",
        "markdown_to_html", "readme_skeleton", "docstring_generator",
        "language_detector", "translation_prompt",
        "uuid_generator", "hash", "timestamp", "base64",
    ]

    def test_all_general_skills_discoverable(self):
        from skills.registry import SkillRegistry
        reg = SkillRegistry()
        reg.auto_discover()
        names = {s.metadata.name for s in reg.get_all_skills()}
        missing = set(self.EXPECTED_SKILLS) - names
        assert not missing, (
            f"Missing general-purpose skills: {missing}. "
            f"Discovered: {sorted(names)}"
        )

    def test_all_general_skills_in_general_category(self):
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

    def test_no_duplicate_names(self):
        from skills.registry import SkillRegistry
        reg = SkillRegistry()
        reg.auto_discover()
        names = [s.metadata.name for s in reg.get_all_skills()]
        assert len(names) == len(set(names)), (
            f"Duplicate skill names detected: "
            f"{[n for n in names if names.count(n) > 1]}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
