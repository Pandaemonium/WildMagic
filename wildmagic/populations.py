"""Realm populations — who fills a realm's zones (CONTENT_FLESHING_ROADMAP Tier 1A).

A realm's zones are populated by its own people: a **conquered** realm by imperial occupiers
*and* local folk, the free **rival** by its own martial people, the empire **heartland** by
imperials, the client **proxy** by deferent locals. Each denizen enters as a *politically
situated person* — **neutral by default**, carrying a typed ``identity``/``role`` — so hostility
is **derived** (the exposure model: witnessed wild magic turns the Empire on you; provocation or
reputation turns others), never baked into the spawn. The deterministic roster ships complete
with the model off; the LLM only enriches names/personalities later.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Denizen:
    """A spawn archetype for a realm's person. ``combatant`` routes to ``spawn_actor`` (a body
    with combat AI, talkable lazily) vs ``spawn_npc`` (a persona that flees). All spawn neutral;
    ``identity`` (the realm or ``imperial``) is attached at spawn time, not stored here."""

    role: str
    posture: str  # garrison | official | civilian | trader | partisan
    char: str
    hp: int
    attack: int
    defense: int
    ai: str
    tags: frozenset[str]
    combatant: bool


# Occupiers (carry identity ["imperial"]). Soldiers/officers can fight (when provoked/exposed);
# the clerk is a non-combatant loyalist who will fear and report a sorcerer rather than draw.
_SOLDIER = Denizen(
    "soldier",
    "garrison",
    "i",
    10,
    3,
    1,
    "legion",
    frozenset({"human", "soldier", "disciplined"}),
    True,
)
_OFFICER = Denizen(
    "officer",
    "garrison",
    "O",
    14,
    4,
    2,
    "legion",
    frozenset({"human", "soldier", "officer"}),
    True,
)
_CLERK = Denizen(
    "clerk", "official", "c", 8, 1, 0, "npc", frozenset({"human", "clerk"}), False
)

# Locals (carry identity [realm_id]). All non-combatant in a quiet-embers realm — resistance is
# latent (the partisan carries grievances, doesn't openly skirmish); per-realm texture (Vint
# loud, rival martial) is Tier 3/4A.
_TOWNSFOLK = Denizen(
    "townsfolk",
    "civilian",
    "p",
    10,
    1,
    0,
    "npc",
    frozenset({"human", "townsfolk"}),
    False,
)
_MERCHANT = Denizen(
    "merchant", "trader", "$", 10, 1, 0, "npc", frozenset({"human", "merchant"}), False
)
_PARTISAN = Denizen(
    "partisan",
    "partisan",
    "r",
    12,
    2,
    0,
    "npc",
    frozenset({"human", "partisan"}),
    False,
)
_PRIEST = Denizen(
    "priest", "civilian", "+", 10, 1, 0, "npc", frozenset({"human", "priest"}), False
)

# The free rival fields its own soldiers (identity = the realm, at war with the Empire).
_RIVAL_WARRIOR = Denizen(
    "soldier",
    "partisan",
    "w",
    12,
    3,
    1,
    "legion",
    frozenset({"human", "soldier"}),
    True,
)

#: A small name pool per role. Tier 4C's split starts here: imperial occupations read as cold
#: Latinate officialese, while local folk read as earthy realm compounds. LLM enrich can still
#: add personal names later; these are the deterministic floor.
_IMPERIAL_ROLE_NAMES: dict[str, tuple[str, ...]] = {
    "soldier": ("legionary", "cohort sentry", "edict guard", "containment lance"),
    "officer": ("decanus", "optio", "tribune's deputy"),
    "clerk": ("tax-clerk", "records-keeper", "notary", "censorial adjunct"),
    "townsfolk": ("weaver", "farmhand", "potter", "cooper", "laborer"),
    "merchant": ("trader", "peddler", "stall-keeper"),
    "partisan": ("malcontent", "quiet partisan", "ember"),
    "priest": ("acolyte", "shrine-keeper"),
}

_ROLE_NAMES: dict[str, tuple[str, ...]] = {
    "soldier": ("watch-spear", "gatehand", "road-guard", "oathblade"),
    "officer": ("captain", "banner-hand", "field elder"),
    "clerk": ("tally-keeper", "inkhand", "ledger-keeper"),
    "townsfolk": ("weaver", "farmhand", "potter", "cooper", "laborer"),
    "merchant": ("trader", "peddler", "stall-keeper"),
    "partisan": ("malcontent", "quiet partisan", "ember"),
    "priest": ("acolyte", "shrine-keeper"),
}

_REALM_ROLE_NAMES: dict[str, dict[str, tuple[str, ...]]] = {
    "stalnaz": {
        "townsfolk": ("glass-tuner", "song-cutter", "lightkeeper"),
        "merchant": ("crystal-factor", "resonance seller"),
        "priest": ("choir-keeper",),
    },
    "brall": {
        "townsfolk": ("alehand", "bone-carver", "hold-keeper"),
        "merchant": ("scrimshaw peddler", "cask-trader"),
        "soldier": ("hold-spear", "jarlsworn"),
    },
    "ryolan": {
        "townsfolk": ("oathhand", "blood-groom", "chariot-mender"),
        "merchant": ("duel-factor", "sash-seller"),
        "soldier": ("duel-guard", "red-spear"),
    },
    "vint": {
        "townsfolk": ("threadhand", "tapestry voter", "rumor-weaver"),
        "merchant": ("charm-knotter", "scarveseller"),
        "partisan": ("backroom vote", "red-thread partisan"),
    },
    "threen": {
        "townsfolk": ("canal-reader", "lampwright", "polite porter"),
        "merchant": ("book-broker", "lockside seller"),
        "clerk": ("petition-copyist", "permit reader"),
    },
    "monteary": {"townsfolk": ("horsehand", "saddle-stitcher", "plain rider")},
    "ontria": {"townsfolk": ("culture-keeper", "clan-spoon", "milkhand")},
    "gontark": {"townsfolk": ("goat-eyed elder", "horn-carver", "curse-minder")},
    "parn": {"townsfolk": ("road-singer", "inked cousin", "tent-mender")},
    "birdfolk": {"townsfolk": ("plume-keeper", "nest-mender", "story-beak")},
    "merfolk": {"townsfolk": ("tide-speaker", "pearl-guard", "reef-proud")},
    "rentacosta": {"townsfolk": ("saltbroker", "dockhand", "tongue-switcher")},
}

REALM_GOODS: dict[str, tuple[str, ...]] = {
    "vigovia": ("sealed ration chit", "censorate seal"),
    "stalnaz": ("charged stalnaz crystal", "resonance shard"),
    "brall": ("brall scrimshaw charm", "bone tally"),
    "ryolan": ("ryolan dueling sash", "blood-red whetstone"),
    "vint": ("vint woven charm", "petition scarf"),
    "threen": ("threen canal locket", "serialized novella"),
    "monteary": ("monteary horsehair bow", "braided gelding cord"),
    "ontria": ("ontrian culture gourd", "clan spoon"),
    "gontark": ("gontark curse-knot", "goat-horn bead"),
    "parn": ("parn song-ink scarf", "desert ink vial"),
    "birdfolk": ("birdfolk plume charm", "story feather"),
    "merfolk": ("merfolk tide pearl", "shell writ"),
    "rentacosta": ("rentacostan salt coin", "dockside phrasebook"),
}

_IMPERIAL = ["imperial"]

DenizenPlacement = tuple[Denizen, list[str]]  # (archetype, identity tokens)


def denizen_plan(
    role: str, realm_id: str, rng: random.Random
) -> list[DenizenPlacement]:
    """The people to spawn in a zone, by the owning realm's geopolitical role. Conquered land
    mixes a light imperial garrison with locals; the heartland is imperial; the proxy is
    deferent locals with the odd imperial guard; the rival fields its own people. Deterministic
    given ``rng``."""
    plan: list[DenizenPlacement] = []
    if role == "conquered":
        for _ in range(rng.randint(1, 2)):
            plan.append((rng.choice([_SOLDIER, _SOLDIER, _OFFICER]), list(_IMPERIAL)))
        if rng.random() < 0.4:
            plan.append((_CLERK, list(_IMPERIAL)))
        for _ in range(rng.randint(2, 3)):
            plan.append(
                (
                    rng.choice([_TOWNSFOLK, _TOWNSFOLK, _MERCHANT, _PARTISAN, _PRIEST]),
                    [realm_id],
                )
            )
    elif role == "founding":
        for _ in range(rng.randint(1, 2)):
            plan.append((rng.choice([_SOLDIER, _OFFICER, _CLERK]), list(_IMPERIAL)))
        for _ in range(rng.randint(1, 2)):
            plan.append((rng.choice([_TOWNSFOLK, _MERCHANT]), list(_IMPERIAL)))
    elif role == "proxy":
        for _ in range(rng.randint(2, 3)):
            plan.append(
                (rng.choice([_TOWNSFOLK, _MERCHANT, _CLERK, _PRIEST]), [realm_id])
            )
        if rng.random() < 0.3:
            plan.append((_SOLDIER, list(_IMPERIAL)))  # an emissary's guard
    elif role == "rival":
        for _ in range(rng.randint(1, 2)):
            plan.append((_RIVAL_WARRIOR, [realm_id]))
        for _ in range(rng.randint(1, 2)):
            plan.append((rng.choice([_TOWNSFOLK, _PARTISAN]), [realm_id]))
    elif role == "independent":
        # A smaller realm's own people — not occupied, not garrisoned; the odd imperial
        # passes through (they let soldiers cross their land).
        for _ in range(rng.randint(2, 3)):
            plan.append(
                (rng.choice([_TOWNSFOLK, _TOWNSFOLK, _MERCHANT, _PRIEST]), [realm_id])
            )
        if rng.random() < 0.25:
            plan.append((_SOLDIER, list(_IMPERIAL)))
    return plan


def denizen_name(
    denizen: Denizen, rng: random.Random, identity: list[str] | None = None
) -> str:
    identity = list(identity or [])
    if "imperial" in identity:
        return rng.choice(_IMPERIAL_ROLE_NAMES.get(denizen.role, (denizen.role,)))
    realm_id = identity[0] if identity else ""
    realm_names = _REALM_ROLE_NAMES.get(realm_id, {})
    names = realm_names.get(denizen.role) or _ROLE_NAMES.get(
        denizen.role, (denizen.role,)
    )
    return rng.choice(names)


def realm_good(realm_id: str, rng: random.Random) -> str | None:
    goods = REALM_GOODS.get(realm_id)
    return rng.choice(goods) if goods else None


def realm_wares(realm_id: str, rng: random.Random) -> dict[str, int]:
    good = realm_good(realm_id, rng)
    return {good: 1, "gold": rng.randint(6, 18)} if good else {}


# --- Concerns (CONTENT_FLESHING_ROADMAP Tier 1B) ----------------------------------------
# A local's plight, stamped on their NPCProfile.concern at spawn, that becomes a quest when the
# player engages them. The slice keeps to deed-closable concerns that need no placement: a slay
# against the occupying garrison (which Tier 1A already populates). Rescue-with-captive-placement
# rides the promise/realization system in a later pass.


@dataclass(frozen=True)
class ConcernTemplate:
    roles: frozenset[str]  # denizen roles that can carry it
    realm_roles: frozenset[
        str
    ]  # realm geopolitical roles it fits (conquered/rival/...)
    kind: str  # rescue | slay | defend | clear
    subject: str  # the plight, voiced in dialogue
    victim_faction: str  # for slay/clear: whose member satisfies it
    reward_gold: int


CONCERN_TEMPLATES: tuple[ConcernTemplate, ...] = (
    ConcernTemplate(
        roles=frozenset({"townsfolk", "partisan", "priest"}),
        realm_roles=frozenset({"conquered"}),
        kind="slay",
        subject="an imperial officer who torments this place",
        victim_faction="empire",
        reward_gold=20,
    ),
    ConcernTemplate(
        # A rescue: the kin is realized as a bound captive in the zone (generation places one
        # and stamps the concern's subject_soul), so freeing them closes the quest.
        roles=frozenset({"townsfolk", "merchant", "priest"}),
        realm_roles=frozenset({"conquered"}),
        kind="rescue",
        subject="my kin, dragged off by the garrison",
        victim_faction="",
        reward_gold=30,
    ),
    ConcernTemplate(
        roles=frozenset({"merchant", "townsfolk"}),
        realm_roles=frozenset({"conquered"}),
        kind="slay",
        subject="the imperial tax-enforcer bleeding us dry",
        victim_faction="empire",
        reward_gold=25,
    ),
    ConcernTemplate(
        roles=frozenset({"partisan", "townsfolk"}),
        realm_roles=frozenset({"rival"}),
        kind="slay",
        subject="imperial scouts probing our border",
        victim_faction="empire",
        reward_gold=20,
    ),
)


#: How the role-neutral locals (townsfolk/merchants) lean, by realm role — the *spread* that
#: makes the opening's witnessed cast land as MIXED reactions (CONTENT_FLESHING_ROADMAP). Words
#: are from the bonds affinity/aversion vocab: oppressed/downtrodden/rebel warm to a sorcerer who
#: strikes the Empire; fearful/loyalist recoil. The role-leaning denizens (partisan→rebel,
#: priest→pious, clerk→loyalist) keep their natural disposition and aren't distributed here.
_DISPOSITION_SPREAD: dict[str, tuple[tuple[str, ...], tuple[int, ...]]] = {
    "conquered": (
        ("oppressed", "downtrodden", "rebel", "fearful", "loyalist"),
        (4, 3, 2, 3, 1),
    ),
    "rival": (("rebel", "oppressed", "fearful"), (4, 2, 1)),
    "proxy": (("fearful", "loyalist", "downtrodden"), (3, 2, 2)),
    "founding": (("loyalist", "fearful", "downtrodden"), (3, 2, 1)),
}

_ROLE_LEANING_ROLES = frozenset({"partisan", "priest", "clerk"})


def realm_disposition(realm_role: str, role: str, rng: random.Random) -> str | None:
    """Distribute a disposition onto a **role-neutral** local (townsfolk/merchant) so a realm's
    common folk react variedly to a witnessed sorcerer; roles with a natural lean keep it. Drawn
    from ``_DISPOSITION_SPREAD`` for the realm role; None when nothing distributes."""
    if role in _ROLE_LEANING_ROLES:
        return None
    spread = _DISPOSITION_SPREAD.get(realm_role)
    if spread is None:
        return None
    words, weights = spread
    return rng.choices(words, weights=weights)[0]


def roll_concern(
    role: str, realm_role: str, rng: random.Random, chance: float = 0.5
) -> dict[str, object] | None:
    """Roll a plight for a local of ``role`` in a realm of ``realm_role`` — most carry one, some
    don't (deterministic given ``rng``). Returns the ``NPCProfile.concern`` dict, or None."""
    candidates = [
        t for t in CONCERN_TEMPLATES if role in t.roles and realm_role in t.realm_roles
    ]
    if not candidates or rng.random() > chance:
        return None
    template = rng.choice(candidates)
    return {
        "type": template.kind,
        "subject": template.subject,
        "victim_faction": template.victim_faction,
        "reward_gold": template.reward_gold,
    }
