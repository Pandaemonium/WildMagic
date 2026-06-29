from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any, Iterable

from .normalize import normalize_id


@dataclass(frozen=True)
class GeneratedCurio:
    """A lightweight semantic item that becomes interesting through reagent use."""

    name: str
    value: int
    material: str
    tags: tuple[str, ...]
    description: str
    source: str = "generated"

    def lore_metadata(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "material": self.material,
            "tags": list(self.tags),
            "generated": True,
            "source_detail": self.source,
        }

    def reward(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "quantity": 1,
            "description": self.description,
            **self.lore_metadata(),
        }


@dataclass(frozen=True)
class _Part:
    name: str
    value: int
    tags: tuple[str, ...]


_MATERIALS: tuple[_Part, ...] = (
    _Part("ash", 3, ("ash", "fire", "death")),
    _Part("bone", 5, ("bone", "death", "body")),
    _Part("brass", 8, ("brass", "metal", "bell")),
    _Part("blue wax", 6, ("wax", "law", "empire")),
    _Part("crystal", 20, ("crystal", "arcane", "fragile")),
    _Part("feather", 4, ("feather", "air", "beast")),
    _Part("glass", 12, ("glass", "light", "fragile")),
    _Part("iron", 10, ("iron", "metal", "conductive")),
    _Part("moss", 4, ("moss", "plant", "healing")),
    _Part("pearl", 45, ("pearl", "water", "moon", "beauty")),
    _Part("red thread", 5, ("thread", "blood", "binding")),
    _Part("river clay", 4, ("clay", "water", "earth")),
    _Part("salt", 4, ("salt", "ward", "dry")),
    _Part("vellum", 5, ("vellum", "paper", "lore")),
)

_FORMS: tuple[_Part, ...] = (
    _Part("bead", 2, ("small", "charm")),
    _Part("bell", 8, ("sound", "alarm")),
    _Part("button", 3, ("clothing", "memory")),
    _Part("chit", 4, ("trade", "token")),
    _Part("coin", 1, ("coin", "trade")),
    _Part("eye", 18, ("sight", "reveal")),
    _Part("knot", 4, ("binding", "thread")),
    _Part("lens", 16, ("sight", "divination")),
    _Part("seal", 14, ("law", "authority")),
    _Part("shard", 5, ("sharp", "fragment")),
    _Part("spool", 5, ("thread", "fate")),
    _Part("thimble", 6, ("craft", "protection")),
    _Part("tooth", 8, ("bite", "body")),
    _Part("vial", 10, ("bottle", "contained")),
)

_ODDITIES: tuple[_Part, ...] = (
    _Part("ash-sung", 8, ("song", "ash")),
    _Part("charter", 8, ("law", "empire")),
    _Part("debtor", 10, ("debt", "trade")),
    _Part("drowned", 8, ("water", "death")),
    _Part("forbidden", 12, ("lore", "secret")),
    _Part("hollowmere", 6, ("frontier", "water")),
    _Part("imperial", 10, ("empire", "authority")),
    _Part("moonlit", 12, ("moon", "beauty")),
    _Part("noon", 9, ("sun", "fire")),
    _Part("river", 5, ("water", "travel")),
    _Part("root-choked", 7, ("plant", "old_magic")),
    _Part("saint", 12, ("holy", "mercy")),
    _Part("saltmarket", 8, ("salt", "debt", "trade")),
    _Part("wild", 10, ("wild", "arcane")),
)

_THEME_TAGS: dict[str, tuple[str, ...]] = {
    "arcane": ("arcane", "crystal", "wild"),
    "bone": ("bone", "death"),
    "death": ("death", "bone", "salt"),
    "empire": ("empire", "law", "authority"),
    "fire": ("fire", "ash", "sun"),
    "lore": ("lore", "secret", "paper"),
    "magic": ("arcane", "wild", "crystal"),
    "natural": ("plant", "water", "earth"),
    "plant": ("plant", "moss", "root_choked_room"),
    "pre_charter": ("old_magic", "wild", "bone"),
    "secret": ("secret", "lore"),
    "slime": ("ooze", "poison", "wet"),
    "trade": ("trade", "coin", "debt"),
    "water": ("water", "moon", "river"),
    "weapons": ("iron", "sharp", "metal"),
}

_TEXTURES: tuple[str, ...] = (
    "warm at the edges",
    "scratched with tiny marks",
    "smelling faintly of rain",
    "too heavy for its size",
    "polished by many nervous thumbs",
    "cold in a way cloth should not be",
    "freckled with old soot",
)

_HINTS: dict[str, str] = {
    "arcane": "a stored spark waiting for a bad idea",
    "authority": "the weight of someone else's permission",
    "beauty": "a shimmer that refuses to sit still",
    "binding": "the suggestion of a knot tightening",
    "death": "a hush like earth over a coffin",
    "debt": "the itch of a promise unpaid",
    "empire": "the sour-blue taste of official ink",
    "fire": "a dry glow like noon under glass",
    "holy": "a tired little mercy",
    "law": "rules written smaller than eyesight",
    "lore": "a fact trying not to be forgotten",
    "moon": "pale light caught in a bend",
    "plant": "green patience and root-pressure",
    "salt": "a clean sting at the back of the tongue",
    "secret": "the feeling that someone hid it twice",
    "sound": "a note too quiet to hear directly",
    "trade": "the hand-to-hand shine of bargaining",
    "water": "a cool pull toward somewhere lower",
    "wild": "a happy, dangerous twitch",
}


def generate_curio(
    rng: random.Random,
    *,
    themes: Iterable[Any] = (),
    region_id: str | None = None,
    source: str = "generated",
) -> GeneratedCurio:
    """Generate one small semantic item from composable parts.

    The item has no bespoke mechanics. Its value and tags matter because the shared reagent
    system already lets wild magic spend and color spells with carried items.
    """

    theme_tags = _theme_tags(themes)
    if region_id:
        theme_tags.add(normalize_id(region_id))
    material = _choose_part(rng, _MATERIALS, theme_tags)
    form = _choose_part(rng, _FORMS, theme_tags)
    oddity = _choose_part(rng, _ODDITIES, theme_tags)
    tags = sorted(
        {
            *material.tags,
            *form.tags,
            *oddity.tags,
            *theme_tags.intersection(
                {
                    "arcane",
                    "authority",
                    "beauty",
                    "binding",
                    "death",
                    "debt",
                    "empire",
                    "fire",
                    "holy",
                    "law",
                    "lore",
                    "moon",
                    "plant",
                    "salt",
                    "secret",
                    "trade",
                    "water",
                    "wild",
                }
            ),
        }
    )
    value = max(1, material.value + form.value + oddity.value + rng.randint(0, 5))
    name = _dedupe_words(f"{oddity.name} {material.name} {form.name}")
    texture = rng.choice(_TEXTURES)
    hint = _hint_for(tags, rng)
    article = "An" if name[:1].lower() in {"a", "e", "i", "o", "u"} else "A"
    description = (
        f"{article} {name}, {texture}. It carries {hint}; useless until a spell "
        "decides otherwise."
    )
    return GeneratedCurio(
        name=name,
        value=value,
        material=material.name,
        tags=tuple(tags),
        description=description,
        source=source,
    )


def _theme_tags(themes: Iterable[Any]) -> set[str]:
    tags: set[str] = set()
    for theme in themes:
        key = normalize_id(str(theme or ""))
        if not key:
            continue
        tags.add(key)
        tags.update(_THEME_TAGS.get(key, ()))
    return tags


def _choose_part(
    rng: random.Random, parts: tuple[_Part, ...], theme_tags: set[str]
) -> _Part:
    weighted: list[_Part] = []
    for part in parts:
        overlap = len(set(part.tags) & theme_tags)
        weighted.extend([part] * (1 + overlap * 3))
    return weighted[rng.randrange(len(weighted))]


def _dedupe_words(name: str) -> str:
    words: list[str] = []
    seen: set[str] = set()
    for word in name.split():
        key = normalize_id(word)
        if key in seen:
            continue
        seen.add(key)
        words.append(word)
    return " ".join(words)


def _hint_for(tags: list[str], rng: random.Random) -> str:
    candidates = [_HINTS[tag] for tag in tags if tag in _HINTS]
    if not candidates:
        candidates = ["a little piece of the world's unfinished business"]
    return candidates[rng.randrange(len(candidates))]
