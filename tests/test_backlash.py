"""Phase D — backlash: the world reacts to what you've done (strategy §5.2).

Standing + spent resources become felt events. A crackdown is not "fear is high" — it is
"the Empire spends a patrol" to hunt you; the people "spend a cell" to rise for you.
Resources are finite with slow regen, so reactions ebb and flow and the world can only
have so much in motion at once. Intents are minted by the daily tick and realized (real
bodies in the world) when you next enter a zone.

See docs/EMERGENT_WORLD_IMPLEMENTATION.md §3 (Phase D), strategy §5.2.
"""

from __future__ import annotations

from wildmagic.engine import (
    EMPIRE_PATROLS_START,
    MAX_PENDING_BACKLASH,
    REBELLION_CELLS_START,
    TURNS_PER_DAY,
    GameEngine,
)


def _advance_one_day(engine: GameEngine) -> None:
    engine.state.turn += TURNS_PER_DAY
    engine._maybe_run_daily_tick()


def _backlash_kinds(engine: GameEngine) -> list[str]:
    return [event.get("kind") for event in engine.state.pending_backlash]


# --- minting intents (the daily tick) --------------------------------------------


def test_high_threat_makes_the_empire_spend_a_patrol() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    empire = engine.state.faction_ledger.get("empire")
    empire.standing["imperial_threat"] = 2.0
    _advance_one_day(engine)
    assert "crackdown" in _backlash_kinds(engine)
    # Regen (+1, capped) then spend (-1): a patrol was spent this day.
    assert empire.resources["patrols"] == EMPIRE_PATROLS_START - 1


def test_high_gratitude_makes_the_people_rise() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    rebellion = engine.state.faction_ledger.get("rebellion")
    rebellion.standing["gratitude"] = 2.0
    _advance_one_day(engine)
    assert "resistance" in _backlash_kinds(engine)
    assert rebellion.resources["cells"] == REBELLION_CELLS_START - 1


def test_calm_standing_provokes_no_backlash() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    _advance_one_day(engine)
    assert engine.state.pending_backlash == []


def test_pending_backlash_is_capped() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    empire = engine.state.faction_ledger.get("empire")
    empire.standing["imperial_threat"] = 5.0
    engine.state.pending_backlash = [{"kind": "crackdown"}] * MAX_PENDING_BACKLASH
    _advance_one_day(engine)
    # Saturated: no new intent minted, no resource spent on one.
    assert len(engine.state.pending_backlash) == MAX_PENDING_BACKLASH


def test_mood_drifts_with_standing() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    engine.state.faction_ledger.get("empire").standing["imperial_threat"] = 3.5
    engine.state.faction_ledger.get("rebellion").standing["gratitude"] = 3.5
    _advance_one_day(engine)
    assert engine.state.faction_ledger.get("empire").mood == "furious"
    assert engine.state.faction_ledger.get("rebellion").mood == "rising"


# --- realizing intents (zone entry) ----------------------------------------------


def test_crackdown_spawns_a_hunting_patrol_on_entry() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    engine.state.pending_backlash = [{"kind": "crackdown"}]
    engine._realize_backlash()
    enforcers = [
        e
        for e in engine.state.entities.values()
        if "backlash" in e.tags and e.faction == "enemy"
    ]
    assert len(enforcers) == 1
    assert "empire" in enforcers[0].tags
    assert engine.state.pending_backlash == []  # consumed


def test_resistance_spawns_an_ally_on_entry() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    engine.state.pending_backlash = [{"kind": "resistance"}]
    engine._realize_backlash()
    allies = [
        e
        for e in engine.state.entities.values()
        if "backlash" in e.tags and e.faction == "ally"
    ]
    assert len(allies) == 1


# --- end to end: deeds -> standing -> backlash -----------------------------------


def test_sustained_pressure_brings_a_crackdown_into_the_world() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    player.attack = 999
    for _ in range(6):  # >= 1.0 imperial_threat
        foe = engine.spawn_actor(
            "legion",
            "l",
            player.x,
            player.y + 1,
            1,
            1,
            0,
            "enemy",
            "melee",
            tags={"empire"},
        )
        engine.attack(player, foe)
    engine.run_world_tick()  # apply the deeds
    _advance_one_day(engine)  # the Empire decides to act
    assert "crackdown" in _backlash_kinds(engine)
    engine._realize_backlash()  # ... and a patrol arrives
    assert any(
        "backlash" in e.tags and e.faction == "enemy"
        for e in engine.state.entities.values()
    )
