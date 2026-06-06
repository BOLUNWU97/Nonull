"""
Skill execution backends / 技能执行后端

Different ways skills can execute their work:
- INLINE: same process, in-process function call (default, safest)
- SUBPROCESS: separate Python process with resource limits
- DOCKER: full container isolation (most secure, slowest)
- HTTP: delegate to a remote service (for distributed skills)

Also re-exports :class:`CodeRunnerSkill` so that ``SkillRegistry.auto_discover``
finds it as a member of the ``skills.execution`` module namespace.
"""
from typing import Any, Dict, Protocol


class ExecutionBackend(Protocol):
    """A way to run skill code in isolation."""

    def execute(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]: ...
    def cleanup(self) -> None: ...
    def is_available(self) -> bool: ...


def get_backend(name: str = "inline") -> "ExecutionBackend":
    """Return a backend instance by name.

    Args:
        name: One of ``"inline"``, ``"subprocess"``, ``"docker"``, ``"http"``.

    Returns:
        An :class:`ExecutionBackend` implementation.

    Raises:
        ValueError: If ``name`` does not match a known backend.
    """
    if name == "inline":
        from skills.execution.inline import InlineBackend
        return InlineBackend()
    elif name == "subprocess":
        from skills.execution.subprocess_backend import SubprocessBackend
        return SubprocessBackend()
    elif name == "docker":
        from skills.execution.docker_backend import DockerBackend
        return DockerBackend()
    elif name == "http":
        from skills.execution.http_backend import HTTPBackend
        return HTTPBackend()
    else:
        raise ValueError(f"Unknown backend: {name}")


# Re-export the BaseSkill wrapper so that auto-discovery (which iterates
# only top-level packages of the ``skills`` tree) finds the concrete
# ``BaseSkill`` subclass as a member of ``skills.execution``.
from skills.execution.executable_skill import CodeRunnerSkill  # noqa: E402


__all__ = ["ExecutionBackend", "get_backend", "CodeRunnerSkill"]
