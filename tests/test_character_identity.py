from __future__ import annotations

from wildmagic.engine import GameEngine
from wildmagic.factions import (
    identity_from_tags,
    resolve_faction,
    seed_phase0_factions,
)
from wildmagic.models import Entity, character_is_noncombatant, role_from_tags
from wildmagic.worldgen import roll_world, seed_factions_from_world


def _entity(**kw) -> Entity:
    base = dict(id="e1", name="Test", kind="actor", x=0, y=0, char="x")
    base.update(kw)
    return Entity(**base)


def test_resolve_faction_prefers_typed_identity() -> None:
    ledger = seed_factions_from_world(roll_world(1))
    # "imperial" allegiance resolves to the empire bloc even with no tags.
    assert resolve_faction(set(), "actor", ledger, identity=["imperial"]) == "empire"
    # A realm allegiance resolves to that realm's faction directly.
    assert resolve_faction(set(), "actor", ledger, identity=["stalnaz"]) == "stalnaz"


def test_resolve_faction_identity_aliases() -> None:
    ledger = seed_phase0_factions()
    assert resolve_faction(set(), "actor", ledger, identity=["rebel"]) == "rebellion"
    assert resolve_faction(set(), "actor", ledger, identity=["imperial"]) == "empire"


def test_resolve_faction_tag_fallback_unchanged() -> None:
    # With no identity, the old tag/kind path still works (no regression to K1/K2).
    ledger = seed_phase0_factions()
    assert resolve_faction({"empire"}, "actor", ledger) == "empire"
    assert resolve_faction(set(), "npc", ledger) == "civilian"
    assert resolve_faction({"beast"}, "actor", ledger) == ""


def test_identity_takes_precedence_over_misleading_tags() -> None:
    ledger = seed_factions_from_world(roll_world(1))
    # An entity carrying a stray "empire" tag but typed as Stalnaz resolves to Stalnaz.
    assert (
        resolve_faction({"empire"}, "actor", ledger, identity=["stalnaz"]) == "stalnaz"
    )


def test_identity_from_tags_bridge() -> None:
    assert identity_from_tags({"empire", "soldier"}) == ["imperial"]
    assert identity_from_tags({"rebel"}) == ["rebel"]
    assert identity_from_tags({"flammable", "beast"}) == []


def test_role_from_tags_bridge() -> None:
    assert role_from_tags({"soldier", "flammable"}) == "soldier"
    assert role_from_tags({"merchant"}) == "merchant"
    assert role_from_tags({"flammable", "undead"}) == ""


def test_character_is_noncombatant_reads_role_then_kind() -> None:
    assert character_is_noncombatant(_entity(role="clerk"))
    assert character_is_noncombatant(_entity(role="merchant"))
    assert not character_is_noncombatant(_entity(role="soldier"))
    # Fallbacks: a bare npc is a non-combatant; a combat actor is not; bound can't fight.
    assert character_is_noncombatant(_entity(kind="npc", role=""))
    assert not character_is_noncombatant(_entity(kind="actor", role=""))
    assert character_is_noncombatant(_entity(kind="actor", role="", tags={"bound"}))


def test_spawn_actor_types_identity_and_role_from_tags() -> None:
    engine = GameEngine(seed=1, scenario="test_chamber")
    soldier = engine.spawn_actor(
        "imperial soldier",
        "s",
        1,
        1,
        hp=10,
        attack=3,
        defense=1,
        faction="enemy",
        ai="melee",
        tags={"empire", "soldier"},
    )
    assert soldier.identity == ["imperial"]
    assert soldier.role == "soldier"
    assert not character_is_noncombatant(soldier)


def test_spawn_npc_types_role_and_identity() -> None:
    engine = GameEngine(seed=1, scenario="test_chamber")
    clerk = engine.spawn_npc(
        "imperial clerk",
        "c",
        2,
        2,
        role="clerk",
        backstory="keeps the ledgers",
        tags={"empire"},
    )
    assert clerk.role == "clerk"
    assert clerk.identity == ["imperial"]
    assert character_is_noncombatant(clerk)
