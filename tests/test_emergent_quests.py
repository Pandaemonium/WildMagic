from __future__ import annotations

from wildmagic.deeds import Deed
from wildmagic.engine import GameEngine
from wildmagic.promises import Objective, Reward
from wildmagic.quests import deed_satisfies


def _engine() -> GameEngine:
    return GameEngine(seed=1, scenario="test_chamber")


def _quest(engine: GameEngine, name: str, objective: Objective, reward=None):
    return engine.add_quest_promise(
        name=name,
        description=f"{name}.",
        contact="Giver",
        location="here",
        objective=objective,
        reward=reward,
    )


def test_objective_vocabulary_widened() -> None:
    for kind in ("rescue", "defend", "slay", "clear", "avenge"):
        obj = Objective.from_dict({"type": kind, "data": {}})
        assert obj is not None and obj.type == kind


def test_deed_satisfies_reads_match_spec() -> None:
    obj = Objective(
        "rescue", {"deed_types": ["freed_captive"], "subject_refs": ["soul:7"]}
    )
    hit = Deed(
        id="d",
        turn=1,
        zone=(0, 0),
        type="freed_captive",
        magnitude=0.4,
        actor="player",
        source="interaction",
        subject_refs=["soul:7"],
    )
    miss = Deed(
        id="d2",
        turn=1,
        zone=(0, 0),
        type="freed_captive",
        magnitude=0.4,
        actor="player",
        source="interaction",
        subject_refs=["soul:9"],
    )
    assert deed_satisfies(obj, hit)
    assert not deed_satisfies(obj, miss)


def test_rescue_quest_closes_by_freeing_the_captive() -> None:
    engine = _engine()
    player = engine.state.player
    captive = engine.spawn_npc(
        "Mara",
        "c",
        player.x + 1,
        player.y,
        role="captive",
        backstory="a prisoner",
        tags={"bound"},
    )
    quest = _quest(
        engine,
        "Find Mara",
        Objective("rescue", {"subject_refs": [captive.soul_id], "count": 1}),
        reward=Reward(gold=10, reputation={"rebellion": 1}),
    )
    gold_before = player.inventory.get("gold", 0)
    assert engine.free_captive() is True
    # Closed by the deed, immediately — no backtracking, no turn-in.
    assert quest.status == "objective_met"
    # The giver's reward settles on the world tick (the deferred half of the hybrid reward).
    engine.run_world_tick()
    assert quest.status == "fulfilled"
    assert player.inventory.get("gold", 0) == gold_before + 10


def test_slay_quest_closes_on_a_matching_kill() -> None:
    engine = _engine()
    player = engine.state.player
    player.attack = 999
    quest = _quest(
        engine,
        "Strike the Empire",
        Objective("slay", {"victim_faction": "empire", "count": 1}),
    )
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
    assert quest.status == "objective_met"


def test_clear_quest_counts_multiple_kills() -> None:
    engine = _engine()
    player = engine.state.player
    player.attack = 999
    quest = _quest(
        engine,
        "Clear the legion",
        Objective("clear", {"victim_faction": "empire", "count": 2}),
    )
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
    assert quest.status == "objective_met"


def test_rescue_mutates_to_avenge_when_the_subject_dies() -> None:
    engine = _engine()
    player = engine.state.player
    player.attack = 999
    mara = engine.spawn_npc(
        "Mara",
        "c",
        player.x + 1,
        player.y,
        role="captive",
        backstory="a prisoner",
        tags={"bound"},
    )
    rescue = _quest(
        engine,
        "Find Mara",
        Objective(
            "rescue",
            {"subject_refs": [mara.soul_id], "subject_name": "Mara", "count": 1},
        ),
    )
    # Mara is killed before she can be freed.
    engine.attack(player, mara)
    engine.run_world_tick()
    assert rescue.status == "changed"
    assert any(p.subject == "Avenge Mara" for p in engine.state.promises)


def test_an_npc_concern_becomes_a_quest_and_closes_from_play() -> None:
    engine = _engine()
    player = engine.state.player
    captive = engine.spawn_npc(
        "Mara",
        "c",
        player.x + 1,
        player.y,
        role="captive",
        backstory="a prisoner",
        tags={"bound"},
    )
    innkeeper = engine.spawn_npc(
        "Innkeeper",
        "i",
        player.x - 1,
        player.y,
        role="innkeeper",
        backstory="runs the inn",
    )
    # The innkeeper carries a plight: their missing daughter (the captive nearby).
    engine.state.npc_profiles[innkeeper.id].concern = {
        "type": "rescue",
        "subject": "my daughter Mara",
        "subject_soul": captive.soul_id,
        "reward_gold": 15,
    }
    # The plight is voiced in dialogue, and engaging the giver opens the quest.
    context = engine.state.npc_profiles[innkeeper.id].to_dialogue_context()
    assert "my_concern" in context
    quest = engine.register_heard_concern(innkeeper.id)
    assert quest is not None and quest.objective.type == "rescue"
    # And it closes from play — freeing Mara, no turn-in.
    assert engine.free_captive() is True
    assert quest.status == "objective_met"
