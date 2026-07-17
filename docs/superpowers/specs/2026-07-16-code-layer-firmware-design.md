# CODE-layer keyboard overhaul — firmware + modifier architecture

**Date:** 2026-07-16
**Status:** Approved (architecture); key-assignment table deferred to a follow-up brainstorm

## Background

The writer-deck's keyboard is a KPrepublic BM43A (QMK, 43 keys, 40% layout, VID:PID
`feed:6060`, USB-bus-powered off the Pi). Its currently-flashed firmware closely mirrors
the stock QMK default (`keyboards/kprepublic/bm43a/keymaps/default/keymap.c`): row 0
(`ESC Q W E R T Y U I O P BSPC`) has no number row, and the only Fn layer (`MO(1)`, bound
to a key labeled "CODE" on this unit) only controls RGB underglow and backlight — it does
not remap any letter to a digit or symbol. Confirmed live via `evtest` on
`/dev/input/by-id/usb-qmkbuilder_keyboard-event-kbd`: holding CODE and pressing Q–P
produces plain, unshifted `KEY_Q`...`KEY_P` events, and CODE itself never appears in the
event stream at all (`MO()` layer keys are silent by QMK design). Numbers and most
symbols are therefore physically unreachable today — not a bug in
`writerdeck/input/keymapper.py`, which already has scancode-to-character mappings for
digits/symbols that simply never fire because no physical key/layer combination emits
those codes.

Also relevant: `writerdeck/input/keymapper.py` already defines `KeyAction.DELETE` (bound
to evdev `KEY_DELETE`, scancode 111) and `KeyAction.SELECT_HOME`/`SELECT_END` (bound to
`KEY_HOME`/`KEY_END`, scancodes 102/107) — none of which this board has a physical key
for, so those actions are also currently dead code, same root cause.

## Goals

- Make numbers and symbols typeable on this physical keyboard.
- Give the user full, low-friction control over what every key combo does, without
  requiring a firmware recompile/reflash to change a binding later.
- Preserve the existing Ctrl/Shift-based shortcut system in `keymapper.py` unchanged.
- Turn the RGB underglow off for good (battery: keyboard is USB-bus-powered off the same
  PiSugar battery as the rest of the device).
- Don't lose the ability to re-enter the bootloader for future reflashes.

## Non-goals

- Deciding the actual per-key symbol/number assignment table — deferred to a follow-up
  brainstorm (user wants to think about ergonomics before committing). This design only
  fixes the *mechanism* by which any such table can be defined and changed freely in
  Python.
- Changing anything about the existing Ctrl/Shift dispatch tables.
- VIA/Vial live-remap support (rejected in favor of the hybrid approach below).

## Decision: hybrid firmware + Python approach

Rejected alternatives:
- **Full custom QMK `keymap.c` with hardcoded layers** — every future rebind requires a
  recompile + reflash cycle. Conflicts with "full control, low friction."
- **VIA/Vial live remapping** — not confirmed present in the currently-flashed firmware,
  and would split keymap logic across two systems (VIA's layer state and
  `keymapper.py`'s own Ctrl/Shift state) instead of one.

Chosen: **one minimal firmware flash, then all layer logic lives in Python.**

### 1. Firmware changes (one-time flash)

- Rebind the physical "CODE" key from `MO(1)` to plain `KC_F13`. Every other key always
  sends its normal, single, unshifted keycode — no on-device layer-switching remains.
  `KC_F13` (evdev `KEY_F13`, code 183) is unused anywhere in `keymapper.py` today.
- Disable RGB entirely in `rules.mk` (`RGBLIGHT_ENABLE = no`, not just removing the layer
  bindings) so the LEDs are off at every boot regardless of any state saved in the
  board's EEPROM from prior use.
- Enable Bootmagic Lite bound to ESC (hold ESC while plugging the keyboard into USB →
  boots into bootloader). This replaces the old `Fn+ESC → QK_BOOT` trick, which is lost
  once CODE stops being a QMK layer key. Bootmagic Lite is independent of the runtime
  keymap, so it can't be broken by anything done in Python later.

### 2. Python-side modifier handling (`writerdeck/input/keymapper.py`)

`KeyMapper` already tracks `_ctrl_held` / `_shift_held` off `_KEY_LEFTCTRL`/
`_KEY_LEFTSHIFT` press/release events (`process_event`, lines ~142-147). Add
`_code_held`, tracked identically off `KEY_F13` (evdev code 183):

```python
_KEY_F13 = 183
...
if scancode == _KEY_F13:
    self._code_held = value != 0
    return KeyAction.UNKNOWN, ""
```

Add a new top-level dispatch branch, checked before the existing `if self._ctrl_held:`
branch:

```python
if self._code_held:
    if self._shift_held:
        # CODE+Shift combos — table TBD in follow-up brainstorm
        ...
    # CODE-only combos — table TBD in follow-up brainstorm
    ...
    return KeyAction.UNKNOWN, ""
```

This is purely additive: existing Ctrl/Shift/plain dispatch paths are untouched. Output
still flows through the existing `(KeyAction.CHAR, char)` / `(KeyAction.<ACTION>, "")`
contract, so `renderer.py`, `document.py`, and `app.py` need no changes to consume
whatever the CODE layer eventually produces — CHAR actions render exactly like any other
typed character, and any new KeyAction variants (if the eventual table needs one, e.g.
for DELETE) are dispatched exactly like existing ones.

`reset()` must also clear `_code_held`, matching the existing `_ctrl_held`/`_shift_held`
clear-on-reset behavior (evdev disconnect / pygame focus loss).

### Known gaps this reopens for the follow-up brainstorm

Two existing dead `KeyAction`s become reachable once a physical modifier-with-events
exists, and should be considered when the key-assignment table is designed:
- `KeyAction.DELETE` — no physical Delete key exists on this board; a natural candidate
  is `CODE+Backspace`.
- `KeyAction.SELECT_HOME` / `KeyAction.SELECT_END` — noted as an open gap in
  `NEXT-STEPS.md` since the 2026-07-15 session (no physical Home/End key). A natural
  candidate is `CODE+Shift+Up/Down`, mirroring the existing `Ctrl+Shift+Up/Down →
  Home/End` pattern from that session.

## Testing / verification plan

- `tests/test_keymapper.py`: unit tests for `_code_held` tracking (press/release/reset)
  and the new dispatch branch, once the table exists.
- Live verification on hardware via `evtest` (as used to diagnose this issue) to confirm
  `KC_F13` fires clean press/release events after reflash, before building out the table.
- Full existing test suite must stay green — this change must not touch any Ctrl/Shift
  dispatch path.

## Open follow-up

A separate brainstorming session will design the actual CODE-layer key assignment table
(which physical key produces which digit/symbol/action). This design doc's job ends at
making that table trivial to define and iterate on in Python.
