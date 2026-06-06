"""
Utility skills / 实用工具技能
"""
from __future__ import annotations
import base64
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from skills.base import BaseSkill, SkillMetadata, SkillCategory


class UuidGeneratorSkill(BaseSkill):
    """Generate one or more UUIDs."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="uuid_generator",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Generate UUIDs (v4 by default). Returns a list of UUID strings.",
            tags=["uuid", "id", "generator"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        count = context.get("count", 1)
        if not isinstance(count, int) or not 1 <= count <= 1000:
            raise ValueError("'count' must be an integer in [1, 1000]")

    def _execute_impl(self, context):
        count = context.get("count", 1)
        version = context.get("version", 4)
        if version == 4:
            uuids = [str(uuid.uuid4()) for _ in range(count)]
        elif version == 1:
            uuids = [str(uuid.uuid1()) for _ in range(count)]
        else:
            return {"error": f"UUID version {version} not supported (use 1 or 4)"}
        return {"uuids": uuids, "count": len(uuids)}


class HashSkill(BaseSkill):
    """Compute hash of a string (md5, sha1, sha256, sha512)."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="hash",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Compute a cryptographic hash of a string.",
            tags=["hash", "crypto", "checksum"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("text"):
            raise ValueError("'text' is required")
        algo = context.get("algorithm", "sha256")
        if algo not in ("md5", "sha1", "sha256", "sha512"):
            raise ValueError(f"algorithm must be md5|sha1|sha256|sha512, got {algo!r}")

    def _execute_impl(self, context):
        text = context["text"]
        algo = context.get("algorithm", "sha256")
        h = hashlib.new(algo)
        h.update(text.encode("utf-8"))
        return {"algorithm": algo, "hash": h.hexdigest()}


class TimestampSkill(BaseSkill):
    """Get current timestamp in ISO format (UTC or local)."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="timestamp",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Get the current timestamp in ISO 8601 format.",
            tags=["time", "timestamp", "datetime"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        pass  # no required inputs

    def _execute_impl(self, context):
        use_utc = context.get("utc", True)
        now = datetime.now(timezone.utc) if use_utc else datetime.now()
        return {
            "iso": now.isoformat(),
            "unix": int(now.timestamp()),
            "utc": use_utc,
        }


class Base64Skill(BaseSkill):
    """Base64 encode or decode a string."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="base64",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Base64 encode or decode a UTF-8 string.",
            tags=["base64", "encoding", "data"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        op = context.get("operation", "encode")
        if op not in ("encode", "decode"):
            raise ValueError(f"operation must be encode|decode, got {op!r}")
        if op == "decode" and not context.get("text"):
            raise ValueError("'text' is required for decode")
        if op == "encode" and "text" not in context:
            raise ValueError("'text' is required for encode")

    def _execute_impl(self, context):
        op = context.get("operation", "encode")
        text = context["text"]
        try:
            if op == "encode":
                encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
                return {"operation": op, "output": encoded}
            else:
                decoded = base64.b64decode(text).decode("utf-8")
                return {"operation": op, "output": decoded}
        except Exception as e:
            return {"operation": op, "error": str(e)}
