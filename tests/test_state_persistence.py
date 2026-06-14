"""
Nonull save_state/load_state 记忆持久化测试 / Tests that save_state actually
persists Neocortex memory and load_state restores it.

钉住一个历史 bug: save_state 之前调 MemorySystem.to_dict() (只返回 stats),
导致完整记忆从未真正持久化。修复后用 Neocortex.to_dict() (working/episodic/
semantic/procedural 四层) + from_dict 完整重建。
"""
import asyncio
import json

import pytest

from core.agent_core import Nonull
from core.llm_client import LLMResponse


class _MockLLM:
    def __init__(self):
        self.model = "gpt-4o"

    def chat(self, messages, tools=None, **kwargs):
        user = messages[-1].content
        if "Decompose into" in user:
            payload = {"subtasks": [{"id": "s1", "description": "d",
                        "verify": "c", "tool": None}],
                       "strategy": "sequential", "estimated_steps": 1}
        elif "Choose the next action" in user:
            payload = {"next_action": "complete", "reasoning": "r", "confidence": 0.9}
        elif "Evaluate honestly" in user:
            payload = {"completed": True, "summary": "done", "score": 0.9}
        else:
            payload = {}
        return LLMResponse(content=json.dumps(payload), model=self.model,
                           usage={"prompt_tokens": 10, "completion_tokens": 5})


def _run_and_get_agent(monkeypatch):
    monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
    a = Nonull()
    a._llm_client = _MockLLM()
    asyncio.run(a.run("task to remember"))
    return a


class TestStatePersistsMemory:
    def test_save_produces_full_neocortex_data(self, monkeypatch, tmp_path):
        """save_state 的 memory 字段应是完整 Neocortex dict, 不是 stats."""
        a = _run_and_get_agent(monkeypatch)
        path = str(tmp_path / "state.json")
        asyncio.run(a.save_state(path))
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        memory = data["memory"]
        assert memory is not None, "memory 不应为 None (run 后应有数据)"
        # 完整 Neocortex dict 含四层
        for layer in ("working", "episodic", "semantic", "procedural"):
            assert layer in memory, f"missing layer: {layer}"

    def test_load_restores_episodic_memory(self, monkeypatch, tmp_path):
        """load_state 应恢复 episodic 记忆 (run 产生的经验)."""
        a = _run_and_get_agent(monkeypatch)
        before = len(a._memory.neocortex.episodic.episodes)
        assert before > 0, "run 应产生 episodic 记忆"
        path = str(tmp_path / "state.json")
        asyncio.run(a.save_state(path))

        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        b = Nonull()
        ok = asyncio.run(b.load_state(path))
        assert ok is True
        assert b._memory.neocortex is not None
        after = len(b._memory.neocortex.episodic.episodes)
        assert after == before, f"episodic 记忆未恢复: {before} -> {after}"

    def test_load_restores_session_metadata(self, monkeypatch, tmp_path):
        """load_state 恢复 session_id / iteration 等元数据."""
        a = _run_and_get_agent(monkeypatch)
        path = str(tmp_path / "state.json")
        asyncio.run(a.save_state(path))
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        b = Nonull()
        asyncio.run(b.load_state(path))
        assert b._session_id == a._session_id
        assert b._iteration == a._iteration

    def test_load_missing_file_returns_false(self, monkeypatch, tmp_path):
        """加载不存在的文件返回 False (不崩)."""
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        a = Nonull()
        ok = asyncio.run(a.load_state(str(tmp_path / "nonexistent.json")))
        assert ok is False
