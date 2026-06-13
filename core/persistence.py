"""
Persistence — 持久化基础设施

Atomic JSON file persistence utilities shared by stateful modules
(SessionMemory, KnowledgeGraph, PromptRegistry, ...).

原子化 JSON 文件持久化工具，供有状态模块共用。

Design / 设计:
- to_dict()/from_dict() 负责（反）序列化，save()/load() 负责文件 I/O
- 原子写：先写临时文件再 os.replace，避免写一半进程挂掉损坏文件
- 统一 UTF-8 + ensure_ascii=False + indent=2，与项目现有约定一致

@module: core.persistence
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any, Dict

logger = logging.getLogger("Nonull.persistence")

#: 持久化文件格式版本 / Persisted file format version
FORMAT_VERSION = 1


def atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    """原子化写 JSON 文件 / Atomically write a JSON file.

    先写同目录临时文件，再 os.replace 原子替换。崩溃时旧文件保持完好。
    Writes to a temp file in the same directory, then os.replace —
    the old file stays intact if the process dies mid-write.

    Args:
        path: 目标文件路径 / Target file path
        data: 可 JSON 序列化的字典 / JSON-serializable dict
    """
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        prefix=".tmp_", suffix=".json", dir=directory
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp_path, path)
        logger.debug("Atomic write: %s", path)
    except Exception:
        # 清理残留临时文件 / Clean up the orphaned temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read_json(path: str) -> Dict[str, Any]:
    """读取 JSON 文件 / Read a JSON file.

    Args:
        path: 文件路径 / File path

    Returns:
        解析后的字典 / Parsed dict

    Raises:
        FileNotFoundError: 文件不存在 / File does not exist
        ValueError: 内容不是 JSON 对象 / Content is not a JSON object
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}, got {type(data).__name__}")
    return data


def wrap_payload(kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """给持久化数据加版本信封 / Wrap payload with a version envelope.

    Args:
        kind:    数据种类标识，如 "session_memory" / Payload kind tag
        payload: 实际数据 / Actual data

    Returns:
        {"format_version": 1, "kind": ..., "data": ...}
    """
    return {
        "format_version": FORMAT_VERSION,
        "kind": kind,
        "data": payload,
    }


def unwrap_payload(envelope: Dict[str, Any], kind: str) -> Dict[str, Any]:
    """解开版本信封并校验种类 / Unwrap envelope and validate kind.

    兼容旧格式：若没有信封结构（无 format_version），原样返回。
    Backward compatible: data without an envelope is returned as-is.

    Args:
        envelope: read_json 的结果 / Result from read_json
        kind:     期望的数据种类 / Expected payload kind

    Returns:
        实际数据字典 / The actual data dict

    Raises:
        ValueError: kind 不匹配 / Kind mismatch
    """
    if "format_version" not in envelope:
        return envelope  # 旧格式，无信封 / legacy format without envelope
    actual_kind = envelope.get("kind", "")
    if actual_kind != kind:
        raise ValueError(
            f"Persisted file kind mismatch: expected '{kind}', got '{actual_kind}'"
        )
    data = envelope.get("data")
    if not isinstance(data, dict):
        raise ValueError("Envelope 'data' field is missing or not an object")
    return data
