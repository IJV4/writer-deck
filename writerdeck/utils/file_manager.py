"""File manager — save/load .txt documents with autosave support."""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from writerdeck.core.document import Document

logger = logging.getLogger(__name__)


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
    def __init__(self, documents_dir: Path, autosave_interval: int = 90) -> None:
        self._dir = documents_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._autosave_interval = autosave_interval
        self._last_autosave = time.monotonic()

    def save(self, doc: Document) -> Path:
        path = self._doc_path(doc.name)
        _atomic_write(path, doc.text)
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

    def new_document_name(self) -> str:
        existing = set(self.list_documents())
        for i in range(1, 10000):
            name = f"untitled-{i}"
            if name not in existing:
                return name
        return f"untitled-{int(time.time())}"

    def _autosave(self, doc: Document) -> None:
        path = self._autosave_path(doc.name)
        _atomic_write(path, doc.text)
        logger.debug("Autosaved %s", path)

    def _doc_path(self, name: str) -> Path:
        return self._dir / f"{name}.txt"

    def _autosave_path(self, name: str) -> Path:
        return self._dir / f"{name}.autosave"
