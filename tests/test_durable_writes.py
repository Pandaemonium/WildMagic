"""Durable world-memory lanes (Stage 7 of the state-surface plan).

Lasting world changes land in distinct systems: entity traits, place/faction/world semantic
notes, promises, and faction standing. Semantic-only writes never touch mechanical state.
"""

from __future__ import annotations

from wildmagic import operations as ops
from wildmagic.engine import GameEngine
from wildmagic.semantics import entity_anchor, place_anchor


def _engine():
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    enemy = engine.spawn_actor(
        "goblin",
        "g",
        player.x + 1,
        player.y,
        hp=8,
        attack=2,
        defense=0,
        faction="enemy",
        ai="hunt",
    )
    return engine, player, enemy


def test_add_trait_effect_uses_entity_lane_and_records_delta() -> None:
    engine, _player, enemy = _engine()

    outcome = engine.apply_wild_magic_resolution(
        {
            "accepted": True,
            "severity": "minor",
            "outcome_text": "A mark settles on it.",
            "effects": [
                {"type": "add_trait", "target": enemy.id, "text": "branded a coward"}
            ],
            "costs": [],
            "rejected_reason": None,
        }
    )

    assert "branded a coward" in enemy.traits
    assert any(d["op"] == "trait" and d["target"] == enemy.id for d in outcome.deltas)
    # And it is also retrievable from the semantic ledger under the entity anchor.
    notes = engine.state.semantics.for_anchors(
        [entity_anchor(enemy.id)], turn=engine.state.turn
    )
    assert any("coward" in n.text for n in notes)


def test_distinct_durable_lanes_write_to_distinct_stores() -> None:
    engine, player, enemy = _engine()
    promises_before = len(engine.state.promises)
    engine.begin_delta_capture()

    ops.write_trait(engine, enemy, "smells of brimstone")  # entity lane
    ops.write_place_note(engine, player.x, player.y, "remembers my name")  # place lane
    ops.adjust_faction(engine, "empire", "fear", 0.3)  # faction lane
    engine._apply_effect(
        {
            "type": "create_promise",
            "kind": "rumor",
            "subject": "a favor owed",
            "text": "the captain owes me a favor",
        }
    )  # promise lane

    # Entity trait -> on the entity (not in promises/place).
    assert "smells of brimstone" in enemy.traits
    # Place note -> in the ledger under the place anchor.
    place_notes = engine.state.semantics.for_anchors(
        [place_anchor(player.x, player.y)], turn=engine.state.turn
    )
    assert any("remembers my name" in n.text for n in place_notes)
    # Faction standing -> moved on the ledger.
    assert engine.state.faction_ledger.factions["empire"] is not None
    # Promise -> a new promise in the ledger, not a trait or a note.
    assert len(engine.state.promises) == promises_before + 1

    ops_seen = {d.op for d in engine._delta_log}
    assert {"trait", "note", "faction"} <= ops_seen


def test_semantic_note_does_not_change_mechanical_state() -> None:
    engine, player, _enemy = _engine()
    hp_before, mana_before = player.hp, player.mana
    flags_before = dict(engine.state.flags)

    engine.begin_delta_capture()
    ops.write_world_note(engine, "the sky cracked here once")

    assert player.hp == hp_before
    assert player.mana == mana_before
    assert engine.state.flags == flags_before  # purely additive to the ledger
