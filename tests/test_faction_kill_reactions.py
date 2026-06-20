from __future__ import annotations

from wildmagic.actions import describe_standing
from wildmagic.engine import BLOOD_FEUD_KILLS, GameEngine
from wildmagic.worldgen import roll_world, seed_factions_from_world


def _world_engine(seed: int = 1) -> tuple[GameEngine, str]:
    engine = GameEngine(seed=seed, scenario="test_chamber")
    world = roll_world(seed)
    engine.state.faction_ledger = seed_factions_from_world(world)
    rival = world.placements[world.rival_realm_id].faction_id
    return engine, rival


def test_relational_reactions_differ_by_stance() -> None:
    engine, rival = _world_engine(1)
    deltas = engine._relational_kill_deltas("empire", 0.2)
    # The Empire marks you a growing threat (the win-pressure axis).
    assert deltas["empire"]["imperial_threat"] > 0
    # Its sworn enemy the rebellion is grateful and emboldened.
    assert deltas["rebellion"]["gratitude"] > 0
    # The free rival (at war with the Empire) is grateful too.
    assert deltas[rival]["gratitude"] > 0
    # The client kingdom (friendly to the Empire) recoils.
    assert deltas["threen"]["fear"] > 0
    assert deltas["threen"]["gratitude"] < 0


def test_empire_never_thanks_a_sorcerer() -> None:
    engine, rival = _world_engine(1)
    # Killing the Empire's *enemy* does not earn the Empire's gratitude — only wariness.
    deltas = engine._relational_kill_deltas(rival, 0.2)
    assert "gratitude" not in deltas.get("empire", {})
    assert deltas["empire"].get("imperial_threat", 0) > 0
    # The victim's own faction fears you.
    assert deltas[rival]["fear"] > 0


def test_diminishing_returns() -> None:
    engine, _rival = _world_engine(1)
    first = engine._relational_kill_deltas("empire", 0.2)["empire"]["imperial_threat"]
    # Pretend the empire has already been hit many times: the next kill moves standing less.
    player = engine.state.player
    player.attack = 999
    for _ in range(8):
        foe = engine.spawn_actor(
            "legionary",
            "l",
            player.x,
            player.y + 1,
            1,
            1,
            0,
            "enemy",
            "melee",
            tags={"empire"},
            role="soldier",
        )
        engine.attack(player, foe)
    later = engine._relational_kill_deltas("empire", 0.2)["empire"]["imperial_threat"]
    assert later < first


def test_killing_a_realm_combatant_emits_deed_and_tally() -> None:
    engine, rival = _world_engine(1)
    player = engine.state.player
    player.attack = 999
    foe = engine.spawn_actor(
        "rival soldier",
        "r",
        player.x,
        player.y + 1,
        1,
        1,
        0,
        "enemy",
        "melee",
        identity=[rival],
        role="soldier",
    )
    engine.attack(player, foe)
    assert engine.kills_by_faction().get(rival) == 1
    assert any(d.type == "killed_combatant" for d in engine.state.deed_ledger.deeds)


def test_blood_feud_threshold_and_standing_tally() -> None:
    engine = GameEngine(seed=1, scenario="test_chamber")  # phase-0 empire + rebellion
    player = engine.state.player
    player.attack = 999
    for _ in range(BLOOD_FEUD_KILLS):
        foe = engine.spawn_actor(
            "legionary",
            "l",
            player.x,
            player.y + 1,
            1,
            1,
            0,
            "enemy",
            "melee",
            tags={"empire"},
            role="soldier",
        )
        engine.attack(player, foe)
    assert "empire" in engine.feuding_factions()
    text = "\n".join(describe_standing(engine))
    assert "Blood on your hands" in text
    assert "blood feud" in text.lower()


def test_dialogue_note_keys_to_npc_faction() -> None:
    engine = GameEngine(seed=1, scenario="test_chamber")
    player = engine.state.player
    player.attack = 999
    for _ in range(2):
        foe = engine.spawn_actor(
            "legionary",
            "l",
            player.x,
            player.y + 1,
            1,
            1,
            0,
            "enemy",
            "melee",
            tags={"empire"},
            role="soldier",
        )
        engine.attack(player, foe)
    # An imperial sees you as a killer of their own.
    scribe = engine.spawn_npc(
        "imperial scribe",
        "s",
        player.x + 2,
        player.y,
        role="clerk",
        backstory="files reports",
        tags={"empire"},
    )
    assert "our own" in engine._kill_standing_note(scribe)
    # A rebel sees you as a scourge of their enemies.
    rebel = engine.spawn_npc(
        "rebel sympathizer",
        "y",
        player.x - 2,
        player.y,
        role="townsfolk",
        backstory="hates the charter",
        identity=["rebel"],
    )
    assert engine._kill_standing_note(rebel)
