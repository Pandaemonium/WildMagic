from __future__ import annotations

import pygame

from wildmagic.rendering.layout import WINDOW_HEIGHT, WINDOW_WIDTH
from wildmagic.rendering.theme import ACCENT, PANEL_EDGE

SCROLLBAR_TRACK = (20, 22, 27)


def draw_fullscreen_backdrop(
    screen: pygame.Surface,
    color: tuple[int, int, int, int],
    *,
    width: int = WINDOW_WIDTH,
    height: int = WINDOW_HEIGHT,
) -> None:
    """Draw a translucent full-screen backdrop over the logical render surface."""

    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill(color)
    screen.blit(overlay, (0, 0))


def centered_rect(width: int, height: int) -> pygame.Rect:
    """Return a rect centered in the logical game window."""

    return pygame.Rect(
        (WINDOW_WIDTH - width) // 2,
        (WINDOW_HEIGHT - height) // 2,
        width,
        height,
    )


def draw_vertical_scrollbar(
    screen: pygame.Surface,
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    total_items: int,
    visible_items: int,
    offset: int,
    max_offset: int,
    dragging: bool = False,
    reverse: bool = False,
) -> tuple[pygame.Rect, pygame.Rect | None]:
    """Draw a standard vertical scrollbar and return its track/thumb rects.

    ``reverse`` maps offset zero to the bottom of the track, matching the game log
    where offset zero means "newest messages visible".
    """

    track = pygame.Rect(x, y, width, height)
    pygame.draw.rect(screen, SCROLLBAR_TRACK, track, border_radius=4)
    if total_items <= visible_items or max_offset <= 0:
        return track, None

    thumb_height = max(28, int(height * (visible_items / total_items)))
    usable = max(1, height - thumb_height)
    offset_fraction = offset / max_offset
    if reverse:
        thumb_y = y + usable - int(usable * offset_fraction)
    else:
        thumb_y = y + int(usable * offset_fraction)
    thumb = pygame.Rect(x, thumb_y, width, thumb_height)
    thumb_color = ACCENT if dragging else PANEL_EDGE
    pygame.draw.rect(screen, thumb_color, thumb, border_radius=4)
    return track, thumb
