"""Phase E — the consequence renderer: the world shows it remembers.

When you return to a zone where you did something public, the place itself bears the mark
of it — one evocative, deterministic prop per kind of deed (a bloodstain where you
slaughtered, ruin where you razed, defiled ground where you desecrated), plus the Empire's
wanted poster that follows your legend. Placed once, replay-safe, no LLM required.

See docs/EMERGENT_WORLD_IMPLEMENTATION.md §3 (Phase E).
"""

from __future__ import annotations

from wildmagic.engine import GameEngine


def _spawn_imperial(engine: GameEngine, x: int, y: int):
    return engine.spawn_actor(
        "legion spearman", "l", x, y, 1, 1, 0, "enemy", "melee", tags={"empire"}
    )


def _consequence_props(engine: GameEngine):
    return [
        e
        for e in engine.state.entities.values()
        if e.kind == "prop" and "consequence" in e.tags
    ]


def test_public_deed_leaves_a_consequence_prop_on_entry() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    player.attack = 99
    foe = _spawn_imperial(engine, player.x, player.y + 1)
    engine.spawn_npc("drover", "d", player.x, player.y + 2, role="drover", backstory="")
    engine.attack(player, foe)
    engine.run_world_tick()  # the deed becomes public + applied

    assert not _consequence_props(engine)  # nothing yet — not re-entered
    engine._on_enter_location()
    marks = _consequence_props(engine)
    assert any("killed_imperials" in m.tags for m in marks)
    assert any("blood" in m.tags for m in marks)


def test_consequence_is_placed_once_per_zone_and_type() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    player.attack = 99
    engine.spawn_npc("drover", "d", player.x, player.y + 2, role="drover", backstory="")
    for _ in range(3):
        foe = _spawn_imperial(engine, player.x, player.y + 1)
        engine.attack(player, foe)
    engine.run_world_tick()

    engine._on_enter_location()
    engine._on_enter_location()
    engine._on_enter_location()
    marks = [m for m in _consequence_props(engine) if "killed_imperials" in m.tags]
    # One mark for the kind of deed, no matter how many times you re-enter.
    assert len(marks) == 1
    # ... and it acknowledges this happened more than once here.
    assert "more than once" in marks[0].description


def test_secret_deed_leaves_no_mark() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    player.attack = 99
    # No witnesses anywhere near: move the pre-placed chamber actors out of sight is hard,
    # so instead assert via the visibility field on a hand-built deed.
    foe = _spawn_imperial(engine, player.x, player.y + 1)
    engine.attack(player, foe)
    deed = engine.state.deed_ledger.deeds[0]
    # The test chamber has a witness (the training dummy), so this one is witnessed; force
    # a secret deed to check the renderer gates on visibility.
    deed.visibility = "secret"
    engine.run_world_tick()
    engine._on_enter_location()
    assert not _consequence_props(engine)


def test_consequence_props_are_deterministic_across_runs() -> None:
    def run() -> set[str]:
        engine = GameEngine(seed=7, scenario="test_chamber")
        player = engine.state.player
        player.attack = 99
        engine.spawn_npc(
            "drover", "d", player.x, player.y + 2, role="drover", backstory=""
        )
        foe = _spawn_imperial(engine, player.x, player.y + 1)
        engine.attack(player, foe)
        engine.run_world_tick()
        engine._on_enter_location()
        return {f"{p.id}:{p.x},{p.y}:{p.name}" for p in _consequence_props(engine)}

    assert run() == run()
