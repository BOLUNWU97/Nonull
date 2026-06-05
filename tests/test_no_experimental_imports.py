"""Guard test: production code must not import from experimental/.

This test parses all .py files in the production tree (anything not under
experimental/) and fails if any of them contain `from experimental` or
`import experimental` statements.
"""
import ast
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTAL_DIR = PROJECT_ROOT / "experimental"

# Directories that should never import from experimental
PRODUCTION_DIRS = ["core", "memory", "safety", "skills", "orchestration",
                   "persona", "channels", "hooks", "config", "examples", "nonull"]


def test_no_experimental_imports():
    """Verify no production code imports from experimental/."""
    violations = []
    for dir_name in PRODUCTION_DIRS:
        d = PROJECT_ROOT / dir_name
        if not d.exists():
            continue
        for py_file in d.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue  # Let other tests catch syntax errors
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module
                    if module and module.startswith("experimental"):
                        violations.append(
                            f"{py_file.relative_to(PROJECT_ROOT)}:{node.lineno} imports {module}"
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("experimental"):
                            violations.append(
                                f"{py_file.relative_to(PROJECT_ROOT)}:{node.lineno} imports {alias.name}"
                            )
    assert not violations, (
        "Production code must not import from experimental/.\n"
        "Violations:\n  " + "\n  ".join(violations)
    )


def test_experimental_dir_exists():
    """Verify the experimental directory still exists (sanity check)."""
    assert EXPERIMENTAL_DIR.exists(), f"Expected {EXPERIMENTAL_DIR} to exist"


if __name__ == "__main__":
    test_no_experimental_imports()
    test_experimental_dir_exists()
    print("All production code is free of experimental/ imports")
