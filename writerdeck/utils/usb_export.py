"""USB export — copy documents to a mounted USB drive."""

from __future__ import annotations

import shutil
from pathlib import Path


def find_usb_mount() -> Path | None:
    """Find the first mounted USB drive under /media or /mnt."""
    for base in ("/media", "/mnt"):
        base_path = Path(base)
        if not base_path.exists():
            continue
        # Check subdirectories (e.g., /media/pi/USBDRIVE)
        try:
            user_dirs = list(base_path.iterdir())
        except (PermissionError, OSError):
            continue
        for user_dir in user_dirs:
            if user_dir.is_dir():
                # Could be /media/USBDRIVE or /media/pi/USBDRIVE
                if user_dir.is_mount():
                    return user_dir
                try:
                    subs = list(user_dir.iterdir())
                except (PermissionError, OSError):
                    continue
                for sub in subs:
                    if sub.is_dir() and sub.is_mount():
                        return sub
    return None


def export_documents(docs_dir: Path, target: Path) -> int:
    """Copy all .txt and .md files from docs_dir to target/writer-deck/.

    Returns the number of files copied.
    """
    export_dir = target / "writer-deck"
    export_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for pattern in ("*.txt", "*.md"):
        for src in docs_dir.rglob(pattern):
            if src.name.endswith(".autosave"):
                continue
            dst = export_dir / src.relative_to(docs_dir)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            count += 1
    return count
