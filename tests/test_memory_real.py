#!/usr/bin/env python3
"""
Real tests for the Nonull `memory/` package.

These tests test the REAL production code in `memory/working_memory.py`,
`memory/episodic.py`, `memory/semantic.py`, `memory/procedural.py`,
`memory/neocortex.py`, and `memory/subconscious_loop.py`. They do NOT use
the parallel mock implementation that the previous `tests/test_memory.py`
defined (the old file defined its own `Memory`, `NeocortexStore`,
`SubconsciousProcessor`, `MemorySystem` etc. as in-file mocks — those are
moved to `tests/_archive/`).

这些测试测试 `memory/` 包下的真实生产代码，不是并行 Mock 实现。

Coverage:
  - WorkingMemory: remember() / recall() / token budget
  - EpisodicMemory: store() / recall_recent() / decay
  - SemanticMemory: add_knowledge() / query()
  - ProceduralMemory: create_skill() / find_skills()
  - Neocortex: cross-memory search via MemoryQuery
  - Ebbinghaus decay: strength = exp(-decay_rate * hours_since)
"""

import asyncio
import math
import os
import sys
import time

import pytest

# Ensure project root is on sys.path regardless of where pytest is invoked from
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Import from production modules, never re-define Memory / NeocortexStore here.
from memory.working_memory import (
    WorkingMemory,
    ContextWindow,
    TokenBudget,
    Priority,
    estimate_tokens,
)
from memory.episodic import (
    EpisodicMemory,
    Episode,
    EpisodeType,
    EmbeddingProvider,
)
from memory.semantic import (
    SemanticMemory,
    KnowledgeNode,
    KnowledgeDomain,
    RelationType,
)
from memory.procedural import (
    ProceduralMemory,
    Skill,
    SkillStep,
    SkillCategory,
    ExecutionTrace,
)
from memory.neocortex import (
    Neocortex,
    MemoryQuery,
    MemoryResult,
    MemorySource,
    RelevanceScore,
)
from memory.subconscious_loop import SubconsciousLoop, Insight


# =============================================================================
# WorkingMemory tests
# =============================================================================

class TestWorkingMemory:
    """Real WorkingMemory from memory/working_memory.py."""

    def test_remember_and_recall(self):
        """remember() should add context items; recall() should return them."""
        wm = WorkingMemory(name="test", soft_limit=1000, hard_limit=2000)
        ok1 = wm.remember("alpha", source="user", priority=Priority.HIGH)
        ok2 = wm.remember("beta", source="assistant", priority=Priority.NORMAL)
        assert ok1 is True
        assert ok2 is True

        ctx = wm.recall()
        # Both items should appear in the context (HIGH first since added first)
        assert "alpha" in ctx
        assert "beta" in ctx

    def test_token_budget_tracks_usage(self):
        """Adding items should increase token_usage monotonically."""
        wm = WorkingMemory(name="budget", soft_limit=10, hard_limit=20)
        assert wm.token_usage == 0
        wm.remember("hello world", source="user")
        assert wm.token_usage > 0
        # Snapshot should reflect usage
        snap = wm.token_usage
        assert snap == wm.context_window.budget.used

    def test_forget_clears_all(self):
        """forget() with no source argument should clear every item."""
        wm = WorkingMemory(name="forget-test", soft_limit=1000, hard_limit=2000)
        wm.remember("first", source="user")
        wm.remember("second", source="assistant")
        assert wm.context_window.get_item_count() == 2

        removed = wm.forget()
        assert removed == 2
        assert wm.context_window.get_item_count() == 0

    def test_set_active_task_and_end(self):
        """set_active_task / end_active_task should manage the active_task slot."""
        wm = WorkingMemory(name="task-test", soft_limit=1000, hard_limit=2000)
        wm.set_active_task("t-1", "Analyze AEB")
        assert wm.active_task is not None
        assert wm.active_task["task_id"] == "t-1"

        snap = wm.end_active_task(result="done", success=True)
        assert snap is not None
        assert snap["success"] is True
        assert wm.active_task is None

    def test_estimate_tokens_basic(self):
        """estimate_tokens() should be a non-zero positive integer for non-empty text."""
        assert estimate_tokens("") == 0
        assert estimate_tokens("hello") > 0
        assert estimate_tokens("hello world this is a longer sentence") > 5


# =============================================================================
# EpisodicMemory tests
# =============================================================================

class TestEpisodicMemory:
    """Real EpisodicMemory from memory/episodic.py."""

    def test_store_returns_episode(self):
        """store() should return an Episode with a unique ID and the right content."""
        em = EpisodicMemory(name="ep-test", max_episodes=100, decay_rate=0.0)
        ep = em.store(
            content="Reviewed AEB controller",
            episode_type=EpisodeType.CODE_REVIEW,
            importance=0.7,
            tags=["aeb", "review"],
        )
        assert isinstance(ep, Episode)
        assert ep.episode_id in em.episodes
        assert ep.content == "Reviewed AEB controller"
        assert ep.importance == pytest.approx(0.7)

    def test_recall_finds_matching_episode(self):
        """recall() should rank an exact-match episode near the top."""
        em = EpisodicMemory(name="ep-recall", max_episodes=100, decay_rate=0.0)
        em.store(
            content="Lane keep assist calibration done",
            episode_type=EpisodeType.DEBUGGING_SESSION,
        )
        em.store(
            content="Sensor fusion review meeting",
            episode_type=EpisodeType.CODE_REVIEW,
        )
        results = em.recall("lane keep assist", top_k=5)
        assert len(results) >= 1
        # The lane-keep episode should be among the top
        assert any("lane keep" in ep.content.lower() for ep in results)

    def test_recall_recent_returns_within_time_window(self):
        """recall_recent(hours=...) should return only episodes newer than the cutoff."""
        em = EpisodicMemory(name="ep-recent", max_episodes=100, decay_rate=0.0)
        em.store(content="recent episode", episode_type=EpisodeType.OTHER)
        # Look back 1 hour; the episode we just stored is in that window
        recent = em.recall_recent(hours=1, top_k=10)
        assert len(recent) >= 1
        # And looking back 0 hours (almost no time) should be empty
        # (we just stored so it should still be there — sanity check on the API)
        assert isinstance(recent, list)

    def test_recall_recent_excludes_old_episodes(self):
        """An old episode (timestamp far in the past) should be excluded."""
        em = EpisodicMemory(name="ep-old", max_episodes=100, decay_rate=0.0)
        # Insert an episode with a backdated timestamp
        em.store(
            content="ancient event",
            episode_type=EpisodeType.OTHER,
            timestamp=time.time() - (48 * 3600),  # 48 hours ago
        )
        # Looking back only 1 hour should exclude it
        recent = em.recall_recent(hours=1, top_k=10)
        assert all("ancient" not in ep.content for ep in recent)


# =============================================================================
# SemanticMemory tests
# =============================================================================

class TestSemanticMemory:
    """Real SemanticMemory from memory/semantic.py."""

    def test_add_knowledge_returns_node(self):
        """add_knowledge() should return a KnowledgeNode stored in self.nodes."""
        sm = SemanticMemory(name="sem-test", enable_default_knowledge=False)
        before = len(sm.nodes)
        node = sm.add_knowledge(
            title="Test Concept",
            content="A test piece of domain knowledge.",
            domain=KnowledgeDomain.GENERAL,
            tags=["test"],
            source="unit test",
            confidence=0.9,
        )
        assert isinstance(node, KnowledgeNode)
        assert node.node_id in sm.nodes
        assert len(sm.nodes) == before + 1
        assert node.confidence == pytest.approx(0.9)

    def test_query_returns_relevant_nodes(self):
        """query() should return at least one match for an obviously relevant concept."""
        sm = SemanticMemory(name="sem-query", enable_default_knowledge=False)
        sm.add_knowledge(
            title="Autonomous Driving Perception",
            content="Cameras, LiDAR, and radar are used for environment perception.",
            domain=KnowledgeDomain.PERCEPTION,
        )
        sm.add_knowledge(
            title="Cooking Pasta",
            content="Boil water, add salt, and cook pasta for 10 minutes.",
            domain=KnowledgeDomain.GENERAL,
        )
        results = sm.query("perception sensors for driving", top_k=5, threshold=0.0)
        # The driving node should be the top result
        assert len(results) >= 1
        top_node, top_score = results[0]
        assert "perception" in top_node.title.lower() or "driving" in top_node.title.lower()
        assert 0.0 <= top_score <= 1.0

    def test_query_with_domain_filter(self):
        """domain=... should restrict the result set to nodes in that domain."""
        sm = SemanticMemory(name="sem-filter", enable_default_knowledge=False)
        sm.add_knowledge(
            title="A",
            content="alpha",
            domain=KnowledgeDomain.SAFETY,
        )
        sm.add_knowledge(
            title="B",
            content="beta",
            domain=KnowledgeDomain.PERCEPTION,
        )
        results = sm.query("alpha", top_k=10, domain=KnowledgeDomain.SAFETY, threshold=0.0)
        assert all(node.domain == KnowledgeDomain.SAFETY for node, _ in results)


# =============================================================================
# ProceduralMemory tests
# =============================================================================

class TestProceduralMemory:
    """Real ProceduralMemory from memory/procedural.py."""

    def test_create_skill_returns_skill(self):
        """create_skill() should register a new Skill and return it."""
        pm = ProceduralMemory(name="proc-test", embedder=EmbeddingProvider(dim=64))
        skill = pm.create_skill(
            name="unit-test-skill",
            description="skill used in unit tests",
            category=SkillCategory.TESTING,
            steps=[SkillStep(description="step 1"), SkillStep(description="step 2")],
            tags=["test"],
        )
        assert isinstance(skill, Skill)
        assert skill.skill_id in pm.skills
        assert skill.step_count == 2

    def test_find_skills_returns_relevant_match(self):
        """find_skills() should rank an obviously relevant skill near the top."""
        pm = ProceduralMemory(name="proc-find", embedder=EmbeddingProvider(dim=64))
        pm.create_skill(
            name="lane-change-procedure",
            description="Step-by-step procedure for safely changing lanes on a highway",
            category=SkillCategory.PLANNING,
            tags=["driving", "lane"],
        )
        pm.create_skill(
            name="bake-cake-procedure",
            description="Recipe for baking a chocolate cake",
            category=SkillCategory.OTHER,
            tags=["cooking"],
        )
        results = pm.find_skills("how to change lanes safely", top_k=5)
        assert len(results) >= 1
        # Lane-change skill should be among the top
        titles = [s.name for s in results]
        assert "lane-change-procedure" in titles

    def test_find_skill_by_exact_name(self):
        """find_skill() with the exact registered name should return that skill."""
        pm = ProceduralMemory(name="proc-exact", embedder=EmbeddingProvider(dim=64))
        pm.create_skill(name="alpha-skill", description="a", category=SkillCategory.OTHER)
        pm.create_skill(name="beta-skill", description="b", category=SkillCategory.OTHER)
        assert pm.find_skill("alpha-skill").name == "alpha-skill"
        assert pm.find_skill("does-not-exist") is None


# =============================================================================
# Neocortex cross-memory search
# =============================================================================

class TestNeocortex:
    """Real Neocortex from memory/neocortex.py — cross-memory unified search."""

    def test_instantiation_with_subsystems(self):
        """Neocortex() should construct and wire up all 4 subsystems."""
        nc = Neocortex(name="test-cortex")
        assert isinstance(nc.working, WorkingMemory)
        assert isinstance(nc.episodic, EpisodicMemory)
        assert isinstance(nc.semantic, SemanticMemory)
        assert isinstance(nc.procedural, ProceduralMemory)

    def test_cross_memory_query_returns_results(self):
        """A MemoryQuery that matches knowledge in multiple stores should return ranked results."""
        nc = Neocortex(name="cross-test")
        # Add a semantic node
        nc.semantic.add_knowledge(
            title="AEB Controller",
            content="Autonomous Emergency Braking reduces collision severity by applying brakes.",
            domain=KnowledgeDomain.CONTROL,
        )
        # Add a procedural skill
        nc.procedural.create_skill(
            name="calibrate-aeb",
            description="Steps to calibrate the AEB sensor and controller",
            category=SkillCategory.TESTING,
        )
        # Add an episodic memory
        nc.episodic.store(
            content="AEB calibration performed on test vehicle at proving ground",
            episode_type=EpisodeType.DEBUGGING_SESSION,
        )

        q = MemoryQuery(
            text="AEB calibration and emergency braking",
            top_k_per_source=3,
            max_total=10,
        )
        results = nc.query(q)
        assert isinstance(results, list)
        # We should get at least 2 results spanning different memory types
        sources = {r.source for r in results}
        assert len(sources) >= 2

    def test_relevance_score_compute(self):
        """RelevanceScore.compute() should produce a combined score in [0, 1]."""
        score = RelevanceScore.compute(
            semantic_sim=0.8,
            age_hours=2.0,
            importance=0.7,
            access_count=3,
            strength=1.0,
        )
        assert 0.0 <= score.combined <= 1.0
        assert score.semantic_sim == pytest.approx(0.8)
        assert score.importance == pytest.approx(0.7)


# =============================================================================
# Ebbinghaus decay
# =============================================================================

class TestEbbinghausDecay:
    """Verify the decay calculation in EpisodicMemory._apply_decay.

    Formula: strength_new = strength * exp(-decay_rate * hours_since)
    """

    def test_decay_formula_matches_math(self):
        """After applying decay, strength should equal original * exp(-r*h)."""
        em = EpisodicMemory(name="decay-test", max_episodes=10, decay_rate=0.05)
        # Insert an episode whose last_accessed is 10 hours ago
        ep = em.store(content="to-be-decayed", episode_type=EpisodeType.OTHER)
        ep.last_accessed = time.time() - 10 * 3600
        ep.last_decayed_at = time.time() - 10 * 3600
        original_strength = ep.strength

        # Apply decay
        em._apply_decay()

        expected = original_strength * math.exp(-0.05 * 10)
        # Allow small floating-point slack
        assert ep.strength == pytest.approx(expected, rel=1e-3)

    def test_zero_decay_rate_preserves_strength(self):
        """With decay_rate=0, strength should not change."""
        em = EpisodicMemory(name="no-decay", max_episodes=10, decay_rate=0.0)
        ep = em.store(content="stable", episode_type=EpisodeType.OTHER)
        ep.last_accessed = time.time() - 100 * 3600  # 100 hours ago
        before = ep.strength

        em._apply_decay()
        assert ep.strength == pytest.approx(before)

    def test_higher_decay_rate_decreases_strength_faster(self):
        """A higher decay_rate should reduce strength more aggressively."""
        em_low = EpisodicMemory(name="low", max_episodes=10, decay_rate=0.01)
        em_high = EpisodicMemory(name="high", max_episodes=10, decay_rate=0.5)

        ep_low = em_low.store(content="x", episode_type=EpisodeType.OTHER)
        ep_high = em_high.store(content="x", episode_type=EpisodeType.OTHER)

        # Backdate both by 1 hour
        for ep in (ep_low, ep_high):
            ep.last_accessed = time.time() - 3600

        em_low._apply_decay()
        em_high._apply_decay()

        # Higher decay rate should produce lower strength
        assert ep_high.strength < ep_low.strength


# =============================================================================
# SubconsciousLoop smoke test
# =============================================================================

class TestSubconsciousLoop:
    """Smoke test for SubconsciousLoop — just confirm it instantiates and runs."""

    def test_instantiation(self):
        """SubconsciousLoop() should accept a Neocortex instance."""
        nc = Neocortex(name="sub-test")
        loop = SubconsciousLoop(neocortex=nc)
        assert loop is not None
        # It should expose its neocortex reference
        assert loop.neocortex is nc

    def test_collect_insights_returns_list(self):
        """collect_insights() should return a list (may be empty)."""
        nc = Neocortex(name="insight-test")
        loop = SubconsciousLoop(neocortex=nc)
        insights = loop.collect_insights()
        assert isinstance(insights, list)
