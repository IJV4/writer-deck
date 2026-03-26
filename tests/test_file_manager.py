"""Tests for atomic file writes and FileManager class."""

from __future__ import annotations

import os
import time
from pathlib import Path

from writerdeck.utils.file_manager import _atomic_write, FileManager
from writerdeck.core.document import Document


class TestAtomicWrite:
    def test_basic_write(self, tmp_path):
        path = tmp_path / "test.txt"
        _atomic_write(path, "hello world")
        assert path.read_text() == "hello world"

    def test_overwrite(self, tmp_path):
        path = tmp_path / "test.txt"
        path.write_text("old")
        _atomic_write(path, "new")
        assert path.read_text() == "new"

    def test_no_temp_files_left(self, tmp_path):
        path = tmp_path / "test.txt"
        _atomic_write(path, "content")
        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert files[0].name == "test.txt"

    def test_unicode_content(self, tmp_path):
        path = tmp_path / "test.txt"
        _atomic_write(path, "hello 世界 🌍")
        assert path.read_text(encoding="utf-8") == "hello 世界 🌍"

    def test_empty_content(self, tmp_path):
        path = tmp_path / "test.txt"
        _atomic_write(path, "")
        assert path.read_text() == ""

    def test_multiline_content(self, tmp_path):
        path = tmp_path / "test.txt"
        content = "line1\nline2\nline3"
        _atomic_write(path, content)
        assert path.read_text() == content


class TestFileManagerSave:
    def test_save_creates_file(self, tmp_path):
        fm = FileManager(tmp_path)
        doc = Document("Hello world")
        doc.name = "test-doc"
        doc.dirty = True
        result = fm.save(doc)
        assert result.exists()
        assert result.read_text() == "Hello world"

    def test_save_clears_dirty(self, tmp_path):
        fm = FileManager(tmp_path)
        doc = Document("Hello")
        doc.name = "test-doc"
        doc.dirty = True
        fm.save(doc)
        assert doc.dirty is False

    def test_save_removes_autosave(self, tmp_path):
        fm = FileManager(tmp_path)
        doc = Document("Hello")
        doc.name = "test-doc"
        doc.dirty = True
        # Create an autosave file first
        autosave_path = tmp_path / "test-doc.autosave"
        autosave_path.write_text("old autosave")
        fm.save(doc)
        assert not autosave_path.exists()

    def test_save_overwrites_existing(self, tmp_path):
        fm = FileManager(tmp_path)
        doc = Document("Version 1")
        doc.name = "test-doc"
        doc.dirty = True
        fm.save(doc)
        doc.load("Version 2", "test-doc")
        doc.dirty = True
        fm.save(doc)
        assert (tmp_path / "test-doc.txt").read_text() == "Version 2"


class TestFileManagerLoad:
    def test_load_from_txt(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "my-doc.txt").write_text("Hello from file")
        doc = Document()
        fm.load("my-doc", doc)
        assert doc.text == "Hello from file"
        assert doc.name == "my-doc"
        assert doc.dirty is False

    def test_load_prefers_newer_autosave(self, tmp_path):
        fm = FileManager(tmp_path)
        txt_path = tmp_path / "my-doc.txt"
        txt_path.write_text("Old version")
        # Ensure autosave is newer
        time.sleep(0.05)
        autosave_path = tmp_path / "my-doc.autosave"
        autosave_path.write_text("Recovered version")
        doc = Document()
        fm.load("my-doc", doc)
        assert doc.text == "Recovered version"
        assert doc.dirty is True  # Marked dirty for recovery

    def test_load_prefers_txt_when_newer(self, tmp_path):
        fm = FileManager(tmp_path)
        autosave_path = tmp_path / "my-doc.autosave"
        autosave_path.write_text("Autosave version")
        time.sleep(0.05)
        txt_path = tmp_path / "my-doc.txt"
        txt_path.write_text("Saved version")
        doc = Document()
        fm.load("my-doc", doc)
        assert doc.text == "Saved version"
        assert doc.dirty is False

    def test_load_autosave_only(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "my-doc.autosave").write_text("Autosave only")
        doc = Document()
        fm.load("my-doc", doc)
        assert doc.text == "Autosave only"
        assert doc.dirty is True

    def test_load_missing_file(self, tmp_path):
        fm = FileManager(tmp_path)
        doc = Document("original")
        doc.name = "original"
        fm.load("nonexistent", doc)
        # Should not crash; doc keeps its original content
        # (load is only called if file exists in path or autosave)
        assert doc.name == "original"


class TestFileManagerAutosave:
    def test_force_autosave_creates_file(self, tmp_path):
        fm = FileManager(tmp_path)
        doc = Document("Auto content")
        doc.name = "test-doc"
        doc.dirty = True
        fm.force_autosave(doc)
        autosave_path = tmp_path / "test-doc.autosave"
        assert autosave_path.exists()
        assert autosave_path.read_text() == "Auto content"

    def test_force_autosave_skips_clean_doc(self, tmp_path):
        fm = FileManager(tmp_path)
        doc = Document("Clean content")
        doc.name = "test-doc"
        doc.dirty = False
        fm.force_autosave(doc)
        assert not (tmp_path / "test-doc.autosave").exists()

    def test_maybe_autosave_respects_interval(self, tmp_path):
        fm = FileManager(tmp_path, autosave_interval=9999)
        doc = Document("Content")
        doc.name = "test-doc"
        doc.dirty = True
        fm.maybe_autosave(doc)
        # Should not save because interval hasn't elapsed
        assert not (tmp_path / "test-doc.autosave").exists()

    def test_maybe_autosave_after_interval(self, tmp_path):
        fm = FileManager(tmp_path, autosave_interval=0)
        fm._last_autosave = 0  # Force interval to have elapsed
        doc = Document("Content")
        doc.name = "test-doc"
        doc.dirty = True
        fm.maybe_autosave(doc)
        assert (tmp_path / "test-doc.autosave").exists()

    def test_maybe_autosave_skips_clean(self, tmp_path):
        fm = FileManager(tmp_path, autosave_interval=0)
        fm._last_autosave = 0
        doc = Document("Content")
        doc.name = "test-doc"
        doc.dirty = False
        fm.maybe_autosave(doc)
        assert not (tmp_path / "test-doc.autosave").exists()


class TestFileManagerListDocuments:
    def test_list_txt_files(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "alpha.txt").write_text("a")
        (tmp_path / "beta.txt").write_text("b")
        docs = fm.list_documents()
        assert docs == ["alpha", "beta"]

    def test_list_md_files(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "notes.md").write_text("# Notes")
        docs = fm.list_documents()
        assert docs == ["notes"]

    def test_list_mixed_txt_and_md(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "alpha.txt").write_text("a")
        (tmp_path / "beta.md").write_text("b")
        docs = fm.list_documents()
        assert docs == ["alpha", "beta"]

    def test_list_ignores_autosave(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "doc.txt").write_text("a")
        (tmp_path / "doc.autosave").write_text("a")
        docs = fm.list_documents()
        assert docs == ["doc"]

    def test_list_empty_dir(self, tmp_path):
        fm = FileManager(tmp_path)
        assert fm.list_documents() == []

    def test_list_deduplicates_txt_and_md(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "same.txt").write_text("a")
        (tmp_path / "same.md").write_text("b")
        docs = fm.list_documents()
        assert docs == ["same"]


class TestFileManagerListEntries:
    def test_lists_files(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "alpha.txt").write_text("a")
        (tmp_path / "beta.txt").write_text("b")
        entries = fm.list_entries()
        assert entries == [("alpha", False), ("beta", False)]

    def test_lists_folders_first(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "notes.txt").write_text("a")
        (tmp_path / "projects").mkdir()
        entries = fm.list_entries()
        assert entries == [("projects", True), ("notes", False)]

    def test_skips_autosave_and_tmp(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "doc.txt").write_text("a")
        (tmp_path / "doc.autosave").write_text("a")
        (tmp_path / "doc.tmp").write_text("a")
        entries = fm.list_entries()
        assert entries == [("doc", False)]

    def test_skips_hidden(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / ".hidden.txt").write_text("a")
        (tmp_path / "visible.txt").write_text("a")
        entries = fm.list_entries()
        assert entries == [("visible", False)]

    def test_subfolder_listing(self, tmp_path):
        fm = FileManager(tmp_path)
        sub = tmp_path / "projects"
        sub.mkdir()
        (sub / "novel.txt").write_text("a")
        entries = fm.list_entries("projects")
        assert entries == [("novel", False)]

    def test_nonexistent_subfolder(self, tmp_path):
        fm = FileManager(tmp_path)
        assert fm.list_entries("nonexistent") == []


class TestFileManagerCreateFolder:
    def test_creates_folder(self, tmp_path):
        fm = FileManager(tmp_path)
        fm.create_folder("projects")
        assert (tmp_path / "projects").is_dir()

    def test_creates_nested_folder(self, tmp_path):
        fm = FileManager(tmp_path)
        fm.create_folder("projects/fiction")
        assert (tmp_path / "projects" / "fiction").is_dir()

    def test_idempotent(self, tmp_path):
        fm = FileManager(tmp_path)
        fm.create_folder("projects")
        fm.create_folder("projects")  # should not raise
        assert (tmp_path / "projects").is_dir()


class TestFileManagerRename:
    def test_renames_file(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "old.txt").write_text("content")
        fm.rename("old", "new")
        assert not (tmp_path / "old.txt").exists()
        assert (tmp_path / "new.txt").read_text() == "content"

    def test_renames_autosave_too(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "old.txt").write_text("content")
        (tmp_path / "old.autosave").write_text("autosave")
        fm.rename("old", "new")
        assert not (tmp_path / "old.autosave").exists()
        assert (tmp_path / "new.autosave").exists()

    def test_rename_into_subfolder(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "doc.txt").write_text("content")
        (tmp_path / "projects").mkdir()
        fm.rename("doc", "projects/doc")
        assert not (tmp_path / "doc.txt").exists()
        assert (tmp_path / "projects" / "doc.txt").read_text() == "content"

    def test_rename_creates_parent_dir(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "doc.txt").write_text("content")
        fm.rename("doc", "newdir/doc")
        assert (tmp_path / "newdir" / "doc.txt").exists()

    def test_rename_missing_file_does_not_raise(self, tmp_path):
        fm = FileManager(tmp_path)
        fm.rename("nonexistent", "new")  # should not raise


class TestFileManagerDelete:
    def test_deletes_file(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "doc.txt").write_text("content")
        fm.delete("doc")
        assert not (tmp_path / "doc.txt").exists()

    def test_deletes_autosave_too(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "doc.txt").write_text("content")
        (tmp_path / "doc.autosave").write_text("autosave")
        fm.delete("doc")
        assert not (tmp_path / "doc.txt").exists()
        assert not (tmp_path / "doc.autosave").exists()

    def test_delete_missing_file_does_not_raise(self, tmp_path):
        fm = FileManager(tmp_path)
        fm.delete("nonexistent")  # should not raise


class TestFileManagerMostRecent:
    def test_returns_none_when_empty(self, tmp_path):
        fm = FileManager(tmp_path)
        assert fm.most_recent_document() is None

    def test_returns_only_document(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "doc.txt").write_text("hello")
        assert fm.most_recent_document() == "doc"

    def test_returns_most_recently_modified(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "old.txt").write_text("old")
        time.sleep(0.05)
        (tmp_path / "new.txt").write_text("new")
        assert fm.most_recent_document() == "new"

    def test_finds_doc_in_subfolder(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "projects").mkdir()
        time.sleep(0.05)
        (tmp_path / "projects" / "novel.txt").write_text("content")
        assert fm.most_recent_document() == "projects/novel"

    def test_ignores_autosave(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "doc.autosave").write_text("autosave")
        assert fm.most_recent_document() is None


class TestFileManagerLastOpen:
    def test_returns_none_when_no_state(self, tmp_path):
        fm = FileManager(tmp_path)
        assert fm.load_last_open() is None

    def test_save_and_load(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "my-doc.txt").write_text("content")
        fm.save_last_open("my-doc")
        assert fm.load_last_open() == "my-doc"

    def test_returns_none_if_file_deleted(self, tmp_path):
        fm = FileManager(tmp_path)
        fm.save_last_open("gone")
        assert fm.load_last_open() is None

    def test_works_with_subfolder_doc(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "projects").mkdir()
        (tmp_path / "projects" / "novel.txt").write_text("content")
        fm.save_last_open("projects/novel")
        assert fm.load_last_open() == "projects/novel"


class TestFileManagerNewDocumentName:
    def test_returns_datetime_format(self, tmp_path):
        import re
        fm = FileManager(tmp_path)
        name = fm.new_document_name()
        assert re.match(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}", name)

    def test_avoids_collision(self, tmp_path):
        fm = FileManager(tmp_path)
        base = fm.new_document_name()
        (tmp_path / f"{base}.txt").write_text("")
        name2 = fm.new_document_name()
        assert name2 != base
        assert name2.startswith(base)

    def test_skips_multiple_collisions(self, tmp_path):
        fm = FileManager(tmp_path)
        base = fm.new_document_name()
        (tmp_path / f"{base}.txt").write_text("")
        (tmp_path / f"{base}-2.txt").write_text("")
        (tmp_path / f"{base}-3.txt").write_text("")
        name = fm.new_document_name()
        assert name == f"{base}-4"
