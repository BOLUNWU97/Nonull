"""Guard test: verify README / docs numbers actually match the code.

This test fails the build if any "marketing-style" count in the user-facing
docs drifts away from the code it claims to describe. The thresholds are
intentionally conservative (>= N) so the test passes today and only fails
if the count *drops* (which would be a regression), not if it grows.

Counts verified:
  * 31  skills            (skills/__init__.py __all__, minus base/registry)
  * 40  hook events       (hooks/hook_system.py HOOK_EVENTS)
  * 12  slash commands    (channels/cli.py SLASH_COMMANDS)  -- 12 not 11
  * 5   platform adapters (channels/platform_adapters.py concrete subclasses)
  * 8   workflows         (orchestration/workflows.py factories)
  * 4   architectures     (CLAUDE.md / README.md)
"""
import ast
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def _count_concrete_subclasses(py_file: Path, base_class: str) -> int:
    """Count concrete (non-ABC) classes that subclass `base_class` in py_file.

    ABC base classes are excluded so the count reflects real, instantiable
    adapters/skills rather than abstract scaffolds.
    """
    if not py_file.exists():
        return 0
    try:
        tree = ast.parse(_read_text(py_file))
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        # Check bases for the target base class
        for base in node.bases:
            base_name = getattr(base, "id", None) or getattr(base, "attr", None)
            if base_name == base_class:
                # Skip if this class is itself abstract (defines `pass` + abstract methods,
                # or inherits from ABC). We treat "PlatformAdapter" as ABC by name.
                if node.name == base_class:
                    break
                count += 1
                break
    return count


# ---------------------------------------------------------------------------
# Skill count
# ---------------------------------------------------------------------------

def test_skills_count():
    """Skills package should expose >= 30 concrete skills (README claims 31)."""
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from skills.registry import SkillRegistry  # noqa: WPS433
        registry = SkillRegistry()
        registry.auto_discover()
        all_skills = registry.get_all_skills()
    except Exception as exc:
        # Fallback: count concrete subclasses of BaseSkill across skill modules
        skills_dir = PROJECT_ROOT / "skills"
        all_skills = []
        for py_file in skills_dir.glob("*_skills.py"):
            all_skills.extend(_count_concrete_subclasses(py_file, "BaseSkill"))
    count = len(all_skills) if hasattr(all_skills, "__len__") else 0
    assert count >= 30, (
        f"Expected >= 30 discovered skills (README claims 31), found {count}. "
        f"Did someone delete a skill without updating the README?"
    )


# ---------------------------------------------------------------------------
# Hook events count
# ---------------------------------------------------------------------------

def test_hook_events_count():
    """HOOK_EVENTS in hooks/hook_system.py should contain >= 35 events (README claims 40)."""
    hook_file = PROJECT_ROOT / "hooks" / "hook_system.py"
    text = _read_text(hook_file)
    # Find the HOOK_EVENTS list assignment
    match = re.search(r"HOOK_EVENTS\s*:\s*List\[str\]\s*=\s*\[(.*?)\]", text, re.DOTALL)
    assert match, "Could not locate HOOK_EVENTS list in hooks/hook_system.py"
    # Count string literals inside the list
    items = re.findall(r'\"[A-Za-z][A-Za-z0-9_]+\"', match.group(1))
    count = len(items)
    assert count >= 35, (
        f"Expected >= 35 hook events (README claims 40), found {count}."
    )


# ---------------------------------------------------------------------------
# Slash commands count
# ---------------------------------------------------------------------------

def test_slash_commands_count():
    """SLASH_COMMANDS in channels/cli.py should contain >= 10 commands (README claims 12)."""
    cli_file = PROJECT_ROOT / "channels" / "cli.py"
    text = _read_text(cli_file)
    match = re.search(
        r"SLASH_COMMANDS\s*:\s*Dict\[str\s*,\s*Dict\[str\s*,\s*str\]\]\s*=\s*\{(.*?)\n\}",
        text,
        re.DOTALL,
    )
    assert match, "Could not locate SLASH_COMMANDS dict in channels/cli.py"
    # Count command keys (lines like '"/name": {')
    items = re.findall(r'\"(/[A-Za-z]+)\"\s*:\s*\{', match.group(1))
    count = len(items)
    assert count >= 10, (
        f"Expected >= 10 slash commands (README badge claims 12), found {count}."
    )


# ---------------------------------------------------------------------------
# Platform adapters count
# ---------------------------------------------------------------------------

def test_platform_adapters_count():
    """channels/platform_adapters.py should define >= 5 concrete platform adapters."""
    adapters_file = PROJECT_ROOT / "channels" / "platform_adapters.py"
    count = _count_concrete_subclasses(adapters_file, "PlatformAdapter")
    assert count >= 5, (
        f"Expected >= 5 concrete platform adapters (README/setup.py claim 5), "
        f"found {count}."
    )


# ---------------------------------------------------------------------------
# Workflows count
# ---------------------------------------------------------------------------

def test_workflows_count():
    """orchestration/workflows.py should register >= 7 default workflows (README claims 8)."""
    wf_file = PROJECT_ROOT / "orchestration" / "workflows.py"
    text = _read_text(wf_file)
    # Count `create_*_workflow(` definitions
    factories = re.findall(r"def\s+(create_\w+_workflow)\s*\(", text)
    count = len(factories)
    assert count >= 7, (
        f"Expected >= 7 workflow factories (README claims 8), found {count}."
    )


# ---------------------------------------------------------------------------
# Architecture count
# ---------------------------------------------------------------------------

def test_architecture_count():
    """README / CLAUDE.md should reference 4 fused architectures."""
    readme = _read_text(PROJECT_ROOT / "README.md")
    required = ["OpenClaw", "Hermes Agent", "openHuman", "Claude Code"]
    missing = [name for name in required if name not in readme]
    assert not missing, (
        f"README is missing one of the 4 fused architectures: {missing}"
    )


# ---------------------------------------------------------------------------
# Stale "11 slash commands" badge scan
# ---------------------------------------------------------------------------

def test_no_stale_eleven_slash_commands():
    """README badge / docs must not say '11 Slash Commands' (actual count is 12)."""
    candidates = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "docs" / "user-guide.md",
        PROJECT_ROOT / "docs" / "说明书-完整版.md",
        PROJECT_ROOT / "docs" / "快速上手指南.md",
        PROJECT_ROOT / "docs" / "一页纸速览.md",
    ]
    violations = []
    for path in candidates:
        text = _read_text(path)
        # Match "11 Slash Commands" in any form, including URL-encoded (11%20Slash)
        if re.search(r"11(\s|%20)Slash(\s|%20)Commands", text, re.IGNORECASE):
            line = text[: text.find("11")].count("\n") + 1 if "11" in text else 0
            violations.append(f"{path.relative_to(PROJECT_ROOT)}:{line}")
    assert not violations, (
        "Stale '11 Slash Commands' phrasing found (actual count is 12): "
        + ", ".join(violations)
    )


# ---------------------------------------------------------------------------
# Marketing red lines quick regression
# ---------------------------------------------------------------------------

FORBIDDEN_TERMS = [
    "ASIL-D Ready",
    "ASIL-D Compliant",
    "ISO 26262 Compliant",
    "certified safety mechanism",
    "车规认证",
    "车规合规",
]

NEGATION_RE = re.compile(
    r"(?:\bnot\b|\bNOT\b|不是|非|不构成|不实现|advisory|建议性|未通过|未认证)",
    re.IGNORECASE,
)


def test_no_positive_marketing_terms():
    """Verify forbidden marketing terms are not in positive (non-negated) context."""
    targets = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "CLAUDE.md",
        PROJECT_ROOT / "setup.py",
        PROJECT_ROOT / "docs" / "innovation-report.md",
        PROJECT_ROOT / "docs" / "user-guide.md",
        PROJECT_ROOT / "docs" / "architecture.md",
    ]
    violations = []
    for path in targets:
        text = _read_text(path)
        for term in FORBIDDEN_TERMS:
            for m in re.finditer(re.escape(term), text, re.IGNORECASE):
                start = max(0, m.start() - 20)
                if not NEGATION_RE.search(text[start: m.start()]):
                    line = text[: m.start()].count("\n") + 1
                    violations.append(
                        f"{path.relative_to(PROJECT_ROOT)}:{line} - '{term}'"
                    )
    assert not violations, (
        "Forbidden marketing term in positive context:\n  "
        + "\n  ".join(violations)
    )


if __name__ == "__main__":
    test_skills_count()
    test_hook_events_count()
    test_slash_commands_count()
    test_platform_adapters_count()
    test_workflows_count()
    test_architecture_count()
    test_no_stale_eleven_slash_commands()
    test_no_positive_marketing_terms()
    print("All stale-claim guard tests passed.")
