"""Tests for core/context_manager.py — Context management."""
from core.context_manager import ContextCompressor, ProgressiveDisclosure


class TestContextCompressor:
    def test_truncate_keeps_system_and_recent(self):
        compressor = ContextCompressor()
        msgs = (
            [{"role": "system", "content": "You are a helpful assistant."}]
            + [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        )
        result = compressor._truncate(msgs, keep_last=3)
        system_count = sum(1 for m in result if m["role"] == "system")
        assert system_count == 1
        assert len(result) <= 4  # system + 3 recent

    def test_summarize_compresses_old_messages(self):
        compressor = ContextCompressor()
        msgs = (
            [{"role": "system", "content": "You are helpful."}]
            + [{"role": "user", "content": f"Detail {i}"} for i in range(10)]
        )
        result = compressor._summarize(msgs, summary_window=3)
        assert len(result) <= 6  # system + summary + 3 recent

    def test_progressive_within_budget(self):
        compressor = ContextCompressor(max_tokens=200)
        long_text = "X" * 100
        msgs = [
            {"role": "user", "content": long_text},
            {"role": "user", "content": long_text},
        ]
        result = compressor._progressive(msgs)
        # Should fit at least one message within 200 token budget
        assert len(result) >= 1

    def test_compress_messages_summary_strategy(self):
        compressor = ContextCompressor()
        msgs = [{"role": "user", "content": f"M{i}"} for i in range(20)]
        result = compressor.compress_messages(msgs, strategy="summary")
        assert len(result) < len(msgs)

    def test_estimate_tokens(self):
        compressor = ContextCompressor()
        # ~4 chars per token
        assert compressor.estimate_tokens("hello world") == 2  # 11//4
        assert compressor.estimate_tokens("") == 0
        assert compressor.estimate_tokens("A" * 100) == 25


class TestProgressiveDisclosure:
    def test_set_and_get(self):
        pd = ProgressiveDisclosure()
        pd.set("code", "def foo(): pass")
        assert pd.get("code") == "def foo(): pass"
        assert pd.get("missing", "fallback") == "fallback"

    def test_build_prompt(self):
        pd = ProgressiveDisclosure()
        pd.set("context", "file: main.py")
        pd.set("goal", "review this code")
        prompt = pd.build_prompt("Review the code", includes=["context", "goal"])
        assert "Task: Review the code" in prompt
        assert "file: main.py" in prompt
        assert "review this code" in prompt

    def test_build_prompt_includes_all_when_not_specified(self):
        pd = ProgressiveDisclosure()
        pd.set("a", "1")
        pd.set("b", "2")
        prompt = pd.build_prompt("test")
        assert "a:" in prompt
        assert "b:" in prompt
