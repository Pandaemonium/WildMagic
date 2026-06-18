"""Dynamic per-cast schema + card-driven context slices (Stage 5 of the state-surface plan).

A plain direct-damage spell gets a smaller effect schema and no specialist slices; a routed
memory-edit / prophecy / animation / conjuration spell gets its effect unlocked and the context
slice its card declared it needs. The narrowed schema is the same shape as the full one.
"""

from __future__ import annotations

from wildmagic import capabilities as cap
from wildmagic import state_view
from wildmagic.engine import GameEngine
from wildmagic.spell_contract import (
    SUPPORTED_EFFECTS,
    SPELL_RESPONSE_JSON_SCHEMA,
    per_cast_response_schema,
)


def _effect_enum(schema: dict) -> list[str]:
    return schema["properties"]["effects"]["items"]["properties"]["type"]["enum"]


# --- per-cast schema ---------------------------------------------------------------------


def test_per_cast_schema_narrows_effect_enum() -> None:
    plain = per_cast_response_schema(sorted(cap.CORE_EFFECT_TYPES))
    assert set(_effect_enum(plain)) == set(cap.CORE_EFFECT_TYPES)
    assert "edit_memory" not in _effect_enum(plain)
    # Same overall shape as the full schema (only the enum changed).
    assert plain["required"] == SPELL_RESPONSE_JSON_SCHEMA["required"]


def test_per_cast_schema_defaults_to_full_set() -> None:
    assert set(_effect_enum(per_cast_response_schema(None))) == set(SUPPORTED_EFFECTS)


def test_per_cast_schema_is_smaller_for_plain_than_specialist() -> None:
    plain = per_cast_response_schema(sorted(cap.CORE_EFFECT_TYPES))
    memory = cap.selected_effect_types(cap.select_cards("make it forget my face"))
    assert len(_effect_enum(plain)) < len(
        _effect_enum(per_cast_response_schema(memory))
    )


# --- card-driven context slices ----------------------------------------------------------


def test_plain_spell_has_no_specialist_slices() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    context = engine.context_for_llm("hurl a fireball at the goblin")
    for slice_name in (
        "target_memories",
        "promise_summaries",
        "nearby_structures",
        "conjurable_items",
    ):
        assert slice_name not in context


def test_memory_spell_receives_target_memories_slice() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    npc = engine.spawn_npc(
        "Suspicious Guard",
        "g",
        player.x + 1,
        player.y,
        role="guard",
        backstory="hunts the player",
        faction="enemy",
    )
    engine.state.npc_profiles[npc.id].memory = ["You walked in carrying chalk."]

    context = engine.context_for_llm("make the guard forget why it came here")

    assert "target_memories" in context
    cards = context["target_memories"]
    assert any(c["id"] == npc.id and "chalk" in " ".join(c["memory"]) for c in cards)


def test_prophecy_spell_receives_promise_summaries_slice() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    context = engine.context_for_llm(
        "somewhere north of here a glass chapel waits for me"
    )
    assert "promise_summaries" in context


def test_slice_names_match_selected_context_slices_helper() -> None:
    spell = "make the nearest enemy forget why it came here"
    selected = cap.select_cards(spell)
    expected = set(cap.selected_context_slices(selected))
    engine = GameEngine(seed=7, scenario="test_chamber")
    built = set(state_view.card_context_slices(engine, spell, selected))
    assert built == expected


# --- audit routing -----------------------------------------------------------------------


def test_resolver_routing_records_cards_effects_and_slices() -> None:
    from wildmagic.wild_magic import _resolver_routing

    routing = _resolver_routing("make the nearest enemy forget why it came here")
    assert "memory_edit" in routing["selected_cards"]
    assert "edit_memory" in routing["selected_effect_types"]
    assert "target_memories" in routing["context_slices"]

    plain = _resolver_routing("hurl a fireball")
    assert plain["selected_cards"] == []
    assert plain["context_slices"] == []
