"""Tests for USB export utilities."""

from pathlib import Path

from writerdeck.utils.usb_export import export_documents, find_usb_mount


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

    def test_export_includes_subfolders(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "top.txt").write_text("top")
        sub = docs_dir / "novel"
        sub.mkdir()
        (sub / "chapter1.md").write_text("# Chapter 1")
        (sub / "notes.txt").write_text("notes")

        target = tmp_path / "usb"
        target.mkdir()

        count = export_documents(docs_dir, target)
        assert count == 3
        export_dir = target / "writer-deck"
        # Relative subpaths are preserved on the target.
        assert (export_dir / "top.txt").exists()
        assert (export_dir / "novel" / "chapter1.md").exists()
        assert (export_dir / "novel" / "notes.txt").exists()

    def test_export_no_collision_same_name_different_folders(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        folder_a = docs_dir / "a"
        folder_b = docs_dir / "b"
        folder_a.mkdir()
        folder_b.mkdir()
        (folder_a / "draft.txt").write_text("from a")
        (folder_b / "draft.txt").write_text("from b")

        target = tmp_path / "usb"
        target.mkdir()

        count = export_documents(docs_dir, target)
        assert count == 2
        export_dir = target / "writer-deck"
        # Same-named files in different folders do not overwrite each other.
        assert (export_dir / "a" / "draft.txt").read_text() == "from a"
        assert (export_dir / "b" / "draft.txt").read_text() == "from b"


class TestFindUsbMount:
    def test_permission_error_on_base_is_skipped(self, tmp_path, monkeypatch):
        # Both base dirs exist but iterdir raises PermissionError; must not propagate.
        media = tmp_path / "media"
        mnt = tmp_path / "mnt"
        media.mkdir()
        mnt.mkdir()

        def fake_iterdir(self):
            raise PermissionError("permission denied")

        monkeypatch.setattr(Path, "iterdir", fake_iterdir)
        monkeypatch.setattr(
            "writerdeck.utils.usb_export.Path",
            _PathFactory({"/media": media, "/mnt": mnt}),
        )

        # PermissionError on the base dir is swallowed, returning None.
        assert find_usb_mount() is None

    def test_permission_error_on_subdir_is_skipped(self, tmp_path, monkeypatch):
        # A 0700-style dir (e.g. /media/root) raises on iterdir; skip, not raise.
        media = tmp_path / "media"
        mnt = tmp_path / "mnt"
        media.mkdir()
        mnt.mkdir()
        root_dir = media / "root"
        root_dir.mkdir()

        real_iterdir = Path.iterdir

        def fake_iterdir(self):
            if self == root_dir:
                raise PermissionError("permission denied")
            return real_iterdir(self)

        monkeypatch.setattr(Path, "iterdir", fake_iterdir)
        # Nothing is a real mount point in the tmp tree.
        monkeypatch.setattr(Path, "is_mount", lambda self: False)
        monkeypatch.setattr(
            "writerdeck.utils.usb_export.Path",
            _PathFactory({"/media": media, "/mnt": mnt}),
        )

        # The unreadable subdir is skipped rather than raising.
        assert find_usb_mount() is None


class _PathFactory:
    """Redirects the module's ``Path("/media")`` / ``Path("/mnt")`` lookups.

    ``find_usb_mount`` hard-codes ``/media`` and ``/mnt``; this maps those to
    tmp_path dirs while leaving all other ``Path(...)`` construction untouched.
    """

    def __init__(self, mapping):
        self._mapping = mapping

    def __call__(self, arg):
        mapped = self._mapping.get(str(arg))
        return mapped if mapped is not None else Path(str(arg))
