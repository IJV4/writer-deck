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
        for user_dir in base_path.iterdir():
            if user_dir.is_dir():
                # Could be /media/USBDRIVE or /media/pi/USBDRIVE
                if user_dir.is_mount():
                    return user_dir
                for sub in user_dir.iterdir():
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
        for src in docs_dir.glob(pattern):
            if src.name.endswith(".autosave"):
                continue
            dst = export_dir / src.name
            shutil.copy2(str(src), str(dst))
            count += 1
    return count
