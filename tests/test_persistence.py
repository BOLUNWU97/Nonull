"""
持久化测试 / Persistence tests — atomic write + round-trip for
SessionMemory, KnowledgeGraph, PromptRegistry.

每个模块验证: save → load → 数据一致 (round-trip)。
"""
import json
import os
import pytest

from core.persistence import (
    atomic_write_json, read_json, wrap_payload, unwrap_payload, FORMAT_VERSION,
)


# ---------------------------------------------------------------------------
# 基础设施 / Infrastructure
# ---------------------------------------------------------------------------

class TestAtomicWrite:
    def test_write_and_read_roundtrip(self, tmp_path):
        path = str(tmp_path / "data.json")
        atomic_write_json(path, {"key": "值", "n": 42})
        data = read_json(path)
        assert data == {"key": "值", "n": 42}

    def test_creates_parent_directory(self, tmp_path):
        path = str(tmp_path / "nested" / "deep" / "data.json")
        atomic_write_json(path, {"x": 1})
        assert read_json(path) == {"x": 1}

    def test_overwrite_preserves_atomicity(self, tmp_path):
        path = str(tmp_path / "data.json")
        atomic_write_json(path, {"v": 1})
        atomic_write_json(path, {"v": 2})
        assert read_json(path) == {"v": 2}
        # 无残留临时文件 / no orphaned temp files
        leftovers = [f for f in os.listdir(tmp_path) if f.startswith(".tmp_")]
        assert leftovers == []

    def test_unicode_not_escaped(self, tmp_path):
        path = str(tmp_path / "cn.json")
        atomic_write_json(path, {"msg": "自动驾驶"})
        raw = open(path, encoding="utf-8").read()
        assert "自动驾驶" in raw  # ensure_ascii=False

    def test_read_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_json(str(tmp_path / "nope.json"))

    def test_read_non_object_raises(self, tmp_path):
        path = str(tmp_path / "arr.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump([1, 2, 3], f)
        with pytest.raises(ValueError):
            read_json(path)


class TestEnvelope:
    def test_wrap_unwrap_roundtrip(self):
        env = wrap_payload("test_kind", {"a": 1})
        assert env["format_version"] == FORMAT_VERSION
        assert unwrap_payload(env, "test_kind") == {"a": 1}

    def test_kind_mismatch_raises(self):
        env = wrap_payload("kind_a", {})
        with pytest.raises(ValueError):
            unwrap_payload(env, "kind_b")

    def test_legacy_format_passthrough(self):
        # 无信封的旧数据原样返回 / legacy data without envelope passes through
        legacy = {"sessions": []}
        assert unwrap_payload(legacy, "session_memory") == legacy


# ---------------------------------------------------------------------------
# SessionMemory
# ---------------------------------------------------------------------------

class TestSessionMemoryPersistence:
    def _build(self):
        from core.session_memory import SessionMemory, MessageRole
        mem = SessionMemory(max_tokens=2000)
        sid = mem.create_session("persist-test")
        mem.add_message(sid, MessageRole.USER, "限速是 60 km/h")
        mem.add_message(sid, MessageRole.ASSISTANT, "收到，已记录限速。")
        mem.extract_facts(sid)
        return mem, sid

    def test_to_dict_from_dict_roundtrip(self):
        from core.session_memory import SessionMemory
        mem, sid = self._build()
        data = mem.to_dict()
        restored = SessionMemory.from_dict(data)

        assert restored.list_sessions() == [sid]
        orig_msgs = mem.get_messages(sid)
        rest_msgs = restored.get_messages(sid)
        assert len(rest_msgs) == len(orig_msgs)
        assert rest_msgs[0].content == orig_msgs[0].content
        assert rest_msgs[0].role == orig_msgs[0].role
        assert restored.get_facts(sid) == mem.get_facts(sid)

    def test_save_load_roundtrip(self, tmp_path):
        from core.session_memory import SessionMemory
        mem, sid = self._build()
        path = str(tmp_path / "sessions.json")
        mem.save(path)
        restored = SessionMemory.load(path)

        assert restored.list_sessions() == [sid]
        assert restored.get_messages(sid)[0].content == "限速是 60 km/h"

    def test_max_tokens_preserved(self, tmp_path):
        from core.session_memory import SessionMemory
        mem, _ = self._build()
        path = str(tmp_path / "s.json")
        mem.save(path)
        restored = SessionMemory.load(path)
        assert restored._max_tokens == 2000

    def test_multiple_sessions(self, tmp_path):
        from core.session_memory import SessionMemory, MessageRole
        mem = SessionMemory()
        for i in range(3):
            sid = mem.create_session(f"s{i}")
            mem.add_message(sid, MessageRole.USER, f"message {i}")
        path = str(tmp_path / "multi.json")
        mem.save(path)
        restored = SessionMemory.load(path)
        assert sorted(restored.list_sessions()) == ["s0", "s1", "s2"]


# ---------------------------------------------------------------------------
# KnowledgeGraph
# ---------------------------------------------------------------------------

class TestKnowledgeGraphPersistence:
    def _build(self):
        from core.graph_memory import KnowledgeGraph
        g = KnowledgeGraph(max_entities=500)
        g.add_entity("LiDAR", entity_type="sensor")
        g.add_entity("测距", entity_type="capability")
        g.add_relation("LiDAR", "provides", "测距")
        return g

    def test_to_dict_from_dict_roundtrip(self):
        from core.graph_memory import KnowledgeGraph
        g = self._build()
        restored = KnowledgeGraph.from_dict(g.to_dict())

        assert len(restored) == 2
        found = restored.get_entity("LiDAR")
        assert found is not None
        assert found.entity_type == "sensor"
        # 关系和邻接索引重建正确 / relations and adjacency rebuilt
        query = restored.neighbors("LiDAR")
        names = [e.name for e in query.entities]
        assert "测距" in names

    def test_max_entities_preserved(self):
        from core.graph_memory import KnowledgeGraph
        g = self._build()
        restored = KnowledgeGraph.from_dict(g.to_dict())
        assert restored._max_entities == 500

    def test_save_load_roundtrip(self, tmp_path):
        from core.graph_memory import KnowledgeGraph
        g = self._build()
        path = str(tmp_path / "graph.json")
        g.save(path)
        restored = KnowledgeGraph.load(path)
        assert len(restored) == 2
        assert restored.get_entity("LiDAR") is not None

    def test_export_json_still_works(self):
        """旧接口 export_json/from_json 保持兼容."""
        from core.graph_memory import KnowledgeGraph
        g = self._build()
        json_str = g.export_json()
        restored = KnowledgeGraph.from_json(json_str)
        assert len(restored) == 2


# ---------------------------------------------------------------------------
# PromptRegistry
# ---------------------------------------------------------------------------

class TestPromptRegistryPersistence:
    def _build(self):
        from core.prompt_registry import PromptRegistry
        reg = PromptRegistry()
        reg.register("greet", "Hello {{name}}!", tags=["demo"])
        reg.register("greet", "Hi {{name}}, welcome!")
        reg.promote("greet", 1, "production")
        reg.register("analyze", "Analyze {{topic|safety}}")
        return reg

    def test_to_dict_from_dict_roundtrip(self):
        from core.prompt_registry import PromptRegistry
        reg = self._build()
        restored = PromptRegistry.from_dict(reg.to_dict())

        assert sorted(p.name for p in restored.list_prompts()) == ["analyze", "greet"]
        # 版本保留 / versions preserved
        assert restored.get("greet").version == 2
        assert restored.get("greet", version=1) is not None
        # 标签部署保留 / label deployment preserved
        assert restored.get("greet", label="production").version == 1

    def test_save_load_roundtrip(self, tmp_path):
        from core.prompt_registry import PromptRegistry
        reg = self._build()
        path = str(tmp_path / "prompts.json")
        reg.save(path)
        restored = PromptRegistry.load(path)

        assert restored.get("greet", label="production").version == 1
        compiled = restored.compile("analyze")
        assert compiled.text == "Analyze safety"

    def test_compile_after_reload(self, tmp_path):
        from core.prompt_registry import PromptRegistry
        reg = self._build()
        path = str(tmp_path / "p.json")
        reg.save(path)
        restored = PromptRegistry.load(path)
        compiled = restored.compile("greet", name="Alice")
        assert compiled.text == "Hi Alice, welcome!"
