from __future__ import annotations

import random

from wildmagic.bonds import _TRAIT_AFFINITY, _TRAIT_AVERSION
from wildmagic.engine import GameEngine
from wildmagic.populations import denizen_plan, realm_disposition


def test_denizen_plan_conquered_mixes_occupiers_and_locals() -> None:
    plan = denizen_plan("conquered", "stalnaz", random.Random(1))
    identities = [tuple(ident) for _denizen, ident in plan]
    assert ("imperial",) in identities  # the garrison
    assert ("stalnaz",) in identities  # the locals


def test_rival_zone_fields_its_own_people_not_imperials() -> None:
    plan = denizen_plan("rival", "brall", random.Random(1))
    identities = {tuple(ident) for _denizen, ident in plan}
    assert ("brall",) in identities
    assert ("imperial",) not in identities  # the free rival is not occupied


def _conquered_placement(engine: GameEngine):
    return next(
        pl
        for pl in sorted(
            engine.state.world_map.placements.values(), key=lambda p: p.realm_id
        )
        if pl.role == "conquered"
    )


def test_conquered_zone_populates_neutral_occupiers_and_locals() -> None:
    engine = GameEngine(seed=1, scenario="frontier")
    placement = _conquered_placement(engine)
    # Inspect only the realm denizens by clearing the start zone's wild inhabitants first.
    player_id = engine.state.player_id
    for eid in [e for e in list(engine.state.entities) if e != player_id]:
        del engine.state.entities[eid]

    engine._populate_realm_denizens(random.Random(7), [], set(), placement)

    # The realm's *people* carry a typed identity (a touch of wild creatures may also spawn,
    # which are legitimately hostile and identity-less — exclude them).
    people = [
        e for e in engine.state.entities.values() if e.id != player_id and e.identity
    ]
    assert people
    # Every denizen enters as a politically situated person — neutral, not hostile-on-sight.
    assert all(e.faction == "neutral" for e in people)
    # A mix of imperial occupiers and locals, all typed.
    assert any("imperial" in e.identity for e in people)
    assert any(placement.realm_id in e.identity for e in people)
    # Soldiers are combatant actors; townsfolk/merchants are talkable personas.
    assert any(e.kind == "actor" and e.role in {"soldier", "officer"} for e in people)
    assert any(e.kind == "npc" and e.role in {"townsfolk", "merchant"} for e in people)


def test_disposition_spread_gives_occupied_locals_mixed_leanings() -> None:
    rng = random.Random(0)
    leanings = [realm_disposition("conquered", "townsfolk", rng) for _ in range(200)]
    affinity = sum(1 for d in leanings if d in _TRAIT_AFFINITY)
    aversion = sum(1 for d in leanings if d in _TRAIT_AVERSION)
    # Mixed reactions: some warm to a sorcerer who strikes the Empire, some recoil...
    assert affinity > 0 and aversion > 0
    # ...but the occupied mostly sympathize.
    assert affinity > aversion


def test_role_leaning_locals_keep_their_natural_disposition() -> None:
    # Partisans (rebel) and priests (pious) aren't distributed — they keep their lean.
    assert realm_disposition("conquered", "partisan", random.Random(1)) is None
    assert realm_disposition("conquered", "priest", random.Random(1)) is None


def test_opening_occupation_scene_stages_once() -> None:
    engine = GameEngine(
        seed=1, scenario="frontier"
    )  # player placed in the unowned start
    placement = _conquered_placement(engine)
    player = engine.state.player
    engine._populate_realm_denizens(
        random.Random(3), [], {(player.x, player.y)}, placement
    )
    assert engine.state.flags.get("opening_scene_staged")
    names = {e.name for e in engine.state.entities.values()}
    assert "cornered local" in names
    # The menacing soldiers are imperial and NEUTRAL (the player chooses whether to provoke).
    soldiers = [
        e
        for e in engine.state.entities.values()
        if "imperial" in e.identity and e.role == "soldier"
    ]
    assert soldiers and all(s.faction == "neutral" for s in soldiers)
    # Staged only once — a second occupied zone doesn't re-run it.
    count_before = sum(
        1 for e in engine.state.entities.values() if e.name == "cornered local"
    )
    engine._populate_realm_denizens(random.Random(4), [], set(), placement)
    count_after = sum(
        1 for e in engine.state.entities.values() if e.name == "cornered local"
    )
    assert count_after == count_before


def test_frontier_run_starts_in_occupied_territory_with_opening_scene() -> None:
    engine = GameEngine(seed=1, scenario="frontier")
    st = engine.state
    placement = st.world_map.placement_at(st.zone_x, st.zone_y)
    assert placement is not None and placement.role == "conquered"
    assert st.flags.get("opening_scene_staged")
    assert any(e.name == "cornered local" for e in st.entities.values())
    # The realm's people are present and neutral (hostility is earned, not spawned).
    locals_present = [
        e
        for e in st.entities.values()
        if e.id != st.player_id and e.identity and e.faction == "neutral"
    ]
    assert locals_present
