"""Guard test: verify user-facing docs do not contain forbidden marketing claims.

This is a smarter version of the CI grep - it handles negation contexts
( e.g. "**不是**车规级" or "**NOT** production-ready" should NOT trigger a fail)
by stripping negation patterns from the text before checking for the forbidden terms.

The forbidden terms list matches the marketing red lines in CLAUDE.md.
"""
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Forbidden marketing terms (case-insensitive). Update if CLAUDE.md red lines change.
FORBIDDEN_TERMS = [
    "ASIL-D Ready",
    "ASIL-D Compliant",
    "ISO 26262 Compliant",
    "production-ready",  # as a positive claim
    "certified safety",
    "certified ISO 26262",
    "车规级",  # 车载规格
]

# Negation patterns that should NOT count as a violation.
# Match these within ~20 chars BEFORE the forbidden term.
NEGATION_PATTERNS = [
    r"\bnot\b",
    r"\bNOT\b",
    r"\bnon[-\s]certified\b",
    r"\bno\s+certification\b",
    r"不是",
    r"非",
    r"不构成",
    r"不实现",
    r"advisory",  # "advisory safety" is fine
    r"建议性",
    r"未通过",
    r"未认证",
]

# Files to check (user-facing docs and root config)
TARGET_FILES = [
    "README.md",
    "CLAUDE.md",
    "AGENT.md",
    "setup.py",
    "config/config.yaml",
    # docs/
    "docs/architecture.md",
    "docs/skills-catalog.md",
    "docs/innovation-report.md",
    "docs/user-guide.md",
    "docs/快速上手指南.md",
    "docs/一页纸速览.md",
    "docs/说明书-完整版.md",
]


def _is_negated(text: str, match_start: int) -> bool:
    """Check if the match is preceded by a negation pattern within 20 chars."""
    context_start = max(0, match_start - 20)
    context = text[context_start:match_start]
    for pat in NEGATION_PATTERNS:
        if re.search(pat, context, re.IGNORECASE):
            return True
    return False


def test_no_marketing_claims():
    """Verify forbidden marketing claims are not present (modulo negation)."""
    violations = []
    for rel_path in TARGET_FILES:
        file_path = PROJECT_ROOT / rel_path
        if not file_path.exists():
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for term in FORBIDDEN_TERMS:
            for m in re.finditer(re.escape(term), text, re.IGNORECASE):
                if not _is_negated(text, m.start()):
                    line = text[:m.start()].count("\n") + 1
                    violations.append(f"{rel_path}:{line} - '{term}' not in negation context")
    assert not violations, (
        "Found forbidden marketing claims not in negation context:\n  "
        + "\n  ".join(violations)
    )


if __name__ == "__main__":
    test_no_marketing_claims()
    print("✓ No forbidden marketing claims found (excluding negation contexts)")
