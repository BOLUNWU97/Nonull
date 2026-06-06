"""Tests for skill execution backends (P16).

Covers:
- InlineBackend (same-process, in-process exec)
- SubprocessBackend (separate process, wall-clock timeout)
- DockerBackend (gracefully reports unavailable when no Docker is installed)
- HTTPBackend (graceful error on unreachable remote)
- CodeRunnerSkill (the BaseSkill wrapper around the backends)
- get_backend() factory and registry.auto_discover() integration
"""
from __future__ import annotations

import os
import sys

import pytest

# Ensure project root is importable when running pytest from any CWD.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.execution import get_backend
from skills.execution.inline import InlineBackend
from skills.execution.subprocess_backend import SubprocessBackend
from skills.execution.docker_backend import DockerBackend
from skills.execution.http_backend import HTTPBackend
from skills.execution.executable_skill import CodeRunnerSkill


# =============================================================================
# InlineBackend
# =============================================================================


class TestInlineBackend:
    def test_execute_simple_script_returns_result(self):
        backend = InlineBackend()
        out = backend.execute("result = 2 + 2", {})
        assert out["success"] is True
        assert out["result"] == 4

    def test_execute_captures_stdout(self):
        backend = InlineBackend()
        out = backend.execute("print('hello world')", {})
        assert out["success"] is True
        assert "hello world" in out["stdout"]
        assert out["result"] is None  # no `result` was assigned

    def test_execute_injects_context(self):
        backend = InlineBackend()
        out = backend.execute("result = context['x'] * 3", {"x": 5})
        assert out["success"] is True
        assert out["result"] == 15

    def test_execute_captures_exception(self):
        backend = InlineBackend()
        out = backend.execute("raise ValueError('boom')", {})
        assert out["success"] is False
        assert "ValueError" in out["error"]
        assert "boom" in out["error"]
        assert "Traceback" in out["traceback"]

    def test_is_available_always_true(self):
        assert InlineBackend().is_available() is True

    def test_cleanup_is_noop(self):
        # Should not raise.
        InlineBackend().cleanup()


# =============================================================================
# SubprocessBackend
# =============================================================================


class TestSubprocessBackend:
    def test_runs_in_separate_process(self):
        # Smoke: a benign script returns success=True via the JSON envelope.
        # The inner runner scrubs the result namespace; we only assert that
        # the subprocess started, ran, and reported success.
        backend = SubprocessBackend(timeout=10.0)
        out = backend.execute("print('hi from subprocess')", {})
        assert out.get("success") is True, out
        assert out.get("returncode") == 0

    def test_receives_context(self):
        backend = SubprocessBackend(timeout=10.0)
        out = backend.execute(
            "result = context['a'] + context['b']", {"a": 3, "b": 4}
        )
        assert out.get("success") is True, out
        assert out.get("returncode") == 0

    def test_reports_timeout(self):
        # The outer subprocess.run timeout (timeout + 2s grace) is the
        # ultimate enforcement on every platform. On POSIX the inner
        # ITIMER_REAL fires first; on Windows the outer timeout is the
        # only mechanism.
        backend = SubprocessBackend(timeout=1.0)
        out = backend.execute(
            "import time\ntime.sleep(60)\nresult = 'never'", {}
        )
        if out.get("success"):
            pytest.fail(f"Subprocess did not honour timeout: {out}")
        assert "error" in out

    def test_is_available_always_true(self):
        assert SubprocessBackend().is_available() is True


# =============================================================================
# DockerBackend
# =============================================================================


class TestDockerBackend:
    def test_graceful_when_docker_missing(self):
        # The CI / dev sandbox has no Docker daemon. The backend must
        # return a friendly error rather than raising.
        backend = DockerBackend()
        if backend.is_available():
            pytest.skip("Docker is available on this host; nothing to test.")
        out = backend.execute("print('hi')", {})
        assert out["success"] is False
        assert "Docker not available" in out["error"]

    def test_execute_short_circuits_when_unavailable(self):
        backend = DockerBackend()
        if backend.is_available():
            pytest.skip("Docker is available on this host; nothing to test.")
        # Should not raise even though the code is invalid Python.
        out = backend.execute("not valid python @@@", {})
        assert out["success"] is False


# =============================================================================
# HTTPBackend
# =============================================================================


class TestHTTPBackend:
    def test_returns_friendly_error_on_unreachable_host(self):
        # Reserved-for-documentation TEST-NET-1 (RFC 5737) — guaranteed
        # not to route, so we get a connection error rather than a hang.
        backend = HTTPBackend(
            base_url="http://192.0.2.1:9", timeout=2.0
        )
        out = backend.execute("print('hi')", {"x": 1})
        assert out["success"] is False
        assert "HTTP error" in out["error"]

    def test_is_available_false_when_unreachable(self):
        backend = HTTPBackend(
            base_url="http://192.0.2.1:9", timeout=2.0
        )
        assert backend.is_available() is False

    def test_strips_trailing_slash_from_base_url(self):
        # Constructor must normalize the base URL.
        backend = HTTPBackend(base_url="http://example.com/")
        assert backend.base_url == "http://example.com"


# =============================================================================
# CodeRunnerSkill
# =============================================================================


class TestCodeRunnerSkill:
    def test_runs_inline_by_default(self):
        skill = CodeRunnerSkill(backend_name="inline")
        skill.activate()
        try:
            result = skill.execute({"code": "result = 7 * 6", "vars": {}})
        finally:
            skill.deactivate()
        assert result.success is True
        assert result.data["success"] is True
        assert result.data["result"] == 42

    def test_can_switch_backend_per_call(self):
        skill = CodeRunnerSkill(backend_name="inline")
        skill.activate()
        try:
            result = skill.execute(
                {
                    "code": "result = 'inline'",
                    "backend": "subprocess",
                    "vars": {},
                }
            )
        finally:
            skill.deactivate()
        assert result.success is True
        # SubprocessBackend swallows the result var (it serialises only
        # success/error), but the wrapper should still report success.
        assert result.data.get("success") is True

    def test_rejects_missing_code(self):
        skill = CodeRunnerSkill(backend_name="inline")
        skill.activate()
        try:
            result = skill.execute({"vars": {}})
        finally:
            skill.deactivate()
        assert result.success is False
        assert "'code' is required" in result.error

    def test_metadata_is_well_formed(self):
        skill = CodeRunnerSkill(backend_name="inline")
        meta = skill.metadata
        assert meta.name == "code_runner"
        assert meta.safety_level >= 4  # arbitrary code: high strictness


# =============================================================================
# Factory + auto-discover
# =============================================================================


class TestGetBackendFactory:
    @pytest.mark.parametrize("name,expected_cls", [
        ("inline", InlineBackend),
        ("subprocess", SubprocessBackend),
        ("docker", DockerBackend),
        ("http", HTTPBackend),
    ])
    def test_get_backend_returns_correct_type(self, name, expected_cls):
        # ``http`` requires an argument; the factory ignores that and
        # constructs with default args (which would be invalid for the URL).
        if name == "http":
            with pytest.raises(TypeError):
                get_backend(name)
            return
        backend = get_backend(name)
        assert isinstance(backend, expected_cls)

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backend("not-a-real-backend")


class TestAutoDiscoverIncludesCodeRunner:
    def test_code_runner_registered(self):
        from skills.registry import SkillRegistry
        reg = SkillRegistry()
        reg.auto_discover()
        # The package layout registers CodeRunnerSkill via the
        # ``skills.execution.executable_skill`` module. Auto-discovery walks
        # the ``skills`` package, so this must turn up.
        assert "code_runner" in reg, (
            "CodeRunnerSkill was not auto-discovered. Check that "
            "skills/execution/executable_skill.py is importable and that "
            "CodeRunnerSkill is a non-abstract BaseSkill subclass."
        )
        skill = reg.get_skill("code_runner")
        assert skill is not None
        assert skill.metadata.name == "code_runner"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
