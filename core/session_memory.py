"""
Session Memory — 会话记忆
Session-scoped conversational memory with progressive summarization.
Inspired by Agno/PhiData session memory management.

@module: core.session_memory
"""

import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("Nonull.session")


class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class SessionMessage:
    role: MessageRole
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_estimate: int = 0

    def __post_init__(self):
        if self.token_estimate == 0:
            self.token_estimate = max(1, len(self.content) // 4)


@dataclass
class SessionRecord:
    session_id: str
    messages: List[SessionMessage] = field(default_factory=list)
    summary: str = ""
    facts: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    total_tokens: int = 0

    def recalculate_tokens(self):
        self.total_tokens = (
            sum(m.token_estimate for m in self.messages)
            + len(self.summary) // 4
        )


class SessionMemory:
    def __init__(
        self,
        max_tokens: int = 4000,
        summarize_fn: Optional[Callable[[str], str]] = None,
    ):
        self._max_tokens = max_tokens
        self._summarize_fn = summarize_fn or self._default_summarize
        self._sessions: Dict[str, SessionRecord] = {}
        self._lock = threading.Lock()

    def create_session(self, session_id: Optional[str] = None) -> str:
        sid = session_id or uuid.uuid4().hex[:16]
        now = time.time()
        with self._lock:
            if sid in self._sessions:
                logger.warning("Session %s already exists, returning existing", sid)
                return sid
            self._sessions[sid] = SessionRecord(
                session_id=sid,
                created_at=now,
                updated_at=now,
            )
        logger.info("Created session %s", sid)
        return sid

    def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            record = self._get_record(session_id)
            msg = SessionMessage(
                role=role,
                content=content,
                metadata=metadata or {},
            )
            record.messages.append(msg)
            record.total_tokens += msg.token_estimate
            record.updated_at = time.time()

            needs_summarize = record.total_tokens > self._max_tokens
            if needs_summarize and len(record.messages) >= 4:
                split = len(record.messages) // 2
                older = record.messages[:split]
                text_block = "\n".join(f"{m.role.value}: {m.content}" for m in older)
                if record.summary:
                    text_block = f"Previous summary: {record.summary}\n\n{text_block}"
                remaining = record.messages[split:]
                snapshot_len = len(record.messages)
            else:
                return

        summary = self._summarize_fn(text_block)

        with self._lock:
            try:
                record = self._get_record(session_id)
            except KeyError:
                return
            new_during_summarize = record.messages[snapshot_len:]
            record.summary = summary
            record.messages = remaining + new_during_summarize
            record.recalculate_tokens()
            record.updated_at = time.time()

    def get_context(self, session_id: str, max_tokens: int = 2000) -> str:
        with self._lock:
            record = self._get_record(session_id)
            parts = []
            budget = max_tokens

            if record.summary:
                summary_tokens = len(record.summary) // 4
                if summary_tokens < budget:
                    parts.append(f"[Summary]\n{record.summary}")
                    budget -= summary_tokens
                else:
                    truncated = record.summary[: budget * 4]
                    parts.append(f"[Summary]\n{truncated}")
                    return "\n\n".join(parts)

            recent_lines = []
            collected_tokens = 0
            for msg in reversed(record.messages):
                if collected_tokens + msg.token_estimate > budget:
                    break
                line = f"{msg.role.value}: {msg.content}"
                recent_lines.append(line)
                collected_tokens += msg.token_estimate

            if recent_lines:
                recent_lines.reverse()
                parts.append("[Recent]\n" + "\n".join(recent_lines))

            return "\n\n".join(parts)

    def get_messages(
        self, session_id: str, limit: int = 50
    ) -> List[SessionMessage]:
        with self._lock:
            record = self._get_record(session_id)
            return list(record.messages[-limit:])

    def get_facts(self, session_id: str) -> List[str]:
        with self._lock:
            record = self._get_record(session_id)
            return list(record.facts)

    def extract_facts(self, session_id: str) -> None:
        with self._lock:
            record = self._get_record(session_id)
            new_facts = []
            recent = record.messages[-10:]

            for msg in recent:
                if msg.role in (MessageRole.USER, MessageRole.ASSISTANT):
                    extracted = self._extract_facts_from_text(msg.content)
                    new_facts.extend(extracted)

            seen = set(record.facts)
            for fact in new_facts:
                if fact not in seen:
                    record.facts.append(fact)
                    seen.add(fact)

            record.updated_at = time.time()
            logger.debug(
                "Extracted %d new facts for session %s",
                len(new_facts),
                session_id,
            )

    def summarize(self, session_id: str) -> None:
        with self._lock:
            record = self._get_record(session_id)
            self._auto_summarize(record)

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            if session_id not in self._sessions:
                raise KeyError(f"Session not found: {session_id}")
            del self._sessions[session_id]
        logger.info("Cleared session %s", session_id)

    def list_sessions(self) -> List[str]:
        with self._lock:
            return list(self._sessions.keys())

    def export_session(self, session_id: str) -> Dict:
        with self._lock:
            record = self._get_record(session_id)
            data = {
                "session_id": record.session_id,
                "summary": record.summary,
                "facts": list(record.facts),
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "total_tokens": record.total_tokens,
                "messages": [
                    {
                        "role": m.role.value,
                        "content": m.content,
                        "timestamp": m.timestamp,
                        "metadata": m.metadata,
                        "token_estimate": m.token_estimate,
                    }
                    for m in record.messages
                ],
            }
            return data

    def import_session(self, data: Dict) -> str:
        sid = data.get("session_id", uuid.uuid4().hex[:16])
        messages = []
        for m in data.get("messages", []):
            messages.append(
                SessionMessage(
                    role=MessageRole(m["role"]),
                    content=m["content"],
                    timestamp=m.get("timestamp", time.time()),
                    metadata=m.get("metadata", {}),
                    token_estimate=m.get("token_estimate", 0),
                )
            )

        record = SessionRecord(
            session_id=sid,
            messages=messages,
            summary=data.get("summary", ""),
            facts=data.get("facts", []),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            total_tokens=data.get("total_tokens", 0),
        )
        record.recalculate_tokens()

        with self._lock:
            self._sessions[sid] = record

        logger.info("Imported session %s with %d messages", sid, len(messages))
        return sid

    def stats(self) -> Dict:
        with self._lock:
            total_messages = sum(
                len(r.messages) for r in self._sessions.values()
            )
            total_tokens = sum(
                r.total_tokens for r in self._sessions.values()
            )
            total_facts = sum(
                len(r.facts) for r in self._sessions.values()
            )
            return {
                "session_count": len(self._sessions),
                "total_messages": total_messages,
                "total_tokens": total_tokens,
                "total_facts": total_facts,
                "max_tokens_per_session": self._max_tokens,
            }

    # ------------------------------------------------------------------
    # 持久化 / Persistence
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict:
        """序列化全部会话 / Serialize all sessions to a dict.

        复用 export_session 的单会话格式。
        Reuses the per-session export_session format.
        """
        with self._lock:
            session_ids = list(self._sessions.keys())
        return {
            "max_tokens": self._max_tokens,
            "sessions": [self.export_session(sid) for sid in session_ids],
        }

    @classmethod
    def from_dict(cls, data: Dict, summarize_fn=None) -> "SessionMemory":
        """从字典重建 / Rebuild from a dict produced by to_dict().

        Args:
            data:         to_dict() 的输出 / Output of to_dict()
            summarize_fn: 可选摘要函数（不可序列化，须重新注入）
                          Optional summarizer (not serializable, re-inject)
        """
        kwargs = {}
        if summarize_fn is not None:
            kwargs["summarize_fn"] = summarize_fn
        mem = cls(max_tokens=data.get("max_tokens", 4000), **kwargs)
        for session_data in data.get("sessions", []):
            mem.import_session(session_data)
        return mem

    def save(self, path: str) -> None:
        """原子化保存到 JSON 文件 / Atomically save to a JSON file."""
        from .persistence import atomic_write_json, wrap_payload
        atomic_write_json(path, wrap_payload("session_memory", self.to_dict()))
        logger.info("SessionMemory saved to %s", path)

    @classmethod
    def load(cls, path: str, summarize_fn=None) -> "SessionMemory":
        """从 JSON 文件加载 / Load from a JSON file."""
        from .persistence import read_json, unwrap_payload
        data = unwrap_payload(read_json(path), "session_memory")
        mem = cls.from_dict(data, summarize_fn=summarize_fn)
        logger.info("SessionMemory loaded from %s (%d sessions)",
                    path, len(mem.list_sessions()))
        return mem

    def _get_record(self, session_id: str) -> SessionRecord:
        if session_id not in self._sessions:
            raise KeyError(f"Session not found: {session_id}")
        return self._sessions[session_id]

    def _auto_summarize(self, record: SessionRecord) -> None:
        if len(record.messages) < 4:
            return

        split = len(record.messages) // 2
        older = record.messages[:split]

        text_block = "\n".join(
            f"{m.role.value}: {m.content}" for m in older
        )

        if record.summary:
            text_block = f"Previous summary: {record.summary}\n\n{text_block}"

        record.summary = self._summarize_fn(text_block)
        record.messages = record.messages[split:]
        record.recalculate_tokens()
        record.updated_at = time.time()

        logger.debug(
            "Auto-summarized session %s: compressed %d messages",
            record.session_id,
            split,
        )

    @staticmethod
    def _default_summarize(text: str) -> str:
        lines = text.strip().split("\n")
        sentences = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Strip role prefix if present
            for prefix in ("user: ", "assistant: ", "system: ", "tool: ", "Previous summary: "):
                if line.lower().startswith(prefix.lower()):
                    line = line[len(prefix):]
                    break
            match = re.match(r"([^.!?]*[.!?])", line)
            if match:
                sentences.append(match.group(1).strip())
            elif len(line) <= 100:
                sentences.append(line)
            else:
                sentences.append(line[:97] + "...")

        return " ".join(sentences)

    _FACT_PATTERNS = [
        re.compile(
            r"(?:^|[.!?]\s+)([A-Z][^.!?]*?\b(?:is|are|was|were|has|have|had)\b[^.!?]*[.!?])",
            re.MULTILINE,
        ),
        # Sentences containing numbers (dates, quantities, versions)
        re.compile(
            r"(?:^|[.!?]\s+)([A-Z][^.!?]*\d+[^.!?]*[.!?])",
            re.MULTILINE,
        ),
    ]

    @classmethod
    def _extract_facts_from_text(cls, text: str) -> List[str]:
        facts = []
        seen = set()
        for pattern in cls._FACT_PATTERNS:
            for match in pattern.finditer(text):
                fact = match.group(1).strip()
                if len(fact) < 10 or len(fact) > 300:
                    continue
                normalized = fact.lower()
                if normalized not in seen:
                    seen.add(normalized)
                    facts.append(fact)
        return facts
