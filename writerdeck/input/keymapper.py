"""Keycode-to-KeyAction mapper."""

from __future__ import annotations

from enum import Enum, auto


class KeyAction(Enum):
    CHAR = auto()
    BACKSPACE = auto()
    DELETE = auto()
    ENTER = auto()
    ARROW_LEFT = auto()
    ARROW_RIGHT = auto()
    ARROW_UP = auto()
    ARROW_DOWN = auto()
    HOME = auto()
    END = auto()
    SAVE = auto()                # Ctrl+S
    SWITCH_MODE_NEXT = auto()    # Ctrl+Tab
    SWITCH_MODE_PREV = auto()    # Ctrl+Shift+Tab
    NEW_DOC = auto()             # Ctrl+N
    OPEN_DOC = auto()            # Ctrl+O
    QUIT = auto()                # Ctrl+Q

    # Phase 2: Undo/Redo
    UNDO = auto()                # Ctrl+Z
    REDO = auto()                # Ctrl+Shift+Z or Ctrl+Y

    # Phase 2: Word movement
    WORD_LEFT = auto()           # Ctrl+Left
    WORD_RIGHT = auto()          # Ctrl+Right
    DELETE_WORD_BACK = auto()    # Ctrl+Backspace

    # Phase 2: Page Up/Down
    PAGE_UP = auto()             # scancode 104
    PAGE_DOWN = auto()           # scancode 109

    # Pagination: Ctrl+Up / Ctrl+Down
    PAGE_PREV = auto()           # Ctrl+Up
    PAGE_NEXT = auto()           # Ctrl+Down

    # Phase 3: Selection
    SELECT_LEFT = auto()         # Shift+Left
    SELECT_RIGHT = auto()        # Shift+Right
    SELECT_UP = auto()           # Shift+Up
    SELECT_DOWN = auto()         # Shift+Down
    SELECT_WORD_LEFT = auto()    # Ctrl+Shift+Left
    SELECT_WORD_RIGHT = auto()   # Ctrl+Shift+Right
    SELECT_HOME = auto()         # Shift+Home
    SELECT_END = auto()          # Shift+End
    SELECT_ALL = auto()          # Ctrl+A

    # Phase 4/5: Overlays & Features
    ESCAPE = auto()              # scancode 1
    TAB = auto()                 # plain Tab (scancode 15, no modifier)
    FIND = auto()                # Ctrl+F
    FONT_MENU = auto()           # Ctrl+Shift+F
    EXPORT_USB = auto()          # Ctrl+E
    OUTLINE = auto()              # Ctrl+H — heading outline overlay
    INFO_OVERLAY = auto()         # Ctrl+I — stats/battery info overlay

    UNKNOWN = auto()


# evdev key constants (subset we care about)
_KEY_ESCAPE = 1
_KEY_BACKSPACE = 14
_KEY_TAB = 15
_KEY_ENTER = 28
_KEY_LEFTCTRL = 29
_KEY_RIGHTCTRL = 97
_KEY_LEFTSHIFT = 42
_KEY_RIGHTSHIFT = 54
_KEY_DELETE = 111
_KEY_HOME = 102
_KEY_END = 107
_KEY_UP = 103
_KEY_DOWN = 108
_KEY_LEFT = 105
_KEY_RIGHT = 106
_KEY_PAGEUP = 104
_KEY_PAGEDOWN = 109

_KEY_A = 30
_KEY_E = 18
_KEY_F = 33
_KEY_H = 35
_KEY_I = 23
_KEY_N = 49
_KEY_O = 24
_KEY_Q = 16
_KEY_S = 31
_KEY_Y = 21
_KEY_Z = 44

# Rough scancode-to-character mapping for standard US layout (printable keys)
_SCANCODE_TO_CHAR: dict[int, tuple[str, str]] = {
    2: ("1", "!"), 3: ("2", "@"), 4: ("3", "#"), 5: ("4", "$"),
    6: ("5", "%"), 7: ("6", "^"), 8: ("7", "&"), 9: ("8", "*"),
    10: ("9", "("), 11: ("0", ")"), 12: ("-", "_"), 13: ("=", "+"),
    16: ("q", "Q"), 17: ("w", "W"), 18: ("e", "E"), 19: ("r", "R"),
    20: ("t", "T"), 21: ("y", "Y"), 22: ("u", "U"), 23: ("i", "I"),
    24: ("o", "O"), 25: ("p", "P"), 26: ("[", "{"), 27: ("]", "}"),
    30: ("a", "A"), 31: ("s", "S"), 32: ("d", "D"), 33: ("f", "F"),
    34: ("g", "G"), 35: ("h", "H"), 36: ("j", "J"), 37: ("k", "K"),
    38: ("l", "L"), 39: (";", ":"), 40: ("'", '"'), 41: ("`", "~"),
    43: ("\\", "|"),
    44: ("z", "Z"), 45: ("x", "X"), 46: ("c", "C"), 47: ("v", "V"),
    48: ("b", "B"), 49: ("n", "N"), 50: ("m", "M"), 51: (",", "<"),
    52: (".", ">"), 53: ("/", "?"),
    57: (" ", " "),  # space
}


class KeyMapper:
    def __init__(self) -> None:
        self._ctrl_held = False
        self._shift_held = False

    def reset(self) -> None:
        """Clear all latched modifier state.

        Called when the input source loses track of key releases (evdev
        disconnect, pygame focus loss) so a modifier held at that moment does
        not stay "stuck" latched after the source recovers.
        """
        self._ctrl_held = False
        self._shift_held = False

    def process_event(self, scancode: int, value: int) -> tuple[KeyAction, str]:
        """Process a raw evdev key event.

        Args:
            scancode: evdev event code (e.g. KEY_A = 30)
            value: 0=release, 1=press, 2=repeat

        Returns:
            (KeyAction, character) — character is non-empty only for CHAR actions.
        """
        # Track modifier state
        if scancode in (_KEY_LEFTCTRL, _KEY_RIGHTCTRL):
            self._ctrl_held = value != 0
            return KeyAction.UNKNOWN, ""
        if scancode in (_KEY_LEFTSHIFT, _KEY_RIGHTSHIFT):
            self._shift_held = value != 0
            return KeyAction.UNKNOWN, ""

        # Only act on press and repeat (not release)
        if value == 0:
            return KeyAction.UNKNOWN, ""

        # Escape (always available)
        if scancode == _KEY_ESCAPE:
            return KeyAction.ESCAPE, ""

        # Page Up / Page Down (no modifiers needed)
        if scancode == _KEY_PAGEUP:
            return KeyAction.PAGE_UP, ""
        if scancode == _KEY_PAGEDOWN:
            return KeyAction.PAGE_DOWN, ""

        # Ctrl combos
        if self._ctrl_held:
            if self._shift_held:
                # Ctrl+Shift combos
                if scancode == _KEY_TAB:
                    return KeyAction.SWITCH_MODE_PREV, ""
                if scancode == _KEY_Z:
                    return KeyAction.REDO, ""
                if scancode == _KEY_LEFT:
                    return KeyAction.SELECT_WORD_LEFT, ""
                if scancode == _KEY_RIGHT:
                    return KeyAction.SELECT_WORD_RIGHT, ""
                if scancode == _KEY_F:
                    return KeyAction.FONT_MENU, ""
                return KeyAction.UNKNOWN, ""
            # Ctrl-only combos
            if scancode == _KEY_S:
                return KeyAction.SAVE, ""
            if scancode == _KEY_TAB:
                return KeyAction.SWITCH_MODE_NEXT, ""
            if scancode == _KEY_N:
                return KeyAction.NEW_DOC, ""
            if scancode == _KEY_O:
                return KeyAction.OPEN_DOC, ""
            if scancode == _KEY_Q:
                return KeyAction.QUIT, ""
            if scancode == _KEY_Z:
                return KeyAction.UNDO, ""
            if scancode == _KEY_Y:
                return KeyAction.REDO, ""
            if scancode == _KEY_LEFT:
                return KeyAction.WORD_LEFT, ""
            if scancode == _KEY_RIGHT:
                return KeyAction.WORD_RIGHT, ""
            if scancode == _KEY_UP:
                return KeyAction.PAGE_PREV, ""
            if scancode == _KEY_DOWN:
                return KeyAction.PAGE_NEXT, ""
            if scancode == _KEY_BACKSPACE:
                return KeyAction.DELETE_WORD_BACK, ""
            if scancode == _KEY_A:
                return KeyAction.SELECT_ALL, ""
            if scancode == _KEY_F:
                return KeyAction.FIND, ""
            if scancode == _KEY_E:
                return KeyAction.EXPORT_USB, ""
            if scancode == _KEY_H:
                return KeyAction.OUTLINE, ""
            if scancode == _KEY_I:
                return KeyAction.INFO_OVERLAY, ""
            return KeyAction.UNKNOWN, ""

        # Shift + navigation = selection
        if self._shift_held:
            if scancode == _KEY_LEFT:
                return KeyAction.SELECT_LEFT, ""
            if scancode == _KEY_RIGHT:
                return KeyAction.SELECT_RIGHT, ""
            if scancode == _KEY_UP:
                return KeyAction.SELECT_UP, ""
            if scancode == _KEY_DOWN:
                return KeyAction.SELECT_DOWN, ""
            if scancode == _KEY_HOME:
                return KeyAction.SELECT_HOME, ""
            if scancode == _KEY_END:
                return KeyAction.SELECT_END, ""

        # Special keys
        if scancode == _KEY_TAB:
            return KeyAction.TAB, ""
        if scancode == _KEY_BACKSPACE:
            return KeyAction.BACKSPACE, ""
        if scancode == _KEY_DELETE:
            return KeyAction.DELETE, ""
        if scancode == _KEY_ENTER:
            return KeyAction.ENTER, ""
        if scancode == _KEY_LEFT:
            return KeyAction.ARROW_LEFT, ""
        if scancode == _KEY_RIGHT:
            return KeyAction.ARROW_RIGHT, ""
        if scancode == _KEY_UP:
            return KeyAction.ARROW_UP, ""
        if scancode == _KEY_DOWN:
            return KeyAction.ARROW_DOWN, ""
        if scancode == _KEY_HOME:
            return KeyAction.HOME, ""
        if scancode == _KEY_END:
            return KeyAction.END, ""

        # Printable characters
        if scancode in _SCANCODE_TO_CHAR:
            normal, shifted = _SCANCODE_TO_CHAR[scancode]
            char = shifted if self._shift_held else normal
            return KeyAction.CHAR, char

        return KeyAction.UNKNOWN, ""
