"""Subprocess execution: separate Python process with resource limits. Medium isolation."""
import json
import subprocess
import sys
import tempfile
import os
from typing import Any, Dict


def _build_runner_script(timeout_seconds: int) -> str:
    """Build the per-run runner script.

    The inner process installs ``signal.setitimer`` to raise a timeout even
    from inside a tight CPU loop. ``signal.setitimer`` is POSIX-only, so
    on Windows we simply skip the inner timer and rely on the outer
    ``subprocess.run`` timeout.

    Stdin protocol: first line is a JSON-encoded context dict, the
    remainder is the user code to exec.
    """
    if os.name == "nt":
        return '''
import sys, json
try:
    first_line = sys.stdin.readline()
    context = json.loads(first_line)
    code = sys.stdin.read()
    exec(code, {"context": context, "__name__": "__main__"})
    print(json.dumps({"success": True, "result": None}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
'''
    return f'''
import sys, json, signal
signal.setitimer(signal.ITIMER_REAL, {timeout_seconds})
try:
    first_line = sys.stdin.readline()
    context = json.loads(first_line)
    code = sys.stdin.read()
    exec(code, {{"context": context, "__name__": "__main__"}})
    print(json.dumps({{"success": True, "result": None}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}))
'''


class SubprocessBackend:
    """Run skill code in a separate Python process with a timeout.

    On POSIX the runner uses ``signal.setitimer`` so the inner process is
    killed even if user code is stuck in a tight CPU loop. The outer
    ``subprocess.run`` call also enforces a wall-clock timeout (2s grace
    over the inner one) so a process that ignores SIGALRM can still be
    reaped. On Windows the inner timer is unavailable; the outer timeout
    is the only enforcement.

    Args:
        timeout:  Wall-clock budget in seconds for one run.
        memory_mb: Soft memory hint in MB (used by callers; not enforced
                   directly on POSIX by ``subprocess`` alone).
    """

    def __init__(self, timeout: float = 30.0, memory_mb: int = 512):
        self.timeout = timeout
        self.memory_mb = memory_mb

    def execute(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # stdin protocol: first line = JSON context, remainder = code
        stdin_payload = json.dumps(context) + "\n" + code
        try:
            proc = subprocess.run(
                [sys.executable, "-c", _build_runner_script(int(self.timeout))],
                input=stdin_payload,
                capture_output=True,
                text=True,
                timeout=self.timeout + 2,
            )
            try:
                # Last line of stdout is the JSON result
                result = json.loads(proc.stdout.strip().split("\n")[-1])
            except (json.JSONDecodeError, IndexError):
                result = {"raw_stdout": proc.stdout, "raw_stderr": proc.stderr}
            result["returncode"] = proc.returncode
            return result
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Timeout after {self.timeout}s"}

    def cleanup(self) -> None:
        pass

    def is_available(self) -> bool:
        return True


__all__ = ["SubprocessBackend"]
