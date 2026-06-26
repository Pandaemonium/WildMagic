from __future__ import annotations

import pygame

from wildmagic.rendering.layout import (
    WindowLayout,
    auto_ui_scale,
    logical_mouse_event,
    toggled_ui_scale,
)


def test_window_layout_scales_base_dimensions() -> None:
    layout = WindowLayout(width=100, height=50, max_ui_scale=3)

    assert layout.scaled_size(1) == (100, 50)
    assert layout.scaled_size(2) == (200, 100)


def test_auto_ui_scale_picks_largest_desktop_fit(monkeypatch) -> None:
    layout = WindowLayout(width=100, height=100, max_ui_scale=3)
    monkeypatch.setattr(pygame.display, "get_desktop_sizes", lambda: [(300, 380)])

    assert auto_ui_scale(layout) == 3


def test_auto_ui_scale_falls_back_when_desktop_size_unavailable(monkeypatch) -> None:
    layout = WindowLayout(width=100, height=100, max_ui_scale=3)

    def raise_pygame_error() -> list[tuple[int, int]]:
        raise pygame.error("display unavailable")

    monkeypatch.setattr(pygame.display, "get_desktop_sizes", raise_pygame_error)

    assert auto_ui_scale(layout) == 1


def test_toggled_ui_scale_switches_between_base_and_max() -> None:
    layout = WindowLayout(width=100, height=100, max_ui_scale=3)

    assert toggled_ui_scale(1, layout) == 3
    assert toggled_ui_scale(2, layout) == 3
    assert toggled_ui_scale(3, layout) == 1


def test_logical_mouse_event_converts_scaled_coordinates() -> None:
    event = pygame.event.Event(
        pygame.MOUSEMOTION,
        {"pos": (24, 10), "rel": (6, -4), "buttons": (1, 0, 0)},
    )

    logical = logical_mouse_event(event, 2)

    assert logical.pos == (12, 5)
    assert logical.rel == (3, -2)
    assert logical.buttons == (1, 0, 0)


def test_logical_mouse_event_ignores_non_positional_events() -> None:
    event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_a})

    assert logical_mouse_event(event, 2) is event
