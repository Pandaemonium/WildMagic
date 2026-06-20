from __future__ import annotations

from wildmagic.engine import GameEngine
from wildmagic.worldgen import REALM_VOICES, realm_voice_line, roll_world


def test_every_core_realm_has_a_voice() -> None:
    world = roll_world(7)
    for realm_id in world.placements:
        assert realm_voice_line(realm_id)  # non-empty voice line
    assert set(REALM_VOICES) >= {
        "vigovia",
        "stalnaz",
        "brall",
        "ryolan",
        "vint",
        "threen",
    }


def test_realm_card_carries_the_voice_line() -> None:
    from wildmagic import state_view

    engine = GameEngine(seed=1, scenario="frontier")
    card = state_view.current_realm_card(engine)
    assert card is not None
    assert card["voice"]  # the per-realm voice flows into dialogue/resolver context


def test_crossing_announces_the_political_shift() -> None:
    engine = GameEngine(seed=1, scenario="frontier")
    world = engine.state.world_map
    rival = world.rival_realm_id
    rival_role = world.placements[rival].role
    # entering the free rival from elsewhere reads as a political shift
    msg = engine._realm_crossing_message(
        "ryolan", *sorted(world.placements[rival].cells)[0]
    )
    assert "free" in msg.lower() and world.placements[rival].realm_id
    assert rival_role == "rival"
    # crossing into occupied land names it as occupied
    conq = next(pl for pl in world.placements.values() if pl.role == "conquered")
    occ_msg = engine._realm_crossing_message(None, *sorted(conq.cells)[0])
    assert "occupied" in occ_msg.lower()
