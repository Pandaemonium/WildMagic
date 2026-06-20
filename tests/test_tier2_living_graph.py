from __future__ import annotations

from wildmagic.engine import BLOOD_FEUD_KILLS, GameEngine


def _engine() -> GameEngine:
    return GameEngine(seed=1, scenario="test_chamber")


def _open_a_feud(engine: GameEngine) -> None:
    p = engine.state.player
    p.attack = 999
    for _ in range(BLOOD_FEUD_KILLS):
        foe = engine.spawn_actor(
            "legionary",
            "l",
            p.x,
            p.y + 1,
            1,
            1,
            0,
            "enemy",
            "melee",
            tags={"empire"},
            role="soldier",
        )
        engine.attack(p, foe)


def test_blood_feud_summons_a_faction_hunter() -> None:
    engine = _engine()
    _open_a_feud(engine)
    assert "empire" in engine.feuding_factions()
    engine._simulate_faction_relations(day=2)
    assert any(
        ev.get("kind") == "feud_hunter" and ev.get("faction") == "empire"
        for ev in engine.state.pending_backlash
    )
    # The hunter realizes as a real body attributed to the feuding faction.
    engine._spawn_backlash_feud_hunter("empire")
    hunters = [e for e in engine.state.entities.values() if "backlash" in e.tags]
    assert hunters and all(h.faction == "enemy" for h in hunters)


def test_warring_factions_generate_offscreen_rumors() -> None:
    engine = _engine()  # phase-0: empire and rebellion are at open war
    found = False
    for day in range(2, 30):
        engine._simulate_faction_relations(day=day)
        if any(p.kind == "rumor" and "war" in p.tags for p in engine.state.promises):
            found = True
            break
    assert found


def test_dialogue_reflects_faction_standing_toward_you() -> None:
    engine = _engine()
    p = engine.state.player
    engine.state.faction_ledger.adjust_standing("rebellion", "gratitude", 2.0)
    rebel = engine.spawn_npc(
        "sympathizer",
        "r",
        p.x + 1,
        p.y,
        role="townsfolk",
        backstory="hates the charter",
        identity=["rebel"],
    )
    assert "grateful" in engine._faction_standing_note(rebel)
    engine.state.faction_ledger.adjust_standing("empire", "imperial_threat", 2.0)
    clerk = engine.spawn_npc(
        "tax-clerk",
        "c",
        p.x - 1,
        p.y,
        role="clerk",
        backstory="files",
        identity=["imperial"],
    )
    assert "threat" in engine._faction_standing_note(clerk)
