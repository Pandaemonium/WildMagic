from __future__ import annotations

from pathlib import Path

import pytest

from wildmagic.spell_contract import (
    COST_DOCUMENTATION,
    EFFECT_DOCUMENTATION,
    OPERATION_REFERENCE_END,
    OPERATION_REFERENCE_START,
    SUPPORTED_COSTS,
    SUPPORTED_EFFECTS,
    render_operation_reference,
    update_operation_reference,
    validate_resolution,
)


ROOT = Path(__file__).resolve().parents[1]


def resolution(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "accepted": True,
        "severity": "minor",
        "outcome_text": "Reality bends.",
        "effects": [{"type": "message", "message": "Reality bends."}],
        "costs": [],
        "rejected_reason": None,
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    ("overrides", "expected_error"),
    [
        ({"accepted": "yes"}, "accepted must be a boolean"),
        ({"effects": []}, "accepted spells must have at least one effect"),
        ({"effects": "damage"}, "effects must be a list"),
        ({"costs": {"type": "mana"}}, "costs must be a list"),
        (
            {"effects": [{"type": "rewrite_reality"}]},
            "unsupported effect type: rewrite_reality",
        ),
        ({"costs": [{"type": "memory"}]}, "unsupported cost type: memory"),
        (
            {"effects": [{"type": "area_damage", "radius": "nearby"}]},
            "area_damage radius must be an integer",
        ),
        (
            {"effects": [{"type": "conjure_creature", "count": 13}]},
            "conjure_creature count must be between 1 and 12",
        ),
        (
            {"effects": [{"type": "create_trigger", "effects": []}]},
            "create_trigger effects must be a non-empty list",
        ),
    ],
)
def test_invalid_resolutions_report_specific_contract_errors(
    overrides: dict[str, object],
    expected_error: str,
) -> None:
    assert validate_resolution(resolution(**overrides)) == expected_error


def test_rejected_resolution_requires_a_reason_but_not_effects() -> None:
    rejected = resolution(
        accepted=False,
        effects=[],
        rejected_reason="The spell cannot fit through mortal hands.",
    )

    assert validate_resolution(rejected) is None

    rejected["rejected_reason"] = " "
    assert validate_resolution(rejected) == "rejected spells need a rejected_reason"


def test_contract_limits_effect_and_cost_collection_sizes() -> None:
    too_many_effects = [{"type": "message"} for _ in range(13)]
    too_many_costs = [{"type": "mana", "amount": 1} for _ in range(9)]

    assert (
        validate_resolution(resolution(effects=too_many_effects))
        == "effects must contain at most 12 entries"
    )
    assert (
        validate_resolution(resolution(costs=too_many_costs))
        == "costs must contain at most 8 entries"
    )


def test_operation_catalogues_drive_supported_types() -> None:
    assert SUPPORTED_EFFECTS == frozenset(EFFECT_DOCUMENTATION)
    assert SUPPORTED_COSTS == frozenset(COST_DOCUMENTATION)


def test_schema_operation_reference_matches_contract() -> None:
    schema = (ROOT / "docs" / "WILD_MAGIC_SCHEMA.md").read_text(encoding="utf-8")
    generated = schema.split(OPERATION_REFERENCE_START, 1)[1].split(
        OPERATION_REFERENCE_END, 1
    )[0]

    assert generated.strip() == render_operation_reference()


def test_operation_reference_updater_is_deterministic(tmp_path: Path) -> None:
    schema = tmp_path / "schema.md"
    schema.write_text(
        "\n".join(
            [
                "# Schema",
                OPERATION_REFERENCE_START,
                "stale",
                OPERATION_REFERENCE_END,
                "After.",
            ]
        ),
        encoding="utf-8",
    )

    assert update_operation_reference(schema) is True
    assert update_operation_reference(schema) is False
    assert render_operation_reference() in schema.read_text(encoding="utf-8")
