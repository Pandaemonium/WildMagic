from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


def _write_jsonl_audit(audit_path: Path, record: dict[str, Any]) -> str | None:
    if os.environ.get("WILDMAGIC_AUDIT_LOG", "1").lower().strip() in {"0", "false", "no", "off"}:
        return None
    try:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
    except OSError:
        return None
    return str(audit_path)


def should_retry_resolution(resolved_provider_name: str, attempt: int, max_attempts: int) -> bool:
    return resolved_provider_name == "ollama" and attempt + 1 < max_attempts


def retry_context(context: dict[str, Any], raw_response: str | None, error: str) -> dict[str, Any]:
    updated = dict(context)
    updated["retry_after_invalid_resolution"] = {
        "error": error,
        "instruction": "The previous response could not be parsed or validated. Return only one complete JSON object.",
        "previous_response_prefix": (raw_response or "")[:600],
    }
    return updated
