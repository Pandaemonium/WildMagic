"""Layer-1 procedural texture: grammars and tables for instant bulk variety.

This layer guarantees nothing is ever blank and manufactures the seed vocabulary
that LLM materialization (canon.py) consumes. A book placed here has a concrete
grammar-tier name ("a water-stained ledger of weather law") the moment the map
exists; its title, author, and pages stay unmaterialized until read or prewarmed.
"""
from __future__ import annotations

import random
from typing import Any


_BOOK_FORMS = (
    "volume", "ledger", "treatise", "folio", "chapbook", "codex",
    "commonplace book", "primer", "registry", "breviary",
)

_BOOK_CONDITIONS = (
    "water-stained", "soot-darkened", "mouse-chewed", "carefully rebound",
    "swollen with damp", "annotated in two hands", "missing its cover",
    "tied shut with twine", "smelling of tallow", "dog-eared",
)

_BOOK_BINDINGS = (
    "cracked leather", "stiff grey board", "oiled canvas", "scraped vellum",
    "thin pine slats", "wine-dark cloth",
)


def grammar_book(rng: random.Random, topics: list[str], era: str) -> dict[str, Any]:
    """A grammar-tier book entry: instant name + description, no model involved.

    The name is deliberately a category description, not a title — titles carry
    world texture and belong to the LLM at materialization time.
    """
    topic = rng.choice(topics) if topics else "matters no one remembers"
    form = rng.choice(_BOOK_FORMS)
    condition = rng.choice(_BOOK_CONDITIONS)
    binding = rng.choice(_BOOK_BINDINGS)
    return {
        "name": f"{condition} {form} of {topic}",
        "description": f"A {form} bound in {binding}, {condition}. It concerns {topic}.",
        "topic": topic,
        "form": form,
        "era": era,
    }
