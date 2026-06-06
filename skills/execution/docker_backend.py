"""Docker execution: full container isolation. Most secure, slowest.

NOTE: Requires Docker to be installed on the host. Falls back gracefully
(returns ``success=False``) if Docker is unavailable; callers can fall back
to :class:`SubprocessBackend` or :class:`InlineBackend` in that case.
"""
import subprocess
from typing import Any, Dict


class DockerBackend:
    """Run skill code in a one-shot Docker container.

    Each invocation launches ``docker run --rm`` with explicit memory
    and CPU caps, so a misbehaving skill cannot exhaust host resources.
    The image is expected to contain a Python interpreter at the default
    location (``/usr/local/bin/python`` is the convention for
    ``python:3.12-slim``).

    Args:
        image:     Docker image tag to use (default: ``python:3.12-slim``).
        memory_mb: Hard memory cap passed to ``--memory``.
        cpus:      CPU quota passed to ``--cpus`` (1.0 == one full core).
    """

    def __init__(self, image: str = "python:3.12-slim", memory_mb: int = 512, cpus: float = 1.0):
        self.image = image
        self.memory_mb = memory_mb
        self.cpus = cpus

    def execute(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_available():
            return {"success": False, "error": "Docker not available. Install Docker or use another backend."}
        try:
            cmd = [
                "docker", "run", "--rm",
                f"--memory={self.memory_mb}m",
                f"--cpus={self.cpus}",
                "-i", self.image,
                "python", "-c", code,
            ]
            proc = subprocess.run(
                cmd, input=str(context), capture_output=True, text=True, timeout=60,
            )
            return {
                "success": proc.returncode == 0,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Container timeout"}

    def cleanup(self) -> None:
        pass

    def is_available(self) -> bool:
        try:
            subprocess.run(["docker", "version"], capture_output=True, timeout=5, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False


__all__ = ["DockerBackend"]
