"""File picker overlay — folder-aware, arrow-navigated list of documents."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import RenderFrame
from writerdeck.modes.overlay import Overlay

_MOVE_HERE = "__move_here__"


class FilePickerOverlay(Overlay):
    def __init__(
        self,
        list_entries: Callable[..., list[tuple[str, bool]]],
        create_folder: Callable[[str], None],
        rename: Callable[[str, str], None],
        delete: Callable[[str], None],
    ) -> None:
        self._list_entries = list_entries
        self._create_folder = create_folder
        self._rename_cb = rename
        self._delete_cb = delete

        # Normal navigation state
        self._folder = ""
        self._selected = 0
        self._entries: list[tuple[str, bool]] = []

        # Current mode: normal | new_folder | rename | delete | move
        self._mode = "normal"

        # Text input shared by new_folder and rename modes
        self._text_input = ""

        # Target document path for rename / delete / move
        self._action_target = ""

        # Move mode: destination folder being browsed + its subfolder list
        self._move_dest = ""
        self._move_selected = 0
        self._move_folders: list[str] = []

        self._refresh_entries()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh_entries(self) -> None:
        self._entries = self._list_entries(self._folder, True)  # sorted by mtime
        max_idx = max(0, len(self._all_items()) - 1)
        self._selected = min(self._selected, max_idx)

    def _refresh_move_folders(self) -> None:
        all_entries = self._list_entries(self._move_dest, False)
        self._move_folders = [name for name, is_dir in all_entries if is_dir]
        self._move_selected = 0

    def _all_items(self) -> list[tuple[str, bool]]:
        items: list[tuple[str, bool]] = []
        if self._folder:
            items.append(("..", True))
        items.extend(self._entries)
        return items

    def _selected_item(self) -> tuple[str, bool] | None:
        items = self._all_items()
        if not items:
            return None
        return items[self._selected]

    def _doc_path_for(self, name: str) -> str:
        return f"{self._folder}/{name}" if self._folder else name

    def _go_up(self) -> None:
        parent = Path(self._folder).parent
        self._folder = "" if str(parent) == "." else str(parent)
        self._selected = 0
        self._refresh_entries()

    def _enter_folder(self, name: str) -> None:
        self._folder = f"{self._folder}/{name}" if self._folder else name
        self._selected = 0
        self._refresh_entries()

    # ------------------------------------------------------------------
    # Input dispatch
    # ------------------------------------------------------------------

    def handle_input(self, action: KeyAction, char: str) -> Any | None:
        if self._mode == "new_folder":
            return self._handle_new_folder(action, char)
        if self._mode == "rename":
            return self._handle_rename(action, char)
        if self._mode == "delete":
            return self._handle_delete(action, char)
        if self._mode == "move":
            return self._handle_move(action, char)
        return self._handle_normal(action, char)

    # ------------------------------------------------------------------
    # Normal mode
    # ------------------------------------------------------------------

    def _handle_normal(self, action: KeyAction, char: str) -> Any | None:
        items = self._all_items()

        if action == KeyAction.ESCAPE:
            return {}

        if action == KeyAction.ARROW_UP:
            self._selected = max(0, self._selected - 1)
            return None

        if action == KeyAction.ARROW_DOWN:
            self._selected = min(len(items) - 1, self._selected + 1)
            return None

        if action == KeyAction.ENTER:
            if not items:
                return {}
            name, is_dir = items[self._selected]
            if name == "..":
                self._go_up()
                return None
            if is_dir:
                self._enter_folder(name)
                return None
            return {"open_doc": self._doc_path_for(name)}

        if char in ("n", "N"):
            self._mode = "new_folder"
            self._text_input = ""
            return None

        # File-only actions (not folders, not "..")
        item = self._selected_item()
        if item and not item[1] and item[0] != "..":
            doc_path = self._doc_path_for(item[0])
            if char in ("r", "R"):
                self._mode = "rename"
                self._action_target = doc_path
                self._text_input = item[0]  # pre-fill with current stem
                return None
            if char in ("d", "D"):
                self._mode = "delete"
                self._action_target = doc_path
                return None
            if char in ("m", "M"):
                self._mode = "move"
                self._action_target = doc_path
                self._move_dest = self._folder
                self._refresh_move_folders()
                return None

        return None

    # ------------------------------------------------------------------
    # New folder mode
    # ------------------------------------------------------------------

    def _handle_new_folder(self, action: KeyAction, char: str) -> Any | None:
        if action == KeyAction.ESCAPE:
            self._mode = "normal"
            self._text_input = ""
            return None
        if action == KeyAction.ENTER:
            name = self._text_input.strip()
            if name:
                folder_path = f"{self._folder}/{name}" if self._folder else name
                self._create_folder(folder_path)
                self._refresh_entries()
            self._mode = "normal"
            self._text_input = ""
            return None
        if action == KeyAction.BACKSPACE:
            self._text_input = self._text_input[:-1]
            return None
        if char and char.isprintable():
            self._text_input += char
            return None
        return None

    # ------------------------------------------------------------------
    # Rename mode
    # ------------------------------------------------------------------

    def _handle_rename(self, action: KeyAction, char: str) -> Any | None:
        if action == KeyAction.ESCAPE:
            self._mode = "normal"
            self._text_input = ""
            return None
        if action == KeyAction.ENTER:
            new_stem = self._text_input.strip()
            if new_stem:
                old_name = self._action_target
                parent = str(Path(old_name).parent)
                new_name = f"{parent}/{new_stem}" if parent != "." else new_stem
                if new_name != old_name:
                    self._rename_cb(old_name, new_name)
                    self._mode = "normal"
                    self._text_input = ""
                    self._refresh_entries()
                    return {"renamed": {"from": old_name, "to": new_name}}
            self._mode = "normal"
            self._text_input = ""
            return None
        if action == KeyAction.BACKSPACE:
            self._text_input = self._text_input[:-1]
            return None
        if char and char.isprintable():
            self._text_input += char
            return None
        return None

    # ------------------------------------------------------------------
    # Delete confirm mode
    # ------------------------------------------------------------------

    def _handle_delete(self, action: KeyAction, char: str) -> Any | None:
        if action == KeyAction.ESCAPE or char in ("n", "N"):
            self._mode = "normal"
            return None
        if char in ("y", "Y"):
            name = self._action_target
            self._delete_cb(name)
            self._mode = "normal"
            self._refresh_entries()
            return {"deleted": name}
        return None

    # ------------------------------------------------------------------
    # Move mode
    # ------------------------------------------------------------------

    def _handle_move(self, action: KeyAction, char: str) -> Any | None:
        items = self._move_items()

        if action == KeyAction.ESCAPE:
            self._mode = "normal"
            return None

        if action == KeyAction.ARROW_UP:
            self._move_selected = max(0, self._move_selected - 1)
            return None

        if action == KeyAction.ARROW_DOWN:
            self._move_selected = min(len(items) - 1, self._move_selected + 1)
            return None

        if action == KeyAction.ENTER:
            if not items:
                return None
            name = items[self._move_selected]
            if name == _MOVE_HERE:
                source = self._action_target
                source_stem = Path(source).name
                new_name = f"{self._move_dest}/{source_stem}" if self._move_dest else source_stem
                self._mode = "normal"
                if new_name != source:
                    self._rename_cb(source, new_name)
                    self._refresh_entries()
                    return {"renamed": {"from": source, "to": new_name}}
                return None
            if name == "..":
                parent = Path(self._move_dest).parent
                self._move_dest = "" if str(parent) == "." else str(parent)
                self._refresh_move_folders()
                return None
            # Navigate into subfolder
            self._move_dest = f"{self._move_dest}/{name}" if self._move_dest else name
            self._refresh_move_folders()
            return None

        return None

    def _move_items(self) -> list[str]:
        items = [_MOVE_HERE]
        if self._move_dest:
            items.append("..")
        items.extend(self._move_folders)
        return items

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self, base_frame: RenderFrame) -> RenderFrame:
        if self._mode == "new_folder":
            lines = [
                "--- New Folder ---",
                "",
                f"Name: {self._text_input}_",
                "",
                "Enter to confirm, Esc to cancel",
            ]
        elif self._mode == "rename":
            lines = [
                f"--- Rename '{Path(self._action_target).name}' ---",
                "",
                f"New name: {self._text_input}_",
                "",
                "Enter to confirm, Esc to cancel",
            ]
        elif self._mode == "delete":
            lines = [
                "--- Delete Document ---",
                "",
                f"Delete '{Path(self._action_target).name}'?",
                "",
                "Y to confirm, Esc to cancel",
            ]
        elif self._mode == "move":
            dest_display = f"/{self._move_dest}" if self._move_dest else "/"
            lines = [
                f"--- Move '{Path(self._action_target).name}' ---",
                f"Destination: {dest_display}",
                "",
            ]
            for i, name in enumerate(self._move_items()):
                prefix = "> " if i == self._move_selected else "  "
                if name == _MOVE_HERE:
                    label = "[Move here]"
                elif name == "..":
                    label = "[..]"
                else:
                    label = f"[{name}]"
                lines.append(f"{prefix}{label}")
            lines.append("")
            lines.append("Enter: select  Esc: cancel")
        else:
            folder_display = f"/{self._folder}" if self._folder else "/"
            lines = [
                f"--- Open Document ({folder_display}) ---",
                "",
            ]
            items = self._all_items()
            if not items:
                lines.append("  (empty)")
            for i, (name, is_dir) in enumerate(items):
                prefix = "> " if i == self._selected else "  "
                label = f"[{name}]" if is_dir else name
                lines.append(f"{prefix}{label}")
            lines.append("")
            lines.append("Enter: open  N: folder  R: rename  D: delete  M: move  Esc: cancel")

        return RenderFrame(
            text_lines=lines,
            cursor_line=0,
            cursor_col=0,
            show_cursor=False,
            stats=None,
            force_full_refresh=True,
            margin_top=8,
            margin_bottom=8,
            margin_left=8,
        )
