"""Tests for StdinReader escape sequence mapping."""

import select

from writerdeck.input.keymapper import KeyAction
from writerdeck.input.stdin_reader import _CTRL_MAP, _ESCAPE_SEQUENCES, StdinReader


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

    def test_ctrl_up_down_paginate(self):
        assert _ESCAPE_SEQUENCES["\x1b[1;5A"] == KeyAction.PAGE_PREV
        assert _ESCAPE_SEQUENCES["\x1b[1;5B"] == KeyAction.PAGE_NEXT

    def test_shift_tab_prev_mode(self):
        assert _ESCAPE_SEQUENCES["\x1b[Z"] == KeyAction.SWITCH_MODE_PREV

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


class TestEscapeLeftover:
    """The _read_escape_sequence contract: unrecognized sequences must return
    the consumed bytes as leftover so Alt+key keystrokes are not dropped."""

    def _feed(self, monkeypatch, chars):
        """Make sys.stdin.read / select return the given chars, then EOF."""
        seq = list(chars)

        def fake_select(rlist, wlist, xlist, timeout):
            return ([object()] if seq else [], [], [])

        def fake_read(_n):
            return seq.pop(0) if seq else ""

        monkeypatch.setattr(select, "select", fake_select)
        import writerdeck.input.stdin_reader as mod
        monkeypatch.setattr(mod.sys.stdin, "read", fake_read, raising=False)

    def test_recognized_sequence_no_leftover(self, monkeypatch):
        self._feed(monkeypatch, "[A")  # arrow up (after leading ESC)
        reader = StdinReader()
        action, leftover = reader._read_escape_sequence("\x1b")
        assert action == KeyAction.ARROW_UP
        assert leftover == ""

    def test_alt_f_returns_leftover_byte(self, monkeypatch):
        # Alt+F sends ESC then 'f' — an unrecognized sequence.
        self._feed(monkeypatch, "f")
        reader = StdinReader()
        action, leftover = reader._read_escape_sequence("\x1b")
        assert action is None
        assert "f" in leftover  # the 'f' must not be dropped

    def test_shift_tab_sequence_parsed(self, monkeypatch):
        # Shift+Tab sends ESC [ Z — a letter-terminated CSI sequence.
        self._feed(monkeypatch, "[Z")
        reader = StdinReader()
        action, leftover = reader._read_escape_sequence("\x1b")
        assert action == KeyAction.SWITCH_MODE_PREV
        assert leftover == ""

    def test_ctrl_up_sequence_parsed(self, monkeypatch):
        self._feed(monkeypatch, "[1;5A")
        reader = StdinReader()
        action, leftover = reader._read_escape_sequence("\x1b")
        assert action == KeyAction.PAGE_PREV
        assert leftover == ""

    def test_insert_key_dropped(self, monkeypatch):
        # Insert sends ESC [ 2 ~ — an unmapped tilde-terminated CSI sequence.
        # It must be consumed whole (no leftover) so "[2~" is never inserted.
        self._feed(monkeypatch, "[2~")
        reader = StdinReader()
        action, leftover = reader._read_escape_sequence("\x1b")
        assert action is None
        assert leftover == ""

    def test_fkey_csi_dropped(self, monkeypatch):
        # F5 sends ESC [ 15 ~ — an unmapped tilde-terminated CSI sequence.
        self._feed(monkeypatch, "[15~")
        reader = StdinReader()
        action, leftover = reader._read_escape_sequence("\x1b")
        assert action is None
        assert leftover == ""

    def test_fkey_ss3_dropped(self, monkeypatch):
        # F1 sends ESC O P — an unmapped letter-terminated SS3 sequence.
        self._feed(monkeypatch, "OP")
        reader = StdinReader()
        action, leftover = reader._read_escape_sequence("\x1b")
        assert action is None
        assert leftover == ""

    def test_unmapped_csi_letter_dropped(self, monkeypatch):
        # An arbitrary unmapped letter-terminated CSI (e.g. ESC [ G) drops.
        self._feed(monkeypatch, "[G")
        reader = StdinReader()
        action, leftover = reader._read_escape_sequence("\x1b")
        assert action is None
        assert leftover == ""

    def test_alt_letter_still_leaks_char(self, monkeypatch):
        # Regression guard: Alt+<letter> (ESC + letter) must still leak its
        # byte so the keystroke is not silently dropped.
        self._feed(monkeypatch, "a")
        reader = StdinReader()
        action, leftover = reader._read_escape_sequence("\x1b")
        assert action is None
        assert "a" in leftover

    def test_mapped_delete_still_works(self, monkeypatch):
        # Delete (ESC [ 3 ~) is mapped and must still resolve, not be dropped.
        self._feed(monkeypatch, "[3~")
        reader = StdinReader()
        action, leftover = reader._read_escape_sequence("\x1b")
        assert action == KeyAction.DELETE
        assert leftover == ""
