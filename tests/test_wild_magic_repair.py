from __future__ import annotations

import json
from typing import Any

from wildmagic.engine import GameEngine
from wildmagic.wild_magic import MagicResolution, resolve_spell


BAD_AURA = {
    "accepted": True,
    "severity": "moderate",
    "outcome_text": "The charm tightens into a heat-dampening knot.",
    "effects": [
        {
            "type": "aura",
            "kind": "status",
            "radius": 3,
            "affects": "allies",
            "turns": 5,
            "label": "cooling ward",
            "duration": 2,
            "display_name": "heat-protective",
        }
    ],
    "costs": [{"type": "mana", "amount": 4}],
    "rejected_reason": None,
}


GOOD_AURA = {
    **BAD_AURA,
    "effects": [{**BAD_AURA["effects"][0], "status": "warded"}],
}


class RepairingProvider:
    name = "ollama"

    def __init__(self) -> None:
        self.contexts: list[dict[str, Any]] = []

    def resolve(self, spell: str, context: dict[str, Any]) -> str:
        self.contexts.append(context)
        if len(self.contexts) == 1:
            return json.dumps(BAD_AURA)
        return json.dumps(GOOD_AURA)


def test_empty_mechanical_aura_is_technical_failure_before_costs() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    mana_before = engine.state.player.mana
    turn_before = engine.state.turn

    outcome = engine.apply_wild_magic_resolution(dict(BAD_AURA))

    assert outcome.technical_failure
    assert not outcome.consumed_turn
    assert engine.state.player.mana == mana_before
    assert engine.state.turn == turn_before
    assert not any("Cost:" in str(message) for message in engine.state.messages)


def test_resolver_repairs_bad_aura_with_short_context() -> None:
    provider = RepairingProvider()

    result: MagicResolution = resolve_spell(
        provider,
        "cool the air with the charm",
        {
            "player": {"hp": 10},
            "room": {"huge": "context that should not be resent"},
            "supported_effects": ["aura", "add_resistance", "add_status"],
        },
    )

    assert not result.technical_failure
    assert result.data == GOOD_AURA
    assert len(provider.contexts) == 2
    repair = provider.contexts[1]["repair_invalid_resolution"]
    assert "room" not in provider.contexts[1]
    assert "status" in repair["valid_options"]
    assert "previous_json" in repair
    assert "heat-protective" in repair["previous_json"]
