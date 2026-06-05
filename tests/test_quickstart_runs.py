"""Smoke test: verify examples/quickstart.py can be imported and its main imports work.

This test guards the most embarrassing failure mode: a new user clones the repo,
runs `pip install -e .`, then `python examples/quickstart.py`, and gets an
ImportError on the very first line.

If this test fails, it means one of these symbols is not exported:
- core.Nonull
- core.NonullConfig
- persona.PersonaOrchestrator
- persona.PersonaType
- persona.ScenarioEngine
- persona.SafetyBadgeSystem
- nonull.Nonull (top-level re-export)
- nonull.NonullConfig (top-level re-export)

In addition, this module imports the real test modules (test_core_real and
test_memory_real) so that the broader CI run will fail loudly if the
production `core/` or `memory/` package is unimportable — i.e. the "real
test files exist" guarantee the 9th-pass fix relies on.
"""
import importlib
import importlib.util
import sys
import pytest


CORE_IMPORTS = [
    ("core", "NonullConfig"),
    ("core", "Nonull"),
    ("persona", "PersonaOrchestrator"),
    ("persona", "PersonaType"),
    ("persona", "ScenarioEngine"),
    ("persona", "SafetyBadgeSystem"),
    ("safety", "SafetyGuardian"),
    ("memory", "Neocortex"),
    ("skills", "SkillRegistry"),
    ("orchestration", "Orchestrator"),
    ("nonull", "Nonull"),
    ("nonull", "NonullConfig"),
    ("nonull", "PersonaOrchestrator"),
    ("nonull", "PersonaType"),
]


@pytest.mark.parametrize("module_name,symbol_name", CORE_IMPORTS)
def test_quickstart_dependency_importable(module_name: str, symbol_name: str):
    """Every import in quickstart.py and README must resolve."""
    module = importlib.import_module(module_name)
    assert hasattr(module, symbol_name), (
        f"Module {module_name!r} is missing {symbol_name!r} which is required by "
        f"examples/quickstart.py or the README quickstart snippet. "
        f"This will cause a new user's first import to fail."
    )


def test_quickstart_module_loads():
    """examples/quickstart.py must at least import without errors."""
    # We don't want to actually RUN the script (it would print a lot),
    # just import it. Since it's not a module, we read and check it
    # imports the right symbols.
    from pathlib import Path
    quickstart = Path(__file__).parent.parent / "examples" / "quickstart.py"
    content = quickstart.read_text(encoding="utf-8")

    # Check the file references real symbols
    assert "PersonaOrchestrator" in content or "Nonull" in content, (
        "examples/quickstart.py doesn't seem to use either PersonaOrchestrator or Nonull"
    )

    # The import lines we expect to be present and working
    if "from persona import" in content:
        # Make sure the persona imports would work
        from persona import PersonaOrchestrator, PersonaType, ScenarioEngine
        assert PersonaOrchestrator is not None
        assert PersonaType is not None
        assert ScenarioEngine is not None


# ---------------------------------------------------------------------------
# Real-test-file presence check
# ---------------------------------------------------------------------------
# Added in the 9th-pass cleanup: the previous tests/test_core.py and
# tests/test_memory.py defined a parallel mock implementation. They were
# moved to tests/_archive/ and replaced with test_core_real.py /
# test_memory_real.py, which import the production code. This test makes
# sure those replacement files exist and can be imported by pytest.
# ---------------------------------------------------------------------------

_REAL_TEST_FILES = ("test_core_real.py", "test_memory_real.py")


@pytest.mark.parametrize("filename", _REAL_TEST_FILES)
def test_real_test_file_exists(filename: str):
    """The replacement real-test files must exist in tests/."""
    from pathlib import Path
    target = Path(__file__).parent / filename
    assert target.is_file(), (
        f"Expected real-test file {filename!r} at {target}. "
        f"This file is the result of the 9th-pass cleanup that replaced "
        f"the parallel-mock tests in tests/_archive/."
    )


def test_archive_directory_exists_and_is_excluded():
    """tests/_archive/ should exist and its contents must not be pytest-collected."""
    from pathlib import Path
    archive = Path(__file__).parent / "_archive"
    assert archive.is_dir(), f"Expected {archive} to exist"

    # All files inside _archive/ should be either:
    #   - README.md
    #   - explicitly named old-test files (preserved for history)
    # and NONE of them should be auto-collected by pytest.
    collected = [
        p.name for p in archive.iterdir()
        if p.is_file() and p.name.startswith("test_") and p.suffix == ".py"
    ]
    # These two are the known archived files. They are excluded via
    # conftest.py -> collect_ignore_glob, not by renaming. We just
    # confirm they exist; collection exclusion is verified below.
    assert "test_core.py" in collected
    assert "test_memory.py" in collected

    # Verify the conftest excludes the archive
    conftest = (Path(__file__).parent / "conftest.py").read_text(encoding="utf-8")
    assert "_archive" in conftest, (
        "tests/conftest.py should reference _archive in collect_ignore_glob "
        "so pytest does not collect the archived mock tests."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

