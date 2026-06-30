from __future__ import annotations

import pygame

from wildmagic.rendering.layout import WINDOW_HEIGHT, WINDOW_WIDTH
from wildmagic.rendering.primitives import centered_rect, draw_fullscreen_backdrop


class FakeScreen:
    def __init__(self) -> None:
        self.blits: list[tuple[object, tuple[int, int]]] = []

    def blit(self, surface: object, pos: tuple[int, int]) -> None:
        self.blits.append((surface, pos))


class FakeSurface:
    def __init__(self, size: tuple[int, int]) -> None:
        self.size = size
        self.fills: list[tuple[int, int, int, int]] = []

    def fill(self, color: tuple[int, int, int, int]) -> None:
        self.fills.append(color)


def test_draw_fullscreen_backdrop_blits_translucent_surface(monkeypatch) -> None:
    surfaces: list[FakeSurface] = []

    def surface(size: tuple[int, int], _flags: int) -> FakeSurface:
        result = FakeSurface(size)
        surfaces.append(result)
        return result

    monkeypatch.setattr(pygame, "Surface", surface)
    screen = FakeScreen()

    draw_fullscreen_backdrop(screen, (1, 2, 3, 4))

    assert surfaces[0].size == (WINDOW_WIDTH, WINDOW_HEIGHT)
    assert surfaces[0].fills == [(1, 2, 3, 4)]
    assert screen.blits == [(surfaces[0], (0, 0))]


def test_centered_rect_uses_logical_window_center() -> None:
    rect = centered_rect(600, 400)

    assert rect.size == (600, 400)
    assert rect.center == (WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)
