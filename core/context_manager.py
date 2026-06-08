"""
Context window management — compression, progressive disclosure, smart truncation.

Inspired by LangChain Deep Agents context management strategies.
"""
from typing import List, Optional, Any
import re


class ContextCompressor:
    """Compress conversation history to fit within token budgets."""

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def compress_messages(self, messages: List[dict], strategy: str = "summary") -> List[dict]:
        if strategy == "truncate":
            return self._truncate(messages)
        elif strategy == "summary":
            return self._summarize(messages)
        elif strategy == "progressive":
            return self._progressive(messages)
        return messages

    def _truncate(self, messages: List[dict], keep_last: int = 10) -> List[dict]:
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        return system_msgs + non_system[-keep_last:]

    def _summarize(self, messages: List[dict], summary_window: int = 6) -> List[dict]:
        if len(messages) <= summary_window + 2:
            return messages
        system_msgs = [m for m in messages if m.get("role") == "system"]
        to_summarize = messages[len(system_msgs):-summary_window]
        recent = messages[-summary_window:]
        total_chars = sum(len(m.get("content", "")) for m in to_summarize)
        summary = f"[Earlier conversation summarized: {len(to_summarize)} msgs, ~{total_chars} chars]"
        return system_msgs + [{"role": "system", "content": summary}] + recent

    def _progressive(self, messages: List[dict]) -> List[dict]:
        budget = self.max_tokens
        result = []
        for m in reversed(messages):
            tokens = self.estimate_tokens(m.get("content", ""))
            if budget - tokens > 0:
                result.insert(0, m)
                budget -= tokens
            else:
                break
        return result


class ProgressiveDisclosure:
    """Reveal info progressively — only include what's needed."""

    def __init__(self):
        self._context: dict = {}

    def set(self, key: str, value: Any):
        self._context[key] = value

    def get(self, key: str, default=None):
        return self._context.get(key, default)

    def build_prompt(self, task: str, includes: Optional[List[str]] = None) -> str:
        parts = [f"Task: {task}"]
        for key in (includes or list(self._context.keys())):
            val = self._context.get(key)
            if val is not None:
                parts.append(f"\n{key}:\n{val}")
        return "\n".join(parts)
