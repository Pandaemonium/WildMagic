from __future__ import annotations

from wildmagic.factions import (
    COMBATIVE_STANCES,
    FactionLedger,
    seed_phase0_factions,
)
from wildmagic.worldgen import roll_world, seed_factions_from_world


def _world_ledger(seed: int) -> tuple[FactionLedger, str, list[str], str]:
    """Return (ledger, rival_faction_id, conquered_faction_ids, proxy_faction_id) for a seed."""
    world = roll_world(seed)
    ledger = seed_factions_from_world(world)
    rival = world.placements[world.rival_realm_id].faction_id
    conquered = [
        pl.faction_id for pl in world.placements.values() if pl.role == "conquered"
    ]
    proxy = next(
        pl.faction_id for pl in world.placements.values() if pl.role == "proxy"
    )
    return ledger, rival, conquered, proxy


def test_phase0_scaffold_has_empire_rebellion_war() -> None:
    ledger = seed_phase0_factions()
    assert ledger.are_hostile("empire", "rebellion")
    assert ledger.stance("empire", "rebellion") == "hostile"
    assert ledger.stance("rebellion", "empire") == "hostile"


def test_self_and_unset_pairs() -> None:
    ledger = seed_phase0_factions()
    assert ledger.stance("empire", "empire") == "self"
    assert ledger.regard("empire", "empire") == 1.0
    # No relationship recorded between empire and an unknown faction → neutral / 0.
    assert ledger.stance("empire", "nobody") == "neutral"
    assert ledger.regard("empire", "nobody") == 0.0
    assert not ledger.are_hostile("empire", "nobody")


def test_world_roll_seeds_core_relationships() -> None:
    ledger, rival, conquered, proxy = _world_ledger(7)

    # Empire vs the free rival: open war, both directions.
    assert ledger.are_hostile("empire", rival)
    assert ledger.stance("empire", rival) == "hostile"
    assert ledger.stance(rival, "empire") == "hostile"

    # Empire holds each conquered realm as a subject; the realm resents the occupier.
    for cid in conquered:
        assert ledger.stance("empire", cid) == "subject"
        assert ledger.stance(cid, "empire") in {"occupier", "wary"}
        assert ledger.regard(cid, "empire") < 0.0

    # The client kingdom plays along; the Empire rules it in fact.
    assert ledger.stance("empire", proxy) == "subject"
    assert ledger.regard(proxy, "empire") > 0.0  # friendly / deferent

    # The Unbound befriend the free rival; both regard each other warmly.
    assert ledger.regard("rebellion", rival) > 0.0
    assert ledger.regard(rival, "rebellion") > 0.0
    # And remain at war with the Empire.
    assert ledger.are_hostile("empire", "rebellion")


def test_regard_signs_track_sentiment() -> None:
    ledger, rival, _conquered, _proxy = _world_ledger(11)
    # An enemy of the empire is regarded negatively; a friend positively.
    assert ledger.regard("empire", rival) < 0.0
    assert ledger.regard("rebellion", rival) > 0.0


def test_cross_realm_peers_left_neutral() -> None:
    # WORLDBUILDING keeps conquered-vs-conquered feeling emergent; the roll must not invent it.
    _ledger, _rival, conquered, _proxy = _world_ledger(3)
    if len(conquered) >= 2:
        a, b = conquered[0], conquered[1]
        assert _ledger.stance(a, b) == "neutral"
        assert _ledger.stance(b, a) == "neutral"


def test_are_hostile_is_symmetric_even_if_one_sided() -> None:
    ledger = FactionLedger()
    ledger.set_relationship("a", "b", "hostile")  # only a → b declared
    assert ledger.are_hostile("a", "b")
    assert ledger.are_hostile("b", "a")
    assert "hostile" in COMBATIVE_STANCES


def test_relationships_survive_serialization() -> None:
    ledger, rival, conquered, _proxy = _world_ledger(5)
    restored = FactionLedger.from_dict(ledger.to_dict())
    assert restored.stance("empire", rival) == ledger.stance("empire", rival)
    for cid in conquered:
        assert restored.stance("empire", cid) == ledger.stance("empire", cid)
        assert restored.stance(cid, "empire") == ledger.stance(cid, "empire")
    assert restored.relationships == ledger.relationships


def test_relationships_deterministic_for_seed() -> None:
    a = seed_factions_from_world(roll_world(42)).relationships
    b = seed_factions_from_world(roll_world(42)).relationships
    assert a == b
