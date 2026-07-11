"""Pygame-based keyboard reader for desktop development."""

from __future__ import annotations

import logging
import queue
from typing import Callable

import pygame

from writerdeck.input.keymapper import KeyAction, KeyMapper

logger = logging.getLogger(__name__)

# Map pygame key constants to evdev scancodes.
# This lets us reuse KeyMapper identically to the evdev path.
_PYGAME_TO_EVDEV: dict[int, int] = {
    # Row 1: Escape + numbers
    pygame.K_ESCAPE: 1,
    pygame.K_1: 2,
    pygame.K_2: 3,
    pygame.K_3: 4,
    pygame.K_4: 5,
    pygame.K_5: 6,
    pygame.K_6: 7,
    pygame.K_7: 8,
    pygame.K_8: 9,
    pygame.K_9: 10,
    pygame.K_0: 11,
    pygame.K_MINUS: 12,
    pygame.K_EQUALS: 13,
    pygame.K_BACKSPACE: 14,
    # Row 2: Tab + QWERTY
    pygame.K_TAB: 15,
    pygame.K_q: 16,
    pygame.K_w: 17,
    pygame.K_e: 18,
    pygame.K_r: 19,
    pygame.K_t: 20,
    pygame.K_y: 21,
    pygame.K_u: 22,
    pygame.K_i: 23,
    pygame.K_o: 24,
    pygame.K_p: 25,
    pygame.K_LEFTBRACKET: 26,
    pygame.K_RIGHTBRACKET: 27,
    pygame.K_RETURN: 28,
    # Row 3: Ctrl + ASDF
    pygame.K_LCTRL: 29,
    pygame.K_a: 30,
    pygame.K_s: 31,
    pygame.K_d: 32,
    pygame.K_f: 33,
    pygame.K_g: 34,
    pygame.K_h: 35,
    pygame.K_j: 36,
    pygame.K_k: 37,
    pygame.K_l: 38,
    pygame.K_SEMICOLON: 39,
    pygame.K_QUOTE: 40,
    pygame.K_BACKQUOTE: 41,
    # Row 4: Shift + ZXCV
    pygame.K_LSHIFT: 42,
    pygame.K_BACKSLASH: 43,
    pygame.K_z: 44,
    pygame.K_x: 45,
    pygame.K_c: 46,
    pygame.K_v: 47,
    pygame.K_b: 48,
    pygame.K_n: 49,
    pygame.K_m: 50,
    pygame.K_COMMA: 51,
    pygame.K_PERIOD: 52,
    pygame.K_SLASH: 53,
    pygame.K_RSHIFT: 54,
    # Space
    pygame.K_SPACE: 57,
    # Right modifiers
    pygame.K_RCTRL: 97,
    # Navigation
    pygame.K_HOME: 102,
    pygame.K_UP: 103,
    pygame.K_PAGEUP: 104,
    pygame.K_LEFT: 105,
    pygame.K_RIGHT: 106,
    pygame.K_END: 107,
    pygame.K_DOWN: 108,
    pygame.K_PAGEDOWN: 109,
    pygame.K_DELETE: 111,
}


class PygameKeyboardReader:
    """Reads keyboard input from pygame events.

    Unlike KeyboardReader and StdinReader, this does not use a background
    thread. Call poll() from the main thread each loop iteration to pump
    pygame events into the queue.
    """

    def __init__(
        self,
        on_any_key: Callable[[], None] | None = None,
    ) -> None:
        self.queue: queue.SimpleQueue[tuple[KeyAction, str]] = queue.SimpleQueue()
        self._on_any_key = on_any_key
        self._mapper = KeyMapper()

    def start(self) -> None:
        """No-op — pygame events are pumped via poll()."""

    def stop(self) -> None:
        """No-op."""

    def poll(self) -> None:
        """Pump pygame events and push key actions to queue.

        Must be called from the main thread (macOS requirement).
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.queue.put((KeyAction.QUIT, ""))
                if self._on_any_key:
                    self._on_any_key()
                continue

            # Focus loss: the window won't receive KEYUP for a modifier held
            # during Alt/Cmd-Tab, so reset the mapper to avoid a stuck modifier.
            if event.type == getattr(pygame, "WINDOWFOCUSLOST", -1):
                self._mapper.reset()
                continue
            if event.type == pygame.ACTIVEEVENT and getattr(event, "gain", 1) == 0:
                self._mapper.reset()
                continue

            if event.type == pygame.KEYDOWN:
                scancode = _PYGAME_TO_EVDEV.get(event.key)
                if scancode is not None:
                    action, char = self._mapper.process_event(scancode, 1)
                    if action != KeyAction.UNKNOWN:
                        self.queue.put((action, char))
                if self._on_any_key:
                    self._on_any_key()

            elif event.type == pygame.KEYUP:
                scancode = _PYGAME_TO_EVDEV.get(event.key)
                if scancode is not None:
                    # Feed release to mapper so modifier state stays in sync
                    self._mapper.process_event(scancode, 0)
