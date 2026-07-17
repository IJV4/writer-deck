# CODE-Layer Keyboard Firmware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reflash the writer-deck's BM43A keyboard so its "CODE" key emits a real, observable `KC_F13` event instead of a silent QMK layer-switch, disable its RGB underglow, and add matching modifier-tracking to `keymapper.py` — laying the groundwork for a future symbol/number key table without needing another firmware flash.

**Architecture:** One-time QMK firmware flash (custom single-layer keymap: CODE key → `KC_F13`, RGB disabled) + additive changes to `writerdeck/input/keymapper.py` (`_code_held` state tracked off evdev `KEY_F13`, code 183, mirroring existing `_ctrl_held`/`_shift_held` tracking). The Python dispatch branch for CODE combos is added now with an intentionally empty table (returns `KeyAction.UNKNOWN`) — the actual symbol/number assignments are a separate follow-up per the design spec.

**Tech Stack:** QMK firmware (C), `qmk` CLI, `dfu-programmer` (atmel-dfu bootloader), Python 3 (`writerdeck/input/keymapper.py`), pytest.

## Global Constraints

- Board: KPrepublic BM43A, QMK keyboard `kprepublic/bm43a`, USB VID:PID `feed:6060`, bootloader `atmel-dfu` on an `atmega32u4`.
- Existing Ctrl/Shift dispatch logic in `writerdeck/input/keymapper.py` must not change behavior — all changes are additive.
- `KC_F13` / evdev `KEY_F13` (code 183) is the chosen unused keycode for the CODE modifier — do not reuse it elsewhere.
- RGB underglow must be disabled in `rules.mk` (`RGBLIGHT_ENABLE = no`), not merely unbound from a layer.
- Bootmagic (hold-ESC-at-plug-in → bootloader) is already enabled by default in this board's `keyboard.json` (`"bootmagic": true`, matrix position `[0,0]` = `KC_ESC`) — no extra config needed to preserve it.
- Pi is reachable at `pi@192.168.1.101`; deploy via `./deploy.sh 192.168.1.101 pi` (from prior session — `deploy.sh` with no args fails DNS resolution on `writer-deck.local`).
- Full test suite (`pytest -q`) must stay green throughout.

---

### Task 1: Set up the QMK build toolchain on the dev machine

**Files:** None (tooling only).

**Interfaces:**
- Produces: a working `qmk` CLI on `PATH` and `~/qmk_firmware` cloned, ready for Task 3's build.

- [ ] **Step 1: Install the QMK CLI**

Run:
```bash
python3 -m pip install --user qmk
```
Expected: pip reports `qmk` installed successfully (or already satisfied).

- [ ] **Step 2: Ensure the CLI is on PATH**

Run:
```bash
export PATH="$HOME/.local/bin:$PATH"
qmk --version
```
Expected: prints a version string like `QMK CLI 1.x.x` (no "command not found").

If `qmk: command not found` persists, add the export line to `~/.zshrc` (this session's shell) and re-source it.

- [ ] **Step 3: Run QMK setup (clones qmk_firmware, installs build deps)**

Run:
```bash
qmk setup -y qmk/qmk_firmware
```
Expected: clones to `~/qmk_firmware` and finishes with a success message. This step installs OS build packages (gcc-avr, avr-libc, etc.) and may prompt for `sudo` — approve it.

- [ ] **Step 4: Verify the toolchain**

Run:
```bash
qmk doctor
```
Expected: output ends with `QMK is ready to go` (or lists only non-blocking warnings — no `Ω` fatal errors about missing compilers).

---

### Task 2: Author the custom keymap source (checked into the writer-deck repo)

**Files:**
- Create: `firmware/bm43a-writerdeck/keymap.c`
- Create: `firmware/bm43a-writerdeck/rules.mk`
- Create: `firmware/bm43a-writerdeck/readme.md`

**Interfaces:**
- Produces: the three files Task 3 copies into the local QMK checkout to build.

- [ ] **Step 1: Write `keymap.c`**

This is the stock BM43A default layout (`ESC Q W E R T Y U I O P BSPC` / `TAB A S D F G H J K L ENT` / `LSFT Z X C V B N M , UP .` / `LCTL LGUI LALT SPC SPC [CODE] LEFT DOWN RIGHT`) with the former `MO(1)` CODE key rebound to `KC_F13`, and the RGB/backlight-only second layer removed entirely (single layer now):

```c
#include QMK_KEYBOARD_H

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = LAYOUT(
        KC_ESC,  KC_Q,    KC_W,    KC_E,    KC_R,    KC_T,    KC_Y,    KC_U,    KC_I,    KC_O,    KC_P,    KC_BSPC,
        KC_TAB,    KC_A,    KC_S,    KC_D,    KC_F,    KC_G,    KC_H,    KC_J,    KC_K,    KC_L,    KC_ENT,
        KC_LSFT,          KC_Z,    KC_X,    KC_C,    KC_V,    KC_B,    KC_N,    KC_M,    KC_COMM, KC_UP,   KC_DOT,
        KC_LCTL, KC_LGUI, KC_LALT, KC_SPC,                 KC_SPC,              KC_F13,  KC_LEFT, KC_DOWN, KC_RGHT
    ),
};
```

- [ ] **Step 2: Write `rules.mk`**

Disables RGB underglow and keycap backlighting for this keymap build (overrides the board-level defaults without touching the shared upstream `keyboard.json`):

```makefile
RGBLIGHT_ENABLE = no
BACKLIGHT_ENABLE = no
```

- [ ] **Step 3: Write `readme.md`**

```markdown
# writer-deck keymap for KPrepublic BM43A

Single-layer keymap. The physical key labeled "CODE" (matrix position `[3,7]`,
next to the arrow cluster) sends `KC_F13` instead of acting as a QMK
momentary-layer key. `writerdeck/input/keymapper.py` treats `KEY_F13` (evdev
code 183) as a third modifier, alongside Ctrl and Shift, and owns all
symbol/number/shortcut logic in Python — this firmware never needs
reflashing again to change a keybinding.

RGB underglow and backlight are disabled (`rules.mk`) since this board is
USB-bus-powered off the same battery as the rest of the device.

Bootloader entry: hold ESC while plugging the keyboard into USB (QMK
Bootmagic, enabled by default on this board — matrix position `[0,0]` is ESC).

## Build

    qmk compile -kb kprepublic/bm43a -km writerdeck

## Flash (via dfu-programmer on the target Pi)

    sudo dfu-programmer atmega32u4 erase
    sudo dfu-programmer atmega32u4 flash kprepublic_bm43a_writerdeck.hex
    sudo dfu-programmer atmega32u4 reset
```

- [ ] **Step 4: Commit**

```bash
cd /home/ismael/projects/writer-deck
git add firmware/bm43a-writerdeck/
git commit -m "firmware: add writer-deck QMK keymap for BM43A (CODE -> KC_F13, RGB off)"
```

---

### Task 3: Build the firmware

**Files:**
- Modify (outside the repo): `~/qmk_firmware/keyboards/kprepublic/bm43a/keymaps/writerdeck/` (created by copying Task 2's files)

**Interfaces:**
- Consumes: `firmware/bm43a-writerdeck/keymap.c`, `rules.mk` from Task 2.
- Produces: `~/qmk_firmware/kprepublic_bm43a_writerdeck.hex`, consumed by Task 4.

- [ ] **Step 1: Copy the keymap into the local QMK checkout**

```bash
mkdir -p ~/qmk_firmware/keyboards/kprepublic/bm43a/keymaps/writerdeck
cp /home/ismael/projects/writer-deck/firmware/bm43a-writerdeck/keymap.c \
   /home/ismael/projects/writer-deck/firmware/bm43a-writerdeck/rules.mk \
   ~/qmk_firmware/keyboards/kprepublic/bm43a/keymaps/writerdeck/
```
Expected: no output; `ls ~/qmk_firmware/keyboards/kprepublic/bm43a/keymaps/writerdeck/` shows both files.

- [ ] **Step 2: Compile**

```bash
cd ~/qmk_firmware
qmk compile -kb kprepublic/bm43a -km writerdeck
```
Expected: ends with a line like `Copying kprepublic_bm43a_writerdeck.hex to qmk_firmware folder` and no `[ERRORS]`.

- [ ] **Step 3: Verify the build artifact**

```bash
ls -la ~/qmk_firmware/kprepublic_bm43a_writerdeck.hex
```
Expected: file exists, non-zero size (a few hundred KB is typical for this MCU's Intel HEX output).

---

### Task 4: Get `dfu-programmer` and the built firmware onto the Pi

**Files:**
- Modify: `setup.sh` (add `dfu-programmer` to the apt install list, so a fresh Pi setup has it going forward)

**Interfaces:**
- Consumes: `~/qmk_firmware/kprepublic_bm43a_writerdeck.hex` from Task 3.
- Produces: `dfu-programmer` installed and `~/kprepublic_bm43a_writerdeck.hex` present on the Pi, consumed by Task 5.

- [ ] **Step 1: Add `dfu-programmer` to `setup.sh`**

Find the existing `apt-get install` block in `setup.sh` (the one with `fonts-hack-ttf`, `evtest`, etc. from the 2026-07-15 session) and add `dfu-programmer` to the package list, e.g.:

```bash
sudo apt-get install -y -qq \
    python3-dev python3-venv python3-pip \
    libfreetype6-dev libjpeg-dev libopenjp2-7-dev \
    libgpiod-dev git evtest dfu-programmer \
    avahi-daemon libnss-mdns \
    fonts-hack-ttf fonts-liberation fonts-courier-prime fonts-ebgaramond \
    fonts-lato fonts-dejavu-core
```

- [ ] **Step 2: Install it on the Pi immediately (don't wait for a full `setup.sh` rerun)**

```bash
ssh pi@192.168.1.101 'sudo apt-get install -y dfu-programmer'
```
Expected: apt reports the package installed (or already the newest version).

- [ ] **Step 3: Copy the built firmware to the Pi**

```bash
scp ~/qmk_firmware/kprepublic_bm43a_writerdeck.hex pi@192.168.1.101:~/
```
Expected: scp shows a completed transfer with the file's byte count.

- [ ] **Step 4: Commit the setup.sh change**

```bash
cd /home/ismael/projects/writer-deck
git add setup.sh
git commit -m "chore: add dfu-programmer to Pi setup for BM43A firmware flashing"
```

---

### Task 5: Flash the keyboard and verify live

**Files:** None (hardware operation + live verification, no repo changes).

**Interfaces:**
- Consumes: `~/kprepublic_bm43a_writerdeck.hex` on the Pi (Task 4), `dfu-programmer` (Task 4).
- Produces: a keyboard that emits `KEY_F13` press/release when CODE is held, verified live — required before Task 7's integration check makes sense.

- [ ] **Step 1: Stop the writer-deck service before flashing**

```bash
ssh pi@192.168.1.101 'sudo systemctl stop writer-deck.service'
```
Expected: no error; `systemctl is-active writer-deck.service` reports `inactive`.

- [ ] **Step 2: Enter the bootloader**

Physically unplug the BM43A from the Pi. While holding down the **ESC** key, plug it back into the Pi's USB port, then release ESC.

Verify:
```bash
ssh pi@192.168.1.101 'lsusb | grep -i atmel'
```
Expected: a line mentioning `Atmel Corp.` (the DFU bootloader), not `qmkbuilder keyboard`. If this doesn't appear, unplug and retry holding ESC more firmly through the full replug.

- [ ] **Step 3: Flash**

```bash
ssh pi@192.168.1.101 'sudo dfu-programmer atmega32u4 erase && sudo dfu-programmer atmega32u4 flash ~/kprepublic_bm43a_writerdeck.hex && sudo dfu-programmer atmega32u4 reset'
```
Expected: `erase` reports success, `flash` reports the checksum/byte count written with no `Bad CRC` or `ERROR` lines, `reset` returns immediately once the device is signaled to restart.

- [ ] **Step 4: Confirm re-enumeration as a normal keyboard**

```bash
ssh pi@192.168.1.101 'sleep 2 && lsusb | grep -i qmkbuilder'
```
Expected: `qmkbuilder keyboard` is back (bus/device numbers may differ from before).

- [ ] **Step 5: Live-verify CODE now sends KEY_F13**

```bash
ssh pi@192.168.1.101 'timeout 15 evtest /dev/input/by-id/usb-qmkbuilder_keyboard-event-kbd' > /tmp/evtest_f13_check.log 2>&1 &
```
While that's capturing, press and release the **CODE** key alone (no other key).

Then check:
```bash
grep -A1 "KEY_F13" /tmp/evtest_f13_check.log
```
Expected: at least one `type 1 (EV_KEY), code 183 (KEY_F13), value 1` line followed by a `value 0` line — proof the key now emits real events instead of nothing.

- [ ] **Step 6: Restart the writer-deck service**

```bash
ssh pi@192.168.1.101 'sudo systemctl start writer-deck.service && sleep 2 && systemctl is-active writer-deck.service'
```
Expected: `active`.

---

### Task 6: Add `_code_held` tracking and the CODE dispatch branch to `keymapper.py`

**Files:**
- Modify: `writerdeck/input/keymapper.py`
- Test: `tests/test_keymapper.py`

**Interfaces:**
- Consumes: evdev `KEY_F13` = 183 (confirmed live in Task 5).
- Produces: `KeyMapper._code_held: bool`, tracked and reset identically to `_ctrl_held`/`_shift_held`. While `_code_held` is `True`, `process_event` returns `(KeyAction.UNKNOWN, "")` for every scancode that would otherwise fall through to the Ctrl/Shift/plain dispatch — an intentionally empty table, per the design spec's deferred follow-up.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_keymapper.py`, inside `class TestModifierTracking` (matching the existing Ctrl/Shift tests directly above it):

```python
    def test_code_press_release(self):
        m = KeyMapper()
        m.process_event(183, 1)  # CODE (KEY_F13) press
        assert m._code_held is True
        m.process_event(183, 0)
        assert m._code_held is False

    def test_code_returns_unknown(self):
        m = KeyMapper()
        action, char = m.process_event(183, 1)
        assert action == KeyAction.UNKNOWN
```

And extend the existing `test_reset_clears_held_modifiers` test in the same class:

```python
    def test_reset_clears_held_modifiers(self):
        m = KeyMapper()
        m.process_event(29, 1)  # Ctrl press
        m.process_event(42, 1)  # Shift press
        m.process_event(183, 1)  # CODE press
        assert m._ctrl_held is True
        assert m._shift_held is True
        assert m._code_held is True
        m.reset()
        assert m._ctrl_held is False
        assert m._shift_held is False
        assert m._code_held is False
```

Add a new test class at the end of the file:

```python
class TestCodeCombos:
    def test_code_plus_letter_returns_unknown(self):
        m = KeyMapper()
        m.process_event(183, 1)  # CODE press
        action, char = m.process_event(16, 1)  # 'q' press
        assert action == KeyAction.UNKNOWN
        assert char == ""

    def test_code_plus_shift_plus_letter_returns_unknown(self):
        m = KeyMapper()
        m.process_event(183, 1)  # CODE press
        m.process_event(42, 1)  # Shift press
        action, char = m.process_event(16, 1)  # 'q' press
        assert action == KeyAction.UNKNOWN
        assert char == ""

    def test_code_released_letter_types_normally(self):
        m = KeyMapper()
        m.process_event(183, 1)  # CODE press
        m.process_event(183, 0)  # CODE release
        action, char = m.process_event(16, 1)  # 'q' press
        assert action == KeyAction.CHAR
        assert char == "q"

    def test_code_does_not_affect_ctrl_combos(self):
        m = KeyMapper()
        m.process_event(29, 1)  # Ctrl press
        action, _ = m.process_event(31, 1)  # 's' press
        assert action == KeyAction.SAVE
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_keymapper.py -v -k "code"`
Expected: `test_code_press_release`, `test_code_returns_unknown`, and all four `TestCodeCombos` tests FAIL with `AttributeError: 'KeyMapper' object has no attribute '_code_held'`. `test_reset_clears_held_modifiers` also FAILs on the new `_code_held` assertion.

- [ ] **Step 3: Implement `_code_held` tracking**

In `writerdeck/input/keymapper.py`, add the constant near the other `_KEY_*` constants (after `_KEY_RIGHTSHIFT = 54`):

```python
_KEY_F13 = 183  # "CODE" key on the BM43A, remapped in firmware to send this
```

In `KeyMapper.__init__` (currently `self._ctrl_held = False` / `self._shift_held = False`), add:

```python
        self._code_held = False
```

In `KeyMapper.reset()`, add the same line.

In `process_event`, immediately after the existing Shift-tracking block:

```python
        if scancode in (_KEY_LEFTSHIFT, _KEY_RIGHTSHIFT):
            self._shift_held = value != 0
            return KeyAction.UNKNOWN, ""
```

add:

```python
        if scancode == _KEY_F13:
            self._code_held = value != 0
            return KeyAction.UNKNOWN, ""
```

- [ ] **Step 4: Implement the CODE dispatch branch**

Immediately before the existing `# Ctrl combos` block (`if self._ctrl_held:`), add:

```python
        # CODE combos — key-assignment table is a deferred follow-up
        # (see docs/superpowers/specs/2026-07-16-code-layer-firmware-design.md);
        # everything is intentionally swallowed for now rather than falling
        # through to a plain character.
        if self._code_held:
            return KeyAction.UNKNOWN, ""

```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_keymapper.py -v`
Expected: all tests PASS, including the new ones and the extended `test_reset_clears_held_modifiers`.

- [ ] **Step 6: Run the full suite to confirm no regressions**

Run: `pytest -q`
Expected: all tests pass (877+ from the prior session, plus the 6 new ones here).

- [ ] **Step 7: Commit**

```bash
cd /home/ismael/projects/writer-deck
git add writerdeck/input/keymapper.py tests/test_keymapper.py
git commit -m "feat: track CODE (KEY_F13) as a third keymapper modifier

Additive only — Ctrl/Shift/plain dispatch unchanged. CODE combos
currently swallow to UNKNOWN; the actual key-assignment table is a
deferred follow-up per docs/superpowers/specs/2026-07-16-code-layer-firmware-design.md"
```

---

### Task 7: Deploy and verify on real hardware

**Files:** None (deployment + live verification).

**Interfaces:**
- Consumes: the flashed keyboard from Task 5, the updated `keymapper.py` from Task 6.

- [ ] **Step 1: Deploy**

```bash
cd /home/ismael/projects/writer-deck
./deploy.sh 192.168.1.101 pi
```
Expected: deploy script completes and reports the writer-deck service restarted.

- [ ] **Step 2: Verify CODE no longer leaks a character**

Open the app on the device (or via `journalctl -u writer-deck.service -f` on the Pi while pressing keys), hold **CODE**, press **Q**. Confirm no "q" appears in the document and no error/traceback appears in the journal.

- [ ] **Step 3: Verify existing shortcuts still work**

Press **Ctrl+S** (Save) and **Shift+Left** (Select) on the physical device. Confirm both behave exactly as before (save triggers, selection highlights) — proving the new CODE branch didn't disturb existing dispatch.

- [ ] **Step 4: Verify RGB is off**

Visually confirm the underglow LEDs are dark (they were reported "on now" before this work).

---

### Task 8: Update NEXT-STEPS.md

**Files:**
- Modify: `NEXT-STEPS.md`

**Interfaces:** None (documentation only).

- [ ] **Step 1: Update the "Function key alternatives" line**

In the "Keyboard Usability (60% keyboard)" section, replace:

```markdown
- **Function key alternatives** — consider Fn+layer combos for missing keys
```

with:

```markdown
- ~~**Function key alternatives**~~ **DONE (2026-07-16, mechanism only):** the
  BM43A's "CODE" key was reflashed from a silent QMK `MO(1)` layer-switch to a
  plain `KC_F13` keycode; `writerdeck/input/keymapper.py` now tracks it as a
  third modifier (`_code_held`) exactly like Ctrl/Shift, verified live via
  `evtest`. The actual number/symbol key-assignment table is still open —
  see `docs/superpowers/specs/2026-07-16-code-layer-firmware-design.md` and
  plan to brainstorm it next.
```

- [ ] **Step 2: Commit**

```bash
cd /home/ismael/projects/writer-deck
git add NEXT-STEPS.md
git commit -m "docs: mark CODE-layer firmware mechanism done in NEXT-STEPS, table still open"
```

---

## Self-Review Notes

- **Spec coverage:** firmware rebind + RGB disable + Bootmagic preservation (Task 2/5), Python `_code_held` tracking mirroring Ctrl/Shift (Task 6), live verification via evtest (Task 5/7), deferred key table explicitly left as a named follow-up, not implemented here (Task 6 Step 4 comment + Task 8). All spec sections have a corresponding task.
- **No placeholders:** the CODE dispatch branch's "empty table" is real, tested, working behavior (swallow-to-UNKNOWN), not a TODO — covered by `TestCodeCombos` in Task 6.
- **Type/signature consistency:** `_code_held: bool` used identically in Task 6 Steps 3-4 and its tests; `KEY_F13 = 183` used consistently across Task 5's live verification and Task 6's Python constant.
