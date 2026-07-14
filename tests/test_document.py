"""Tests for Document text buffer and cursor model."""


from writerdeck.core.document import Document, Selection


class TestInsert:
    def test_insert_char(self):
        doc = Document()
        doc.insert("H")
        doc.insert("i")
        assert doc.text == "Hi"
        assert doc.cursor_col == 2
        assert doc.dirty is True

    def test_insert_newline(self):
        doc = Document("Hello")
        doc.cursor_col = 5
        doc.insert("\n")
        assert doc.lines == ["Hello", ""]
        assert doc.cursor_line == 1
        assert doc.cursor_col == 0

    def test_insert_mid_line(self):
        doc = Document("Hllo")
        doc.cursor_col = 1
        doc.insert("e")
        assert doc.text == "Hello"
        assert doc.cursor_col == 2


class TestDelete:
    def test_delete_backward(self):
        doc = Document("Hi")
        doc.cursor_col = 2
        doc.delete_backward()
        assert doc.text == "H"
        assert doc.cursor_col == 1

    def test_delete_backward_at_start_of_line(self):
        doc = Document("Hello\nWorld")
        doc.cursor_line = 1
        doc.cursor_col = 0
        doc.delete_backward()
        assert doc.text == "HelloWorld"
        assert doc.cursor_line == 0
        assert doc.cursor_col == 5

    def test_delete_backward_at_doc_start(self):
        doc = Document("Hi")
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.delete_backward()
        assert doc.text == "Hi"

    def test_delete_forward(self):
        doc = Document("Hi")
        doc.cursor_col = 0
        doc.delete_forward()
        assert doc.text == "i"

    def test_delete_forward_joins_lines(self):
        doc = Document("Hello\nWorld")
        doc.cursor_line = 0
        doc.cursor_col = 5
        doc.delete_forward()
        assert doc.text == "HelloWorld"

    def test_delete_forward_at_end_of_doc(self):
        doc = Document("Hi")
        doc.cursor_col = 2
        doc.delete_forward()
        assert doc.text == "Hi"  # no change

    def test_delete_backward_with_selection_deletes_selection(self):
        doc = Document("Hello World")
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.select_all()
        doc.delete_backward()
        assert doc.text == ""

    def test_delete_forward_with_selection_deletes_selection(self):
        doc = Document("Hello World")
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.select_all()
        doc.delete_forward()
        assert doc.text == ""


class TestCursorMovement:
    def test_move_left(self):
        doc = Document("Hi")
        doc.cursor_col = 2
        doc.move_left()
        assert doc.cursor_col == 1

    def test_move_left_wraps_up(self):
        doc = Document("AB\nCD")
        doc.cursor_line = 1
        doc.cursor_col = 0
        doc.move_left()
        assert doc.cursor_line == 0
        assert doc.cursor_col == 2

    def test_move_left_at_doc_start(self):
        doc = Document("Hi")
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.move_left()
        assert doc.cursor_line == 0
        assert doc.cursor_col == 0

    def test_move_right_wraps_down(self):
        doc = Document("AB\nCD")
        doc.cursor_line = 0
        doc.cursor_col = 2
        doc.move_right()
        assert doc.cursor_line == 1
        assert doc.cursor_col == 0

    def test_move_right_at_doc_end(self):
        doc = Document("AB\nCD")
        doc.cursor_line = 1
        doc.cursor_col = 2
        doc.move_right()
        assert doc.cursor_line == 1
        assert doc.cursor_col == 2

    def test_move_up_clamps_col(self):
        doc = Document("Hi\nHello")
        doc.cursor_line = 1
        doc.cursor_col = 4
        doc.move_up()
        assert doc.cursor_line == 0
        assert doc.cursor_col == 2  # clamped to len("Hi")

    def test_move_up_at_first_line(self):
        doc = Document("Hello")
        doc.cursor_line = 0
        doc.cursor_col = 3
        doc.move_up()
        assert doc.cursor_line == 0
        assert doc.cursor_col == 3

    def test_move_down(self):
        doc = Document("Hello\nHi")
        doc.cursor_line = 0
        doc.cursor_col = 4
        doc.move_down()
        assert doc.cursor_line == 1
        assert doc.cursor_col == 2  # clamped to len("Hi")

    def test_move_down_at_last_line(self):
        doc = Document("Hello")
        doc.cursor_line = 0
        doc.cursor_col = 3
        doc.move_down()
        assert doc.cursor_line == 0
        assert doc.cursor_col == 3

    def test_move_home(self):
        doc = Document("Hello")
        doc.cursor_col = 3
        doc.move_home()
        assert doc.cursor_col == 0

    def test_move_end(self):
        doc = Document("Hello")
        doc.cursor_col = 0
        doc.move_end()
        assert doc.cursor_col == 5


class TestProperties:
    def test_current_line(self):
        doc = Document("hello\nworld")
        doc.cursor_line = 1
        assert doc.current_line == "world"

    def test_line_count(self):
        doc = Document("a\nb\nc")
        assert doc.line_count == 3

    def test_line_count_empty(self):
        doc = Document()
        assert doc.line_count == 1

    def test_char_count(self):
        doc = Document("hello")
        assert doc.char_count == 5

    def test_char_count_multiline(self):
        doc = Document("hi\nthere")
        assert doc.char_count == 8  # includes newline

    def test_lines_returns_copy(self):
        doc = Document("hello")
        lines = doc.lines
        lines.append("extra")
        assert doc.line_count == 1  # original unmodified


class TestWordCount:
    def test_empty(self):
        assert Document().word_count == 0

    def test_words(self):
        doc = Document("Hello beautiful world")
        assert doc.word_count == 3

    def test_multiline(self):
        doc = Document("one two\nthree four five")
        assert doc.word_count == 5

    def test_extra_whitespace(self):
        doc = Document("  hello   world  ")
        assert doc.word_count == 2

    def test_tabs_and_newlines(self):
        doc = Document("word1\tword2\n\nword3")
        assert doc.word_count == 3


class TestLoadSave:
    def test_load_resets_cursor(self):
        doc = Document("old text")
        doc.cursor_col = 5
        doc.dirty = True
        doc.load("new text", "test")
        assert doc.text == "new text"
        assert doc.cursor_line == 0
        assert doc.cursor_col == 0
        assert doc.dirty is False

    def test_mark_saved(self):
        doc = Document()
        doc.insert("x")
        assert doc.dirty is True
        doc.mark_saved()
        assert doc.dirty is False

    def test_load_clears_undo(self):
        doc = Document("text")
        doc.cursor_col = 4
        doc.insert("!")
        assert len(doc._undo_stack) > 0
        doc.load("new", "new")
        assert len(doc._undo_stack) == 0
        assert len(doc._redo_stack) == 0

    def test_load_clears_selection(self):
        doc = Document("hello")
        doc.select_all()
        assert doc.selection is not None
        doc.load("new", "new")
        assert doc.selection is None

    def test_load_empty_string(self):
        doc = Document("old text")
        doc.load("", "empty")
        assert doc.lines == [""]
        assert doc.line_count == 1

    def test_load_preserves_name_when_none(self):
        doc = Document("text")
        doc.name = "keep-this"
        doc.load("new text")
        assert doc.name == "keep-this"


class TestUndoRedo:
    def test_undo_insert(self):
        doc = Document()
        doc.insert("H")
        doc._last_undo_time = 0
        doc.insert("i")
        assert doc.text == "Hi"
        doc.undo()
        assert doc.text == "H"

    def test_redo_after_undo(self):
        doc = Document()
        doc.insert("H")
        doc._last_undo_time = 0
        doc.insert("i")
        doc.undo()
        assert doc.text == "H"
        doc.redo()
        assert doc.text == "Hi"

    def test_undo_empty_stack(self):
        doc = Document()
        assert doc.undo() is False

    def test_redo_empty_stack(self):
        doc = Document()
        assert doc.redo() is False

    def test_redo_cleared_on_new_edit(self):
        doc = Document()
        doc.insert("a")
        doc._last_undo_time = 0
        doc.insert("b")
        doc.undo()
        doc._last_undo_time = 0
        doc.insert("c")
        assert doc.redo() is False

    def test_undo_delete_backward(self):
        doc = Document("Hello")
        doc.cursor_col = 5
        doc.delete_backward()
        assert doc.text == "Hell"
        doc.undo()
        assert doc.text == "Hello"

    def test_coalesce_fast_inserts(self):
        doc = Document()
        doc.insert("a")
        doc.insert("b")
        doc.insert("c")
        assert len(doc._undo_stack) == 1
        doc.undo()
        assert doc.text == ""

    def test_undo_stack_capacity_100(self):
        doc = Document()
        # Push 101 distinct undo groups
        for i in range(101):
            doc._last_undo_time = 0  # Force new group
            doc.insert(str(i % 10))
        # maxlen=100, so oldest is evicted
        assert len(doc._undo_stack) == 100

    def test_undo_restores_cursor_position(self):
        doc = Document("Hello")
        doc.cursor_line = 0
        doc.cursor_col = 5
        doc._last_undo_time = 0
        doc.insert("\n")
        assert doc.cursor_line == 1
        doc.undo()
        assert doc.cursor_line == 0
        assert doc.cursor_col == 5

    def test_undo_clears_selection(self):
        doc = Document()
        doc.insert("Hello")
        doc.select_all()
        doc.undo()
        assert doc.selection is None

    def test_multiple_undo_redo_cycle(self):
        doc = Document()
        doc.insert("A")
        doc._last_undo_time = 0
        doc.insert("B")
        doc._last_undo_time = 0
        doc.insert("C")
        assert doc.text == "ABC"
        doc.undo()
        assert doc.text == "AB"
        doc.undo()
        assert doc.text == "A"
        doc.redo()
        assert doc.text == "AB"
        doc.redo()
        assert doc.text == "ABC"

    def test_undo_newline(self):
        doc = Document("Hello")
        doc.cursor_col = 5
        doc._last_undo_time = 0
        doc.insert("\n")
        assert doc.line_count == 2
        doc.undo()
        assert doc.line_count == 1
        assert doc.text == "Hello"

    def test_undo_delete_forward(self):
        doc = Document("AB")
        doc.cursor_col = 0
        doc.delete_forward()
        assert doc.text == "B"
        doc.undo()
        assert doc.text == "AB"


class TestWordMovement:
    def test_move_word_right(self):
        doc = Document("hello world")
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.move_word_right()
        assert doc.cursor_col == 6

    def test_move_word_left(self):
        doc = Document("hello world")
        doc.cursor_line = 0
        doc.cursor_col = 11
        doc.move_word_left()
        assert doc.cursor_col == 6

    def test_move_word_left_from_start(self):
        doc = Document("hello\nworld")
        doc.cursor_line = 1
        doc.cursor_col = 0
        doc.move_word_left()
        assert doc.cursor_line == 0

    def test_delete_word_backward(self):
        doc = Document("hello world")
        doc.cursor_line = 0
        doc.cursor_col = 11
        doc.delete_word_backward()
        assert doc.text == "hello "

    def test_move_word_right_with_punctuation(self):
        doc = Document("hello, world")
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.move_word_right()
        # Should skip past "hello" and punctuation+space
        assert doc.cursor_col == 7

    def test_move_word_left_with_punctuation(self):
        doc = Document("hello, world")
        doc.cursor_line = 0
        doc.cursor_col = 12
        doc.move_word_left()
        assert doc.cursor_col == 7

    def test_move_word_right_at_end_of_line(self):
        doc = Document("hello\nworld")
        doc.cursor_line = 0
        doc.cursor_col = 5
        doc.move_word_right()
        assert doc.cursor_line == 1
        assert doc.cursor_col == 0

    def test_move_word_right_at_doc_end(self):
        doc = Document("hello")
        doc.cursor_line = 0
        doc.cursor_col = 5
        doc.move_word_right()
        assert doc.cursor_col == 5  # no change

    def test_move_word_left_at_doc_start(self):
        doc = Document("hello")
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.move_word_left()
        assert doc.cursor_col == 0

    def test_move_word_right_empty_line(self):
        doc = Document("hello\n\nworld")
        doc.cursor_line = 0
        doc.cursor_col = 5
        doc.move_word_right()
        assert doc.cursor_line == 1

    def test_delete_word_backward_joins_lines(self):
        doc = Document("hello\nworld")
        doc.cursor_line = 1
        doc.cursor_col = 0
        doc.delete_word_backward()
        assert doc.text == "helloworld"

    def test_delete_word_backward_with_selection(self):
        doc = Document("hello world")
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.select_all()
        doc.delete_word_backward()
        assert doc.text == ""

    def test_move_word_right_multiple_spaces(self):
        doc = Document("hello   world")
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.move_word_right()
        assert doc.cursor_col == 8


class TestSelection:
    def test_select_all(self):
        doc = Document("hello\nworld")
        doc.select_all()
        assert doc.selection is not None
        assert doc.get_selected_text() == "hello\nworld"

    def test_clear_selection(self):
        doc = Document("hello")
        doc.select_all()
        doc.clear_selection()
        assert doc.selection is None

    def test_delete_selection(self):
        doc = Document("hello world")
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.select_all()
        doc.delete_selection()
        assert doc.text == ""

    def test_insert_replaces_selection(self):
        doc = Document("hello")
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.select_all()
        doc.insert("X")
        assert doc.text == "X"

    def test_shift_arrow_creates_selection(self):
        doc = Document("hello")
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.move_right(extend=True)
        doc.move_right(extend=True)
        assert doc.selection is not None
        assert doc.get_selected_text() == "he"

    def test_movement_clears_selection(self):
        doc = Document("hello")
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.move_right(extend=True)
        doc.move_right()  # no extend -> clears selection
        assert doc.selection is None

    def test_get_selected_text_multiline(self):
        doc = Document("hello\nworld\nfoo")
        doc.selection = Selection(0, 3, 2, 2)
        assert doc.get_selected_text() == "lo\nworld\nfo"

    def test_get_selected_text_no_selection(self):
        doc = Document("hello")
        assert doc.get_selected_text() == ""

    def test_delete_selection_returns_false_when_none(self):
        doc = Document("hello")
        assert doc.delete_selection() is False

    def test_delete_selection_same_line(self):
        doc = Document("hello world")
        doc.selection = Selection(0, 5, 0, 11)
        doc.delete_selection()
        assert doc.text == "hello"
        assert doc.cursor_col == 5

    def test_delete_selection_multiline(self):
        doc = Document("aaa\nbbb\nccc")
        doc.selection = Selection(0, 1, 2, 2)
        doc.delete_selection()
        assert doc.text == "ac"
        assert doc.cursor_line == 0
        assert doc.cursor_col == 1

    def test_delete_selection_three_lines(self):
        doc = Document("line1\nline2\nline3\nline4")
        doc.selection = Selection(1, 0, 2, 5)
        doc.delete_selection()
        # Selection (1,0)→(2,5): before="" after="" → lines[1]=""
        # del lines[2:3] removes "line3"
        assert doc.lines == ["line1", "", "line4"]

    def test_selection_ordered_forward(self):
        sel = Selection(0, 5, 2, 3)
        assert sel.ordered() == (0, 5, 2, 3)

    def test_selection_ordered_backward(self):
        sel = Selection(2, 3, 0, 5)
        assert sel.ordered() == (0, 5, 2, 3)

    def test_selection_ordered_same_line(self):
        sel = Selection(1, 8, 1, 2)
        assert sel.ordered() == (1, 2, 1, 8)

    def test_select_up_extends(self):
        doc = Document("aaa\nbbb")
        doc.cursor_line = 1
        doc.cursor_col = 1
        doc.move_up(extend=True)
        assert doc.selection is not None
        assert doc.cursor_line == 0

    def test_select_down_extends(self):
        doc = Document("aaa\nbbb")
        doc.cursor_line = 0
        doc.cursor_col = 1
        doc.move_down(extend=True)
        assert doc.selection is not None
        assert doc.cursor_line == 1

    def test_select_home(self):
        doc = Document("hello")
        doc.cursor_col = 3
        doc.move_home(extend=True)
        assert doc.selection is not None
        assert doc.get_selected_text() == "hel"

    def test_select_end(self):
        doc = Document("hello")
        doc.cursor_col = 2
        doc.move_end(extend=True)
        assert doc.selection is not None
        assert doc.get_selected_text() == "llo"

    def test_select_word_left(self):
        doc = Document("hello world")
        doc.cursor_line = 0
        doc.cursor_col = 11
        doc.move_word_left(extend=True)
        assert doc.selection is not None
        assert doc.get_selected_text() == "world"

    def test_select_word_right(self):
        doc = Document("hello world")
        doc.cursor_line = 0
        doc.cursor_col = 0
        doc.move_word_right(extend=True)
        assert doc.selection is not None
        # Selects "hello " (word + trailing whitespace)
        assert "hello" in doc.get_selected_text()


class TestFindReplace:
    def test_find_next(self):
        doc = Document("hello world hello")
        pos = doc.find_next("hello", 0, 0)
        assert pos == (0, 0)

    def test_find_next_from_offset(self):
        doc = Document("hello world hello")
        pos = doc.find_next("hello", 0, 1)
        assert pos == (0, 12)

    def test_find_next_wraps(self):
        doc = Document("hello\nworld")
        pos = doc.find_next("hello", 1, 0)
        assert pos == (0, 0)

    def test_find_not_found(self):
        doc = Document("hello world")
        pos = doc.find_next("xyz", 0, 0)
        assert pos is None

    def test_find_empty_query(self):
        doc = Document("hello")
        pos = doc.find_next("", 0, 0)
        assert pos is None

    def test_replace_at(self):
        doc = Document("hello world")
        doc.replace_at(0, 6, "world", "earth")
        assert doc.text == "hello earth"

    def test_replace_at_no_match(self):
        doc = Document("hello world")
        doc.replace_at(0, 0, "xyz", "abc")
        assert doc.text == "hello world"  # unchanged

    def test_replace_at_marks_dirty(self):
        doc = Document("hello world")
        doc.dirty = False
        doc.replace_at(0, 6, "world", "earth")
        assert doc.dirty is True

    def test_replace_at_returns_bool(self):
        doc = Document("hello world")
        assert doc.replace_at(0, 6, "world", "earth") is True
        assert doc.replace_at(0, 0, "xyz", "abc") is False

    def test_replace_at_one_undo_entry(self):
        # BUG-1: find "cat" replace "dog" via located match, one undo restores.
        doc = Document("the cat sat")
        pos = doc.find_next("cat", 0, 0)
        assert pos == (0, 4)
        assert doc.replace_at(pos[0], pos[1], "cat", "dog") is True
        assert doc.text == "the dog sat"
        assert doc.undo() is True
        assert doc.text == "the cat sat"
        # Exactly one entry — a second undo has nothing to pop.
        assert doc.undo() is False

    def test_replace_at_no_match_leaves_undo_unchanged(self):
        # BUG-1: a no-op replace must not push an inert undo snapshot.
        doc = Document("the cat sat")
        doc.dirty = False
        assert doc.replace_at(0, 0, "cat", "dog") is False
        assert doc.text == "the cat sat"
        assert doc.dirty is False
        assert doc.undo() is False  # undo stack untouched

    def test_find_multiline(self):
        doc = Document("aaa\nbbb\nccc\naaa")
        pos = doc.find_next("aaa", 0, 1)
        assert pos == (3, 0)

    def test_find_on_second_line(self):
        doc = Document("aaa\nbbb")
        pos = doc.find_next("bbb", 0, 0)
        assert pos == (1, 0)


class TestWordCountCache:
    def test_word_count_cached_after_access(self):
        doc = Document("hello world")
        first = doc.word_count
        assert doc._word_count_dirty is False
        second = doc.word_count
        assert first == second == 2
        assert doc._word_count_dirty is False

    def test_word_count_invalidated_on_insert(self):
        doc = Document("hello")
        _ = doc.word_count  # populate cache
        assert doc._word_count_dirty is False
        doc.insert(" world")
        assert doc._word_count_dirty is True
        assert doc.word_count == 2

    def test_word_count_invalidated_on_delete(self):
        doc = Document("hello world")
        _ = doc.word_count
        assert doc._word_count_dirty is False
        doc.delete_backward()
        assert doc._word_count_dirty is True

    def test_word_count_invalidated_on_undo(self):
        doc = Document()
        doc.insert("hello")
        _ = doc.word_count
        assert doc._word_count_dirty is False
        doc.undo()
        assert doc._word_count_dirty is True

    def test_redo_stack_bounded(self):
        doc = Document()
        # Do 101 inserts (defeating coalescing so each is its own undo group)
        # then undo them all — this fills the redo stack beyond 100.
        for _i in range(101):
            doc._last_undo_time = 0  # Force a new undo group per insert
            doc.insert("a")
        for _i in range(101):
            doc.undo()
        assert len(doc._redo_stack) <= 100

    def test_edit_after_undo_invalidates_redo(self):
        # Task 1 regression: an edit within the 1s coalesce window, made while
        # the undo stack is non-empty, must still invalidate redo — the stale
        # redo snapshot must not resurrect the superseded text nor drop the
        # just-typed char.
        doc = Document()
        # First undo group.
        doc.insert("a")
        # Second, distinct undo group.
        doc._last_undo_time = 0
        doc.insert("b")
        assert doc.text == "ab"
        # Undo the second group.
        doc.undo()
        assert doc.text == "a"
        # Now type again WITHIN the coalesce window (same "insert" action, and
        # _last_undo_time is recent because undo() left it untouched). This is
        # a new edit and must clear the redo stack.
        doc.insert("c")
        assert doc.text == "ac"
        # redo() must be a no-op: it must not resurrect "ab" nor lose "c".
        assert doc.redo() is False
        assert doc.text == "ac"
