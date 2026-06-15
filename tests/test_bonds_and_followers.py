"""Phase F — bonds, organizations & followers (strategy §5.3).

The richness comes from a few general primitives, not bespoke events. The three layers are
orthogonal (combat faction / org membership / personal bond); bonds drift from the player's
legend bent by each NPC's traits; crossing the follow line is a moment; turning butcher
loses the believers; a parted follower's memory persists and colours later bonds; founding
an organization draws true believers to it.

See docs/EMERGENT_WORLD_IMPLEMENTATION.md §3 (Phase F).
"""

from __future__ import annotations

from wildmagic.bonds import Bond
from wildmagic.engine import GameEngine


def _npc(engine: GameEngine, name: str, x: int, y: int, traits: list[str]):
    entity = engine.spawn_npc(
        name, "n", x, y, role="stranger", backstory="", traits=traits
    )
    return entity, engine.state.npc_profiles[entity.id]


def _legend(engine: GameEngine, tag: str, weight: float) -> None:
    engine.state.legend_ledger.add_tag(engine.state.player_soul_id, tag, weight)


# --- the three orthogonal layers -------------------------------------------------


def test_bond_is_orthogonal_to_combat_faction_and_affiliation() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    entity, profile = _npc(engine, "reeve", 3, 3, traits=[])
    profile.bond = Bond(loyalty=90.0, affiliations=["player_org_guild"])
    # Combat-neutral, org-affiliated, personally devoted — all at once.
    assert entity.faction == "neutral"
    assert "player_org_guild" in profile.bond.affiliations
    assert profile.bond.is_follower()


# --- legend x traits drives bonds ------------------------------------------------


def test_same_legend_lands_opposite_on_rebel_and_loyalist() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    _legend(engine, "liberator", 5.0)
    _legend(engine, "defiant", 5.0)
    _, rebel = _npc(engine, "freedman", 3, 3, traits=["downtrodden"])
    _, loyalist = _npc(engine, "clerk", 3, 5, traits=["loyalist"])
    engine._simulate_bonds()
    assert rebel.bond.admiration > 0 and rebel.bond.loyalty > 0
    assert loyalist.bond.resentment > 0
    assert loyalist.bond.loyalty <= 0


# --- threshold moments -----------------------------------------------------------


def test_crossing_the_follow_line_is_a_moment() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    _legend(engine, "liberator", 8.0)
    _, profile = _npc(engine, "freed prisoner", 3, 3, traits=["downtrodden"])
    for _ in range(6):
        engine._simulate_bonds()
        if profile.bond.is_follower():
            break
    assert profile.bond.is_follower()
    assert "follower" in profile.traits
    assert any("follow you" in note for note in profile.memory)


def test_turning_butcher_loses_a_believer() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    _, profile = _npc(engine, "old comrade", 3, 3, traits=["downtrodden", "follower"])
    profile.bond.loyalty = 60.0  # already pledged
    _legend(engine, "butcher", 10.0)
    for _ in range(6):
        engine._simulate_bonds()
        if "follower" not in profile.traits:
            break
    assert "follower" not in profile.traits
    assert any("left your side" in note for note in profile.memory)


# --- the durable consequence (a memory colours later bonds) -----------------------


def test_memory_makes_reputation_land_harder() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    _legend(engine, "liberator", 2.0)
    _, with_memory = _npc(engine, "one who knows you", 3, 3, traits=["downtrodden"])
    with_memory.memory.append("I will never forget what you did for me.")
    _, a_stranger = _npc(engine, "a stranger", 3, 5, traits=["downtrodden"])
    engine._simulate_bonds()
    # First-hand memory (personal x1.5) means the same legend moves them further.
    assert with_memory.bond.loyalty > a_stranger.bond.loyalty


# --- organizations draw believers ------------------------------------------------


def test_founding_an_org_draws_a_true_believer() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    org = engine.found_organization("the Ashen Hand")
    assert org.kind == "player_org"
    assert org.player_rank == "founder"
    _legend(engine, "liberator", 10.0)
    _, profile = _npc(engine, "zealot", 3, 3, traits=["downtrodden"])
    for _ in range(6):
        engine._simulate_bonds()
    assert profile.bond.is_follower()
    assert org.id in profile.bond.affiliations


def test_followers_readout_lists_followers_and_orgs() -> None:
    from wildmagic.actions import describe_followers

    engine = GameEngine(seed=7, scenario="test_chamber")
    engine.found_organization("the Ashen Hand")
    _, profile = _npc(engine, "lieutenant", 3, 3, traits=[])
    profile.bond = Bond(loyalty=80.0)
    lines = "\n".join(describe_followers(engine))
    assert "the Ashen Hand" in lines
    assert "lieutenant" in lines
