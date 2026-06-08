"""File system skills — LangChain Deep Agents style."""
from typing import Any, Dict
from skills.base import BaseSkill, SkillMetadata, SkillCategory
from skills.filesystem.backend import get_backend


class ReadFileSkill(BaseSkill):
    """Read a file with optional line offset/limit."""
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="file_read", version="0.1.0", category=SkillCategory.GENERAL,
            description="Read a file with optional line offset and limit.",
            tags=["filesystem", "read", "file"], safety_level=2)
    def _validate_input(self, ctx):
        if not ctx.get("path"): raise ValueError("'path' required")
    def _execute_impl(self, ctx):
        return get_backend().read(ctx["path"], ctx.get("offset", 0), ctx.get("limit"))


class WriteFileSkill(BaseSkill):
    """Write content to a file."""
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="file_write", version="0.1.0", category=SkillCategory.GENERAL,
            description="Write content to a file (overwrites existing). Safe for small files.",
            tags=["filesystem", "write", "file"], safety_level=3)
    def _validate_input(self, ctx):
        if not ctx.get("path"): raise ValueError("'path' required")
        if "content" not in ctx: raise ValueError("'content' required")
    def _execute_impl(self, ctx):
        return {"success": get_backend().write(ctx["path"], ctx["content"]), "path": ctx["path"]}


class EditFileSkill(BaseSkill):
    """Edit a file by replacing text."""
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="file_edit", version="0.1.0", category=SkillCategory.GENERAL,
            description="Edit a file by replacing old_str with new_str (first occurrence).",
            tags=["filesystem", "edit", "file"], safety_level=3)
    def _validate_input(self, ctx):
        for k in ("path", "old_str", "new_str"):
            if not ctx.get(k): raise ValueError(f"'{k}' required")
    def _execute_impl(self, ctx):
        ok = get_backend().edit(ctx["path"], ctx["old_str"], ctx["new_str"])
        return {"success": ok, "path": ctx["path"]}


class GlobSkill(BaseSkill):
    """Find files matching a glob pattern."""
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="glob", version="0.1.0", category=SkillCategory.GENERAL,
            description="Find files matching a glob pattern (e.g. **/*.py).",
            tags=["filesystem", "glob", "search"], safety_level=1)
    def _validate_input(self, ctx):
        if not ctx.get("pattern"): raise ValueError("'pattern' required")
    def _execute_impl(self, ctx):
        return {"files": get_backend().glob(ctx["pattern"])}


class GrepSkill(BaseSkill):
    """Search for a regex pattern in files."""
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="grep", version="0.1.0", category=SkillCategory.GENERAL,
            description="Search for a regex pattern in files. Returns matches with file:line.",
            tags=["filesystem", "grep", "search", "regex"], safety_level=1)
    def _validate_input(self, ctx):
        if not ctx.get("pattern"): raise ValueError("'pattern' required")
        if not ctx.get("path"): raise ValueError("'path' required")
    def _execute_impl(self, ctx):
        return {"matches": get_backend().grep(ctx["pattern"], ctx["path"], ctx.get("recursive", True))}


class ListDirSkill(BaseSkill):
    """List files and directories in a path."""
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="list_dir", version="0.1.0", category=SkillCategory.GENERAL,
            description="List files and directories in a path (non-recursive).",
            tags=["filesystem", "list", "directory"], safety_level=1)
    def _validate_input(self, ctx):
        if not ctx.get("path"): raise ValueError("'path' required")
    def _execute_impl(self, ctx):
        return {"files": get_backend().list_dir(ctx["path"])}
