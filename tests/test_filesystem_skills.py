"""Tests for skills/filesystem/ — Deep Agents style file system abstraction."""
import os
import tempfile
from pathlib import Path
import pytest

from skills.filesystem.backend import LocalBackend, get_backend, set_backend
from skills.filesystem.fs_skills import (
    ReadFileSkill, WriteFileSkill, EditFileSkill,
    GlobSkill, GrepSkill, ListDirSkill,
)


class TestBackend:
    def test_local_backend_read(self):
        b = LocalBackend()
        content = b.read(__file__, limit=5)
        lines = content.split("\n")
        assert len(lines) <= 5
        assert "Tests" in content

    def test_local_backend_write_and_read(self):
        b = LocalBackend()
        tmp = tempfile.mktemp(suffix=".txt")
        try:
            assert b.write(tmp, "hello world")
            assert b.read(tmp) == "hello world"
        finally:
            os.unlink(tmp)

    def test_local_backend_edit(self):
        b = LocalBackend()
        tmp = tempfile.mktemp(suffix=".txt")
        try:
            b.write(tmp, "foo bar baz")
            assert b.edit(tmp, "bar", "qux")
            assert b.read(tmp) == "foo qux baz"
        finally:
            os.unlink(tmp)

    def test_local_backend_exists(self):
        assert get_backend().exists(__file__)
        assert not get_backend().exists("/nonexistent_file_xyz")

    def test_local_backend_glob(self):
        files = get_backend().glob("**/test_filesystem_skills.py")
        assert len(files) >= 1

    def test_local_backend_grep(self):
        matches = get_backend().grep("TestBackend", __file__)
        assert len(matches) >= 1

    def test_local_backend_list_dir(self):
        entries = get_backend().list_dir(".")
        assert len(entries) >= 1

    def test_set_backend_swaps_implementation(self):
        orig = get_backend()
        fake = LocalBackend()
        set_backend(fake)
        try:
            assert get_backend() is fake
        finally:
            set_backend(orig)
            assert get_backend() is orig


class FailingBackend(LocalBackend):
    """Backend that fails on all operations."""
    def read(self, path, offset=0, limit=None):
        raise PermissionError("Access denied")


class TestReadFileSkill:
    def test_reads_file(self):
        skill = ReadFileSkill()
        skill.activate()
        result = skill.execute({"path": __file__, "limit": 3})
        assert result.success
        assert "Tests for skills/filesystem" in result.data


class TestWriteFileSkill:
    def test_writes_file(self):
        tmp = tempfile.mktemp(suffix=".txt")
        skill = WriteFileSkill()
        skill.activate()
        try:
            result = skill.execute({"path": tmp, "content": "test content"})
            assert result.success
        finally:
            os.unlink(tmp)


class TestGlobSkill:
    def test_glob(self):
        skill = GlobSkill()
        skill.activate()
        result = skill.execute({"pattern": "**/*.py"})
        assert result.success
        assert len(result.data.get("files", [])) > 0


class TestGrepSkill:
    def test_grep(self):
        skill = GrepSkill()
        skill.activate()
        result = skill.execute({"pattern": "class", "path": __file__})
        assert result.success
        assert len(result.data.get("matches", [])) > 0


class TestListDirSkill:
    def test_list_dir(self):
        skill = ListDirSkill()
        skill.activate()
        result = skill.execute({"path": "."})
        assert result.success
        assert len(result.data.get("files", [])) > 0
