from __future__ import annotations

import pygame


def draw_text(
    screen: pygame.Surface,
    text: str,
    x: int,
    y: int,
    font: pygame.font.Font,
    color: tuple[int, int, int],
) -> int:
    """Render one text line and return the next baseline y position."""
    surface = font.render(text, True, color)
    screen.blit(surface, (x, y))
    return y + surface.get_height() + 2
