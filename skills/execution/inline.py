"""Inline execution: same process, function call. Default, safest for trusted code."""
import io
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from typing import Any, Dict


class InlineBackend:
    """Run skill code in the current process. Fast but not isolated.

    This backend should be used for trusted, agent-generated code only.
    It does NOT protect against malicious input: anything executed here runs
    with the full privileges of the host process. For untrusted code, prefer
    :class:`SubprocessBackend` or :class:`DockerBackend`.
    """

    def execute(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Capture stdout/stderr
            stdout_buf = io.StringIO()
            stderr_buf = io.StringIO()
            local_ns = {"context": context, "__builtins__": __builtins__}
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(code, local_ns)
            return {
                "success": True,
                "stdout": stdout_buf.getvalue(),
                "stderr": stderr_buf.getvalue(),
                "result": local_ns.get("result"),
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc(),
            }

    def cleanup(self) -> None:
        pass

    def is_available(self) -> bool:
        return True


__all__ = ["InlineBackend"]
