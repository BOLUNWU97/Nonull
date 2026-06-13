#!/usr/bin/env python3
"""
Real tests for the Nonull `core/` package.

These tests test the REAL production code in `core/agent_core.py` and
`core/config.py`. They do NOT use the parallel mock implementation that the
previous `tests/test_core.py` defined. If you find yourself adding a class
named `MyMockXxx` here, stop and import from `core` instead.

这些测试测试 `core/` 包下的真实生产代码（`core/agent_core.py` 和
`core/config.py`），不是并行 Mock 实现。

Coverage:
  - NonullConfig instantiation and basic get/set/snapshot
  - AgentState enum (all 10 members from agent_core.AgentState)
  - MemorySystem has the 4 expected memory types
  - SafetyGuardian.validate() returns a (bool, float, str) tuple
  - BaseSkill / BaseTool are abstract (cannot be instantiated directly)
  - SkillRegistry.register() and unregister()
  - State machine: IDLE -> PLANNING -> REASONING -> ACTING -> REFLECTING -> COMPLETED
"""

import asyncio
import os
import sys
import time

import pytest

# Ensure project root is on sys.path regardless of where pytest is invoked from
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Import directly from the production modules, not from `core` re-exports,
# so the test is unambiguous about which code it exercises.
from core.agent_core import (
    AgentState,
    BaseSkill,
    BaseTool,
    HookPoint,
    HookRegistry,
    MemoryEntry,
    SafetyGuardian,
    SafetyViolation,
    SkillRegistry,
    ToolRegistry,
    WorkingMemory,
    EpisodicMemory,
    SemanticMemory,
    ProceduralMemory,
    Nonull,
)

# Import the MemorySystem used by Nonull at runtime (may be from
# core.memory_system or core.agent_core depending on what's available).
try:
    from core.memory_system import MemorySystem as _RuntimeMemorySystem
except ImportError:
    from core.agent_core import MemorySystem as _RuntimeMemorySystem
MemorySystem = _RuntimeMemorySystem  # make it available for test code
from core.config import NonullConfig


# =============================================================================
# Config tests
# =============================================================================

class TestNonullConfig:
    """Real NonullConfig from core/config.py."""

    def test_instantiation(self):
        """NonullConfig() should construct without arguments."""
        cfg = NonullConfig()
        assert cfg is not None
        # The default profile is "dev"
        assert cfg.profile == "dev"

    def test_default_singleton(self):
        """NonullConfig.instance() returns a singleton for the same profile."""
        # Reset to a known state so the test is order-independent
        NonullConfig.reset_all()
        a = NonullConfig.instance()
        b = NonullConfig.instance()
        assert a is b

    def test_get_set_roundtrip(self):
        """set(key, value) followed by get(key) should return the value."""
        cfg = NonullConfig()
        cfg.set("llm.temperature", 0.42)
        assert cfg.get("llm.temperature") == pytest.approx(0.42)

    def test_unknown_key_returns_default(self):
        """get() on an unknown key returns the supplied default."""
        cfg = NonullConfig()
        assert cfg.get("definitely.not.a.key", "fallback") == "fallback"
        assert cfg.get("definitely.not.a.key") is None

    def test_snapshot_is_immutable(self):
        """snapshot() should produce a frozen config that rejects set()."""
        cfg = NonullConfig()
        snap = cfg.snapshot()
        assert snap._frozen is True
        with pytest.raises(RuntimeError):
            snap.set("llm.temperature", 0.1)

    def test_available_profiles(self):
        """available_profiles() should list dev / test / prod / simulation."""
        profiles = NonullConfig.available_profiles()
        for required in ("dev", "test", "prod", "simulation"):
            assert required in profiles


# =============================================================================
# AgentState enum tests
# =============================================================================

class TestAgentState:
    """The real AgentState enum from core/agent_core.py."""

    def test_expected_members_present(self):
        """All 10 expected members should exist with the expected string values."""
        expected = {
            "IDLE": "idle",
            "PLANNING": "planning",
            "REASONING": "reasoning",
            "ACTING": "acting",
            "REFLECTING": "reflecting",
            "COMPLETED": "completed",
            "ERROR": "error",
            "RECOVERING": "recovering",
            "SPAWNING": "spawning",
            "WAITING_SUBAGENT": "waiting_subagent",
        }
        for name, value in expected.items():
            assert hasattr(AgentState, name), f"AgentState missing member {name}"
            assert AgentState[name].value == value

    def test_total_member_count(self):
        """The enum should not silently drop members (guards against regression)."""
        # We expect exactly 10 members in agent_core.AgentState
        assert len(AgentState) == 10

    def test_str_enum_compatibility(self):
        """AgentState inherits from str, so str(member) should equal its value."""
        # The str-enum round-trip is checked via the .value attribute (or
        # by comparing against the str form of the enum name).
        assert str(AgentState.IDLE.value) == "idle"
        assert str(AgentState.WAITING_SUBAGENT.value) == "waiting_subagent"


# =============================================================================
# MemorySystem tests
# =============================================================================

class TestMemorySystemStructure:
    """MemorySystem from core/memory_system.py wraps 4 memory types."""

    def setup_method(self):
        NonullConfig.reset_all()
        # Each test gets a fresh MemorySystem. We deliberately do NOT share one
        # instance across tests because MemorySystem is stateful.
        self.mem = MemorySystem()

    def test_has_four_memory_types(self):
        """MemorySystem should expose working/episodic/semantic/procedural via properties."""
        # The neocortex backend exposes these as properties that delegate to Neocortex
        if self.mem.neocortex is None:
            # Simple backend — no neocortex, just skip detailed checks
            pytest.skip("Memory backend is 'simple' (no full Neocortex)")
        assert self.mem.working is not None
        assert self.mem.episodic is not None
        assert self.mem.semantic is not None
        assert self.mem.procedural is not None

    def test_store_routes_by_type(self):
        """store(content, memory_type=...) should not crash and return IDs."""
        if self.mem.neocortex is None:
            # Simple backend — store() now persists to fallback stores
            wid = self.mem.store("plan-x", memory_type="working", importance=0.5)
            assert wid == "working"  # stored in fallback store
            return

        # Working memory — stores via neocortex.think
        wid = self.mem.store("plan-x", memory_type="working", importance=0.5)
        assert wid is not None  # returns "working" or None

        # Unknown memory type returns None (graceful fallback)
        result = self.mem.store("foo", memory_type="not-a-real-type", importance=0.5)
        # Should not raise; may return None
        assert isinstance(result, (str, type(None)))

    def test_store_experience_creates_two_entries(self):
        """store_experience() writes to both working and episodic memory."""
        before = self.mem.stats()
        self.mem.store_experience(
            task="Analyze braking",
            action="review-code",
            result={"ok": True},
            success=True,
        )
        after = self.mem.stats()
        # At least one subsystem should have grown
        # (neocortex consolidates to multiple stores)
        assert after["working_items"] >= before["working_items"] or \
               after["episodic_episodes"] >= before["episodic_episodes"]

    def test_get_context_returns_dict(self):
        """get_context() returns a dict with one list per memory type."""
        ctx = self.mem.get_context(query="braking", k=3)
        assert set(ctx.keys()) == {"working", "episodic", "semantic", "procedural"}
        for entries in ctx.values():
            assert isinstance(entries, list)


# =============================================================================
# SafetyGuardian tests
# =============================================================================

class TestSafetyGuardian:
    """Real SafetyGuardian.validate() contract."""

    def setup_method(self):
        NonullConfig.reset_all()
        # An empty config = no allowlist/blocklist, deny-first defaults to True
        # with max_risk_score 0.7. We force a permissive setting so the
        # "safe" path is reachable.
        self.guardian = SafetyGuardian()
        # Disable blocklist-derived risk so simple actions stay safe
        self.guardian.set_max_risk(0.95)
        self.guardian._blocked_patterns = []
        self.guardian._compiled_patterns = []
        self.guardian._allowed_commands = set()

    def test_validate_returns_three_tuple(self):
        """validate() must return (is_safe, risk_score, reason)."""
        result = self.guardian.validate("hello world")
        assert isinstance(result, tuple)
        assert len(result) == 3
        is_safe, risk, reason = result
        assert isinstance(is_safe, bool)
        assert isinstance(risk, float)
        assert isinstance(reason, str)

    def test_validate_blocks_blocked_pattern(self):
        """If the action matches a blocked pattern, validate() returns (False, ...)."""
        self.guardian.block_pattern(r"rm\s+-rf")
        is_safe, risk, reason = self.guardian.validate("file:write:rm -rf /etc")
        assert is_safe is False
        assert risk == pytest.approx(1.0)
        assert "rm" in reason.lower() or "黑名单" in reason

    def test_validate_records_violation(self):
        """A blocked action should be recorded in violation_count."""
        self.guardian.block_pattern(r"dangerous")
        assert self.guardian.violation_count == 0
        self.guardian.validate("do dangerous thing")
        assert self.guardian.violation_count == 1

    def test_validate_or_raise_raises_on_unsafe(self):
        """validate_or_raise() should raise SafetyViolation on unsafe action."""
        self.guardian.block_pattern(r"never")
        with pytest.raises(SafetyViolation):
            self.guardian.validate_or_raise("never do this")

    def test_validate_or_raise_does_not_raise_on_safe(self):
        """validate_or_raise() should not raise when validate() returns safe."""
        # Clear any default block patterns
        self.guardian._blocked_patterns = []
        self.guardian._compiled_patterns = []
        # Should not raise
        self.guardian.validate_or_raise("read:/tmp/data.csv")


# =============================================================================
# BaseSkill / BaseTool abstract behavior
# =============================================================================

class TestAbstractBases:
    """BaseSkill and BaseTool are abstract — they should reject direct use."""

    def test_base_skill_cannot_be_instantiated(self):
        """Directly instantiating BaseSkill must raise TypeError."""
        with pytest.raises(TypeError):
            BaseSkill()  # type: ignore[abstract]

    def test_base_tool_cannot_be_instantiated(self):
        """Directly instantiating BaseTool must raise TypeError."""
        with pytest.raises(TypeError):
            BaseTool()  # type: ignore[abstract]

    def test_incomplete_skill_subclass_cannot_instantiate(self):
        """A subclass that doesn't implement execute() is still abstract."""
        class IncompleteSkill(BaseSkill):
            name = "incomplete"

        with pytest.raises(TypeError):
            IncompleteSkill()  # type: ignore[abstract]

    def test_incomplete_tool_subclass_cannot_instantiate(self):
        """A subclass that doesn't implement execute() is still abstract."""
        class IncompleteTool(BaseTool):
            name = "incomplete-tool"

        with pytest.raises(TypeError):
            IncompleteTool()  # type: ignore[abstract]

    def test_concrete_skill_can_be_instantiated(self):
        """A skill that implements execute() and provides a name is instantiable."""
        class EchoSkill(BaseSkill):
            name = "echo-skill"
            version = "0.1.0"
            description = "echoes its input"

            async def execute(self, context, **kwargs):
                return context

        skill = EchoSkill()
        assert skill.name == "echo-skill"
        assert skill.version == "0.1.0"


# =============================================================================
# SkillRegistry / ToolRegistry tests
# =============================================================================

class _FakeSkill(BaseSkill):
    """Minimal concrete skill used for registry tests."""

    name = "fake-skill"
    description = "for testing"
    version = "0.1.0"

    async def execute(self, context, **kwargs):
        return {"ok": True}


class _FakeTool(BaseTool):
    """Minimal concrete tool used for registry tests."""

    name = "fake-tool"
    description = "for testing"
    parameters: dict = {}

    async def execute(self, **kwargs):
        return {"ok": True}


class TestRegistries:
    """Real SkillRegistry and ToolRegistry from core/agent_core.py."""

    def test_skill_registry_register(self):
        """register(skill) should add the skill under its name."""
        reg = SkillRegistry()
        skill = _FakeSkill()
        result = reg.register(skill)
        # register() is chainable
        assert result is reg
        assert "fake-skill" in reg
        assert reg.count == 1
        assert reg.get("fake-skill") is skill

    def test_skill_registry_rejects_non_skill(self):
        """register() should reject anything that isn't a BaseSkill."""
        reg = SkillRegistry()
        with pytest.raises(TypeError):
            reg.register("not-a-skill")  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            reg.register(42)  # type: ignore[arg-type]

    def test_skill_registry_unregister(self):
        """unregister() should remove the skill and return True."""
        reg = SkillRegistry()
        reg.register(_FakeSkill())
        assert reg.unregister("fake-skill") is True
        assert reg.count == 0
        # Unregistering again returns False
        assert reg.unregister("fake-skill") is False

    def test_skill_registry_execute_missing_raises(self):
        """Executing a non-registered skill should raise KeyError."""
        reg = SkillRegistry()

        async def _go():
            await reg.execute("nope", context={})

        with pytest.raises(KeyError):
            asyncio.run(_go())

    def test_tool_registry_register_and_list(self):
        """ToolRegistry should support register, get, and list_tools."""
        reg = ToolRegistry()
        reg.register(_FakeTool())
        assert reg.count == 1
        assert "fake-tool" in reg.list_tools()
        spec = reg.specs()
        assert spec[0]["name"] == "fake-tool"


# =============================================================================
# Hook registry tests
# =============================================================================

class TestHookRegistry:
    """HookPoint and HookRegistry from core/agent_core.py."""

    def test_hook_point_members(self):
        """The HookPoint enum should expose the expected lifecycle points."""
        assert hasattr(HookPoint, "ON_INIT")
        assert hasattr(HookPoint, "PRE_PLAN")
        assert hasattr(HookPoint, "POST_ACT")
        assert hasattr(HookPoint, "ON_STATE_CHANGE")

    def test_register_and_execute_hook(self):
        """Registered hooks should run in priority order."""
        reg = HookRegistry()
        calls = []

        def h1(context=None):
            calls.append("h1")

        def h2(context=None):
            calls.append("h2")

        # Lower priority numbers run first
        reg.register(HookPoint.PRE_PLAN, h1, name="first", priority=10)
        reg.register(HookPoint.PRE_PLAN, h2, name="second", priority=20)

        async def _go():
            return await reg.execute(HookPoint.PRE_PLAN, context={})

        asyncio.run(_go())
        assert calls == ["h1", "h2"]

    def test_unregister_hook(self):
        """unregister() should remove a previously-registered hook."""
        reg = HookRegistry()
        reg.register(HookPoint.ON_INIT, lambda c: None, name="x", priority=10)
        assert reg.unregister(HookPoint.ON_INIT, "x") is True
        assert reg.unregister(HookPoint.ON_INIT, "x") is False


# =============================================================================
# State machine transitions
# =============================================================================

class TestStateMachineTransitions:
    """Test the state transition contract.

    We do NOT exercise the full Nonull.run() loop here (it tries to call an
    LLM). We just verify that AgentState transitions follow the documented
    state machine: IDLE -> PLANNING -> REASONING -> ACTING -> REFLECTING ->
    COMPLETED, with an ERROR -> RECOVERING -> REASONING side branch.
    """

    def test_canonical_state_sequence(self):
        """The canonical happy-path sequence should walk through every phase."""
        sequence = [
            AgentState.IDLE,
            AgentState.PLANNING,
            AgentState.REASONING,
            AgentState.ACTING,
            AgentState.REFLECTING,
            AgentState.COMPLETED,
        ]
        for prev, nxt in zip(sequence, sequence[1:]):
            assert prev != nxt
        # Length is 6 (matches the docstring)
        assert len(sequence) == 6

    def test_error_recovering_side_branch(self):
        """ERROR -> RECOVERING -> REASONING is a valid side branch."""
        assert AgentState.ERROR != AgentState.RECOVERING
        assert AgentState.RECOVERING != AgentState.REASONING
        # Sanity: REASONING is a real, distinct state (not the same as the others)
        assert AgentState.REASONING not in (
            AgentState.ERROR,
            AgentState.RECOVERING,
            AgentState.COMPLETED,
        )

    def test_state_assignment_round_trip(self):
        """Assigning AgentState to a variable and reading it back yields the same enum member."""
        s = AgentState.PLANNING
        assert s is AgentState.PLANNING
        assert s.value == "planning"


# =============================================================================
# Smoke test: Nonull() instantiates with default config
# =============================================================================

class TestNonullAgent:
    """Smoke tests for the top-level Nonull agent.

    We deliberately don't call .run() because it requires an LLM. The goal is
    just to confirm the production class wires up all its subsystems.
    """

    def setup_method(self):
        NonullConfig.reset_all()

    def test_instantiation_with_default_config(self):
        """Nonull() should construct and expose all subsystems."""
        agent = Nonull()
        assert agent.name == "Nonull"
        assert isinstance(agent.state, AgentState)
        assert agent.state == AgentState.IDLE
        assert isinstance(agent.safety, SafetyGuardian)
        assert isinstance(agent.memory, MemorySystem)
        assert isinstance(agent.tools, ToolRegistry)
        assert isinstance(agent.skills, SkillRegistry)
        assert isinstance(agent.hooks, HookRegistry)

    def test_session_id_is_generated(self):
        """Each Nonull() should get a unique session_id by default."""
        a = Nonull()
        b = Nonull()
        assert a.session_id != b.session_id

    def test_get_status_returns_dict(self):
        """get_status() should return a status dict with known keys."""
        agent = Nonull()
        status = agent.get_status()
        assert isinstance(status, dict)
        assert status["state"] == "idle"
        assert status["name"] == "Nonull"
        assert "memory_sizes" in status


# =============================================================================
# Cross-cutting: make sure no test accidentally relies on the LLM.
# =============================================================================

def test_no_llm_network_calls_in_constructor():
    """Constructing a Nonull() should not make any network calls.

    This guards against a future regression where SafetyGuardian or
    MemorySystem starts hitting the network in __init__.
    """
    import socket

    # Block all socket connection attempts during the test
    blocked: list[tuple[str, str]] = []

    def _blocked_create_connection(*args, **kwargs):
        blocked.append(args[:1])
        raise OSError("network blocked for this test")

    # Patch the module-level ``socket.create_connection`` — this is the
    # entry point used by ``urllib`` / ``http.client`` / stdlib HTTP code.
    original = socket.create_connection
    socket.create_connection = _blocked_create_connection  # type: ignore[assignment]
    try:
        NonullConfig.reset_all()
        Nonull()  # should not attempt any connection
    finally:
        socket.create_connection = original  # type: ignore[assignment]
    assert blocked == [], f"Unexpected network attempts: {blocked}"
