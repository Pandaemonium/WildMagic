from __future__ import annotations

import random

from wildmagic.equipment import equipment_slot_for_item
from wildmagic.game_data import FOCUS_SPECS
from wildmagic.populations import denizen_name, denizen_plan, realm_good, realm_wares
from wildmagic.worldgen import (
    MINOR_REALM_IDS,
    roll_world,
    seed_factions_from_world,
)


def test_smaller_realms_placed_seeded_and_populated() -> None:
    world = roll_world(7)
    placed = [rid for rid in MINOR_REALM_IDS if rid in world.placements]
    assert len(placed) == len(MINOR_REALM_IDS)  # all seven peoples placed
    assert all(world.placements[rid].role == "independent" for rid in placed)

    ledger = seed_factions_from_world(world)
    for rid in MINOR_REALM_IDS:
        faction = ledger.get(rid)
        assert faction is not None and faction.kind == "independent"
    # In the Empire's gravity: it is content, they are warily deferent.
    assert ledger.stance("empire", MINOR_REALM_IDS[0]) == "friendly"
    assert ledger.stance(MINOR_REALM_IDS[0], "empire") == "wary"

    # They field their own people.
    plan = denizen_plan("independent", "monteary", random.Random(1))
    assert any("monteary" in ident for _denizen, ident in plan)


def test_realm_goods_are_equipment_and_focus_texture() -> None:
    rng = random.Random(2)
    good = realm_good("stalnaz", rng)
    assert good in {"charged stalnaz crystal", "resonance shard"}

    wares = realm_wares("brall", random.Random(3))
    assert any(item in wares for item in {"brall scrimshaw charm", "bone tally"})

    assert equipment_slot_for_item("charged stalnaz crystal") == "charm"
    assert equipment_slot_for_item("monteary horsehair bow") == "weapon"
    assert "crystal" in FOCUS_SPECS["charged stalnaz crystal"]["themes"]


def test_denizen_names_follow_folk_vs_imperial_split() -> None:
    denizen = denizen_plan("conquered", "stalnaz", random.Random(1))[0][0]
    imperial_name = denizen_name(denizen, random.Random(1), ["imperial"])
    assert imperial_name in {
        "legionary",
        "cohort sentry",
        "edict guard",
        "containment lance",
        "decanus",
        "optio",
        "tribune's deputy",
    }

    local = next(
        d
        for d, ident in denizen_plan("conquered", "stalnaz", random.Random(5))
        if ident == ["stalnaz"] and d.role == "townsfolk"
    )
    local_name = denizen_name(local, random.Random(1), ["stalnaz"])
    assert local_name in {"glass-tuner", "song-cutter", "lightkeeper"}
