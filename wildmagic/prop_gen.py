"""Prop generation provider — one short JSON call dresses a room with set-pieces.

Experimental. Mirrors the town-generation shape (town_gen.py): a Protocol provider
with Ollama + Mock variants, a tolerant parser, and JSONL audit. The engine drives
these calls in the background per room and swaps the results in only for props the
player has not seen yet (engine.py). See docs/ARCHITECTURE.md and the plan in chat.

The generated props are pure set-dressing: ambient room flavor, never structural or
quest props. Tags are mostly free-form flavor that the wild-magic resolver reads as
idiom, but a recognized subset (flammable, wood, plant, water, web, snaring, ...) is
mechanically load-bearing (combat.py), so the prompt steers the model toward reusing
that vocabulary where it applies — otherwise a wooden chair won't burn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Protocol

from .config import audit_dir, get_props_model, get_props_provider
from .llm_client import (
    _post_ollama_chat,
    strip_thinking,
    normalize_ollama_url,
    ollama_host,
    ollama_timeout_seconds,
    ollama_num_ctx,
    ollama_num_gpu,
    ollama_keep_alive,
    ollama_thinking_enabled,
    ollama_json_format_enabled,
    ollama_props_num_predict,
    ollama_props_temperature,
)
from .llm_resolver import _write_jsonl_audit
from .prompts import PROPS_SYSTEM_PROMPT, MECHANICAL_TAGS_PROMPT

# Tags the engine actually reacts to (fire-spread, snaring, etc.). Surfaced to the
# model in the call context as the vocabulary to prefer; anything else is flavor.
MECHANICAL_TAGS: tuple[str, ...] = MECHANICAL_TAGS_PROMPT

_MAX_PROPS_PER_BATCH = 6


@dataclass
class PropSpec:
    """A generated set-dressing prop. `char` may be empty — the engine assigns a
    glyph by tag when the model omits or fumbles it."""

    name: str
    description: str
    char: str = ""
    blocks: bool = False
    tags: list[str] = field(default_factory=list)


def _clean_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit].strip()


def _clean_char(value: Any) -> str:
    """One printable, non-space ASCII glyph, or '' for the engine to fill in."""
    for ch in str(value or ""):
        if ch.isprintable() and not ch.isspace() and ord(ch) < 128:
            return ch
    return ""


def _clean_tags(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    seen: list[str] = []
    for raw in value:
        tag = "_".join(str(raw).lower().split())
        tag = "".join(c for c in tag if c.isalnum() or c == "_")
        if tag and tag not in seen:
            seen.append(tag)
        if len(seen) >= 8:
            break
    return seen


def parse_prop_batch(raw: str) -> list[PropSpec]:
    """Parse a JSON batch from the LLM into validated PropSpecs, tolerating slop.

    Accepts either {"props": [...]} or a bare list. Each prop needs at least a name
    and a description; everything else is sanitized or defaulted."""
    data = json.loads(strip_thinking(raw).strip())
    if isinstance(data, dict):
        items = data.get("props") or data.get("items") or []
    elif isinstance(data, list):
        items = data
    else:
        items = []
    specs: list[PropSpec] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = _clean_text(item.get("name"), 40)
        description = _clean_text(item.get("description"), 200)
        if not name or not description:
            continue
        specs.append(
            PropSpec(
                name=name,
                description=description,
                char=_clean_char(item.get("char")),
                blocks=bool(item.get("blocks", False)),
                tags=_clean_tags(item.get("tags")),
            )
        )
        if len(specs) >= _MAX_PROPS_PER_BATCH:
            break
    return specs


class PropProvider(Protocol):
    name: str

    def generate(self, context: dict[str, Any]) -> list[PropSpec]: ...


class OllamaPropProvider:
    name = "ollama"
    purpose = "props"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._model_override = model
        self.model = model or get_props_model()
        self.base_url = (
            normalize_ollama_url(base_url) if base_url else ollama_host(self.purpose)
        )
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else ollama_timeout_seconds(self.purpose)
        )

    def generate(self, context: dict[str, Any]) -> list[PropSpec]:
        payload = {
            "model": self._model_override or get_props_model(),
            "stream": False,
            "think": ollama_thinking_enabled(self.purpose),
            "messages": [
                {"role": "system", "content": PROPS_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context, ensure_ascii=True)},
            ],
            "options": {
                "temperature": ollama_props_temperature(),
                "top_p": 0.95,
                "num_predict": ollama_props_num_predict(),
                "num_ctx": ollama_num_ctx(self.purpose),
                "num_gpu": ollama_num_gpu(self.purpose),
            },
            "keep_alive": ollama_keep_alive(self.purpose),
        }
        if ollama_json_format_enabled(self.purpose):
            payload["format"] = "json"
        try:
            data = _post_ollama_chat(self.base_url, payload, self.timeout_seconds)
        except ValueError as exc:
            if (
                "Unexpected empty grammar stack" not in str(exc)
                or "format" not in payload
            ):
                raise
            retry_payload = dict(payload)
            retry_payload.pop("format", None)
            data = _post_ollama_chat(self.base_url, retry_payload, self.timeout_seconds)
        content = data.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            _write_prop_audit(self, context, None, None, True, "no message.content")
            raise ValueError("Ollama response did not include message.content")
        try:
            specs = parse_prop_batch(content)
        except Exception as exc:
            _write_prop_audit(self, context, content, None, True, str(exc))
            raise
        _write_prop_audit(self, context, content, specs, False, None)
        return specs


class MockPropProvider:
    """Deterministic offline stand-in: derives a small, varied batch from the room
    context so tests and demos are reproducible without a model."""

    name = "mock"

    def generate(self, context: dict[str, Any]) -> list[PropSpec]:
        room = context.get("room") or {}
        region = str(context.get("region") or "the wild")
        room_type = str(room.get("room_type") or "chamber")
        era = str(room.get("era") or "old")
        condition = str(room.get("condition") or "dusty")
        count = max(1, min(_MAX_PROPS_PER_BATCH, int(context.get("count") or 2)))
        palette = [
            ("oddment", "%", False, ["debris"]),
            ("relic", "*", False, ["magic", "fragile"]),
            ("furnishing", "n", True, ["wood", "flammable"]),
            ("vessel", "u", False, ["stone"]),
            ("growth", "p", False, ["plant", "flammable"]),
            ("marking", ";", False, ["stone", "lore"]),
        ]
        specs: list[PropSpec] = []
        for i in range(count):
            base, char, blocks, tags = palette[i % len(palette)]
            specs.append(
                PropSpec(
                    name=f"{condition} {room_type} {base}",
                    description=(
                        f"A {condition} {base} of {region}, left from the {era} days "
                        f"in this {room_type}."
                    ),
                    char=char,
                    blocks=blocks,
                    tags=list(tags),
                )
            )
        return specs


def _write_prop_audit(
    provider: PropProvider,
    context: dict[str, Any],
    raw_response: str | None,
    specs: list[PropSpec] | None,
    technical_failure: bool,
    error: str | None,
) -> str | None:
    audit_path = audit_dir() / "prop_audit.jsonl"
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": getattr(provider, "name", "unknown"),
        "model": getattr(provider, "model", None),
        "ollama_base_url": getattr(provider, "base_url", None),
        "prompt": {
            "messages": [
                {"role": "system", "content": PROPS_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context, ensure_ascii=True)},
            ],
            "context": context,
        },
        "raw_response": raw_response,
        "props": [spec.__dict__ for spec in specs] if specs is not None else None,
        "technical_failure": technical_failure,
        "error": error,
    }
    return _write_jsonl_audit(audit_path, record)


def make_prop_provider(provider_name: str | None = None) -> PropProvider | None:
    """Return a prop provider, or None when prop generation is disabled.

    'off' (or 'none') -> None (pure static prop list). 'mock' -> deterministic stub.
    'ollama'/'auto'/anything else -> Ollama. Auto-fallback to the static list when
    Ollama is unreachable is handled by the engine (it probes first and keeps the
    already-placed static props on any failure)."""
    provider = (provider_name or get_props_provider()).lower().strip()
    if provider in {"off", "none", "static", "disabled"}:
        return None
    if provider == "mock":
        return MockPropProvider()
    return OllamaPropProvider()
