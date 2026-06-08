"""
Reasoning Sandwich — use different models/configs for different phases.

Inspired by LangChain Deep Agents:
- PLAN phase: use powerful model (high reasoning)
- EXECUTE phase: use faster/cheaper model
- VERIFY phase: use powerful model again
"""
from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class PhaseConfig:
    model: str = ""
    temperature: float = 0.2
    max_tokens: int = 2048
    timeout: float = 15.0


@dataclass
class ReasoningSandwichConfig:
    plan: PhaseConfig = field(default_factory=lambda: PhaseConfig(temperature=0.3, max_tokens=4096))
    execute: PhaseConfig = field(default_factory=lambda: PhaseConfig(temperature=0.1, max_tokens=2048))
    verify: PhaseConfig = field(default_factory=lambda: PhaseConfig(temperature=0.2, max_tokens=2048))

    @classmethod
    def from_env(cls):
        plan = PhaseConfig(
            model=os.environ.get("NONULL_PLAN_MODEL", ""),
            temperature=float(os.environ.get("NONULL_PLAN_TEMP", "0.3")),
        )
        execute = PhaseConfig(
            model=os.environ.get("NONULL_EXECUTE_MODEL", ""),
            temperature=float(os.environ.get("NONULL_EXECUTE_TEMP", "0.1")),
        )
        verify = PhaseConfig(
            model=os.environ.get("NONULL_VERIFY_MODEL", ""),
            temperature=float(os.environ.get("NONULL_VERIFY_TEMP", "0.2")),
        )
        return cls(plan=plan, execute=execute, verify=verify)


class ReasoningSandwich:
    """Applies different model configs for each phase."""

    def __init__(self, config: Optional[ReasoningSandwichConfig] = None):
        self.config = config or ReasoningSandwichConfig.from_env()

    def for_phase(self, phase: str) -> dict:
        cfg = getattr(self.config, phase, None)
        if cfg is None:
            return {}
        result = {}
        if cfg.model:
            result["model"] = cfg.model
        result["temperature"] = cfg.temperature
        result["max_tokens"] = cfg.max_tokens
        return result
