"""
File system abstraction — unified read/write/edit/glob/grep with pluggable backends.
Inspired by LangChain Deep Agents file system abstraction.
"""
from skills.filesystem.backend import FileSystemBackend, LocalBackend, get_backend, set_backend
from skills.filesystem.fs_skills import (
    ReadFileSkill, WriteFileSkill, EditFileSkill,
    GlobSkill, GrepSkill, ListDirSkill,
)
