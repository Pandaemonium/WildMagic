"""Phase B — multidimensional standing consumed + the kill-emperor gate (D9).

Standing is multi-axis (Phase A.1 covers the split); Phase B makes it *bite*: the player's
imperial_threat spends down the Empire's finite defenses each day, and only when those
defenses break is the emperor reachable and killable. Killing him is the win — not a
standing threshold, a body. `Reward.reputation` is finally consumed.

See docs/EMERGENT_WORLD_IMPLEMENTATION.md §3 (Phase B), §0.5 (D9).
"""

from __future__ import annotations

from wildmagic.engine import GameEngine
from wildmagic.factions import EMPIRE_DEFENSE_START, FactionLedger, seed_phase0_factions
from wildmagic.promises import Reward


def _spawn_imperial(engine: GameEngine, x: int, y: int):
    return engine.spawn_actor(
        "legion spearman", "l", x, y, 1, 1, 0, "enemy", "melee", tags={"empire"}
    )


def _spawn_emperor(engine: GameEngine, x: int, y: int):
    return engine.spawn_actor(
        "the Emperor", "E", x, y, 1, 1, 0, "enemy", "melee", tags={"empire", "emperor"}
    )


# --- the resource gate -----------------------------------------------------------


def test_pressure_depletes_empire_defenses_daily() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    empire = engine.state.faction_ledger.get("empire")
    assert empire.resources["defense"] == EMPIRE_DEFENSE_START
    # Stand up some imperial_threat directly, then run a day.
    empire.standing["imperial_threat"] = 5.0
    engine.state.turn += engine_turns_per_day()
    engine._maybe_run_daily_tick()
    assert empire.resources["defense"] == EMPIRE_DEFENSE_START - 5


def test_no_threat_no_depletion() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    empire = engine.state.faction_ledger.get("empire")
    engine.state.turn += engine_turns_per_day()
    engine._maybe_run_daily_tick()
    assert empire.resources["defense"] == EMPIRE_DEFENSE_START


def test_emperor_unreachable_until_defenses_break() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    empire = engine.state.faction_ledger.get("empire")
    assert engine.emperor_reachable() is False
    empire.resources["defense"] = 0
    assert engine.emperor_reachable() is True


# --- the kill-emperor win --------------------------------------------------------


def test_emperor_survives_while_sealed_then_dies_when_reachable() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    player.attack = 999
    emperor = _spawn_emperor(engine, player.x, player.y + 1)

    # Sealed: the blow cannot land.
    engine.attack(player, emperor)
    assert emperor.alive
    assert engine.state.victory is False

    # Break the defenses, then strike: he falls and the run is won.
    engine.state.faction_ledger.get("empire").resources["defense"] = 0
    engine.attack(player, emperor)
    assert not emperor.alive
    assert engine.state.victory is True
    assert engine.state.game_over is True


def test_pressure_loop_end_to_end_opens_the_road() -> None:
    # Drive real pressure: kill imperials, let the daily tick apply + spend defenses.
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    player.attack = 999
    empire = engine.state.faction_ledger.get("empire")
    # Each imperial kill adds 0.2 imperial_threat; accumulate a strong threat.
    for _ in range(20):
        foe = _spawn_imperial(engine, player.x, player.y + 1)
        engine.attack(player, foe)
    engine.run_world_tick()  # apply the deeds -> imperial_threat rises
    assert empire.standing_of("imperial_threat") > 0
    # Run several days of pressure; defenses bleed toward zero.
    for _ in range(EMPIRE_DEFENSE_START + 2):
        engine.state.turn += engine_turns_per_day()
        engine._maybe_run_daily_tick()
        if engine.emperor_reachable():
            break
    assert engine.emperor_reachable() is True


# --- Reward.reputation is finally consumed ---------------------------------------


def test_quest_reward_reputation_applies_to_standing() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    engine.add_quest_promise(
        name="Free the prisoners",
        description="Open the cells.",
        contact="Old Tally",
        location="here",
        reward=Reward(reputation={"rebellion": 5, "empire.imperial_threat": 3}),
        tags=["quest"],
    )
    before_gratitude = engine.state.faction_ledger.get("rebellion").standing_of(
        "gratitude"
    )
    completed = engine.complete_quest_by_index(0)
    assert completed is not None
    rebellion = engine.state.faction_ledger.get("rebellion")
    empire = engine.state.faction_ledger.get("empire")
    assert (
        rebellion.standing_of("gratitude") == before_gratitude + 5
    )  # bare id -> gratitude
    assert empire.standing_of("imperial_threat") == 3  # faction.axis form


# --- the spend primitive ---------------------------------------------------------


def test_faction_spend_depletes_and_blocks_when_empty() -> None:
    ledger = seed_phase0_factions()
    assert ledger.spend("empire", "defense", 5) is True
    assert ledger.get("empire").resources["defense"] == EMPIRE_DEFENSE_START - 5
    assert ledger.spend("empire", "defense", 9999) is False  # can't overspend
    assert ledger.get("empire").resources["defense"] == EMPIRE_DEFENSE_START - 5


def engine_turns_per_day() -> int:
    from wildmagic.engine import TURNS_PER_DAY

    return TURNS_PER_DAY
