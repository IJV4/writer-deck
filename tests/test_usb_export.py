"""Tests for USB export utilities."""

from pathlib import Path

from writerdeck.utils.usb_export import export_documents


class TestExportDocuments:
    def test_export_copies_txt(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "hello.txt").write_text("Hello")
        (docs_dir / "world.txt").write_text("World")
        (docs_dir / "draft.autosave").write_text("draft")

        target = tmp_path / "usb"
        target.mkdir()

        count = export_documents(docs_dir, target)
        assert count == 2
        assert (target / "writer-deck" / "hello.txt").exists()
        assert (target / "writer-deck" / "world.txt").exists()
        # Autosave files should not be exported
        exported = list((target / "writer-deck").iterdir())
        assert len(exported) == 2

    def test_export_copies_md(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "notes.md").write_text("# Notes")

        target = tmp_path / "usb"
        target.mkdir()

        count = export_documents(docs_dir, target)
        assert count == 1
        assert (target / "writer-deck" / "notes.md").exists()

    def test_export_empty_dir(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        target = tmp_path / "usb"
        target.mkdir()

        count = export_documents(docs_dir, target)
        assert count == 0
