"""Pluggable filesystem backends — LangChain Deep Agents style."""
from abc import ABC, abstractmethod
from typing import List, Optional
from pathlib import Path
import re


class FileSystemBackend(ABC):
    """Unified file system interface. Supports local, S3, memory, etc."""
    @abstractmethod
    def read(self, path: str, offset: int = 0, limit: int = None) -> str: ...
    @abstractmethod
    def write(self, path: str, content: str) -> bool: ...
    @abstractmethod
    def edit(self, path: str, old_str: str, new_str: str) -> bool: ...
    @abstractmethod
    def list_dir(self, path: str) -> List[str]: ...
    @abstractmethod
    def glob(self, pattern: str) -> List[str]: ...
    @abstractmethod
    def grep(self, pattern: str, path: str, recursive: bool = True) -> List[dict]: ...
    @abstractmethod
    def exists(self, path: str) -> bool: ...


class LocalBackend(FileSystemBackend):
    """Local disk backend."""
    def read(self, path, offset=0, limit=None):
        p = Path(path)
        if not p.exists():
            return f"File not found: {path}"
        text = p.read_text(encoding="utf-8")
        lines = text.split("\n")
        if offset:
            lines = lines[offset:]
        if limit:
            lines = lines[:limit]
        return "\n".join(lines)

    def write(self, path, content):
        Path(path).write_text(content, encoding="utf-8")
        return True

    def edit(self, path, old_str, new_str):
        p = Path(path)
        if not p.exists():
            return False
        content = p.read_text(encoding="utf-8")
        if old_str not in content:
            return False
        content = content.replace(old_str, new_str, 1)
        p.write_text(content, encoding="utf-8")
        return True

    def list_dir(self, path):
        p = Path(path)
        if not p.exists():
            return []
        return [str(x.relative_to(p)) for x in p.iterdir()]

    def glob(self, pattern):
        return [str(p) for p in Path().glob(pattern)]

    def grep(self, pattern, path, recursive=True):
        results = []
        p = Path(path)
        if p.is_file():
            files = [p]
        elif recursive:
            files = list(p.rglob("*"))
        else:
            files = list(p.glob("*"))
        for f in files:
            if f.is_file():
                try:
                    for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").split("\n"), 1):
                        if re.search(pattern, line, re.IGNORECASE):
                            results.append({"file": str(f), "line": i, "content": line.strip()})
                except Exception:
                    pass
        return results

    def exists(self, path):
        return Path(path).exists()


_backend: FileSystemBackend = LocalBackend()

def get_backend() -> FileSystemBackend:
    return _backend

def set_backend(backend: FileSystemBackend):
    global _backend
    _backend = backend
