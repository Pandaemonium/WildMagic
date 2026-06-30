from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pygame


@dataclass(frozen=True)
class RenderContext:
    """Small rendering-facing view of the Pygame host.

    This keeps frame-level renderers from reaching through the full ``GameUI``
    object when they only need drawing surfaces, fonts, engine state, and current
    overlay text.
    """

    screen: pygame.Surface
    tile_font: pygame.font.Font
    small_font: pygame.font.Font
    engine: Any
    command_label: str
    autoplay_overlay_lines: list[tuple[str, tuple[int, int, int]]]

    @classmethod
    def from_host(cls, host: Any) -> "RenderContext":
        return cls(
            screen=host.screen,
            tile_font=host.tile_font,
            small_font=host.small_font,
            engine=host.engine,
            command_label=host._command_label,
            autoplay_overlay_lines=host.autoplay.overlay_lines(),
        )
