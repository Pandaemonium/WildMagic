from __future__ import annotations

from types import SimpleNamespace

import pygame

from wildmagic.models import FLOOR
from wildmagic.rendering.inspect_tooltip import draw_inspect_tooltip


class FakeRenderedText:
    def __init__(self, text: str) -> None:
        self.text = text

    def get_width(self) -> int:
        return len(self.text) * 8


class FakeFont:
    def __init__(self) -> None:
        self.rendered: list[str] = []

    def get_linesize(self) -> int:
        return 14

    def render(
        self, text: str, _antialias: bool, _color: tuple[int, int, int]
    ) -> FakeRenderedText:
        self.rendered.append(text)
        return FakeRenderedText(text)


class FakeScreen:
    def __init__(self) -> None:
        self.blits: list[tuple[object, tuple[int, int]]] = []

    def blit(self, surface: object, pos: tuple[int, int]) -> None:
        self.blits.append((surface, pos))


class FakeEngine:
    def __init__(self, state: SimpleNamespace, explored: bool = True) -> None:
        self.state = state
        self.explored = explored

    def is_explored(self, _x: int, _y: int) -> bool:
        return self.explored

    def is_visible(self, _x: int, _y: int) -> bool:
        return True

    def room_profile_at(self, _x: int, _y: int):
        return None


def _entity(**overrides) -> SimpleNamespace:
    values = {
        "id": "book1",
        "x": 1,
        "y": 1,
        "alive": True,
        "kind": "prop",
        "statuses": set(),
        "char": "?",
        "name": "ancient tome",
        "tags": {"book"},
        "details": {"title_materialized": True, "summary_materialized": True},
        "description": "A useful description of the old book.",
        "item_type": None,
        "material": None,
        "hp": 1,
        "max_hp": 1,
        "mana": 0,
        "max_mana": 0,
        "faction": "neutral",
        "status_display": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _host(explored: bool = True) -> SimpleNamespace:
    player = _entity(
        id="player",
        x=1,
        y=0,
        kind="actor",
        char="@",
        name="player",
        tags=set(),
        details={},
        hp=10,
        max_hp=10,
        mana=5,
        max_mana=5,
    )
    book = _entity()
    state = SimpleNamespace(
        tiles=[
            [FLOOR, FLOOR, FLOOR],
            [FLOOR, FLOOR, FLOOR],
            [FLOOR, FLOOR, FLOOR],
        ],
        tile_tags={"1,1": ["dusty"]},
        entities={"player": player, "book1": book},
        player=player,
        player_id="player",
        npc_profiles={},
        canon_records={},
        target_x=None,
        target_y=None,
    )
    return SimpleNamespace(
        inspect_tile=(1, 1),
        inspect_button_rects=[],
        engine=FakeEngine(state, explored=explored),
        screen=FakeScreen(),
        small_font=FakeFont(),
    )


def test_draw_inspect_tooltip_clears_unexplored_tile() -> None:
    host = _host(explored=False)

    draw_inspect_tooltip(host)

    assert host.inspect_tile is None
    assert host.inspect_button_rects == []
    assert host.screen.blits == []


def test_draw_inspect_tooltip_builds_book_and_target_buttons(monkeypatch) -> None:
    monkeypatch.setattr(pygame.draw, "rect", lambda *_args, **_kwargs: None)
    host = _host()

    draw_inspect_tooltip(host)

    rendered = host.small_font.rendered
    commands = [command for _rect, command in host.inspect_button_rects]
    assert any("Floor" in text for text in rendered)
    assert "  [ Read ]" in rendered
    assert "  [ Investigate ]" in rendered
    assert "  [ + Target this ]" in rendered
    assert commands == ["read ancient tome", "investigate book1", "target 1 1"]
