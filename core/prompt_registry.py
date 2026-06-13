"""
Prompt Registry — 提示词注册表
Versioned prompt management with labels and variable compilation.
Inspired by Langfuse prompt management.

@module: core.prompt_registry
"""

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

logger = logging.getLogger("Nonull.prompts")

VARIABLE_PATTERN = re.compile(r"\{\{(\w+)(?:\|([^}]*))?\}\}")


def _extract_variables(template: str) -> List[str]:
    return list(dict.fromkeys(m.group(1) for m in VARIABLE_PATTERN.finditer(template)))


@dataclass
class PromptVersion:
    version: int
    template: str
    labels: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    variables: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.variables:
            self.variables = _extract_variables(self.template)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "template": self.template,
            "labels": self.labels,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "variables": self.variables,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptVersion":
        return cls(
            version=data["version"],
            template=data["template"],
            labels=data.get("labels", []),
            created_at=data.get("created_at", time.time()),
            metadata=data.get("metadata", {}),
            variables=data.get("variables", []),
        )


@dataclass
class PromptRecord:
    name: str
    versions: List[PromptVersion] = field(default_factory=list)
    description: str = ""
    tags: List[str] = field(default_factory=list)

    @property
    def latest_version(self) -> int:
        if not self.versions:
            return 0
        return max(v.version for v in self.versions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "versions": [v.to_dict() for v in self.versions],
            "description": self.description,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptRecord":
        return cls(
            name=data["name"],
            versions=[PromptVersion.from_dict(v) for v in data.get("versions", [])],
            description=data.get("description", ""),
            tags=data.get("tags", []),
        )


@dataclass
class CompiledPrompt:
    text: str
    source_name: str
    source_version: int
    variables_used: Dict[str, str] = field(default_factory=dict)


class PromptRegistry:

    def __init__(self):
        self._records: Dict[str, PromptRecord] = {}
        self._lock = threading.Lock()

    def register(
        self,
        name: str,
        template: str,
        description: str = "",
        labels: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PromptVersion:
        with self._lock:
            if name in self._records:
                record = self._records[name]
                next_version = record.latest_version + 1
                if description:
                    record.description = description
                if tags is not None:
                    record.tags = tags
            else:
                next_version = 1
                record = PromptRecord(
                    name=name,
                    description=description,
                    tags=tags or [],
                )
                self._records[name] = record

            pv = PromptVersion(
                version=next_version,
                template=template,
                labels=labels or [],
                metadata=metadata or {},
            )
            record.versions.append(pv)

            logger.info(
                "Registered prompt '%s' v%d (labels=%s)", name, next_version, pv.labels
            )
            return pv

    def get(
        self,
        name: str,
        version: Optional[int] = None,
        label: Optional[str] = None,
    ) -> Optional[PromptVersion]:
        with self._lock:
            record = self._records.get(name)
            if record is None:
                return None

            if version is not None:
                for v in record.versions:
                    if v.version == version:
                        return v
                return None

            if label is not None:
                candidates = [v for v in record.versions if label in v.labels]
                if not candidates:
                    return None
                return max(candidates, key=lambda v: v.version)

            if not record.versions:
                return None
            return max(record.versions, key=lambda v: v.version)

    def compile(
        self,
        prompt_name: str,
        label: Optional[str] = None,
        version: Optional[int] = None,
        **variables: str,
    ) -> CompiledPrompt:
        pv = self.get(prompt_name, version=version, label=label)
        if pv is None:
            raise ValueError(f"Prompt '{prompt_name}' not found")

        defaults: Dict[str, str] = {}
        required: List[str] = []
        for m in VARIABLE_PATTERN.finditer(pv.template):
            var_name = m.group(1)
            default_val = m.group(2)
            if default_val is not None:
                defaults[var_name] = default_val
            elif var_name not in variables:
                required.append(var_name)

        if required:
            missing = [r for r in required if r not in variables]
            if missing:
                raise ValueError(
                    f"Missing required variables for prompt '{prompt_name}': {missing}"
                )

        variables_used: Dict[str, str] = {}

        def _replace(match: re.Match) -> str:
            var_name = match.group(1)
            default_val = match.group(2)
            if var_name in variables:
                value = variables[var_name]
            elif default_val is not None:
                value = default_val
            else:
                raise ValueError(f"Missing variable '{var_name}' for prompt '{prompt_name}'")
            variables_used[var_name] = value
            return value

        text = VARIABLE_PATTERN.sub(_replace, pv.template)

        logger.debug(
            "Compiled prompt '%s' v%d with variables %s",
            prompt_name,
            pv.version,
            list(variables_used.keys()),
        )

        return CompiledPrompt(
            text=text,
            source_name=prompt_name,
            source_version=pv.version,
            variables_used=variables_used,
        )

    def promote(self, name: str, version: int, label: str) -> None:
        with self._lock:
            record = self._records.get(name)
            if record is None:
                raise ValueError(f"Prompt '{name}' not found")

            target = None
            for v in record.versions:
                if v.version == version:
                    target = v
                    break

            if target is None:
                raise ValueError(
                    f"Version {version} not found for prompt '{name}'"
                )

            if label not in target.labels:
                target.labels.append(label)
                logger.info(
                    "Promoted prompt '%s' v%d to '%s'", name, version, label
                )

    def demote(self, name: str, version: int, label: str) -> None:
        with self._lock:
            record = self._records.get(name)
            if record is None:
                raise ValueError(f"Prompt '{name}' not found")

            target = None
            for v in record.versions:
                if v.version == version:
                    target = v
                    break

            if target is None:
                raise ValueError(
                    f"Version {version} not found for prompt '{name}'"
                )

            if label in target.labels:
                target.labels.remove(label)
                logger.info(
                    "Demoted prompt '%s' v%d from '%s'", name, version, label
                )

    def list_prompts(self, tag: Optional[str] = None) -> List[PromptRecord]:
        with self._lock:
            records = list(self._records.values())
            if tag is not None:
                records = [r for r in records if tag in r.tags]
            return records

    def get_history(self, name: str) -> List[PromptVersion]:
        with self._lock:
            record = self._records.get(name)
            if record is None:
                return []
            return sorted(record.versions, key=lambda v: v.version)

    def delete(self, name: str) -> None:
        with self._lock:
            if name in self._records:
                del self._records[name]
                logger.info("Deleted prompt '%s'", name)

    def export_json(self) -> str:
        with self._lock:
            data = {
                "prompts": {
                    name: record.to_dict()
                    for name, record in self._records.items()
                },
                "exported_at": time.time(),
            }
            return json.dumps(data, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "PromptRegistry":
        data = json.loads(json_str)
        registry = cls()
        with registry._lock:
            for name, record_data in data.get("prompts", {}).items():
                registry._records[name] = PromptRecord.from_dict(record_data)
        logger.info("Loaded %d prompts from JSON", len(registry._records))
        return registry

    # ------------------------------------------------------------------
    # 持久化 / Persistence
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 / Serialize to a dict."""
        with self._lock:
            return {
                "prompts": {
                    name: record.to_dict()
                    for name, record in self._records.items()
                },
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptRegistry":
        """从字典重建 / Rebuild from a dict produced by to_dict()."""
        registry = cls()
        with registry._lock:
            for name, record_data in data.get("prompts", {}).items():
                registry._records[name] = PromptRecord.from_dict(record_data)
        return registry

    def save(self, path: str) -> None:
        """原子化保存到 JSON 文件 / Atomically save to a JSON file."""
        from .persistence import atomic_write_json, wrap_payload
        atomic_write_json(path, wrap_payload("prompt_registry", self.to_dict()))
        logger.info("PromptRegistry saved to %s", path)

    @classmethod
    def load(cls, path: str) -> "PromptRegistry":
        """从 JSON 文件加载 / Load from a JSON file."""
        from .persistence import read_json, unwrap_payload
        data = unwrap_payload(read_json(path), "prompt_registry")
        registry = cls.from_dict(data)
        logger.info("PromptRegistry loaded from %s (%d prompts)",
                    path, len(registry._records))
        return registry

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total_versions = sum(
                len(r.versions) for r in self._records.values()
            )
            all_labels: set[str] = set()
            all_tags: set[str] = set()
            for record in self._records.values():
                all_tags.update(record.tags)
                for v in record.versions:
                    all_labels.update(v.labels)

            return {
                "total_prompts": len(self._records),
                "total_versions": total_versions,
                "labels": sorted(all_labels),
                "tags": sorted(all_tags),
            }
