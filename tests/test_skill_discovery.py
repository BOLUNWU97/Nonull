"""Tests for experimental skill discovery."""
from experimental.skill_discovery import SkillDiscoveryEngine


def test_record_and_find_patterns():
    eng = SkillDiscoveryEngine(min_frequency=2)
    for _ in range(3):
        eng.record_task("Review this Python function for bugs")
    for _ in range(2):
        eng.record_task("Search the web for Python tutorials")
    proposals = eng.find_repeating_patterns()
    assert len(proposals) >= 1
    assert any("code_review" in p.name or "search" in p.name for p in proposals)
