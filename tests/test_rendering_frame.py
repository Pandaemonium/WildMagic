from __future__ import annotations

from types import SimpleNamespace

from wildmagic.rendering.frame import draw_game_frame
from wildmagic.rendering.theme import BACKGROUND


class FakeScreen:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.fills: list[tuple[int, int, int]] = []

    def fill(self, color: tuple[int, int, int]) -> None:
        self.calls.append("fill")
        self.fills.append(color)


class FakeHost:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.screen = FakeScreen(self.calls)
        self.inspect_tile = None
        self.menu_active = False
        self.book_popup = None
        self.queue_debug_active = False
        self.awaiting_command = False
        self.scene = None

    def _active_scene(self):
        return self.scene

    def _awaiting_command(self) -> bool:
        return self.awaiting_command

    def draw_llm_panel(self) -> None:
        self.calls.append("llm")

    def draw_map(self) -> None:
        self.calls.append("map")

    def draw_panel(self) -> None:
        self.calls.append("panel")

    def draw_autoplay_overlay(self) -> None:
        self.calls.append("autoplay")

    def draw_resolving_indicator(self) -> None:
        self.calls.append("resolving")

    def draw_inspect_tooltip(self) -> None:
        self.calls.append("inspect")

    def draw_curse_tooltip(self) -> None:
        self.calls.append("curse")

    def draw_menu(self) -> None:
        self.calls.append("menu")

    def draw_book_popup(self) -> None:
        self.calls.append("book")

    def draw_queue_debug(self) -> None:
        self.calls.append("queue")


def test_draw_game_frame_composes_base_view_in_order() -> None:
    host = FakeHost()

    draw_game_frame(host)

    assert host.screen.fills == [BACKGROUND]
    assert host.calls == [
        "fill",
        "llm",
        "map",
        "panel",
        "autoplay",
        "curse",
    ]


def test_draw_game_frame_draws_active_overlays_after_base_view() -> None:
    host = FakeHost()
    host.awaiting_command = True
    host.inspect_tile = (1, 2)
    host.menu_active = True
    host.book_popup = {"title": "Book"}
    host.queue_debug_active = True

    draw_game_frame(host)

    assert host.calls == [
        "fill",
        "llm",
        "map",
        "panel",
        "autoplay",
        "resolving",
        "inspect",
        "curse",
        "menu",
        "book",
        "queue",
    ]


def test_draw_game_frame_delegates_to_active_scene() -> None:
    host = FakeHost()
    scene_calls: list[str] = []
    host.scene = SimpleNamespace(draw=lambda: scene_calls.append("scene"))

    draw_game_frame(host)

    assert scene_calls == ["scene"]
    assert host.calls == []
