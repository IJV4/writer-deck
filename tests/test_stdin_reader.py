"""Tests for StdinReader escape sequence mapping."""

from writerdeck.input.stdin_reader import _ESCAPE_SEQUENCES, _CTRL_MAP
from writerdeck.input.keymapper import KeyAction


class TestEscapeSequences:
    def test_arrow_keys_mapped(self):
        assert _ESCAPE_SEQUENCES["\x1b[A"] == KeyAction.ARROW_UP
        assert _ESCAPE_SEQUENCES["\x1b[B"] == KeyAction.ARROW_DOWN
        assert _ESCAPE_SEQUENCES["\x1b[C"] == KeyAction.ARROW_RIGHT
        assert _ESCAPE_SEQUENCES["\x1b[D"] == KeyAction.ARROW_LEFT

    def test_shift_arrows_mapped(self):
        assert _ESCAPE_SEQUENCES["\x1b[1;2A"] == KeyAction.SELECT_UP
        assert _ESCAPE_SEQUENCES["\x1b[1;2D"] == KeyAction.SELECT_LEFT

    def test_ctrl_arrows_mapped(self):
        assert _ESCAPE_SEQUENCES["\x1b[1;5C"] == KeyAction.WORD_RIGHT
        assert _ESCAPE_SEQUENCES["\x1b[1;5D"] == KeyAction.WORD_LEFT

    def test_page_keys(self):
        assert _ESCAPE_SEQUENCES["\x1b[5~"] == KeyAction.PAGE_UP
        assert _ESCAPE_SEQUENCES["\x1b[6~"] == KeyAction.PAGE_DOWN

    def test_home_end(self):
        assert _ESCAPE_SEQUENCES["\x1b[H"] == KeyAction.HOME
        assert _ESCAPE_SEQUENCES["\x1b[F"] == KeyAction.END


class TestCtrlMap:
    def test_save(self):
        assert _CTRL_MAP[19] == KeyAction.SAVE  # Ctrl+S

    def test_undo(self):
        assert _CTRL_MAP[26] == KeyAction.UNDO  # Ctrl+Z

    def test_redo(self):
        assert _CTRL_MAP[25] == KeyAction.REDO  # Ctrl+Y

    def test_find(self):
        assert _CTRL_MAP[6] == KeyAction.FIND  # Ctrl+F

    def test_select_all(self):
        assert _CTRL_MAP[1] == KeyAction.SELECT_ALL  # Ctrl+A
