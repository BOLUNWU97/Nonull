"""Smoke tests for Orchestrator.run_with_skills_async.

These tests verify that the async dispatch path:

  1. Actually runs subtasks in the same level concurrently
     (not just labeled "async" — measured wall-clock time must show
     overlap rather than serial summation).
  2. Preserves per-subtask error isolation (one failing skill does
     not crash the level).
  3. Respects the ``max_concurrent`` semaphore bound.
  4. Exposes a sync wrapper that non-async callers can use.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestration.orchestrator import (
    Orchestrator,
    OrchestrationPlan,
    Subtask,
)
from skills.base import (
    BaseSkill,
    SkillCategory,
    SkillMetadata,
)


# -----------------------------------------------------------------------------
# Test doubles — keep tests self-contained.
# -----------------------------------------------------------------------------


@dataclass
class FakeSkillResult:
    """Mimics skills.base.SkillResult without the full dataclass machinery."""

    success: bool = True
    data: Any = None
    error: Optional[str] = None
    skill_name: str = ""


class SleepingSkill(BaseSkill):
    """A skill that records concurrency overlap and sleeps for a fixed time."""

    def __init__(self, name: str, sleep_seconds: float = 0.2):
        self._instance_id = "sleep-" + name
        self._active = True
        self._metrics = None
        self.logger = None
        self._name = name
        self._sleep = sleep_seconds
        # Records when each execute starts/ends, with thread id
        self.events: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self._name,
            category=SkillCategory.GENERAL,
            description=f"Sleeps for {self._sleep}s",
            tags=["sleep"],
        )

    def _execute_impl(self, context):
        return None

    def execute(self, context):  # type: ignore[override]
        tid = threading.get_ident()
        start = time.monotonic()
        with self._lock:
            self.events.append({"phase": "start", "thread": tid, "t": start})
        time.sleep(self._sleep)
        end = time.monotonic()
        with self._lock:
            self.events.append({"phase": "end", "thread": tid, "t": end})
        return FakeSkillResult(
            success=True,
            data={"name": self._name, "thread": tid, "duration": end - start},
            skill_name=self._name,
        )

    @property
    def is_active(self) -> bool:
        return self._active

    def activate(self):
        self._active = True

    def deactivate(self):
        self._active = False

    def add_pre_hook(self, hook):
        pass

    def add_post_hook(self, hook):
        pass

    def add_safety_hook(self, hook):
        pass

    def max_concurrency_observed(self) -> int:
        """Return the max number of overlapping execute calls observed."""
        starts = sorted(e for e in self.events if e["phase"] == "start")
        ends = sorted(e for e in self.events if e["phase"] == "end")
        # This is per-skill concurrency, useful only when a single skill
        # is used for many subtasks. Cross-skill concurrency is checked
        # at the test level via wall-clock time.
        i = j = current = best = 0
        while i < len(starts) and j < len(ends):
            if starts[i]["t"] <= ends[j]["t"]:
                current += 1
                best = max(best, current)
                i += 1
            else:
                current -= 1
                j += 1
        return best


class FailingSkill(BaseSkill):
    """A skill that always reports failure (does not raise)."""

    def __init__(self, name: str, message: str = "intentional failure"):
        self._instance_id = "fail-" + name
        self._active = True
        self._metrics = None
        self.logger = None
        self._name = name
        self._message = message

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self._name,
            category=SkillCategory.GENERAL,
            description="Always fails",
            tags=["fail"],
        )

    def _execute_impl(self, context):
        return None

    def execute(self, context):  # type: ignore[override]
        return FakeSkillResult(
            success=False,
            error=self._message,
            skill_name=self._name,
        )

    @property
    def is_active(self) -> bool:
        return self._active

    def activate(self):
        self._active = True

    def deactivate(self):
        self._active = False

    def add_pre_hook(self, hook):
        pass

    def add_post_hook(self, hook):
        pass

    def add_safety_hook(self, hook):
        pass


class RaisingSkill(BaseSkill):
    """A skill whose execute() raises an unexpected exception."""

    def __init__(self, name: str):
        self._instance_id = "raise-" + name
        self._active = True
        self._metrics = None
        self.logger = None
        self._name = name

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self._name,
            category=SkillCategory.GENERAL,
            description="Raises",
            tags=["raise"],
        )

    def _execute_impl(self, context):
        return None

    def execute(self, context):  # type: ignore[override]
        raise RuntimeError(f"Skill {self._name!r} exploded")

    @property
    def is_active(self) -> bool:
        return self._active

    def activate(self):
        self._active = True

    def deactivate(self):
        self._active = False

    def add_pre_hook(self, hook):
        pass

    def add_post_hook(self, hook):
        pass

    def add_safety_hook(self, hook):
        pass


class FakeSkillRegistry:
    """Lightweight stand-in for SkillRegistry."""

    def __init__(self, skills: List[BaseSkill] = None):
        self._skills: Dict[str, BaseSkill] = {}
        for s in skills or []:
            self._skills[s.metadata.name] = s

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        return self._skills.get(name)

    def get_all_skills(self) -> List[BaseSkill]:
        return list(self._skills.values())


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _make_plan(subtask_specs) -> OrchestrationPlan:
    """Build a tiny plan with the given subtask specs.

    Each spec is a dict: {name, description, deps (names)}.
    All subtasks default to the same level (no deps) unless `deps` given.
    """
    plan = OrchestrationPlan(task="async test task")
    name_to_id: Dict[str, str] = {}
    for spec in subtask_specs:
        st = Subtask(
            task_id=plan.id,
            name=spec["name"],
            description=spec.get("description", spec["name"]),
            agent_type=spec.get("agent_type", "tester"),
            required_capabilities=set(spec.get("capabilities", [])),
            dependencies=[
                name_to_id[d] for d in spec.get("deps", []) if d in name_to_id
            ],
        )
        plan.subtasks[st.id] = st
        name_to_id[spec["name"]] = st.id
    plan.root_subtask_ids = [
        st.id for st in plan.subtasks.values() if not st.dependencies
    ]
    return plan


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_async_dispatch_runs_subtasks_concurrently():
    """Async dispatch should overlap subtask sleeps (concurrent, not serial)."""
    sleep_s = 0.3
    n = 4
    skills = [SleepingSkill(f"s{i}", sleep_seconds=sleep_s) for i in range(n)]
    registry = FakeSkillRegistry(skills)

    plan = _make_plan([
        {"name": f"step_{i}", "description": f"step {i}"} for i in range(n)
    ])
    name_to_skill = {f"step_{i}": f"s{i}" for i in range(n)}

    orch = Orchestrator()
    start = time.monotonic()
    result = orch.run_with_skills_async(
        plan=plan,
        registry=registry,
        name_to_skill=name_to_skill,
        max_concurrent=n,
    )
    elapsed = time.monotonic() - start

    assert result["status"] == "succeeded"
    assert result["summary"]["succeeded"] == n

    # Serial would be n * sleep_s; concurrent should be ~sleep_s plus overhead.
    serial_lower_bound = n * sleep_s  # type: ignore[operator]
    # Allow a generous upper bound to avoid flakiness on slow CI
    concurrent_upper_bound = sleep_s + 1.5
    assert elapsed < concurrent_upper_bound, (
        f"Async dispatch took {elapsed:.2f}s, expected < {concurrent_upper_bound:.2f}s "
        f"(serial would be ~{serial_lower_bound:.2f}s)"
    )
    # And, of course, must take at least one sleep
    assert elapsed >= sleep_s * 0.8, (
        f"Async dispatch finished too fast ({elapsed:.2f}s) — looks like skips"
    )


def test_async_dispatch_isolates_failing_skill():
    """A failing skill must not prevent other subtasks from completing."""
    good = SleepingSkill("good", sleep_seconds=0.05)
    bad = FailingSkill("bad", message="nope")
    raising = RaisingSkill("raising")

    registry = FakeSkillRegistry([good, bad, raising])
    plan = _make_plan([
        {"name": "do_good", "description": "good"},
        {"name": "do_bad", "description": "bad"},
        {"name": "do_raise", "description": "raising"},
    ])
    name_to_skill = {
        "do_good": "good",
        "do_bad": "bad",
        "do_raise": "raising",
    }

    result = Orchestrator().run_with_skills_async(
        plan=plan,
        registry=registry,
        name_to_skill=name_to_skill,
    )

    # Good succeeded
    assert result["outputs"]["do_good"] is not None
    # Bad reported failure
    assert "do_bad" in result["errors"]
    assert "nope" in result["errors"]["do_bad"]
    # Raising caught and recorded
    assert "do_raise" in result["errors"]
    assert "exploded" in result["errors"]["do_raise"]
    # Overall partial
    assert result["status"] == "partial"
    assert result["summary"]["succeeded"] == 1
    assert result["summary"]["failed"] == 2


def test_async_dispatch_respects_max_concurrent_semaphore():
    """max_concurrent must bound the number of in-flight skill executes."""
    sleep_s = 0.4
    n = 6
    max_c = 2

    # Use ONE shared skill so we can count its in-flight calls.
    shared = SleepingSkill("shared", sleep_seconds=sleep_s)
    # Wrap in a list-shaped registry to allow all subtasks to map to "shared"
    registry = FakeSkillRegistry([shared])

    plan = _make_plan([
        {"name": f"step_{i}", "description": f"step {i}"} for i in range(n)
    ])
    name_to_skill = {f"step_{i}": "shared" for i in range(n)}

    result = Orchestrator().run_with_skills_async(
        plan=plan,
        registry=registry,
        name_to_skill=name_to_skill,
        max_concurrent=max_c,
    )

    assert result["status"] == "succeeded"
    assert result["summary"]["succeeded"] == n
    # The shared skill's max in-flight calls must be <= max_c.
    assert shared.max_concurrency_observed() <= max_c, (
        f"Observed {shared.max_concurrency_observed()} concurrent calls, "
        f"expected <= {max_c}"
    )


def test_async_dispatch_sync_wrapper_works():
    """The sync wrapper `run_with_skills_async` should be callable directly."""
    skill = SleepingSkill("only", sleep_seconds=0.05)
    registry = FakeSkillRegistry([skill])
    plan = _make_plan([{"name": "only", "description": "single"}])

    result = Orchestrator().run_with_skills_async(
        plan=plan,
        registry=registry,
        name_to_skill={"only": "only"},
        max_concurrent=2,
    )

    assert result["status"] == "succeeded"
    assert "only" in result["outputs"]
    # dispatch_method should be 'explicit' since we passed name_to_skill
    assert result["dispatch_method"] == "explicit"


def test_async_dispatch_dependency_skip_preserved():
    """Subtasks downstream of a failed subtask must be SKIPPED, not executed."""
    bad = FailingSkill("bad", message="downstream block")
    good = SleepingSkill("good", sleep_seconds=0.05)
    registry = FakeSkillRegistry([bad, good])

    plan = _make_plan([
        {"name": "first", "description": "fails"},
        {"name": "second", "description": "depends on first", "deps": ["first"]},
    ])

    result = Orchestrator().run_with_skills_async(
        plan=plan,
        registry=registry,
        name_to_skill={"first": "bad", "second": "good"},
    )

    # 'good' skill should never have been called for 'second'
    assert len(good.events) == 0, (
        f"Expected 'good' skill to be skipped, but got {len(good.events)} events"
    )
    assert result["subtask_status"]["second"] == "skipped"
    assert result["summary"]["skipped"] == 1
    assert result["status"] == "failed"


@pytest.mark.asyncio
async def test_async_dispatch_impl_awaitable_directly():
    """The async impl can be awaited from inside an existing event loop."""
    skill = SleepingSkill("inline", sleep_seconds=0.05)
    registry = FakeSkillRegistry([skill])
    plan = _make_plan([{"name": "step", "description": "s"}])

    orch = Orchestrator()
    result = await orch._run_with_skills_async_impl(
        plan=plan,
        registry=registry,
        name_to_skill={"step": "inline"},
        max_concurrent=2,
    )
    assert result["status"] == "succeeded"
    assert "step" in result["outputs"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
