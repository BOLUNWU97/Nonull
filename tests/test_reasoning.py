"""Tests for core/reasoning.py — Reasoning Sandwich."""
import os
import pytest

from core.reasoning import ReasoningSandwich, ReasoningSandwichConfig, PhaseConfig


class TestPhaseConfig:
    def test_defaults(self):
        cfg = PhaseConfig()
        assert cfg.temperature == 0.2
        assert cfg.max_tokens == 2048

    def test_custom_values(self):
        cfg = PhaseConfig(model="gpt-4", temperature=0.5, max_tokens=100)
        assert cfg.model == "gpt-4"
        assert cfg.temperature == 0.5
        assert cfg.max_tokens == 100


class TestReasoningSandwichConfig:
    def test_default_factory(self):
        cfg = ReasoningSandwichConfig()
        assert cfg.plan.temperature == 0.3
        assert cfg.plan.max_tokens == 4096
        assert cfg.execute.temperature == 0.1
        assert cfg.verify.temperature == 0.2

    def test_custom_config(self):
        cfg = ReasoningSandwichConfig(
            plan=PhaseConfig(temperature=0.5),
            execute=PhaseConfig(model="fast-model", temperature=0.0),
        )
        assert cfg.plan.temperature == 0.5
        assert cfg.execute.model == "fast-model"
        assert cfg.plan.temperature == 0.5  # custom overrides default


class TestReasoningSandwich:
    def test_default_instantiation(self):
        rs = ReasoningSandwich()
        plan = rs.for_phase("plan")
        assert plan["temperature"] == 0.3
        assert plan["temperature"] == 0.3

    def test_execute_phase(self):
        rs = ReasoningSandwich()
        execute = rs.for_phase("execute")
        assert execute["temperature"] == 0.1
        assert execute["max_tokens"] == 2048

    def test_unknown_phase_returns_empty(self):
        rs = ReasoningSandwich()
        assert rs.for_phase("nonexistent") == {}

    def test_from_env(self):
        os.environ["NONULL_PLAN_MODEL"] = "gpt-5"
        os.environ["NONULL_EXECUTE_TEMP"] = "0.05"
        try:
            cfg = ReasoningSandwichConfig.from_env()
            assert cfg.plan.model == "gpt-5"
            assert cfg.execute.temperature == 0.05
        finally:
            del os.environ["NONULL_PLAN_MODEL"]
            del os.environ["NONULL_EXECUTE_TEMP"]
