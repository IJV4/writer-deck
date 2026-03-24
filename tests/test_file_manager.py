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


class TestFileManagerNewDocumentName:
    def test_first_untitled(self, tmp_path):
        fm = FileManager(tmp_path)
        assert fm.new_document_name() == "untitled-1"

    def test_skips_existing(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "untitled-1.txt").write_text("")
        assert fm.new_document_name() == "untitled-2"

    def test_skips_multiple_existing(self, tmp_path):
        fm = FileManager(tmp_path)
        (tmp_path / "untitled-1.txt").write_text("")
        (tmp_path / "untitled-2.txt").write_text("")
        (tmp_path / "untitled-3.txt").write_text("")
        assert fm.new_document_name() == "untitled-4"
