from __future__ import annotations

from wildmagic.actions import describe_state, summarize_state
from wildmagic.engine import GameEngine
from wildmagic.models import CanonRecord, STAIRS_DOWN


def test_room_profiles_feed_context_and_headless_inspect() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    state = engine.state
    current_room = engine.room_profile_at(state.player.x, state.player.y)

    assert current_room is not None
    assert current_room.room_type
    assert current_room.topics
    assert state.tile_rooms[f"{state.player.x},{state.player.y}"] == current_room.id

    context = engine.context_for_llm("make the room remember its oldest book")
    assert context["current_room"]["id"] == current_room.id
    assert any(room["id"] == current_room.id for room in context["nearby_rooms"])

    inspect_lines = describe_state(engine)
    assert any(line.startswith("Current room:") and current_room.room_type in line for line in inspect_lines)
    assert any(line.startswith("Visible rooms:") and current_room.room_type in line for line in inspect_lines)


def test_canon_records_are_retrieved_by_room_threads_and_summarized() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    room = engine.room_profile_at(engine.state.player.x, engine.state.player.y)
    assert room is not None

    record = engine.add_canon_record(
        CanonRecord(
            id="canon_test_book",
            kind="book",
            attachment={"kind": "room", "room_id": room.id},
            title="The Bell That Learned Rain",
            text="A water-stained book insists a chapel north of town still rings when storms come.",
            summary="A chapel is said to ring in storms.",
            tags=[room.topics[0], "chapel", "rain"],
            source="mock",
            seed_packet={"room_id": room.id},
            turn_created=engine.state.turn,
        )
    )

    assert record.status == "canonical"
    context = engine.context_for_llm("ask the room about the chapel")
    assert any(item["id"] == "canon_test_book" for item in context["nearby_canon"])

    summary = summarize_state(engine)
    assert summary["canon_records"][0]["id"] == "canon_test_book"
    assert summary["canon_records"][0]["attachment"]["room_id"] == room.id


def test_room_profiles_survive_dungeon_floor_snapshots() -> None:
    engine = GameEngine(seed=11, scenario="dungeon")
    before = {room_id: room.to_public_dict() for room_id, room in engine.state.room_profiles.items()}
    assert before

    engine._save_dungeon_floor(engine.state.depth)
    engine.state.room_profiles.clear()
    engine.state.tile_rooms.clear()
    engine._load_dungeon_floor(engine.state.depth, STAIRS_DOWN)

    after = {room_id: room.to_public_dict() for room_id, room in engine.state.room_profiles.items()}
    assert after == before
    assert engine.room_profile_at(engine.state.player.x, engine.state.player.y) is not None
