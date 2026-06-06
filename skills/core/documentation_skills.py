"""
Documentation skills / 文档生成技能
"""
from __future__ import annotations
import re
from typing import Any, Dict, List
from skills.base import BaseSkill, SkillMetadata, SkillCategory


class MarkdownToHtmlSkill(BaseSkill):
    """Convert simple markdown to HTML (subset)."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="markdown_to_html",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Convert basic markdown (headers, bold, italic, code, links) to HTML.",
            tags=["markdown", "html", "documentation"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not isinstance(context.get("markdown", ""), str):
            raise ValueError("'markdown' must be a string")

    def _execute_impl(self, context):
        md = context["markdown"]
        html = md
        # Headers
        html = re.sub(r"^###### (.+)$", r"<h6>\1</h6>", html, flags=re.MULTILINE)
        html = re.sub(r"^##### (.+)$", r"<h5>\1</h5>", html, flags=re.MULTILINE)
        html = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
        # Bold and italic
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
        # Code
        html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
        # Links
        html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)
        # Paragraphs (very naive)
        html = re.sub(r"\n\n", r"</p><p>", html)
        html = f"<p>{html}</p>"
        return {"html": html}


class ReadmeSkeletonSkill(BaseSkill):
    """Generate a README skeleton from a project name + description."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="readme_skeleton",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Generate a README.md skeleton with placeholders for a new project.",
            tags=["readme", "documentation", "template"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("project_name"):
            raise ValueError("'project_name' is required")

    def _execute_impl(self, context):
        name = context["project_name"]
        desc = context.get("description", "TODO: write a one-line description")
        template = f"""# {name}

{desc}

## Installation

```bash
pip install {name.lower().replace(' ', '-')}
```

## Quick Start

```python
from {name.lower().replace(' ', '_')} import main
main()
```

## Documentation

TODO: link to docs

## License

TODO: choose a license
"""
        return {"readme": template, "filename": "README.md"}


class DocstringGeneratorSkill(BaseSkill):
    """Generate a Google-style docstring skeleton for a Python function signature."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="docstring_generator",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Generate a Google-style docstring skeleton from a function signature.",
            tags=["python", "docstring", "documentation"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("signature"):
            raise ValueError("'signature' is required")

    def _execute_impl(self, context):
        sig = context["signature"]
        # Naive parse: extract function name and params
        m = re.match(r"def\s+(\w+)\s*\((.*?)\)\s*(?:->\s*(\S+))?:", sig)
        if not m:
            return {"docstring": '"""TODO: write docstring."""'}
        name, params, ret = m.groups()
        param_list = [p.strip().split(":")[0].strip().split("=")[0].strip() for p in params.split(",") if p.strip() and p.strip() != "self"]
        lines = [f'def {name}({", ".join(["self"] + param_list) if "self" in sig else ", ".join(param_list)}):']
        lines.append(f'    """TODO: one-line summary.')
        lines.append("")
        if param_list:
            lines.append("    Args:")
            for p in param_list:
                lines.append(f"        {p}: TODO")
        if ret:
            lines.append("")
            lines.append("    Returns:")
            lines.append(f"        {ret}: TODO")
        lines.append('    """')
        return {"docstring": "\n".join(lines), "function_name": name, "param_count": len(param_list)}
