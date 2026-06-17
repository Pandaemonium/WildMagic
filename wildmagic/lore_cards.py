"""Lore cards — tiered authored world-knowledge for dialogue, books, and beyond.

Design + rationale: docs/LORE_CARDS.md. World fact this serves: docs/WORLDBUILDING.md.

This module is **pure data + pure functions** — no HTTP/provider logic (mirrors
`capabilities.py` / `spell_contract.py`). The generative router's actual model call is
injected as `route_call` (wired per consumer in `lore_router.py`), so the gate and the
deterministic selection path are fully testable with no backend.

Two filters, both must pass (docs/LORE_CARDS.md §3):
  1. ACCESS GATE  — a knower reaches a card iff the sum of their lore levels across the
                    card's tags >= the card's threshold (pure sum; everyone is 0 by default).
  2. RELEVANCE    — a cheap keyword/subject prefilter, then an optional generative router,
                    pick the on-topic few. No topical hit => inject nothing (a bare "hello").
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping


@dataclass(frozen=True)
class LoreCard:
    name: str  # unique id, e.g. "stalnaz_rule"
    tags: tuple[
        str, ...
    ]  # access keys (regions/traditions): ("stalnaz",) or ("threen", "crystal")
    threshold: int  # combined lore across tags to ACCESS (single-tag: the 0-4 tier)
    triggers: tuple[
        str, ...
    ]  # keyword stems for the cheap prefilter + deterministic fallback
    index_line: str  # one-line gloss the router sees in the candidate menu
    text: str  # the fact block injected into the consuming prompt
    version: int = 1  # bump on content change (future cache invalidation)


# ----------------------------------------------------------------------------------------
# The registry — L0 (folksy common knowledge) + L1 (basic familiarity), carved from
# WORLDBUILDING.md. Deeper tiers (L2-L4) are deferred (docs/LORE_CARDS.md §13/§15). L0 text
# is the one-line reputation a tavern traveler would repeat; never scholarly or metaphysical.
# ----------------------------------------------------------------------------------------
LORE_CARDS: tuple[LoreCard, ...] = (
    # --- The Empire (empire = the whole construction; vigovia = the heartland) ---
    LoreCard(
        name="empire_basics",
        tags=("empire",),
        threshold=0,
        triggers=("empire", "imperial", "emperor", "vigovia", "vigo", "censorate"),
        index_line="The Grand Empire of Vigovia and its reach.",
        text=(
            "The Grand Empire of Vigovia was founded long ago by Vigo the Lawgiver and has "
            "since swallowed other realms. Most people just call it 'the Empire.' It keeps "
            "the roads safe, the coin good, and magic strictly licensed."
        ),
    ),
    LoreCard(
        name="empire_peace",
        tags=("empire",),
        threshold=0,
        triggers=(
            "peace",
            "road",
            "roads",
            "coin",
            "money",
            "common",
            "tongue",
            "language",
            "safe",
            "trade",
        ),
        index_line="The everyday peace of empire: safe roads, common coin and tongue.",
        text=(
            "Whatever people grumble, the Empire's peace is real: the roads are safe, a "
            "common coin spends nearly everywhere, and most folk share the common tongue. "
            "Many quietly prefer it that way."
        ),
    ),
    LoreCard(
        name="empire_heartland",
        tags=("vigovia",),
        threshold=1,
        triggers=(
            "vigovia",
            "vigovian",
            "heartland",
            "beard",
            "bureaucrat",
            "bureaucracy",
            "permit",
            "lawyer",
            "vigo",
        ),
        index_line="Vigovia the heartland: bureaucratic, orderly, charter-proud.",
        text=(
            "Vigovia proper — the Empire's heartland — is stodgy and bureaucratic, fond of "
            "permits, lawyers, and full beards. To become a charter mage there is a great "
            "honor, weighty as becoming a physician."
        ),
    ),
    LoreCard(
        name="charter_basics",
        tags=("charter",),
        threshold=0,
        triggers=("charter", "license", "licensed", "permit", "chartermage"),
        index_line="Charter magic: the Empire's licensed, repeatable magic.",
        text=(
            "Charter magic is the Empire's licensed magic — worked by trained charter mages "
            "to a fixed, approved repertoire. Cold, precise, repeatable, and legal."
        ),
    ),
    LoreCard(
        name="charter_truth",
        tags=("charter",),
        threshold=1,
        triggers=(
            "charter",
            "tradition",
            "traditions",
            "outlaw",
            "outlawed",
            "forbidden",
            "banned",
            "ban",
        ),
        index_line="How the charter subsumed and licensed the old traditions.",
        text=(
            "The charter did not invent magic; it tamed it — licensing safe versions of the "
            "old traditions and outlawing whatever it judged dangerous. A modern woven charm "
            "or blessed tattoo is an old folk art now performed by a licensed mage."
        ),
    ),
    LoreCard(
        name="shadow_purge",
        tags=("shadow_purge",),
        threshold=1,
        triggers=(
            "shadow",
            "purge",
            "possession",
            "possessed",
            "spirit",
            "spirits",
            "sorcerer",
            "catastrophe",
        ),
        index_line="The Shadow Purge that justified the charter.",
        text=(
            "The Shadow Purge is the horror every schoolchild knows: a cult of shadow "
            "sorcerers loosed body-jumping shadow spirits through a great Vigovian city, "
            "turning the possessed against their own families. The Empire has justified the "
            "charter by it ever since."
        ),
    ),
    # --- Stalnaz / crystal ---
    LoreCard(
        name="stalnaz_basics",
        tags=("stalnaz",),
        threshold=0,
        triggers=(
            "stalnaz",
            "stalnazan",
            "queendom",
            "music",
            "art",
            "philosophy",
            "philosopher",
        ),
        index_line="Stalnaz: queendom of music, art, and philosophy.",
        text=(
            "Stalnaz is the queendom famed the world over for its music, art, and "
            "philosophy — the realm everyone else quietly measures their own refinement "
            "against."
        ),
    ),
    LoreCard(
        name="stalnaz_rule",
        tags=("stalnaz",),
        threshold=1,
        triggers=(
            "queen",
            "queendom",
            "heiress",
            "succession",
            "investiture",
            "regicide",
            "holiday",
            "throne",
        ),
        index_line="Stalnaz's queens, chosen heiresses, and founding holiday.",
        text=(
            "Stalnaz is ruled by a queen who names her own heiress — often a daughter, as "
            "often a worthy unrelated woman groomed at court. The first queen took the throne "
            "by murdering her tyrant husband, and that founding is celebrated openly with a "
            "great annual holiday."
        ),
    ),
    LoreCard(
        name="crystal_basics",
        tags=("crystal",),
        threshold=0,
        triggers=("crystal", "gem", "gemstone", "quartz", "lattice"),
        index_line="Crystal magic, Stalnaz's signature tradition.",
        text=(
            "Crystal magic is Stalnaz's signature art — light and song coaxed through cut "
            "stone."
        ),
    ),
    LoreCard(
        name="crystal_truth",
        tags=("crystal",),
        threshold=1,
        triggers=(
            "crystal",
            "store",
            "stored",
            "energy",
            "charge",
            "charged",
            "channel",
        ),
        index_line="Crystals genuinely store magical energy (charge, then channel).",
        text=(
            "Unlike most traditions, crystal magic has a real material edge: a crystal "
            "stores magical energy, so one hand can slowly charge it and another draw it out "
            "later. It is why Stalnaz could build a civilization on stone."
        ),
    ),
    # --- Brall / bone ---
    LoreCard(
        name="brall_basics",
        tags=("brall",),
        threshold=0,
        triggers=(
            "brall",
            "bralli",
            "ale",
            "tale",
            "tales",
            "scrimshaw",
            "jarl",
            "jarls",
            "hold",
            "holds",
        ),
        index_line="Brall: ale, tall tales, scrimshaw, and the Bone Jarls.",
        text=(
            "Brall is a boisterous land of ale, tall tales, and scrimshaw, its holds ruled "
            "by the council of Bone Jarls."
        ),
    ),
    LoreCard(
        name="bone_basics",
        tags=("bone",),
        threshold=0,
        triggers=("bone", "bones", "scrimshaw", "whalebone"),
        index_line="Bone magic, Brall's tradition.",
        text=(
            "Bone magic is Brall's old tradition, worked through carved whale and beast bone "
            "(working human bone is strictly charter-taboo)."
        ),
    ),
    # --- Ryolan / blood ---
    LoreCard(
        name="ryolan_basics",
        tags=("ryolan",),
        threshold=0,
        triggers=(
            "ryolan",
            "ryolani",
            "honor",
            "honour",
            "duel",
            "duels",
            "chariot",
            "chariots",
            "race",
            "races",
        ),
        index_line="Ryolan: honor, duels, chariot races, blood magic.",
        text=(
            "Ryolan is a kingdom of honor and the duel, mad for its chariot races, with "
            "blood magic in its past and a king on its throne."
        ),
    ),
    LoreCard(
        name="blood_basics",
        tags=("blood",),
        threshold=0,
        triggers=("blood", "duel", "palm", "oath", "oaths"),
        index_line="Blood magic, Ryolan's tradition.",
        text=(
            "Blood magic is Ryolan's tradition; even now a duel opens with the duelists "
            "cutting their own off-hand palm, a gesture descended from it."
        ),
    ),
    # --- Vint / woven ---
    LoreCard(
        name="vint_basics",
        tags=("vint",),
        threshold=0,
        triggers=(
            "vint",
            "vintan",
            "gossip",
            "rumor",
            "rumour",
            "republic",
            "politics",
            "tapestry",
            "tapestries",
        ),
        index_line="Vint: the gossipy woven republic.",
        text=(
            "Vint is a gossipy republic famed for its woven charms and tapestries and its "
            "ever-churning, rumor-driven politics."
        ),
    ),
    LoreCard(
        name="woven_basics",
        tags=("woven",),
        threshold=0,
        triggers=(
            "woven",
            "weave",
            "charm",
            "charms",
            "tapestry",
            "tapestries",
            "scarf",
            "cloth",
            "embroider",
            "embroidered",
        ),
        index_line="Woven magic, Vint's tradition.",
        text=(
            "Woven magic is Vint's tradition — charms embroidered into scarves, swaddles, "
            "and tapestries. Vintan tapestries are prized exports; the charms themselves are "
            "now bought from charter mages."
        ),
    ),
    # --- Threen ---
    LoreCard(
        name="threen_basics",
        tags=("threen",),
        threshold=0,
        triggers=("threen", "threenian", "canal", "canals", "independent"),
        index_line="Threen: the independent canal-kingdom.",
        text=(
            "Threen is a wealthy canal-kingdom, officially independent — though everyone "
            "knows it answers to the emperor. It prides itself on literature and fine "
            "artisan goods."
        ),
    ),
    # --- The small realms and peoples ---
    LoreCard(
        name="monteary_basics",
        tags=("monteary",),
        threshold=0,
        triggers=(
            "monteary",
            "horse",
            "horses",
            "gelding",
            "geldings",
            "stallion",
            "stallions",
            "mare",
            "mares",
        ),
        index_line="Monteary: the horse-realm.",
        text=(
            "Monteary breeds the finest horses in the world, prized for its geldings — and "
            "it guards its stallions jealously to keep the monopoly."
        ),
    ),
    LoreCard(
        name="ontria_basics",
        tags=("ontria",),
        threshold=0,
        triggers=(
            "ontria",
            "ontrian",
            "yoghurt",
            "yogurt",
            "tribe",
            "tribes",
            "clan",
            "clans",
        ),
        index_line="Ontria: the yoghurt tribes.",
        text=(
            "Ontria is a land of tribes, each keeping its own sacred culture of yoghurt "
            "whose ritual eating grants the clan its own peculiar powers."
        ),
    ),
    LoreCard(
        name="gontark_basics",
        tags=("gontark",),
        threshold=0,
        triggers=(
            "gontark",
            "goat",
            "goatfolk",
            "goatkin",
            "curse",
            "curses",
            "horn",
            "horns",
        ),
        index_line="Gontark: the goatfolk and their curses.",
        text=(
            "Gontark is home to the caprine goatfolk — horned and slit-eyed, and feared "
            "across the world for their vicious curses."
        ),
    ),
    LoreCard(
        name="parn_basics",
        tags=("parn",),
        threshold=0,
        triggers=(
            "parn",
            "desert",
            "nomad",
            "nomads",
            "caravan",
            "caravans",
            "tattoo",
            "tattoos",
            "tattooed",
        ),
        index_line="The Parn: tattooed desert caravans.",
        text=(
            "The Parn are tattooed nomads of the desert, traveling in caravans with no king "
            "and a deep love of music."
        ),
    ),
    LoreCard(
        name="birdfolk_basics",
        tags=("birdfolk",),
        threshold=0,
        triggers=(
            "birdfolk",
            "bird",
            "birds",
            "avian",
            "feather",
            "feathers",
            "plumage",
            "wing",
            "wings",
        ),
        index_line="Birdfolk: sociable avian storytellers.",
        text=(
            "The birdfolk are avian people of every shape and bright plumage — endlessly "
            "sociable, and famous for collecting and carrying true stories."
        ),
    ),
    LoreCard(
        name="merfolk_basics",
        tags=("merfolk",),
        threshold=0,
        triggers=("merfolk", "merman", "mermaid", "sea", "ocean", "deep", "fish"),
        index_line="Merfolk: proud, xenophobic sea-people.",
        text=(
            "The merfolk keep to the deep ocean, proud and standoffish, holding themselves "
            "above land-folk; they trade, but rarely warmly."
        ),
    ),
    LoreCard(
        name="rentacosta_basics",
        tags=("rentacosta",),
        threshold=0,
        triggers=(
            "rentacosta",
            "sailor",
            "sailors",
            "ship",
            "ships",
            "sail",
            "port",
            "coast",
            "voyage",
        ),
        index_line="Rentacosta: the free city of sailors.",
        text=(
            "Rentacosta is a relaxed, salt-worn free city of sailors and traders — worldly, "
            "multilingual, and the one place that deals freely with the merfolk."
        ),
    ),
)

_BY_NAME: dict[str, LoreCard] = {c.name: c for c in LORE_CARDS}
KNOWN_TAGS: frozenset[str] = frozenset(t for c in LORE_CARDS for t in c.tags)

# Book subjects (and any free-text topic) are generated metadata, NOT guaranteed tags.
# Normalize onto the canonical vocabulary before matching; unknowns are dropped.
TAG_ALIASES: dict[str, str] = {
    "crystals": "crystal",
    "crystal magic": "crystal",
    "charter law": "charter",
    "charter magic": "charter",
    "charters": "charter",
    "the empire": "empire",
    "grand empire": "empire",
    "imperial": "empire",
    "vigovian": "vigovia",
    "stalnazan": "stalnaz",
    "stalnazi": "stalnaz",
    "bralli": "brall",
    "ryolani": "ryolan",
    "vintan": "vint",
    "threenian": "threen",
    "ontrian": "ontria",
    "montearian": "monteary",
    "bone magic": "bone",
    "blood magic": "blood",
    "woven magic": "woven",
    "the parn": "parn",
    "goatfolk": "gontark",
    "the shadow purge": "shadow_purge",
}


def normalize_lore_tags(raw: Iterable[str]) -> set[str]:
    """Map free-text subjects onto canonical tags; drop anything unknown."""
    out: set[str] = set()
    for s in raw:
        k = str(s).strip().lower()
        k = TAG_ALIASES.get(k, k)
        if k in KNOWN_TAGS:
            out.add(k)
    return out


# ----------------------------------------------------------------------------------------
# Seeding NPC lore at generation (deterministic, rules-first; docs/LORE_CARDS.md §11).
# Depends only on role/traits/tags/region strings, so it is replay-safe.
# ----------------------------------------------------------------------------------------
_ROLE_LEVELS: tuple[tuple[tuple[str, ...], int], ...] = (
    (
        (
            "scholar",
            "philosoph",
            "sage",
            "priest",
            "scribe",
            "loremaster",
            "historian",
            "chronicler",
            "keeper of",
        ),
        3,
    ),
    (
        (
            "guide",
            "innkeeper",
            "barkeep",
            "bartender",
            "host",
            "elder",
            "steward",
            "archivist",
            "librarian",
        ),
        2,
    ),
    (
        (
            "noble",
            "official",
            "magistrate",
            "captain",
            "courtier",
            "lord",
            "lady",
            "governor",
        ),
        2,
    ),
    (("merchant", "trader", "peddler", "factor"), 1),
)


def _role_level(role: str) -> int:
    r = role.lower()
    for keywords, level in _ROLE_LEVELS:
        if any(k in r for k in keywords):
            return level
    return 1  # the commoner floor: locals know their own region a little


def seed_npc_lore(
    role: str,
    traits: Iterable[str] = (),
    tags: Iterable[str] = (),
    region: str = "",
) -> dict[str, int]:
    """Assign an NPC's starting lore from their role and where they are. Region/tradition
    tags come from their entity tags, the region name, and any tradition named in the role
    text itself ("crystal-keyer" -> crystal). Everything stays at the implicit 0 otherwise.
    """
    level = _role_level(role)
    sources = (
        list(tags) + _WORD_RE.findall(region.lower()) + _WORD_RE.findall(role.lower())
    )
    home = normalize_lore_tags(sources)
    return {tag: level for tag in home}


# ----------------------------------------------------------------------------------------
# 1. The access gate (pure)
# ----------------------------------------------------------------------------------------
def knows(lore: Mapping[str, int], card: LoreCard) -> bool:
    """Pure-sum access: sum of the knower's levels across the card's tags >= threshold.
    A knower is 0 on any tag they don't list, so threshold-0 cards are universal."""
    return sum(lore.get(t, 0) for t in card.tags) >= card.threshold


def eligible_cards(
    lore: Mapping[str, int], registry: Iterable[LoreCard] = LORE_CARDS
) -> list[LoreCard]:
    return [c for c in registry if knows(lore, c)]


# ----------------------------------------------------------------------------------------
# 2. Relevance routing
# ----------------------------------------------------------------------------------------
LORE_ROUTER_SCHEMA: dict = {
    "type": "object",
    "properties": {"cards": {"type": "array", "items": {"type": "string"}}},
    "required": ["cards"],
}

_WORD_RE = re.compile(r"[a-z]+")


def _query_words(query: str) -> set[str]:
    return set(_WORD_RE.findall(query.lower()))


def _card_terms(card: LoreCard) -> set[str]:
    return set(card.triggers) | set(card.tags)


def _keyword_hit(card: LoreCard, words: set[str]) -> bool:
    # A query word matches a term if it equals it or starts with it (plurals/possessives:
    # "horses" -> "horse", "stalnazan" -> "stalnaz"). Recall-biased on purpose.
    terms = _card_terms(card)
    return any(any(w == t or w.startswith(t) for t in terms) for w in words)


def prefilter(cands: list[LoreCard], query: str, subjects: set[str]) -> list[LoreCard]:
    """Keyword/tag hits over eligible candidates. `subjects` are HARD, already-normalized
    topic tags (e.g. a book's subjects). Recall-biased — matches tags AND triggers."""
    words = _query_words(query)
    hits: list[LoreCard] = []
    for c in cands:
        if subjects & set(c.tags):  # hard topic match (books)
            hits.append(c)
        elif _keyword_hit(c, words):  # query keyword match
            hits.append(c)
    return hits


def _score(
    card: LoreCard, words: set[str], subjects: set[str], bias: set[str]
) -> tuple:
    """Rank key: more on-topic first, then speaker-bias, then foundational (lower threshold)."""
    terms = _card_terms(card)
    hits = sum(1 for w in words for t in terms if w == t or w.startswith(t))
    subj_hit = 1 if subjects & set(card.tags) else 0
    bias_hit = 1 if bias & set(card.tags) else 0
    return (subj_hit, hits, bias_hit, -card.threshold)


def _rank(
    cards: list[LoreCard], query: str, subjects: set[str], bias: set[str]
) -> list[LoreCard]:
    words = _query_words(query)
    return sorted(cards, key=lambda c: _score(c, words, subjects, bias), reverse=True)


def _budget(cards: list[LoreCard], max_cards: int, max_chars: int) -> list[LoreCard]:
    """Bound the injection by BOTH a card count and a character budget — five L4 cards
    weigh far more than five L0 lines."""
    out: list[LoreCard] = []
    used = 0
    for c in cards[:max_cards]:
        if out and used + len(c.text) > max_chars:
            break
        out.append(c)
        used += len(c.text)
    return out


def build_router_messages(
    knower_blurb: str, query: str, cands: list[LoreCard]
) -> list[dict]:
    index = "\n".join(f"- {c.name}: {c.index_line}" for c in cands)
    system = (
        "You are a retrieval router for a speaker's world-knowledge. Given who the speaker "
        "is and what is being discussed, choose which LORE CARDS (by id) are relevant to THIS "
        "exchange. Pick only what is on-topic — usually 1 to 5, fewer is better. "
        'Return ONLY {"cards": ["id", ...]}.\n\nAvailable lore cards:\n' + index
    )
    user = json.dumps({"speaker": knower_blurb, "topic": query}, ensure_ascii=True)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def select_lore_cards(
    lore: Mapping[str, int],
    query: str,
    *,
    subjects: Iterable[
        str
    ] = (),  # HARD topic (book subjects): authoritative, drives selection
    bias_tags: Iterable[
        str
    ] = (),  # SOFT speaker bias (NPC expertise): ranking tiebreak only
    knower_blurb: str = "",
    route_call: Callable[[list[dict]], list[str] | None] | None = None,
    registry: Iterable[LoreCard] = LORE_CARDS,
    max_cards: int = 5,
    max_chars: int = 1200,
) -> list[LoreCard]:
    """The whole pipeline: gate, prefilter, optional router, budget. See docs/LORE_CARDS.md §8.

    `route_call` is injected (so this module stays provider-free) and returns the selected
    ids, or None on failure (distinct from a deliberate empty []): a broken router falls back
    to deterministic ranking, while a router that found nothing relevant injects nothing.
    """
    elig = eligible_cards(lore, registry)
    if not elig:
        return []
    subj = normalize_lore_tags(subjects)
    bias = normalize_lore_tags(bias_tags)
    hinted = prefilter(elig, query, subj)
    if not hinted:
        # No topical engagement (a bare "hello") -> inject nothing, router or not. A soft
        # bias_tag ALONE never selects: local lore waits to be asked about.
        return []
    if route_call is None or len(hinted) <= max_cards:
        return _budget(_rank(hinted, query, subj, bias), max_cards, max_chars)
    names = route_call(build_router_messages(knower_blurb, query, hinted))
    if names is None:  # router FAILED -> deterministic fallback
        return _budget(_rank(hinted, query, subj, bias), max_cards, max_chars)
    chosen = [
        c for c in hinted if c.name in set(names)
    ]  # subset of eligible; unknown ids ignored
    return _budget(chosen, max_cards, max_chars)  # a successful empty [] is respected
