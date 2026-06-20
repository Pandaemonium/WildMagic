from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import audit_log_enabled


def _write_jsonl_audit(audit_path: Path, record: dict[str, Any]) -> str | None:
    if not audit_log_enabled():
        return None
    try:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
    except OSError:
        return None
    return str(audit_path)


def should_retry_resolution(
    resolved_provider_name: str, attempt: int, max_attempts: int
) -> bool:
    return resolved_provider_name == "ollama" and attempt + 1 < max_attempts


def retry_context(
    context: dict[str, Any], raw_response: str | None, error: str
) -> dict[str, Any]:
    """A compact repair payload for spell-resolution retries.

    Wild-magic repair should be fast: the model already chose an intent, so the retry only needs
    the spell, the invalid JSON, and the contract error/options. Do not resend the whole game
    context unless a future repair kind truly needs it.
    """
    valid_options = {}
    if "Valid status values:" in error:
        valid_options["status"] = error.split("Valid status values:", 1)[1].strip()
    updated = {
        "repair_invalid_resolution": {
            "error": error,
            "instruction": (
                "The previous response could not be parsed or validated. Return only one "
                "complete JSON object, fixing only the invalid fields."
            ),
            "valid_options": valid_options,
            "previous_json": (raw_response or "")[:1200],
        },
    }
    return updated
