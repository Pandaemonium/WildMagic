"""Smoke tests for the alternative starting hubs (besides Hollowmere).

Each new start scenario is a single calm/dense surface zone living in its own
Region, with a stair down into that region's themed dungeon. These tests assert
the structural invariants the generators promise: a player, a reachable down-stair,
the right Region, and the per-zone character (trading hub vs. dense dungeon vs.
book/investigation hub). See generation.py and docs/AESTHETICS_AND_TONE.md.
"""

from __future__ import annotations

from collections import deque

from wildmagic.engine import GameEngine
from wildmagic.models import BLOCKING_TILES, DOOR, STAIRS_DOWN


def _stair_pos(engine: GameEngine) -> tuple[int, int] | None:
    for y, row in enumerate(engine.state.tiles):
        for x, tile in enumerate(row):
            if tile == STAIRS_DOWN:
                return x, y
    return None


def _reachable(engine: GameEngine, goal: tuple[int, int]) -> bool:
    player = engine.state.player
    start = (player.x, player.y)
    queue: deque[tuple[int, int]] = deque([start])
    seen = {start}
    while queue:
        x, y = queue.popleft()
        if (x, y) == goal:
            return True
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) in seen or not engine.in_bounds(nx, ny):
                continue
            tile = engine.state.tiles[ny][nx]
            if tile in BLOCKING_TILES and tile != DOOR:
                continue
            seen.add((nx, ny))
            queue.append((nx, ny))
    return False


def _counts(engine: GameEngine) -> dict[str, int]:
    entities = engine.state.entities.values()
    return {
        "npcs": sum(1 for e in entities if e.kind == "npc"),
        "enemies": sum(
            1 for e in entities if e.kind == "actor" and e.faction == "enemy"
        ),
        "props": sum(1 for e in entities if e.kind == "prop"),
        "books": sum(
            1 for e in entities if e.kind == "prop" and e.details.get("book_seed")
        ),
    }


def test_each_hub_has_player_and_reachable_stair() -> None:
    for scenario, region_id in (
        ("bazaar", "saltmarket"),
        ("warren", "warren"),
        ("archive", "stacks"),
    ):
        for seed in (1, 7, 42, 1000):
            engine = GameEngine(seed=seed, scenario=scenario)
            assert engine.state.player_id in engine.state.entities
            assert engine.region.id == region_id
            stair = _stair_pos(engine)
            assert stair is not None, (scenario, seed, "no down-stair")
            assert _reachable(engine, stair), (scenario, seed, "stair unreachable")


def test_bazaar_is_a_calm_trading_hub() -> None:
    engine = GameEngine(seed=7, scenario="bazaar")
    counts = _counts(engine)
    # A bazaar is merchants, not monsters: several NPCs, no scripted enemies on arrival.
    assert counts["npcs"] >= 4
    assert counts["enemies"] == 0
    # Named anchors are present and carry wares to trade.
    profiles = engine.state.npc_profiles.values()
    assert any(p.name == "Saffira Doss" and p.wares for p in profiles)


def test_warren_is_a_dense_dungeon_with_a_safe_entry() -> None:
    engine = GameEngine(seed=7, scenario="warren")
    counts = _counts(engine)
    # Dense: many adjoining rooms thick with props and enemies.
    assert counts["enemies"] >= 8
    assert counts["props"] >= 20
    assert len(engine.state.room_profiles) >= 12
    # The player's own starting tile is not occupied by an enemy (safe entry pocket).
    player = engine.state.player
    on_player = [
        e
        for e in engine.state.entities.values()
        if e.faction == "enemy" and (e.x, e.y) == (player.x, player.y)
    ]
    assert not on_player


def test_archive_offers_books_and_investigation() -> None:
    engine = GameEngine(seed=7, scenario="archive")
    counts = _counts(engine)
    assert counts["npcs"] >= 4
    assert counts["enemies"] == 0
    assert counts["books"] >= 3
    # Investigation: at least one room hides a searchable secret slot.
    secret_slots = sum(len(p.secret_slots) for p in engine.state.room_profiles.values())
    assert secret_slots >= 1


def test_hub_descent_keeps_the_region() -> None:
    # Standing on the stair and descending should drop into the same Region's
    # themed dungeon, not reset to the frontier.
    engine = GameEngine(seed=7, scenario="archive")
    stair = _stair_pos(engine)
    assert stair is not None
    player = engine.state.player
    player.x, player.y = stair
    assert engine.descend_stairs()
    assert engine.state.depth == 2
    assert engine.region.id == "stacks"
