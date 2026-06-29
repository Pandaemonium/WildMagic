from __future__ import annotations

import json

from wildmagic.spell_contract import validate_resolution
from wildmagic.resolution_parsing import parse_resolution_json


def parse(data: dict[str, object]) -> dict[str, object]:
    return parse_resolution_json(json.dumps(data))


def test_singular_effect_and_cost_are_normalized_to_contract_lists() -> None:
    normalized = parse(
        {
            "accepted": True,
            "severity": "minor",
            "message": "Blue fire gathers around the goblin.",
            "effect": "damage",
            "target": "the nearest enemy",
            "details": {"amount": 7, "damage_type": "fire"},
            "cost": "3 mana",
            "rejected_reason": None,
        }
    )

    assert normalized["outcome_text"] == "Blue fire gathers around the goblin."
    effect = normalized["effects"][0]
    assert effect["type"] == "damage"
    assert effect["target"] == "nearest_enemy"
    assert effect["amount"] == 7
    assert effect["damage_type"] == "fire"
    assert normalized["costs"] == [{"type": "mana", "amount": 3}]
    assert validate_resolution(normalized) is None


def test_flavor_status_is_preserved_while_using_canonical_mechanics() -> None:
    normalized = parse(
        {
            "accepted": True,
            "severity": "moderate",
            "outcome_text": "Crystal closes over the bandit.",
            "effects": [
                {
                    "type": "status",
                    "target": "all hostiles",
                    "status": "crystallized",
                    "duration": 4,
                }
            ],
            "costs": [],
            "rejected_reason": None,
        }
    )

    assert normalized["effects"] == [
        {
            "type": "add_status",
            "target": "all_enemies",
            "status": "frozen",
            "duration": 4,
            "display_name": "crystallized",
        }
    ]
    assert validate_resolution(normalized) is None


def test_effect_misplaced_in_costs_is_recovered() -> None:
    normalized = parse(
        {
            "accepted": True,
            "severity": "minor",
            "outcome_text": "The wraith shines with a new vulnerability.",
            "effects": [{"type": "message", "message": "The light finds a flaw."}],
            "costs": [
                {
                    "type": "add_weakness",
                    "target": "the nearest enemy",
                    "damage_type": "radiant",
                    "amount": 25,
                }
            ],
            "rejected_reason": None,
        }
    )

    assert normalized["costs"] == []
    assert normalized["effects"][-1] == {
        "type": "add_weakness",
        "target": "nearest_enemy",
        "damage_type": "radiant",
        "amount": 25,
    }
    assert validate_resolution(normalized) is None


def test_nested_single_use_trigger_is_normalized() -> None:
    normalized = parse(
        {
            "accepted": True,
            "severity": "moderate",
            "outcome_text": "A retaliatory spark waits beneath the skin.",
            "effects": [
                {
                    "type": "trigger",
                    "trigger": {
                        "event": "when hit",
                        "once": True,
                        "action": "burn the attacker",
                    },
                }
            ],
            "costs": [],
            "rejected_reason": None,
        }
    )

    effect = normalized["effects"][0]
    assert effect["type"] == "create_trigger"
    assert effect["trigger"] == "when hit"
    assert effect["charges"] == 1
    assert effect["effects"] == [
        {
            "type": "damage",
            "target": "trigger_source",
            "amount": 5,
            "damage_type": "fire",
        }
    ]
    assert validate_resolution(normalized) is None


def test_bare_effect_object_is_wrapped_as_one_effect_resolution() -> None:
    normalized = parse(
        {
            "type": "create_tiles",
            "target": "prop_5",
            "radius": 1,
            "tile": "fire",
            "duration": 4,
        }
    )

    assert normalized["accepted"] is True
    assert normalized["effects"] == [
        {
            "type": "create_tiles",
            "target": "prop_5",
            "radius": 1,
            "tile": "fire",
            "duration": 4,
        }
    ]
    assert validate_resolution(normalized) is None


def test_common_output_wrapper_is_unwrapped() -> None:
    normalized = parse(
        {
            "input": "bind the goblin",
            "output": {
                "accepted": True,
                "severity": "minor",
                "message": "White cords snap tight.",
                "effects": [
                    {
                        "type": "add_status",
                        "target": "the nearest enemy",
                        "status": "bound",
                        "duration": 3,
                    }
                ],
                "costs": [{"type": "item", "item": "grave salt", "amount": 1}],
            },
        }
    )

    assert normalized["spell"] == "bind the goblin"
    assert normalized["outcome_text"] == "White cords snap tight."
    assert normalized["effects"][0]["target"] == "nearest_enemy"
    assert normalized["effects"][0]["status"] == "webbed"
    assert normalized["costs"] == [{"type": "item", "item": "grave salt", "amount": 1}]
    assert validate_resolution(normalized) is None


def test_item_cost_name_alias_is_normalized_to_item() -> None:
    normalized = parse(
        {
            "accepted": True,
            "severity": "moderate",
            "outcome_text": "Salt and slime draw a circle shut.",
            "effects": [
                {
                    "type": "add_status",
                    "target": "nearest_enemy",
                    "status": "webbed",
                    "duration": 4,
                }
            ],
            "costs": [
                {"type": "item", "name": "viscous residue", "amount": 1},
                {"type": "item", "reagent": "grave salt", "quantity": 2},
            ],
        }
    )

    assert normalized["costs"] == [
        {
            "type": "item",
            "name": "viscous residue",
            "amount": 1,
            "item": "viscous residue",
        },
        {
            "type": "item",
            "reagent": "grave salt",
            "quantity": 2,
            "item": "grave salt",
            "amount": 2,
        },
    ]
    assert validate_resolution(normalized) is None
