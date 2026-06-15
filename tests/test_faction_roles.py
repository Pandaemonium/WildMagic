"""Stable faction-role abstraction (minimal Phase C foundation, per Codex feedback).

The emergent systems target *roles* (empire bloc / resistance / player_org), not literal
`empire`/`rebellion` ids, so they generalize the moment Phase C seeds a full roster. Deed
consequences are written by role and resolved to the concrete faction(s) filling it; deed
location is keyed by place (zone + depth) so dungeon levels don't blur.
"""

from __future__ import annotations

from wildmagic.engine import GameEngine
from wildmagic.factions import ROLE_TO_KINDS, seed_phase0_factions


def _spawn_imperial(engine: GameEngine, x: int, y: int):
    return engine.spawn_actor(
        "legion", "l", x, y, 1, 1, 0, "enemy", "melee", tags={"empire"}
    )


def test_role_queries_resolve_to_concrete_factions() -> None:
    ledger = seed_phase0_factions()
    assert ledger.ids_by_role("empire") == ["empire"]
    assert ledger.ids_by_role("resistance") == ["rebellion"]
    assert ledger.ids_by_role("rival") == []  # unfilled on the scaffold
    assert ledger.primary("empire").id == "empire"
    assert ledger.primary("resistance").id == "rebellion"
    assert ledger.primary("rival") is None
    assert "empire_core" in ROLE_TO_KINDS["empire"]


def test_deed_consequences_resolve_role_to_concrete_ids() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    player.attack = 99
    foe = _spawn_imperial(engine, player.x, player.y + 1)
    engine.attack(player, foe)
    deed = engine.state.deed_ledger.deeds[0]
    # Stored deltas are keyed by concrete faction id, not the rule's role name.
    assert "empire" in deed.standing_deltas
    assert "rebellion" in deed.standing_deltas
    assert "resistance" not in deed.standing_deltas


def test_consequences_do_not_blur_across_depth() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    player.attack = 99
    engine.spawn_npc("drover", "d", player.x, player.y + 2, role="drover", backstory="")
    foe = _spawn_imperial(engine, player.x, player.y + 1)
    engine.attack(player, foe)  # deed recorded at depth 1
    engine.run_world_tick()

    deed = engine.state.deed_ledger.deeds[0]
    assert deed.place_key == "0,0@1"

    # On a different depth, the surface deed leaves no mark.
    engine.state.depth = 2
    engine._render_deed_consequences()
    assert not [e for e in engine.state.entities.values() if "consequence" in e.tags]

    # Back at the original depth, the mark appears.
    engine.state.depth = 1
    engine._render_deed_consequences()
    assert [e for e in engine.state.entities.values() if "consequence" in e.tags]
