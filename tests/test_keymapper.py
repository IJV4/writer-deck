"""Comprehensive tests for KeyMapper — all key combos and edge cases."""

from __future__ import annotations

from writerdeck.input.keymapper import KeyAction, KeyMapper


class TestModifierTracking:
    def test_ctrl_press_release(self):
        m = KeyMapper()
        m.process_event(29, 1)  # Ctrl press
        assert m._ctrl_held is True
        m.process_event(29, 0)  # Ctrl release
        assert m._ctrl_held is False

    def test_right_ctrl(self):
        m = KeyMapper()
        m.process_event(97, 1)  # Right Ctrl press
        assert m._ctrl_held is True
        m.process_event(97, 0)
        assert m._ctrl_held is False

    def test_shift_press_release(self):
        m = KeyMapper()
        m.process_event(42, 1)  # Left Shift press
        assert m._shift_held is True
        m.process_event(42, 0)
        assert m._shift_held is False

    def test_right_shift(self):
        m = KeyMapper()
        m.process_event(54, 1)  # Right Shift press
        assert m._shift_held is True
        m.process_event(54, 0)
        assert m._shift_held is False

    def test_modifier_returns_unknown(self):
        m = KeyMapper()
        action, char = m.process_event(29, 1)
        assert action == KeyAction.UNKNOWN

    def test_reset_clears_held_modifiers(self):
        m = KeyMapper()
        m.process_event(29, 1)  # Ctrl press
        m.process_event(42, 1)  # Shift press
        assert m._ctrl_held is True
        assert m._shift_held is True
        m.reset()
        assert m._ctrl_held is False
        assert m._shift_held is False

    def test_reset_then_plain_key(self):
        m = KeyMapper()
        m.process_event(29, 1)  # Ctrl press (would latch)
        m.reset()
        # After reset, 's' should be a plain char, not SAVE
        action, char = m.process_event(31, 1)
        assert action == KeyAction.CHAR
        assert char == "s"

    def test_release_returns_unknown(self):
        m = KeyMapper()
        action, char = m.process_event(30, 0)  # 'a' release
        assert action == KeyAction.UNKNOWN


class TestKeyRepeat:
    def test_repeat_acts_like_press(self):
        m = KeyMapper()
        action, char = m.process_event(30, 2)  # 'a' repeat
        assert action == KeyAction.CHAR
        assert char == "a"

    def test_ctrl_combo_on_repeat(self):
        m = KeyMapper()
        m.process_event(29, 1)  # Ctrl
        action, _ = m.process_event(31, 2)  # S repeat
        assert action == KeyAction.SAVE


class TestCtrlCombos:
    def test_ctrl_s_save(self):
        m = KeyMapper()
        m.process_event(29, 1)
        action, _ = m.process_event(31, 1)
        assert action == KeyAction.SAVE

    def test_ctrl_tab_switch_mode_next(self):
        m = KeyMapper()
        m.process_event(29, 1)
        action, _ = m.process_event(15, 1)  # Tab
        assert action == KeyAction.SWITCH_MODE_NEXT

    def test_ctrl_shift_tab_switch_mode_prev(self):
        m = KeyMapper()
        m.process_event(29, 1)  # Ctrl
        m.process_event(42, 1)  # Shift
        action, _ = m.process_event(15, 1)  # Tab
        assert action == KeyAction.SWITCH_MODE_PREV

    def test_ctrl_n_new_doc(self):
        m = KeyMapper()
        m.process_event(29, 1)
        action, _ = m.process_event(49, 1)
        assert action == KeyAction.NEW_DOC

    def test_ctrl_o_open_doc(self):
        m = KeyMapper()
        m.process_event(29, 1)
        action, _ = m.process_event(24, 1)
        assert action == KeyAction.OPEN_DOC

    def test_ctrl_q_quit(self):
        m = KeyMapper()
        m.process_event(29, 1)
        action, _ = m.process_event(16, 1)
        assert action == KeyAction.QUIT

    def test_ctrl_z_undo(self):
        m = KeyMapper()
        m.process_event(29, 1)
        action, _ = m.process_event(44, 1)
        assert action == KeyAction.UNDO

    def test_ctrl_y_redo(self):
        m = KeyMapper()
        m.process_event(29, 1)
        action, _ = m.process_event(21, 1)
        assert action == KeyAction.REDO

    def test_ctrl_shift_z_redo(self):
        m = KeyMapper()
        m.process_event(29, 1)
        m.process_event(42, 1)
        action, _ = m.process_event(44, 1)
        assert action == KeyAction.REDO

    def test_ctrl_left_word_left(self):
        m = KeyMapper()
        m.process_event(29, 1)
        action, _ = m.process_event(105, 1)
        assert action == KeyAction.WORD_LEFT

    def test_ctrl_right_word_right(self):
        m = KeyMapper()
        m.process_event(29, 1)
        action, _ = m.process_event(106, 1)
        assert action == KeyAction.WORD_RIGHT

    def test_ctrl_backspace_delete_word_back(self):
        m = KeyMapper()
        m.process_event(29, 1)
        action, _ = m.process_event(14, 1)
        assert action == KeyAction.DELETE_WORD_BACK

    def test_ctrl_a_select_all(self):
        m = KeyMapper()
        m.process_event(29, 1)
        action, _ = m.process_event(30, 1)
        assert action == KeyAction.SELECT_ALL

    def test_ctrl_f_find(self):
        m = KeyMapper()
        m.process_event(29, 1)
        action, _ = m.process_event(33, 1)
        assert action == KeyAction.FIND

    def test_ctrl_e_export(self):
        m = KeyMapper()
        m.process_event(29, 1)
        action, _ = m.process_event(18, 1)
        assert action == KeyAction.EXPORT_USB

    def test_ctrl_shift_f_font_menu(self):
        m = KeyMapper()
        m.process_event(29, 1)
        m.process_event(42, 1)
        action, _ = m.process_event(33, 1)
        assert action == KeyAction.FONT_MENU

    def test_ctrl_shift_up_home(self):
        # No physical Home key on this keyboard; Ctrl+Up is already Page
        # Prev, so Home is remapped to Ctrl+Shift+Up.
        m = KeyMapper()
        m.process_event(29, 1)
        m.process_event(42, 1)
        action, _ = m.process_event(103, 1)
        assert action == KeyAction.HOME

    def test_ctrl_shift_down_end(self):
        m = KeyMapper()
        m.process_event(29, 1)
        m.process_event(42, 1)
        action, _ = m.process_event(108, 1)
        assert action == KeyAction.END

    def test_ctrl_unknown_key_returns_unknown(self):
        m = KeyMapper()
        m.process_event(29, 1)
        action, _ = m.process_event(2, 1)  # '1' key
        assert action == KeyAction.UNKNOWN

    def test_ctrl_shift_unknown_returns_unknown(self):
        m = KeyMapper()
        m.process_event(29, 1)
        m.process_event(42, 1)
        action, _ = m.process_event(2, 1)  # '1' key
        assert action == KeyAction.UNKNOWN


class TestShiftSelection:
    def test_shift_left(self):
        m = KeyMapper()
        m.process_event(42, 1)
        action, _ = m.process_event(105, 1)
        assert action == KeyAction.SELECT_LEFT

    def test_shift_right(self):
        m = KeyMapper()
        m.process_event(42, 1)
        action, _ = m.process_event(106, 1)
        assert action == KeyAction.SELECT_RIGHT

    def test_shift_up(self):
        m = KeyMapper()
        m.process_event(42, 1)
        action, _ = m.process_event(103, 1)
        assert action == KeyAction.SELECT_UP

    def test_shift_down(self):
        m = KeyMapper()
        m.process_event(42, 1)
        action, _ = m.process_event(108, 1)
        assert action == KeyAction.SELECT_DOWN

    def test_shift_home(self):
        m = KeyMapper()
        m.process_event(42, 1)
        action, _ = m.process_event(102, 1)
        assert action == KeyAction.SELECT_HOME

    def test_shift_end(self):
        m = KeyMapper()
        m.process_event(42, 1)
        action, _ = m.process_event(107, 1)
        assert action == KeyAction.SELECT_END

    def test_ctrl_shift_left_select_word_left(self):
        m = KeyMapper()
        m.process_event(29, 1)
        m.process_event(42, 1)
        action, _ = m.process_event(105, 1)
        assert action == KeyAction.SELECT_WORD_LEFT

    def test_ctrl_shift_right_select_word_right(self):
        m = KeyMapper()
        m.process_event(29, 1)
        m.process_event(42, 1)
        action, _ = m.process_event(106, 1)
        assert action == KeyAction.SELECT_WORD_RIGHT


class TestSpecialKeys:
    def test_escape(self):
        m = KeyMapper()
        action, _ = m.process_event(1, 1)
        assert action == KeyAction.ESCAPE

    def test_plain_tab(self):
        m = KeyMapper()
        action, _ = m.process_event(15, 1)  # Tab, no modifiers
        assert action == KeyAction.TAB

    def test_plain_tab_not_switch_mode(self):
        """Plain Tab must not be mistaken for the Ctrl+Tab mode-cycle action."""
        m = KeyMapper()
        action, _ = m.process_event(15, 1)
        assert action != KeyAction.SWITCH_MODE_NEXT

    def test_page_up(self):
        m = KeyMapper()
        action, _ = m.process_event(104, 1)
        assert action == KeyAction.PAGE_UP

    def test_page_down(self):
        m = KeyMapper()
        action, _ = m.process_event(109, 1)
        assert action == KeyAction.PAGE_DOWN

    def test_backspace(self):
        m = KeyMapper()
        action, _ = m.process_event(14, 1)
        assert action == KeyAction.BACKSPACE

    def test_delete(self):
        m = KeyMapper()
        action, _ = m.process_event(111, 1)
        assert action == KeyAction.DELETE

    def test_enter(self):
        m = KeyMapper()
        action, _ = m.process_event(28, 1)
        assert action == KeyAction.ENTER

    def test_arrow_left(self):
        m = KeyMapper()
        action, _ = m.process_event(105, 1)
        assert action == KeyAction.ARROW_LEFT

    def test_arrow_right(self):
        m = KeyMapper()
        action, _ = m.process_event(106, 1)
        assert action == KeyAction.ARROW_RIGHT

    def test_arrow_up(self):
        m = KeyMapper()
        action, _ = m.process_event(103, 1)
        assert action == KeyAction.ARROW_UP

    def test_arrow_down(self):
        m = KeyMapper()
        action, _ = m.process_event(108, 1)
        assert action == KeyAction.ARROW_DOWN

    def test_home(self):
        m = KeyMapper()
        action, _ = m.process_event(102, 1)
        assert action == KeyAction.HOME

    def test_end(self):
        m = KeyMapper()
        action, _ = m.process_event(107, 1)
        assert action == KeyAction.END

    def test_unknown_scancode(self):
        m = KeyMapper()
        action, _ = m.process_event(999, 1)
        assert action == KeyAction.UNKNOWN


class TestPrintableChars:
    def test_lowercase_a(self):
        m = KeyMapper()
        action, char = m.process_event(30, 1)
        assert action == KeyAction.CHAR
        assert char == "a"

    def test_uppercase_a(self):
        m = KeyMapper()
        m.process_event(42, 1)  # Shift
        action, char = m.process_event(30, 1)
        assert action == KeyAction.CHAR
        assert char == "A"

    def test_space(self):
        m = KeyMapper()
        action, char = m.process_event(57, 1)
        assert action == KeyAction.CHAR
        assert char == " "

    def test_number_1(self):
        m = KeyMapper()
        action, char = m.process_event(2, 1)
        assert action == KeyAction.CHAR
        assert char == "1"

    def test_shift_number_1_exclaim(self):
        m = KeyMapper()
        m.process_event(42, 1)
        action, char = m.process_event(2, 1)
        assert action == KeyAction.CHAR
        assert char == "!"

    def test_semicolon(self):
        m = KeyMapper()
        action, char = m.process_event(39, 1)
        assert action == KeyAction.CHAR
        assert char == ";"

    def test_shift_semicolon_colon(self):
        m = KeyMapper()
        m.process_event(42, 1)
        action, char = m.process_event(39, 1)
        assert action == KeyAction.CHAR
        assert char == ":"

    def test_all_letter_scancodes(self):
        """Verify all letter keys (q-p, a-l, z-m) produce correct chars."""
        m = KeyMapper()
        letter_map = {
            16: "q", 17: "w", 18: "e", 19: "r", 20: "t",
            21: "y", 22: "u", 23: "i", 24: "o", 25: "p",
            30: "a", 31: "s", 32: "d", 33: "f", 34: "g",
            35: "h", 36: "j", 37: "k", 38: "l",
            44: "z", 45: "x", 46: "c", 47: "v",
            48: "b", 49: "n", 50: "m",
        }
        for scancode, expected_char in letter_map.items():
            action, char = m.process_event(scancode, 1)
            assert action == KeyAction.CHAR, f"scancode {scancode}"
            assert char == expected_char, f"scancode {scancode}: expected {expected_char!r}, got {char!r}"

    def test_all_symbol_scancodes(self):
        """Verify punctuation/symbol keys."""
        m = KeyMapper()
        symbol_map = {
            12: ("-", "_"), 13: ("=", "+"),
            26: ("[", "{"), 27: ("]", "}"),
            39: (";", ":"), 40: ("'", '"'), 41: ("`", "~"),
            43: ("\\", "|"),
            51: (",", "<"), 52: (".", ">"), 53: ("/", "?"),
        }
        for scancode, (normal, shifted) in symbol_map.items():
            m._shift_held = False
            action, char = m.process_event(scancode, 1)
            assert char == normal, f"scancode {scancode} normal"
            m._shift_held = True
            action, char = m.process_event(scancode, 1)
            assert char == shifted, f"scancode {scancode} shifted"
        m._shift_held = False
