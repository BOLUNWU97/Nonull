"""Basic tests for memory/ modules — focused tests for core functionality."""
import pytest
from memory.working_memory import WorkingMemory
from memory.semantic import SemanticMemory, KnowledgeNode
from memory.procedural import ProceduralMemory, Skill


class TestWorkingMemoryBasics:
    def test_store_and_retrieve(self):
        wm = WorkingMemory(capacity=10)
        wm.store({"content": "test", "metadata": {"type": "test"}}, importance=0.5)
        results = wm.retrieve("test", k=5)
        assert len(results) > 0

    def test_store_and_recall(self):
        wm = WorkingMemory(capacity=10)
        entry_id = wm.store({"content": "hello"}, importance=0.5)
        results = wm.recall("hello", k=5)
        assert len(results) > 0

    def test_forget_clears(self):
        wm = WorkingMemory(capacity=10)
        wm.store({"content": "data"}, importance=0.5)
        wm.forget()
        results = wm.retrieve("data", k=5)
        assert len(results) == 0

    def test_token_usage(self):
        wm = WorkingMemory(capacity=10)
        tokens = wm.token_usage()
        assert isinstance(tokens, (int, float))


class TestSemanticMemoryBasics:
    def test_add_knowledge(self):
        sm = SemanticMemory()
        sm.add_knowledge("is_a", "Python", {"type": "language"}, "test")
        assert len(sm._knowledge) > 0

    def test_query_returns_results(self):
        sm = SemanticMemory()
        sm.add_knowledge("is_a", "Python", {"type": "language"}, "test")
        results = sm.query("Python")
        assert len(results) > 0


class TestProceduralMemoryBasics:
    def test_create_skill(self):
        pm = ProceduralMemory()
        pm.create_skill("test_skill", {"steps": []}, "test")
        found = pm.find_skills("test", k=5)
        assert len(found) > 0

    def test_find_skills_returns_matches(self):
        pm = ProceduralMemory()
        pm.create_skill("review_code", {"steps": [{"action": "analyze"}]}, "test")
        results = pm.find_skills("review", k=5)
        assert len(results) > 0
