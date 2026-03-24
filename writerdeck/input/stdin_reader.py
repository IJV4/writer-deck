"""Stdin fallback keyboard reader — for desktop development without evdev."""

from __future__ import annotations

import logging
import queue
import select
import sys
import threading
from typing import Callable

from writerdeck.input.keymapper import KeyAction

logger = logging.getLogger(__name__)

# ANSI escape sequence to KeyAction mapping
_ESCAPE_SEQUENCES: dict[str, KeyAction] = {
    "\x1b[A": KeyAction.ARROW_UP,
    "\x1b[B": KeyAction.ARROW_DOWN,
    "\x1b[C": KeyAction.ARROW_RIGHT,
    "\x1b[D": KeyAction.ARROW_LEFT,
    "\x1b[H": KeyAction.HOME,
    "\x1b[F": KeyAction.END,
    "\x1b[5~": KeyAction.PAGE_UP,
    "\x1b[6~": KeyAction.PAGE_DOWN,
    "\x1b[3~": KeyAction.DELETE,
    # Shift+arrow (selection)
    "\x1b[1;2A": KeyAction.SELECT_UP,
    "\x1b[1;2B": KeyAction.SELECT_DOWN,
    "\x1b[1;2C": KeyAction.SELECT_RIGHT,
    "\x1b[1;2D": KeyAction.SELECT_LEFT,
    "\x1b[1;2H": KeyAction.SELECT_HOME,
    "\x1b[1;2F": KeyAction.SELECT_END,
    # Ctrl+arrow (word movement)
    "\x1b[1;5C": KeyAction.WORD_RIGHT,
    "\x1b[1;5D": KeyAction.WORD_LEFT,
    # Ctrl+Shift+arrow (word selection)
    "\x1b[1;6C": KeyAction.SELECT_WORD_RIGHT,
    "\x1b[1;6D": KeyAction.SELECT_WORD_LEFT,
}

# Ctrl+key byte values
_CTRL_MAP: dict[int, KeyAction] = {
    1: KeyAction.SELECT_ALL,   # Ctrl+A
    5: KeyAction.EXPORT_USB,   # Ctrl+E
    6: KeyAction.FIND,         # Ctrl+F
    14: KeyAction.NEW_DOC,     # Ctrl+N
    15: KeyAction.OPEN_DOC,    # Ctrl+O
    17: KeyAction.QUIT,        # Ctrl+Q
    19: KeyAction.SAVE,        # Ctrl+S
    25: KeyAction.REDO,        # Ctrl+Y
    26: KeyAction.UNDO,        # Ctrl+Z
}


class StdinReader:
    """Reads keyboard input from stdin in raw mode. Same interface as KeyboardReader."""

    def __init__(
        self,
        action_queue: queue.SimpleQueue | None = None,
        on_any_key: Callable[[], None] | None = None,
    ) -> None:
        self.queue: queue.SimpleQueue[tuple[KeyAction, str]] = (
            action_queue or queue.SimpleQueue()
        )
        self._on_any_key = on_any_key
        self._thread: threading.Thread | None = None
        self._running = False
        self._old_settings = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._restore_terminal()

    def _restore_terminal(self) -> None:
        if self._old_settings is not None:
            try:
                import termios
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old_settings)
            except Exception:
                pass
            self._old_settings = None

    def _read_loop(self) -> None:
        try:
            import tty
            import termios
        except ImportError:
            logger.error("termios not available — stdin keyboard unavailable")
            return

        try:
            fd = sys.stdin.fileno()
        except (AttributeError, ValueError):
            logger.error("stdin is not a terminal")
            return

        self._old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while self._running:
                # Use select to avoid blocking forever
                if not select.select([sys.stdin], [], [], 0.1)[0]:
                    continue
                ch = sys.stdin.read(1)
                if not ch:
                    continue

                if self._on_any_key:
                    self._on_any_key()

                if ch == "\x1b":
                    # Possible escape sequence
                    action = self._read_escape_sequence(ch)
                    if action:
                        self.queue.put((action, ""))
                    else:
                        self.queue.put((KeyAction.ESCAPE, ""))
                elif ch == "\r" or ch == "\n":
                    self.queue.put((KeyAction.ENTER, ""))
                elif ch == "\x7f" or ch == "\x08":
                    self.queue.put((KeyAction.BACKSPACE, ""))
                elif ch == "\t":
                    self.queue.put((KeyAction.SWITCH_MODE_NEXT, ""))
                elif ord(ch) in _CTRL_MAP:
                    self.queue.put((_CTRL_MAP[ord(ch)], ""))
                elif ch.isprintable():
                    self.queue.put((KeyAction.CHAR, ch))
        finally:
            self._restore_terminal()

    def _read_escape_sequence(self, first: str) -> KeyAction | None:
        """Try to read a full ANSI escape sequence."""
        buf = first
        # Read more characters with short timeout
        for _ in range(8):
            if not select.select([sys.stdin], [], [], 0.05)[0]:
                break
            ch = sys.stdin.read(1)
            if not ch:
                break
            buf += ch
            if buf in _ESCAPE_SEQUENCES:
                return _ESCAPE_SEQUENCES[buf]
            # Tilde-terminated sequences
            if ch == "~":
                return _ESCAPE_SEQUENCES.get(buf)
            # Letter-terminated CSI sequences
            if ch.isalpha() and len(buf) >= 3:
                return _ESCAPE_SEQUENCES.get(buf)
        return _ESCAPE_SEQUENCES.get(buf)
