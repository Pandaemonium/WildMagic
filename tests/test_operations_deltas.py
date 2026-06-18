"""Operation primitives + state deltas (Stage 6 of the state-surface plan).

A successful cast records a StateDelta per mutation on WildMagicOutcome.deltas; a cast that
rolls back records none. Lets tests assert applied behavior without parsing message text.
"""

from __future__ import annotations

import json

from wildmagic import operations
from wildmagic.actions import GameSession
from wildmagic.engine import GameEngine


def _engine_with_enemy():
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    enemy = engine.spawn_actor(
        "goblin",
        "g",
        player.x + 1,
        player.y,
        hp=12,
        attack=2,
        defense=0,
        faction="enemy",
        ai="hunt",
    )
    return engine, player, enemy


def _resolution(effects, costs=None):
    return {
        "accepted": True,
        "severity": "moderate",
        "outcome_text": "The wild magic answers.",
        "effects": effects,
        "costs": costs or [],
        "rejected_reason": None,
    }


class _FixedProvider:
    name = "fixed"

    def __init__(self, payload: dict):
        self.payload = payload

    def resolve(self, spell: str, context: dict) -> str:
        return json.dumps(self.payload)


def test_multi_effect_cast_records_a_sequence_of_deltas() -> None:
    engine, player, enemy = _engine_with_enemy()

    outcome = engine.apply_wild_magic_resolution(
        _resolution(
            [
                {
                    "type": "damage",
                    "target": enemy.id,
                    "amount": 4,
                    "damage_type": "fire",
                },
                {
                    "type": "add_status",
                    "target": enemy.id,
                    "status": "burning",
                    "duration": 3,
                },
                {
                    "type": "create_tile",
                    "x": player.x + 2,
                    "y": player.y,
                    "tile": "fire",
                },
            ]
        )
    )

    ops = [d["op"] for d in outcome.deltas]
    assert ops == ["damage", "status", "create_tile"]
    damage = outcome.deltas[0]
    assert damage["target"] == enemy.id
    assert damage["details"]["dealt"] > 0
    assert outcome.deltas[1]["details"]["status"] == "burning"


def test_no_capture_outside_a_cast() -> None:
    # Mutators used outside apply_wild_magic_resolution record nothing (capture is off).
    engine, _player, enemy = _engine_with_enemy()
    engine.damage_entity(enemy, 3, "fire")
    assert engine._delta_log == []


def test_rollback_discards_deltas(monkeypatch) -> None:
    engine, player, enemy = _engine_with_enemy()

    def fail_after_mutation(effect: dict) -> list[str]:
        engine.damage_entity(enemy, 5, "fire")  # a partial mutation + a recorded delta
        raise RuntimeError("boom")

    monkeypatch.setattr(engine, "_apply_effect", fail_after_mutation)

    outcome = engine.apply_wild_magic_resolution(
        _resolution([{"type": "damage", "target": enemy.id, "amount": 5}])
    )

    assert outcome.technical_failure is True
    assert outcome.deltas == []  # nothing leaks out of a rolled-back cast
    assert engine._delta_log == []


def test_operations_primitives_apply_and_record() -> None:
    engine, _player, enemy = _engine_with_enemy()
    engine.begin_delta_capture()

    operations.apply_damage(engine, enemy, 3, "frost")
    operations.apply_status(engine, enemy, "frozen", 2)

    ops = [d.op for d in engine._delta_log]
    assert ops == ["damage", "status"]
    assert enemy.statuses.get("frozen") == 2


def test_session_records_wild_magic_deltas_for_replay() -> None:
    provider = _FixedProvider(
        _resolution(
            [
                {
                    "type": "add_status",
                    "target": "nearest_enemy",
                    "status": "burning",
                    "duration": 3,
                }
            ]
        )
    )
    session = GameSession(seed=7, scenario="test_chamber", provider=provider)

    result = session.cast_wild("set the nearest enemy burning")

    assert result.wild_magic is not None
    assert result.wild_magic["deltas"][0]["op"] == "status"
    assert session.records[-1]["wild_magic"]["deltas"] == result.wild_magic["deltas"]
