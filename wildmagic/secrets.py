"""Engine-owned secret resolution for the investigate verb.

The engine decides everything mechanical about a secret before any model is
prompted: whether it exists (placed at generation as a RoomProfile secret slot),
what anchors it, what the reward is, and how long searching takes. The LLM only
words the clue. None of these functions call a provider.
"""
from __future__ import annotations

import random
from typing import Any


# Searching takes in-game time; the danger clock keeps running. Uniform rule:
# even apparently safe rooms cost these turns (towns, libraries, camps alike).
_DIFFICULTY_TURNS = {"plain": 1, "careful": 2, "demanding": 3}


# Reward pools keyed by slot reward tag. The engine picks the actual reward;
# the LLM may describe or evoke it but never chooses or replaces it.
# Entries: (inventory name, quantity_range)
_REWARD_POOLS: dict[str, list[tuple[str, tuple[int, int]]]] = {
    "lore": [
        ("inkstained letter", (1, 1)),
        ("scrap of old vellum", (1, 1)),
        ("wax-sealed note", (1, 1)),
    ],
    "magic": [
        ("mana crystal", (1, 1)),
        ("chalk", (1, 2)),
    ],
    "arcane": [
        ("mana crystal", (1, 1)),
        ("smoke vial", (1, 1)),
    ],
    "death": [
        ("grave salt", (1, 2)),
        ("polished knucklebone", (1, 1)),
    ],
    "bone": [
        ("polished knucklebone", (1, 2)),
        ("grave salt", (1, 1)),
    ],
    "empire": [
        ("old iron key", (1, 1)),
        ("dented imperial buckle", (1, 1)),
    ],
    "weapons": [
        ("old iron key", (1, 1)),
        ("whetstone", (1, 1)),
    ],
}

_DEFAULT_POOL: list[tuple[str, tuple[int, int]]] = [
    ("trinket", (1, 1)),
    ("gold", (4, 12)),
    ("smoke vial", (1, 1)),
]

_SECRET_KIND_LABELS = {
    "hidden_compartment": "a hidden compartment",
    "loose_page": "a loose page tucked away",
    "sealed_cache": "a sealed cache",
    "false_sigil": "a false sigil concealing a nook",
    "burial_niche": "a burial niche",
    "marked_skull": "a marked skull, hollow inside",
    "locked_drawer": "a stuck drawer",
    "sealed_sample": "a sealed sample case",
    "loose_flagstone": "a loose flagstone",
    "stashed_key": "a stash wedged out of sight",
    "hollow_altar": "a hollow in the altar",
    "hidden_reliquary": "a hidden reliquary",
    "drain_cache": "a cache in the drain",
    "submerged_slot": "a submerged slot",
    "false_bottom": "a false bottom",
    "crate_cache": "a cache among the crates",
    "root_gap": "a gap behind the roots",
    "buried_cache": "a shallow buried cache",
}


def slot_turn_cost(slot: dict[str, Any]) -> int:
    return _DIFFICULTY_TURNS.get(str(slot.get("reveal_difficulty") or "plain"), 1)


def secret_kind_label(slot: dict[str, Any]) -> str:
    kind = str(slot.get("kind") or "hidden_compartment")
    return _SECRET_KIND_LABELS.get(kind, "a hidden space")


def choose_anchor(slot: dict[str, Any], props: list[Any], rng: random.Random) -> str:
    """The concrete thing the clue points at and the player must investigate by
    name. A prop in the room when one exists; otherwise a floor feature."""
    if props:
        prop = sorted(props, key=lambda entity: entity.id)[rng.randrange(len(props))]
        return prop.name
    return "the floor"


# Flavor weaknesses by creature tag: prose-level vulnerabilities that a wild
# spell can exploit. Where the entity has real mechanical weaknesses, those are
# preferred — the prose then IS the stat, readable as fiction.
_FLAVOR_WEAKNESSES_BY_TAG: dict[str, list[str]] = {
    "goblin": ["sudden bright light", "the smell of burning hair", "being laughed at"],
    "slime": ["salt", "dry heat", "chalk dust"],
    "undead": ["consecrated ground", "salt scattered in a line", "its own true name"],
    "death": ["grave salt", "morning bells"],
    "beast": ["fire", "loud sudden noise"],
    "vermin": ["smoke", "vinegar"],
    "scavenger": ["the scent of something larger"],
    "flesh": ["stinging smoke", "cold iron"],
    "construct": ["water in the joints", "a missing word of command"],
    "spirit": ["iron filings", "an honest question"],
    "soldier": ["broken formation", "orders it cannot verify"],
    "empire": ["paperwork it cannot produce", "questions of jurisdiction"],
}

_DEFAULT_FLAVOR_WEAKNESSES = ["sudden bright light", "cold iron", "its own reflection"]


def choose_weakness_hint(entity: Any, rng: random.Random) -> dict[str, Any]:
    """One weakness per study. Real mechanical weaknesses win (the prose then
    encodes a true stat); otherwise a flavor weakness drawn from tags, which a
    wild spell can exploit through the resolver's own judgment."""
    weaknesses = dict(getattr(entity, "weaknesses", None) or {})
    if weaknesses:
        damage_type = sorted(weaknesses)[rng.randrange(len(weaknesses))]
        return {"kind": "mechanical", "damage_type": damage_type}
    pool: list[str] = []
    for tag in sorted(getattr(entity, "tags", set()) or set()):
        pool.extend(_FLAVOR_WEAKNESSES_BY_TAG.get(str(tag), []))
    if not pool:
        pool = list(_DEFAULT_FLAVOR_WEAKNESSES)
    return {"kind": "flavor", "hint": pool[rng.randrange(len(pool))]}


def decoration_menu(room_tags: list[str], rng: random.Random, count: int = 3) -> list[dict[str, str]]:
    """Engine-built menu of non-blocking prop templates fitting the room's
    tags. A sweep that finds no secret may let the LLM pick ONE of these to
    surface on the map — the engine validates the choice against this menu."""
    from .props import PROP_CATEGORIES, get_prop_template

    pool: list[str] = []
    for category, prop_ids in PROP_CATEGORIES.items():
        if category in set(room_tags):
            pool.extend(pid for pid in prop_ids if not get_prop_template(pid).blocks)
    pool = sorted(set(pool))
    if not pool:
        return []
    rng.shuffle(pool)
    return [
        {"template": pid, "name": get_prop_template(pid).name}
        for pid in pool[:count]
    ]


def choose_reward(slot: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    pool: list[tuple[str, tuple[int, int]]] = []
    for tag in slot.get("possible_reward_tags", []):
        pool.extend(_REWARD_POOLS.get(str(tag), []))
    if not pool:
        pool = list(_DEFAULT_POOL)
    name, (low, high) = pool[rng.randrange(len(pool))]
    return {"name": name, "quantity": rng.randint(low, high)}
