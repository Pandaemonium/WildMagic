"""The deed interpreter (Phase A.2) — the LLM reading *meaning* off a spell outcome.

Combat kills already become deeds deterministically (Phase A.1, via the death path). What
stays genuinely ambiguous is *non-lethal* wild magic: did that conjuring raise the dead?
raze a building? desecrate a shrine? unleash an atrocity? Effect types (`summon`,
`transform_entity`, …) can't answer that — the answer lives in the semantic outcome, which
is exactly what an LLM reads well (D5: rules for the clear-cut, the LLM for the ambiguous).

This module follows the established provider pattern (lore.py): a `DeedInterpreterProvider`
protocol with Ollama / Mock / Auto implementations, a `resolve_deed_interpretation` that
audits to JSONL, and — crucially — a **deterministic fallback** (`fallback_classify`) that
runs offline, in tests, and in replay so the skeleton never depends on a backend. The
interpreter only ever classifies into the bounded `DEED_TYPES`; consequences still come
from the deterministic rules table (deeds.py), keeping the world coherent and replay-safe.

The classification is recorded on the wild-magic action record (reusing that replay
channel), so a replay reproduces the same deed without a model call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import urllib.error
from typing import Any, Protocol

from .config import (
    audit_dir,
    fallbacks_enabled,
    get_deeds_model,
    get_deeds_provider,
    ollama_deeds_num_predict,
    ollama_host,
    ollama_json_format_enabled,
    ollama_keep_alive,
    ollama_num_ctx,
    ollama_num_gpu,
    ollama_temperature,
    ollama_thinking_enabled,
    ollama_timeout_seconds,
)
from .llm_client import (
    _post_ollama_chat_with_json_retry,
    normalize_ollama_url,
    strip_thinking,
)
from .llm_resolver import _write_jsonl_audit
from .normalize import normalize_id
from .prompts import DEED_INTERPRETER_SYSTEM_PROMPT


#: The deed types the interpreter may assign (the non-combat, ambiguous acts). A subset of
#: DEED_TYPES — combat deeds are emitted by the rules path, not classified here.
INTERPRETABLE_DEED_TYPES: tuple[str, ...] = (
    "raised_dead",
    "razed_building",
    "desecration",
    "cast_atrocity",
)

# The cheap, deterministic gate + fallback. The GATE is broad (it decides whether to spend
# a model call at all); the FALLBACK is conservative (it must classify deterministically
# offline, so it only fires on strong, specific phrasing — the LLM adds the recall).
_GATE_KEYWORDS: tuple[str, ...] = (
    "dead",
    "corpse",
    "undead",
    "skeleton",
    "skeletal",
    "zombie",
    "revenant",
    "reanimat",
    "raise",
    "raised",
    "rise from",
    "raze",
    "razed",
    "collapse",
    "crumble",
    "rubble",
    "demolish",
    "topple",
    "shatter",
    "level the",
    "burn down",
    "burns down",
    "bring down",
    "desecrat",
    "defile",
    "profane",
    "altar",
    "shrine",
    "grave",
    "tomb",
    "sacred",
    "holy ground",
    "unhallow",
    "sepulcher",
    "cataclysm",
    "catastroph",
    "firestorm",
    "inferno",
    "devastat",
    "annihilat",
    "maelstrom",
    "wildfire",
)

# Conservative deterministic classification: ordered (type, required-substring) rules. The
# first match wins. Phrasing is specific to avoid false positives offline.
_FALLBACK_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "raised_dead",
        (
            "raise the dead",
            "raised the dead",
            "reanimat",
            "skeleton rises",
            "skeletons rise",
            "the dead rise",
            "dead walk",
            "undead servant",
            "animate the corpse",
            "animate the dead",
        ),
    ),
    ("desecration", ("desecrat", "defile", "unhallow", "profane the")),
    (
        "razed_building",
        (
            "razed",
            "raze the",
            "collapses into rubble",
            "brought down",
            "brings down",
            "reduced to rubble",
            "topples the",
            "burns down",
        ),
    ),
    (
        "cast_atrocity",
        (
            "cataclysm",
            "firestorm",
            "engulfs everything",
            "annihilat",
            "catastroph",
            "devastates the",
        ),
    ),
)


@dataclass
class DeedInterpretation:
    """The interpreter's verdict on one outcome. ``deed_type`` is None when the outcome is
    not a deed (the common case)."""

    deed_type: str | None
    magnitude: float = 0.3
    summary: str = ""
    target_tags: list[str] | None = None
    interpretation_source: str = "fallback"  # "llm" | "fallback"
    technical_failure: bool = False
    error: str | None = None
    provider_name: str = "fallback"
    raw_response: str | None = None
    audit_path: str | None = None

    def to_record(self) -> dict[str, Any]:
        """The compact form recorded on the wild-magic action for replay fidelity."""
        return {
            "deed_type": self.deed_type,
            "magnitude": self.magnitude,
            "summary": self.summary,
            "target_tags": list(self.target_tags or []),
            "interpretation_source": self.interpretation_source,
        }


def outcome_is_deed_candidate(text: str) -> bool:
    """Cheap gate: does this spell outcome even hint at an interpretable deed? Keeps the
    common case (ordinary spells) a zero-call path."""
    lowered = text.lower()
    return any(keyword in lowered for keyword in _GATE_KEYWORDS)


def fallback_classify(context: dict[str, Any]) -> DeedInterpretation:
    """The deterministic interpreter used offline/in tests/in replay. Conservative: only a
    strong, specific phrase classifies a deed; otherwise it's not a deed."""
    text = f"{context.get('spell', '')} {context.get('outcome', '')}".lower()
    for deed_type, needles in _FALLBACK_RULES:
        if any(needle in text for needle in needles):
            return DeedInterpretation(
                deed_type=deed_type,
                magnitude=0.3,
                summary=_fallback_summary(deed_type),
                target_tags=_fallback_target_tags(deed_type),
                interpretation_source="fallback",
                provider_name="fallback",
            )
    return DeedInterpretation(
        deed_type=None, interpretation_source="fallback", provider_name="fallback"
    )


def _fallback_summary(deed_type: str) -> str:
    return {
        "raised_dead": "raised the dead to walk",
        "razed_building": "brought a structure down in rubble",
        "desecration": "defiled what others hold sacred",
        "cast_atrocity": "unleashed a catastrophe",
    }.get(deed_type, deed_type.replace("_", " "))


def _fallback_target_tags(deed_type: str) -> list[str]:
    return {
        "raised_dead": ["dead"],
        "razed_building": ["structure"],
        "desecration": ["shrine"],
        "cast_atrocity": [],
    }.get(deed_type, [])


class DeedInterpreterProvider(Protocol):
    name: str

    def interpret(self, context: dict[str, Any]) -> str: ...


class OllamaDeedInterpreterProvider:
    name = "ollama"
    purpose = "deeds"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._model_override = model
        self.model = model or get_deeds_model()
        self.base_url = (
            normalize_ollama_url(base_url) if base_url else ollama_host(self.purpose)
        )
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else ollama_timeout_seconds(self.purpose)
        )

    def interpret(self, context: dict[str, Any]) -> str:
        payload = {
            "model": self._model_override or get_deeds_model(),
            "stream": False,
            "think": ollama_thinking_enabled(self.purpose),
            "messages": [
                {"role": "system", "content": DEED_INTERPRETER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context, ensure_ascii=True)},
            ],
            "options": {
                "temperature": ollama_temperature(),
                "top_p": 0.9,
                "num_predict": ollama_deeds_num_predict(),
                "num_ctx": ollama_num_ctx(self.purpose),
                "num_gpu": ollama_num_gpu(self.purpose),
            },
            "keep_alive": ollama_keep_alive(self.purpose),
        }
        if ollama_json_format_enabled(self.purpose):
            payload["format"] = "json"
        data = _post_ollama_chat_with_json_retry(
            self.base_url, payload, self.timeout_seconds
        )
        content = data.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama response did not include message.content")
        return content


class MockDeedInterpreterProvider:
    """A deterministic stand-in that classifies from the same conservative phrasing as the
    fallback — so tests can exercise the LLM path without a backend."""

    name = "mock"

    def interpret(self, context: dict[str, Any]) -> str:
        verdict = fallback_classify(context)
        return json.dumps(
            {
                "deed_type": verdict.deed_type or "none",
                "magnitude": verdict.magnitude,
                "summary": verdict.summary,
                "target_tags": verdict.target_tags or [],
            }
        )


class AutoDeedInterpreterProvider:
    name = "auto"

    def __init__(self) -> None:
        self.ollama = OllamaDeedInterpreterProvider()
        self.mock = MockDeedInterpreterProvider()
        self.last_provider_name = "ollama"

    def interpret(self, context: dict[str, Any]) -> str:
        try:
            self.last_provider_name = self.ollama.name
            return self.ollama.interpret(context)
        except (OSError, TimeoutError, urllib.error.URLError, ValueError):
            if not fallbacks_enabled():
                raise
            self.last_provider_name = self.mock.name
            return self.mock.interpret(context)


def make_deed_interpreter_provider(
    provider_name: str | None = None,
) -> DeedInterpreterProvider | None:
    """None means "no LLM interpreter" — the engine then uses the deterministic fallback
    only (offline, tests, replay)."""
    provider = (provider_name or get_deeds_provider()).lower().strip()
    if provider in {"off", "none", "disabled"}:
        return None
    if provider == "mock":
        return MockDeedInterpreterProvider()
    if provider == "ollama":
        return OllamaDeedInterpreterProvider()
    return AutoDeedInterpreterProvider()


def resolve_deed_interpretation(
    provider: DeedInterpreterProvider | None, context: dict[str, Any]
) -> DeedInterpretation:
    """Classify one outcome. With no provider (or on any failure) returns the deterministic
    fallback, so the engine always gets a usable, replay-safe verdict."""
    if provider is None:
        return fallback_classify(context)
    resolved_name = _provider_name(provider)
    raw: str | None = None
    try:
        raw = provider.interpret(context)
        verdict = _parse_interpretation(raw)
        verdict.provider_name = resolved_name
        verdict.raw_response = raw
        verdict.audit_path = _write_audit(context, raw, verdict, None, resolved_name)
        return verdict
    except (
        OSError,
        TimeoutError,
        urllib.error.URLError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        # Degrade to the deterministic fallback — never break the spell on a bad verdict.
        verdict = fallback_classify(context)
        verdict.technical_failure = True
        verdict.error = str(exc)
        verdict.raw_response = raw
        verdict.audit_path = _write_audit(
            context, raw, verdict, str(exc), _provider_name(provider)
        )
        return verdict


def _parse_interpretation(raw: str) -> DeedInterpretation:
    cleaned = strip_thinking(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise TypeError("deed interpretation was not a JSON object")
    raw_type = normalize_id(str(parsed.get("deed_type") or "none"))
    deed_type = raw_type if raw_type in INTERPRETABLE_DEED_TYPES else None
    magnitude = _bounded_float(parsed.get("magnitude"), 0.1, 1.0, 0.3)
    summary = re.sub(r"\s+", " ", str(parsed.get("summary") or "")).strip()[:160]
    tags_raw = parsed.get("target_tags")
    if isinstance(tags_raw, str):
        tags_raw = re.split(r"[,;/]", tags_raw)
    target_tags = [
        normalize_id(str(t)) for t in (tags_raw or []) if normalize_id(str(t))
    ][:3]
    return DeedInterpretation(
        deed_type=deed_type,
        magnitude=magnitude,
        summary=summary if deed_type else "",
        target_tags=target_tags,
        interpretation_source="llm",
    )


def _bounded_float(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, parsed))


def _provider_name(provider: DeedInterpreterProvider | None) -> str:
    if isinstance(provider, AutoDeedInterpreterProvider):
        return provider.last_provider_name
    return getattr(provider, "name", "fallback")


def _write_audit(
    context: dict[str, Any],
    raw_response: str | None,
    verdict: DeedInterpretation,
    error: str | None,
    resolved_provider_name: str,
) -> str | None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": resolved_provider_name,
        "prompt": {
            "messages": [
                {"role": "system", "content": DEED_INTERPRETER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context, ensure_ascii=True)},
            ],
            "context": context,
        },
        "raw_response": raw_response,
        "verdict": verdict.to_record(),
        "technical_failure": verdict.technical_failure,
        "error": error,
    }
    return _write_jsonl_audit(audit_dir() / "deed_interp_audit.jsonl", record)
