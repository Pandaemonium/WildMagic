from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pygame


TILE_SIZE = 18
MAP_PIXEL_WIDTH = 42 * TILE_SIZE
MAP_PIXEL_HEIGHT = 28 * TILE_SIZE
PANEL_WIDTH = 430
LLM_PANEL_WIDTH = 520
MAP_OFFSET_X = LLM_PANEL_WIDTH
WINDOW_WIDTH = LLM_PANEL_WIDTH + MAP_PIXEL_WIDTH + PANEL_WIDTH
WINDOW_HEIGHT = 800

# Largest integer UI scale the toggle offers. Auto-detection only selects it when
# the desktop can actually fit the scaled-up window.
MAX_UI_SCALE = 2


@dataclass(frozen=True)
class WindowLayout:
    width: int = WINDOW_WIDTH
    height: int = WINDOW_HEIGHT
    max_ui_scale: int = MAX_UI_SCALE

    def scaled_size(self, ui_scale: int) -> tuple[int, int]:
        return self.width * ui_scale, self.height * ui_scale


DEFAULT_WINDOW_LAYOUT = WindowLayout()


def auto_ui_scale(layout: WindowLayout = DEFAULT_WINDOW_LAYOUT) -> int:
    """Pick the largest integer UI scale that fits the primary desktop.

    The calculation leaves headroom for the taskbar and title bar. A 4K display
    can usually fit the 2x window; 1080p/1440p displays generally stay at 1x and
    let the user opt into 2x via the toggle.

    Requires pygame.display to be initialised; falls back to 1x if unavailable.
    """
    try:
        desktop_w, desktop_h = pygame.display.get_desktop_sizes()[0]
    except (pygame.error, IndexError, AttributeError):
        return 1
    usable_h = desktop_h - 80
    scale = 1
    for candidate in range(2, layout.max_ui_scale + 1):
        candidate_w, candidate_h = layout.scaled_size(candidate)
        if candidate_w <= desktop_w and candidate_h <= usable_h:
            scale = candidate
    return scale


def toggled_ui_scale(
    current_scale: int, layout: WindowLayout = DEFAULT_WINDOW_LAYOUT
) -> int:
    return 1 if current_scale >= layout.max_ui_scale else layout.max_ui_scale


def logical_mouse_event(event: pygame.event.Event, ui_scale: int) -> pygame.event.Event:
    if not hasattr(event, "pos"):
        return event
    attributes: dict[str, Any] = event.dict.copy()
    attributes["pos"] = tuple(coordinate // ui_scale for coordinate in event.pos)
    if "rel" in attributes:
        attributes["rel"] = tuple(
            coordinate / ui_scale for coordinate in attributes["rel"]
        )
    return pygame.event.Event(event.type, attributes)


def logical_mouse_pos(ui_scale: int) -> tuple[int, int]:
    return tuple(coordinate // ui_scale for coordinate in pygame.mouse.get_pos())
