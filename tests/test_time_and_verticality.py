"""Phase 0.5 — lateral-first overworld & time foundations (D2, D4).

Two commitments the rest of the plan builds on:
  * Verticality is bounded and never a win/progression axis — descent caps at a site's
    levels and reaching the bottom is not victory (§0.2).
  * A day/night clock derived from the turn count, a camp/rest action, and a daily world
    tick that fires once at 05:00 (§0.3).

See docs/EMERGENT_WORLD_IMPLEMENTATION.md §3 (Phase 0.5).
"""

from __future__ import annotations

from wildmagic.engine import GameEngine, TURNS_PER_DAY
from wildmagic.models import STAIRS_DOWN


def _spawn_imperial(engine: GameEngine, x: int, y: int):
    return engine.spawn_actor(
        "legion spearman", "l", x, y, 1, 1, 0, "enemy", "melee", tags={"empire"}
    )


# --- bounded, lateral-first verticality (§0.2) -----------------------------------


def test_normal_descent_does_not_win() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    assert engine.descend_stairs() is True
    assert engine.state.depth == 2
    assert engine.state.victory is False
    assert engine.state.game_over is False


def test_descent_is_bounded_and_never_wins_at_the_cap() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    # Pretend we are already at the deepest level of this site, standing on a down-stair.
    engine.state.depth = engine.state.max_depth
    player = engine.state.player
    assert engine.tile_at(player.x, player.y) == STAIRS_DOWN
    assert engine.descend_stairs() is False  # the passage bottoms out
    assert engine.state.depth == engine.state.max_depth  # no deeper
    assert engine.state.victory is False
    assert engine.state.game_over is False


# --- the day/night clock (§0.3) --------------------------------------------------


def test_clock_is_derived_from_the_turn_count() -> None:
    engine = GameEngine(seed=1, scenario="test_chamber")
    state = engine.state
    # The run opens on day 1 at dawn (turn_of_day 0 == 05:00).
    assert state.day == 1
    assert state.turn_of_day == 0
    assert state.day_phase == "dawn"

    state.turn = TURNS_PER_DAY  # the next dawn
    assert state.day == 2
    assert state.turn_of_day == 0
    assert state.day_phase == "dawn"

    state.turn = TURNS_PER_DAY + TURNS_PER_DAY // 2  # +12h -> 17:00
    assert state.day == 2
    assert state.day_phase == "day"


def test_rest_defaults_to_eight_hours_and_recovers() -> None:
    engine = GameEngine(seed=1, scenario="test_chamber")
    player = engine.state.player
    player.mana = 0
    turn_before = engine.state.turn

    assert engine.camp_rest() is True  # 8 hours by default
    # 8h of a 1440-round day = 480 rounds.
    assert engine.state.turn - turn_before == 480
    assert player.mana == player.max_mana


def test_rest_until_a_named_time() -> None:
    engine = GameEngine(seed=1, scenario="test_chamber")
    engine.state.turn = 600  # 05:00 + 600 min = 15:00
    assert round(engine.state.hour_of_day) == 15
    assert engine.camp_rest(until_hour=5.0) is True  # rest until the next dawn
    assert engine.state.turn_of_day == 0
    assert engine.state.day_phase == "dawn"
    assert engine.state.day == 2


# --- the daily 05:00 tick (§0.3) -------------------------------------------------


def test_daily_tick_fires_once_per_day() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    player.attack = 99
    foe = _spawn_imperial(engine, player.x, player.y + 1)
    engine.attack(player, foe)
    empire = engine.state.faction_ledger.get("empire")

    # At turn 0 (day 1, dawn) no automatic tick has run: the deed is recorded, unapplied.
    assert engine.state.deed_ledger.deeds[0].applied is False
    assert empire.standing_of("imperial_threat") == 0.0

    # Resting until the next dawn crosses 05:00, so the daily tick fires.
    engine.camp_rest(until_hour=5.0)
    assert engine.state.deed_ledger.deeds[0].applied is True
    threat = empire.standing_of("imperial_threat")
    assert threat > 0.0
    assert engine.state.ticked_through_day == engine.state.day

    # A second day passes with no new deeds: the tick fires but applies nothing new.
    engine.camp_rest(until_hour=5.0)
    assert empire.standing_of("imperial_threat") == threat
    assert engine.state.ticked_through_day == engine.state.day


def test_same_seed_same_tick_outcome() -> None:
    def run() -> float:
        engine = GameEngine(seed=42, scenario="test_chamber")
        player = engine.state.player
        player.attack = 99
        foe = _spawn_imperial(engine, player.x, player.y + 1)
        engine.attack(player, foe)
        engine.camp_rest(until_hour=5.0)  # cross dawn so the tick applies the deed
        return engine.state.faction_ledger.get("empire").standing_of("imperial_threat")

    assert run() == run() > 0.0
