"""Provider wiring for the lore-card router (docs/LORE_CARDS.md §9).

Keeps the model call out of `lore_cards.py` (which stays pure data + functions). The
`route_call` inherits the consumer purpose's **load-time** Ollama options
(model / host / num_ctx / num_gpu / keep_alive) so it shares the already-resident runner
with zero reload, and overrides only **request-time** options: a small num_predict, low
temperature, the strict cards JSON-schema, and no thinking (§3.1, the latency lever).
"""

from __future__ import annotations

import json
from typing import Any, Callable

from .config import (
    get_canon_model,
    get_dialogue_model,
    get_lore_model,
    lore_cards_enabled,
    ollama_host,
    ollama_keep_alive,
    ollama_num_ctx,
    ollama_num_gpu,
    ollama_timeout_seconds,
)
from .llm_client import _post_ollama_chat, strip_thinking
from .lore_cards import (
    LORE_ROUTER_SCHEMA,
    LoreCard,
    normalize_lore_tags,
    select_lore_cards,
)

# Purpose -> model getter. The CONSUMER passes the purpose it is itself generating under, so
# the router lands on the model that is (or is about to be) resident for that work.
_PURPOSE_MODEL: dict[str, Callable[[], str]] = {
    "dialogue": get_dialogue_model,
    "canon": get_canon_model,
    "lore": get_lore_model,
}


def make_lore_route_call(
    purpose: str,
) -> Callable[[list[dict]], list[str] | None]:
    """Bind a generative router call to a consumer purpose. Returns selected card ids, or
    ``None`` on any failure (kept distinct from a successful empty ``[]`` — see
    `select_lore_cards`)."""
    model = _PURPOSE_MODEL.get(purpose, get_dialogue_model)()
    host = ollama_host(purpose)
    ctx = ollama_num_ctx(purpose)
    gpu = ollama_num_gpu(purpose)
    keep = ollama_keep_alive(purpose)
    timeout = ollama_timeout_seconds(purpose)

    def call(messages: list[dict]) -> list[str] | None:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "format": LORE_ROUTER_SCHEMA,
            "think": False,
            "keep_alive": keep,
            "options": {
                "temperature": 0.1,
                "num_predict": 96,
                "num_ctx": ctx,
                "num_gpu": gpu,
            },
        }
        try:
            resp = _post_ollama_chat(host, payload, timeout)
            content = strip_thinking(resp.get("message", {}).get("content") or "")
            cards = json.loads(content).get("cards")
            return [str(c) for c in cards] if isinstance(cards, list) else None
        except (OSError, KeyError, ValueError, TypeError):
            # OSError covers urllib's URLError/timeout; ValueError covers the HTTP-error
            # wrap and bad JSON. Any failure => deterministic fallback in the caller.
            return None

    return call


def dialogue_lore_cards(
    profile: Any,
    message: str,
    *,
    provider_name: str,
    region_name: str = "",
) -> list[LoreCard]:
    """Select the lore cards an NPC may draw on for this line. Returns [] when the feature
    is off. The router runs on the dialogue model only when the dialogue provider is a real
    Ollama backend; under mock it uses the deterministic ranking path (no server)."""
    if not lore_cards_enabled() or profile is None:
        return []
    lore: dict[str, int] = getattr(profile, "lore", None) or {}
    role = getattr(profile, "role", "") or ""
    route_call = None if provider_name == "mock" else make_lore_route_call("dialogue")
    blurb = role + (f" in {region_name}" if region_name else "")
    return select_lore_cards(
        lore,
        message,
        bias_tags=tuple(lore.keys()),  # soft bias toward this NPC's own expertise
        knower_blurb=blurb.strip(),
        route_call=route_call,
    )


def book_lore_cards(
    subjects: Any,
    title: str,
    *,
    author_level: int = 3,
    max_cards: int = 4,
) -> list[LoreCard]:
    """Select background world-canon for a book's THREADS slot. The book's `subjects` are
    authoritative HARD topic tags, so this uses the deterministic path (no router call,
    keeping the canon pipeline replay-safe). The book is modeled as a knower whose author
    knows their subjects deeply (docs/LORE_CARDS.md §6/§10.2)."""
    if not lore_cards_enabled():
        return []
    subj = normalize_lore_tags(subjects or [])
    if not subj:
        return []
    author_lore = {tag: author_level for tag in subj}
    return select_lore_cards(
        author_lore,
        title or "",
        subjects=subj,  # HARD topic — drives selection even when the title is opaque
        route_call=None,  # deterministic: subjects are authoritative, no LLM needed
        max_cards=max_cards,
    )
