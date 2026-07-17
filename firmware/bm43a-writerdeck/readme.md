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
