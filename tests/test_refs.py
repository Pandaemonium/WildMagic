"""Normalized refs + selectors (Stage 3 of the state-surface plan).

Covers: normalize_ref classification, the bind_* resolvers (entity/tile/room/faction/
selector and legacy raw strings), legacy parity through engine.resolve_target*, and
end-to-end effect application via typed entity and tile refs. Explicit invalid typed refs
fail the cast transactionally; legacy strings keep their old forgiving behavior.
"""

from __future__ import annotations

from wildmagic import refs
from wildmagic.engine import GameEngine
from wildmagic.models import FIRE


def _engine():
    engine = GameEngine(seed=11, scenario="test_chamber")
    player = engine.state.player
    enemy = engine.spawn_actor(
        "cave spider",
        "s",
        player.x + 2,
        player.y,
        hp=8,
        attack=2,
        defense=0,
        faction="enemy",
        ai="hunt",
    )
    return engine, player, enemy


# --- normalize_ref -----------------------------------------------------------------------


def test_normalize_ref_classifies_each_shape() -> None:
    assert refs.normalize_ref("nearest_enemy") == refs.Ref(
        kind="raw", raw="nearest_enemy"
    )
    assert refs.normalize_ref(None) == refs.Ref(kind="raw", raw="")
    assert refs.normalize_ref({"kind": "entity", "id": "actor_3"}) == refs.Ref(
        kind="entity", id="actor_3"
    )
    assert refs.normalize_ref({"kind": "tile", "x": 12, "y": 8}) == refs.Ref(
        kind="tile", x=12, y=8
    )
    assert refs.normalize_ref({"kind": "room", "id": "room_2"}) == refs.Ref(
        kind="room", id="room_2"
    )
    assert refs.normalize_ref({"kind": "faction", "id": "Empire"}) == refs.Ref(
        kind="faction", id="empire"
    )
    assert refs.normalize_ref({"selector": "nearest_enemy"}) == refs.Ref(
        kind="selector", selector="nearest_enemy"
    )
    # Untagged dicts are inferred from their keys.
    assert refs.normalize_ref({"x": 1, "y": 2}).kind == "tile"
    assert refs.normalize_ref({"id": "actor_9"}).kind == "entity"
    # An already-built ref passes through untouched.
    tile = refs.Ref(kind="tile", x=1, y=1)
    assert refs.normalize_ref(tile) is tile


def test_normalize_ref_handles_uncoercible_tile_coords() -> None:
    ref = refs.normalize_ref({"kind": "tile", "x": "nope", "y": 4})
    assert ref.kind == "tile" and ref.x is None and ref.y == 4


# --- bind_ref ----------------------------------------------------------------------------


def test_bind_ref_entity_and_selector_and_raw() -> None:
    engine, player, enemy = _engine()

    assert (
        refs.bind_ref(engine, refs.normalize_ref({"kind": "entity", "id": enemy.id}))
        is enemy
    )
    assert (
        refs.bind_ref(engine, refs.normalize_ref({"selector": "nearest_enemy"}))
        is enemy
    )
    assert refs.bind_ref(engine, refs.normalize_ref("player")) is player
    # A tile ref binds to the living occupant of that square.
    assert (
        refs.bind_ref(
            engine, refs.normalize_ref({"kind": "tile", "x": enemy.x, "y": enemy.y})
        )
        is enemy
    )


def test_bind_ref_invalid_entity_is_none() -> None:
    engine, _player, _enemy = _engine()
    assert (
        refs.bind_ref(engine, refs.normalize_ref({"kind": "entity", "id": "nope_999"}))
        is None
    )


# --- bind_position -----------------------------------------------------------------------


def test_bind_position_tile_entity_and_room() -> None:
    engine, player, enemy = _engine()

    assert refs.bind_position(
        engine, refs.normalize_ref({"kind": "tile", "x": 5, "y": 6})
    ) == (5, 6)
    assert refs.bind_position(
        engine, refs.normalize_ref({"kind": "entity", "id": enemy.id})
    ) == (
        enemy.x,
        enemy.y,
    )
    room = engine.room_profile_at(player.x, player.y)
    assert room is not None
    assert refs.bind_position(
        engine, refs.normalize_ref({"kind": "room", "id": room.id})
    ) == (
        room.center[0],
        room.center[1],
    )


def test_bind_position_selected_tile_for_bare_mark() -> None:
    engine, player, _enemy = _engine()
    tx, ty = player.x, player.y + 3
    assert engine.set_target(tx, ty) is True  # bare tile, no occupant
    # The selected-target keyword resolves to the marked square.
    assert refs.bind_position(engine, refs.normalize_ref("there")) == (tx, ty)


def test_bind_position_clamps_out_of_bounds_tile() -> None:
    engine, _player, _enemy = _engine()
    pos = refs.bind_position(
        engine, refs.normalize_ref({"kind": "tile", "x": 99999, "y": -5})
    )
    assert pos == (engine.state.width - 1, 0)


def test_typed_ref_error_rejects_invalid_explicit_refs() -> None:
    engine, _player, _enemy = _engine()

    assert (
        refs.typed_ref_error(engine, {"kind": "entity", "id": "nope_999"})
        == "unknown entity ref: nope_999"
    )
    assert (
        refs.typed_ref_error(engine, {"kind": "tile", "x": 99999, "y": -5})
        == "tile ref out of bounds: 99999,-5"
    )
    assert (
        refs.typed_ref_error(engine, {"selector": "not_a_real_selector"})
        == "unknown selector ref: not_a_real_selector"
    )


# --- bind_group --------------------------------------------------------------------------


def test_bind_group_selectors_and_faction() -> None:
    engine, _player, enemy = _engine()

    assert enemy in refs.bind_group(engine, refs.normalize_ref("all_enemies"))
    assert enemy in refs.bind_group(
        engine, refs.normalize_ref({"kind": "faction", "id": "enemy"})
    )
    # An entity ref becomes a singleton group.
    assert refs.bind_group(
        engine, refs.normalize_ref({"kind": "entity", "id": enemy.id})
    ) == [enemy]
    # Faction with no members is empty (no partial / bogus binding).
    assert (
        refs.bind_group(engine, refs.normalize_ref({"kind": "faction", "id": "nobody"}))
        == []
    )


# --- legacy parity through the engine ----------------------------------------------------


def test_engine_resolve_target_still_accepts_legacy_strings() -> None:
    engine, player, enemy = _engine()
    assert engine.resolve_target("player") is player
    assert engine.resolve_target("nearest_enemy") is enemy
    assert engine.resolve_target(enemy.id) is enemy
    assert enemy in engine.resolve_target_group("all_enemies")


# --- end-to-end effect application -------------------------------------------------------


def test_damage_effect_accepts_typed_entity_ref() -> None:
    engine, _player, enemy = _engine()
    before = enemy.hp

    engine._apply_effect(
        {"type": "damage", "target": {"kind": "entity", "id": enemy.id}, "amount": 3}
    )

    assert enemy.hp < before


def test_create_tile_effect_accepts_typed_tile_ref() -> None:
    engine, player, _enemy = _engine()
    tx, ty = player.x + 1, player.y

    engine._apply_effect(
        {
            "type": "create_tile",
            "target": {"kind": "tile", "x": tx, "y": ty},
            "tile": "fire",
        }
    )

    assert engine.tile_at(tx, ty) == FIRE


def test_invalid_entity_ref_fails_transactionally_without_mutating() -> None:
    engine, _player, enemy = _engine()
    before = enemy.hp

    outcome = engine.apply_wild_magic_resolution(
        {
            "accepted": True,
            "severity": "minor",
            "outcome_text": "The spell reaches for a missing thing.",
            "effects": [
                {
                    "type": "damage",
                    "target": {"kind": "entity", "id": "nope_999"},
                    "amount": 5,
                }
            ],
            "costs": [],
            "rejected_reason": None,
        }
    )

    assert outcome.technical_failure is True
    assert outcome.consumed_turn is False
    assert enemy.hp == before
    assert "unknown entity ref" in outcome.messages[0]
