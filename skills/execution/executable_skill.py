"""
ExecutableSkill — a skill that runs arbitrary code with the chosen backend.

This enables "code as a skill" use cases: a user can describe a task and
the agent generates code that runs in a sandbox to produce the answer.
"""
from typing import Any, Dict

from skills.base import BaseSkill, SkillMetadata, SkillCategory
from skills.execution import get_backend


class CodeRunnerSkill(BaseSkill):
    """Run arbitrary Python code in a sandboxed execution backend.

    Use cases: ad-hoc data transformations, quick calculations, prototype scripts.
    ADVISORY: Do not run untrusted code in INLINE backend.
    """

    def __init__(self, backend_name: str = "inline"):
        super().__init__()
        self._backend_name = backend_name
        self._backend = get_backend(backend_name)

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="code_runner",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description=(
                "Run arbitrary Python code in a sandboxed execution backend. "
                "Default backend: inline. Configure with 'backend' parameter."
            ),
            tags=["code", "sandbox", "execution", "script"],
            author="Nonull Team",
            safety_level=4,  # high strictness because arbitrary code
            max_execution_ms=60000,
        )

    def _validate_input(self, context: Dict[str, Any]) -> None:
        if not context.get("code"):
            raise ValueError("'code' is required")

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        backend_name = context.get("backend", self._backend_name)
        if backend_name != self._backend_name:
            self._backend = get_backend(backend_name)
            self._backend_name = backend_name

        return self._backend.execute(context["code"], context.get("vars", {}))


__all__ = ["CodeRunnerSkill"]
