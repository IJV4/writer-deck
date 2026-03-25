"""Pygame-based display driver for desktop development."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

import pygame

from writerdeck.display.driver import WIDTH, HEIGHT

logger = logging.getLogger(__name__)


class PygameDriver:
    """Displays rendered frames in an 800x480 pygame window."""

    def __init__(self) -> None:
        self._screen: pygame.Surface | None = None
        self._sleeping = False

    def init(self) -> None:
        if self._screen is None:
            pygame.init()
            self._screen = pygame.display.set_mode((WIDTH, HEIGHT))
            pygame.display.set_caption("Writer Deck")
            pygame.key.set_repeat(500, 100)
            logger.info("PygameDriver initialized (%dx%d)", WIDTH, HEIGHT)
        self._sleeping = False

    def display_full(self, image: Image.Image) -> None:
        self._blit(image)

    def display_full_4gray(self, image: Image.Image) -> None:
        self._blit(image)

    def display_partial(self, image: Image.Image) -> None:
        self._blit(image)

    def wake(self) -> None:
        self._sleeping = False

    def sleep(self) -> None:
        self._sleeping = True
        if self._screen is not None:
            self._screen.fill((128, 128, 128))
            pygame.display.flip()
        logger.info("PygameDriver sleeping")

    def close(self) -> None:
        pygame.quit()
        self._screen = None
        logger.info("PygameDriver closed")

    def _blit(self, image: Image.Image) -> None:
        if self._screen is None:
            return
        self._sleeping = False
        rgb = image.convert("RGB")
        surface = pygame.image.fromstring(rgb.tobytes(), (WIDTH, HEIGHT), "RGB")
        self._screen.blit(surface, (0, 0))
        pygame.display.flip()
