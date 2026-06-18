"""Effect registry coverage contract (Stage 4 of the state-surface plan).

The registry is the single metadata home for effects; these tests pin that it cannot drift
from the contract, the capability cards, the alias map, or the schema doc.
"""

from __future__ import annotations

from pathlib import Path

from wildmagic import capabilities as cap
from wildmagic import effect_registry as er
from wildmagic import resolution_parsing as rp
from wildmagic.spell_contract import SUPPORTED_EFFECTS

SCHEMA_DOC = Path("docs/WILD_MAGIC_SCHEMA.md")


def test_registry_matches_supported_effects() -> None:
    assert er.registered_effects() == set(SUPPORTED_EFFECTS)


def test_every_effect_has_a_core_or_card_home() -> None:
    for spec in er.REGISTRY.values():
        # Core xor card-owned (mirrors the capability-routing carve).
        assert spec.core != bool(spec.cards), spec.name
        if spec.core:
            assert spec.name in cap.CORE_EFFECT_TYPES
        else:
            for card_name in spec.cards:
                card = next(c for c in cap.CAPABILITY_CARDS if c.name == card_name)
                assert spec.name in card.effect_types


def test_card_ownership_and_context_match_capabilities() -> None:
    for card in cap.CAPABILITY_CARDS:
        for effect in card.effect_types:
            spec = er.effect_spec(effect)
            assert spec is not None
            assert card.name in spec.cards
            for ctx in card.required_context:
                assert ctx in spec.required_context


def test_alias_map_is_shared_and_targets_registered_effects() -> None:
    # resolution_parsing uses the registry's alias map directly (one source of truth).
    assert rp._EFFECT_TYPE_ALIASES is er.EFFECT_TYPE_ALIASES
    for alias, canonical in er.EFFECT_TYPE_ALIASES.items():
        assert canonical in er.REGISTRY, alias
        assert alias in er.effect_spec(canonical).aliases


def test_every_effect_has_a_summary() -> None:
    missing = [name for name, spec in er.REGISTRY.items() if not spec.summary]
    assert not missing


def test_schema_doc_lists_every_registered_effect() -> None:
    text = SCHEMA_DOC.read_text(encoding="utf-8")
    missing = [name for name in er.registered_effects() if f"`{name}`" not in text]
    assert not missing


def test_canonical_effect_resolves_names_and_aliases() -> None:
    assert er.canonical_effect("damage") == "damage"
    assert er.canonical_effect("healing") == "heal"
    assert er.canonical_effect("prophecy") == "create_promise"
    assert er.canonical_effect("not_an_effect") is None
