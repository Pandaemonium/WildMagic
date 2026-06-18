from __future__ import annotations

from wildmagic import capabilities as cap
from wildmagic.engine import GameEngine
from wildmagic.spell_contract import SUPPORTED_COSTS


def test_plain_spell_context_advertises_core_effects_only() -> None:
    spell = "hurl a roaring fireball at the goblin"
    engine = GameEngine(seed=7, scenario="test_chamber")

    context = engine.context_for_llm(spell)

    assert context["supported_effects"] == sorted(cap.CORE_EFFECT_TYPES)
    assert "memory_edit" not in context["supported_effects"]
    assert "transform_entity" not in context["supported_effects"]


def test_specialist_spell_context_matches_routed_capabilities() -> None:
    spell = "make the nearest enemy forget it ever saw me"
    engine = GameEngine(seed=7, scenario="test_chamber")
    selected = cap.select_cards(spell)

    context = engine.context_for_llm(spell)

    assert context["supported_effects"] == sorted(cap.selected_effect_types(selected))
    assert "edit_memory" in context["supported_effects"]


def test_context_supported_costs_come_from_contract() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")

    context = engine.context_for_llm("a small spark")

    assert context["supported_costs"] == sorted(SUPPORTED_COSTS)
