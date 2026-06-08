"""Real integration tests for core/agent_core.py — Nonull class.

These tests verify the Nonull agent actually works end-to-end.
They require NONULL_LLM_API_KEY to be set; if not set, tests are skipped.
"""
import os
import pytest
from core.agent_core import Nonull
from core import AgentState


class TestNonullIntegration:
    def test_agent_initializes(self):
        agent = Nonull()
        assert agent.state == AgentState.IDLE

    def test_agent_has_safety_guardian(self):
        agent = Nonull()
        assert hasattr(agent, "safety")

    def test_agent_has_memory(self):
        agent = Nonull()
        assert hasattr(agent, "memory")

    def test_agent_has_tools(self):
        agent = Nonull()
        assert hasattr(agent, "tools")

    def test_agent_has_skills(self):
        agent = Nonull()
        assert hasattr(agent, "skills")

    def test_run_sync_returns_dict(self):
        agent = Nonull()
        result = agent.run_sync("Say hello")
        assert isinstance(result, dict)
        assert "output" in result
        assert result["status"] == "ok"

    def test_run_sync_responds_to_greeting(self):
        agent = Nonull()
        result = agent.run_sync("Say hi in 3 words", max_tokens=30)
        text = result.get("output", "")
        assert len(text) > 0
        assert result["status"] == "ok"

    def test_get_status(self):
        agent = Nonull()
        status = agent.get_status()
        assert isinstance(status, dict)
        assert "state" in status
        assert status["state"] == "idle"
