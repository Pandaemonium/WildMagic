from __future__ import annotations

from wildmagic.actions import GameSession
from wildmagic.engine import GameEngine


def _beaten_enemy(engine: GameEngine, name: str = "legionary"):
    player = engine.state.player
    foe = engine.spawn_actor(
        name,
        "l",
        player.x + 1,
        player.y,
        12,
        1,
        0,
        "enemy",
        "melee",
        tags={"soldier"},
        identity=["imperial"],
        role="soldier",
    )
    foe.hp = 3
    engine.state.visible.add(engine.tile_key(foe.x, foe.y))
    return foe


def test_spare_beaten_enemy_records_mercy_and_stands_them_down() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    foe = _beaten_enemy(engine)

    assert engine.spare_enemy() is True

    assert "spared" in foe.tags
    assert foe.faction == "neutral"
    assert not engine.is_hostile_to(foe, engine.state.player)
    assert any(deed.type == "spared_enemy" for deed in engine.state.deed_ledger.deeds)

    engine.run_world_tick()
    assert "merciful" in engine.legend_words(engine.state.player_soul_id)


def test_spare_requires_leverage() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    foe = _beaten_enemy(engine)
    foe.hp = foe.max_hp
    turn = engine.state.turn

    assert engine.spare_enemy() is False

    assert "spared" not in foe.tags
    assert foe.faction == "enemy"
    assert engine.state.turn == turn
    assert not any(
        deed.type == "spared_enemy" for deed in engine.state.deed_ledger.deeds
    )


def test_spare_command_uses_shared_action_layer() -> None:
    session = GameSession(seed=7, scenario="test_chamber", provider_name="mock")
    foe = _beaten_enemy(session.engine, name="wall sergeant")

    result = session.execute_command("spare sergeant")

    assert result.action == "spare"
    assert result.success
    assert result.consumed_turn
    assert "spared" in foe.tags
