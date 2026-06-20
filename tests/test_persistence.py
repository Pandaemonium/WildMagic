from __future__ import annotations

import json

from wildmagic.actions import GameSession, summarize_state
from wildmagic.engine import GameEngine
from wildmagic.persistence import (
    engine_from_snapshot,
    engine_to_snapshot,
    session_from_snapshot,
    session_to_snapshot,
)
from wildmagic.semantics import place_anchor


def _json_round_trip(data: dict) -> dict:
    return json.loads(json.dumps(data, sort_keys=True))


def test_engine_snapshot_round_trips_full_state_and_runtime() -> None:
    engine = GameEngine(seed=11, scenario="dungeon", provider_name="mock")
    player = engine.state.player
    engine.record_note(
        place_anchor(player.x, player.y),
        "the flagstones hum in a key nobody admits knowing",
        kind="mood",
        source="test",
        salience=4,
    )
    engine.state.add_message("Careful now.", is_danger=True)
    engine.set_target(player.x, player.y)
    engine._save_dungeon_floor(engine.state.depth)

    snapshot = _json_round_trip(engine_to_snapshot(engine))
    restored = engine_from_snapshot(snapshot, provider_name="mock")

    assert restored.validate_state() == []
    assert summarize_state(restored) == summarize_state(engine)
    assert restored.state.messages[-1].is_danger is True
    assert restored.state.semantics.for_anchors(
        [place_anchor(player.x, player.y)], turn=restored.state.turn
    )[0].text.startswith("the flagstones hum")
    assert set(restored.state.dungeon_floors) == set(engine.state.dungeon_floors)
    assert restored.next_entity_id("actor") == engine.next_entity_id("actor")
    assert restored.rng.randint(1, 1_000_000) == engine.rng.randint(1, 1_000_000)


def test_restored_session_continues_like_original(monkeypatch) -> None:
    monkeypatch.setenv("WILDMAGIC_CANON_PREWARM_ENABLED", "0")
    session = GameSession(
        seed=7,
        scenario="test_chamber",
        provider_name="mock",
        dialogue_provider_name="mock",
        lore_provider_name="mock",
        flesh_provider_name="mock",
        canon_provider_name="mock",
        deed_interpreter_provider_name="off",
    )
    try:
        session.execute_command("open")
        snapshot = _json_round_trip(session_to_snapshot(session))
        restored = session_from_snapshot(snapshot, provider_name="mock")
        try:
            for command in ("wait", "spark", "wait"):
                left = session.execute_command(command)
                right = restored.execute_command(command)
                assert right.to_record() == left.to_record()
                assert summarize_state(restored.engine) == summarize_state(
                    session.engine
                )
        finally:
            restored.close()
    finally:
        session.close()
