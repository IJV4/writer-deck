"""File manager — save/load .txt documents with autosave support."""

from __future__ import annotations

import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from writerdeck.core.document import Document

logger = logging.getLogger(__name__)

# Editable document extensions, in preference order. New documents default to
# the first (.txt, the native format); an existing .md is loaded and saved back
# in place rather than being read as empty and silently forked into a new .txt.
_DOC_SUFFIXES = (".txt", ".md")


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically via temp file + rename."""
    dir_fd = None
    fd = -1
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        os.write(fd, content.encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.rename(tmp_path, str(path))
        tmp_path = None
    except Exception:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


class FileManager:
    def __init__(
        self,
        documents_dir: Path,
        autosave_interval: int = 90,
        default_format: str = "txt",
    ) -> None:
        self._dir = documents_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._autosave_interval = autosave_interval
        # Extension (WITHOUT a leading dot) used for brand-new documents that
        # have no existing file and no remembered loaded suffix.
        self._default_suffix = "." + default_format.lstrip(".")
        self._last_autosave = time.monotonic()

    def _sanitize_name(self, name: str) -> Path:
        """Resolve a document name to a path constrained to the docs root.

        Document names may legitimately contain forward-slash subpaths (e.g.
        ``projects/novel``), but a typed absolute path or ``..`` traversal must
        not be able to escape ``self._dir`` — for save, autosave AND the
        recovery read path. Raises ``ValueError`` on any name that would resolve
        outside the documents root.

        Returns the (unresolved) ``self._dir / name`` join so callers get a path
        under the configured directory verbatim; only the traversal *check* uses
        ``resolve()`` so symlinked temp dirs don't change the returned path.
        """
        base = self._dir / name
        root = self._dir.resolve()
        resolved = base.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError(f"Document name escapes documents root: {name!r}")
        return base

    def save(self, doc: Document) -> Path:
        path = self._doc_save_path(doc)
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, doc.text)
        # Remember the suffix we just wrote so subsequent saves/autosaves stay
        # on it (a new .md doc must not fork into a .txt on its second save).
        doc.loaded_suffix = path.suffix
        # Remove autosave file on explicit save
        autosave_path = self._autosave_path(doc.name)
        if autosave_path.exists():
            autosave_path.unlink()
        doc.mark_saved()
        logger.info("Saved %s", path)
        return path

    def load(self, name: str, doc: Document) -> None:
        path = self._doc_path(name)
        autosave_path = self._autosave_path(name)
        # Remember the on-disk suffix so save()/autosave write back in place
        # (a .md stays .md) rather than forking into a new .txt. When only an
        # autosave exists, fall back to the resolved doc suffix.
        doc.loaded_suffix = path.suffix

        # Recovery: prefer autosave if it's newer
        if autosave_path.exists() and path.exists():
            if autosave_path.stat().st_mtime > path.stat().st_mtime:
                text = autosave_path.read_text(encoding="utf-8")
                doc.load(text, name)
                doc.dirty = True  # Mark dirty so user knows it's recovered
                logger.info("Recovered from autosave: %s", autosave_path)
                return

        if path.exists():
            text = path.read_text(encoding="utf-8")
            doc.load(text, name)
            logger.info("Loaded %s", path)
        elif autosave_path.exists():
            text = autosave_path.read_text(encoding="utf-8")
            doc.load(text, name)
            doc.dirty = True
            logger.info("Loaded from autosave: %s", autosave_path)

    def maybe_autosave(self, doc: Document) -> None:
        if not doc.dirty:
            return
        now = time.monotonic()
        if now - self._last_autosave < self._autosave_interval:
            return
        self._autosave(doc)
        self._last_autosave = now

    def force_autosave(self, doc: Document) -> None:
        if doc.dirty:
            self._autosave(doc)

    def list_documents(self) -> list[str]:
        stems: set[str] = set()
        for pattern in ("*.txt", "*.md"):
            for p in self._dir.glob(pattern):
                stems.add(p.stem)
        return sorted(stems)

    def list_entries(self, subfolder: str = "", sort_by_modified: bool = False) -> list[tuple[str, bool]]:
        """Return (name, is_dir) pairs in subfolder, folders first then files."""
        base = self._dir / subfolder if subfolder else self._dir
        if not base.exists():
            return []
        entries: list[tuple[str, bool, float]] = []
        try:
            for p in base.iterdir():
                if p.name.startswith("."):
                    continue
                mtime = p.stat().st_mtime
                if p.is_dir():
                    entries.append((p.name, True, mtime))
                elif p.suffix in (".txt", ".md") and not p.name.endswith(".autosave") and not p.name.endswith(".tmp"):
                    entries.append((p.stem, False, mtime))
        except PermissionError:
            pass
        if sort_by_modified:
            entries.sort(key=lambda x: (not x[1], -x[2]))
        else:
            entries.sort(key=lambda x: (not x[1], x[0].lower()))
        return [(name, is_dir) for name, is_dir, _ in entries]

    def create_folder(self, path: str) -> None:
        """Create a subfolder under the documents directory."""
        (self._dir / path).mkdir(parents=True, exist_ok=True)
        logger.info("Created folder %s", self._dir / path)

    def rename(self, old_name: str, new_name: str) -> None:
        """Rename a document (and its autosave if present), keeping its extension."""
        old_path = self._doc_path(old_name)
        # Keep the source file's extension (.txt or .md) on the target so a
        # renamed .md stays .md rather than being resurrected as a new .txt.
        new_path = self._doc_path(new_name).with_suffix(old_path.suffix)
        new_path.parent.mkdir(parents=True, exist_ok=True)
        if old_path.exists():
            old_path.rename(new_path)
        old_auto = self._autosave_path(old_name)
        new_auto = self._autosave_path(new_name)
        if old_auto.exists():
            old_auto.rename(new_auto)
        logger.info("Renamed %s -> %s", old_name, new_name)

    def delete(self, name: str) -> None:
        """Delete a document and its autosave file."""
        path = self._doc_path(name)
        if path.exists():
            path.unlink()
        auto = self._autosave_path(name)
        if auto.exists():
            auto.unlink()
        logger.info("Deleted %s", name)

    def most_recent_document(self) -> str | None:
        """Return the name of the most recently modified document."""
        best: str | None = None
        best_mtime = 0.0
        for p in self._dir.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in (".txt", ".md"):
                continue
            if p.name.startswith(".") or p.name.endswith(".tmp"):
                continue
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if mtime > best_mtime:
                best_mtime = mtime
                rel = p.relative_to(self._dir)
                parts = list(rel.parts)
                parts[-1] = Path(parts[-1]).stem
                best = "/".join(parts)
        return best

    def save_last_open(self, name: str) -> None:
        """Persist the name of the last opened document."""
        try:
            (self._dir / ".last_open").write_text(name, encoding="utf-8")
        except OSError:
            pass

    def load_last_open(self) -> str | None:
        """Return the last opened document name if the file still exists."""
        p = self._dir / ".last_open"
        if not p.exists():
            return None
        try:
            name = p.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not name:
            return None
        # Verify the document file still exists
        if self._doc_path(name).exists() or self._autosave_path(name).exists():
            return name
        return None

    def new_document_name(self) -> str:
        now = datetime.now()
        base = now.strftime("%Y-%m-%d_%H-%M")
        existing = set(self.list_documents())
        if base not in existing:
            return base
        for i in range(2, 10000):
            name = f"{base}-{i}"
            if name not in existing:
                return name
        return f"{base}-{int(time.time())}"

    def _autosave(self, doc: Document) -> None:
        path = self._autosave_path(doc.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, doc.text)
        logger.debug("Autosaved %s", path)

    def _doc_save_path(self, doc: Document) -> Path:
        """Resolve where ``doc`` should be written.

        Honours the suffix the document was loaded from (``doc.loaded_suffix``)
        so a ``.md`` is saved back in place rather than forked into a ``.txt``.
        A brand-new document — one with no existing on-disk file — uses the
        configured default format instead.
        """
        base = self._sanitize_name(doc.name)
        # If the document already lives on disk under some known suffix, keep
        # writing to the one it was loaded from.
        for suffix in _DOC_SUFFIXES:
            if Path(f"{base}{suffix}").exists():
                return Path(f"{base}{doc.loaded_suffix or _DOC_SUFFIXES[0]}")
        # Brand-new document: use the configured default format.
        return Path(f"{base}{self._default_suffix}")

    def _doc_path(self, name: str) -> Path:
        """Resolve a document name to its on-disk path.

        Probes the known suffixes and returns the first that exists, so a
        document that lives only as ``name.md`` is loaded and saved back to
        that ``.md`` file (rather than read as empty and forked into a new
        ``.txt``). Falls back to the configured default format for a brand-new
        document. Names are sanitized so a typed ``/`` or ``..`` cannot escape
        the documents root.
        """
        base = self._sanitize_name(name)
        for suffix in _DOC_SUFFIXES:
            candidate = Path(f"{base}{suffix}")
            if candidate.exists():
                return candidate
        return Path(f"{base}{self._default_suffix}")

    def _autosave_path(self, name: str) -> Path:
        return Path(f"{self._sanitize_name(name)}.autosave")
