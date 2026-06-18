from __future__ import annotations

from pathlib import Path

from wildmagic.models import MECHANICAL_STATUSES
from wildmagic.spell_contract import SUPPORTED_COSTS, SUPPORTED_EFFECTS


SCHEMA_DOC = Path("docs/WILD_MAGIC_SCHEMA.md")


def test_schema_doc_lists_supported_effects_and_costs() -> None:
    text = SCHEMA_DOC.read_text(encoding="utf-8")

    missing_effects = [
        effect for effect in sorted(SUPPORTED_EFFECTS) if f"`{effect}`" not in text
    ]
    missing_costs = [
        cost for cost in sorted(SUPPORTED_COSTS) if f"`{cost}`" not in text
    ]

    assert not missing_effects
    assert not missing_costs


def test_schema_doc_lists_mechanical_statuses() -> None:
    text = SCHEMA_DOC.read_text(encoding="utf-8")

    missing = [
        status for status in sorted(MECHANICAL_STATUSES) if f"`{status}`" not in text
    ]

    assert not missing
