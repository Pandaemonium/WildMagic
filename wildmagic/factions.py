"""Factions — the powers the world's standing/resources are tracked against.

A Faction is a power the player can affect: a kingdom, the Empire bloc, a resistance, a
guild, or (Phase F) a player-founded organization. Each carries **multidimensional
standing** toward the player (an open set of axes — notoriety, fear, gratitude, …) and a
pool of spendable **resources** it acts through (Phase B+).

Phase 0 seeds just two poles — the Empire and one rebel faction — with a 2-axis standing
(``imperial_threat`` on the Empire, ``gratitude`` on the rebels). The full rolled roster
(fixed kingdoms in rolled roles, §0.1) replaces this scaffold in Phase C.

The ``FactionLedger`` is serialized inside a run but **never carried between runs** (a new
run rolls fresh factions — no meta-progression).

See `EMERGENT_WORLD_IMPLEMENTATION.md` §1.2 / §0.1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


#: The standing axes a faction can hold toward the player (strategy §5.1). Open-ended —
#: the world roll may add run-specific axes — but this is the curated core vocabulary.
STANDING_AXES: tuple[str, ...] = (
    "notoriety",
    "fear",
    "gratitude",
    "legitimacy",
    "uncanniness",
    "imperial_threat",
)

#: The kinds a faction can be (§0.1). ``empire_core``/``conquered``/``proxy`` make up the
#: Empire bloc; ``player_org`` is a Phase-F player-founded organization.
FACTION_KINDS: tuple[str, ...] = (
    "empire_core",
    "conquered",
    "proxy",
    "rival",
    "independent",
    "resistance",
    "guild",
    "cult",
    "player_org",
)


#: The bounded vocabulary of **directed** inter-faction stances — how faction A regards
#: faction B (``FACTION_KILL_REPUTATION.md`` §10; the one input that unblocks both relational
#: kill reactions K3–K5 and derived combat stance §0). Directed, because a relationship can be
#: asymmetric: an empire holds a conquered realm as a ``subject`` while that realm regards the
#: empire as an ``occupier``. The world roll seeds these from roles + ruler disposition
#: (``worldgen.seed_factions_from_world``); the simulator and AI read them, never literal ids.
FACTION_STANCES: tuple[str, ...] = (
    "allied",  # close ally / same bloc — fights at your side
    "friendly",  # warm but independent
    "subject",  # A holds B in subjugation (the overlord's grip — control, not warmth)
    "occupier",  # B's view of the power that conquered it — resentful submission
    "wary",  # uneasy, watchful, no open break
    "rival",  # standing opposition short of open war
    "hostile",  # at open war / sworn enemy
    "neutral",  # no strong feeling (the default for any unset pair)
)

#: Each stance's **sentiment** in [-1, 1] — how warmly A regards B. Drives relational kill
#: reactions (a kill of X pleases X's enemies and angers X's friends, scaled by this) and the
#: combat-stance derivation (negative-enough sentiment ⇒ willing to fight). Self is +1.
STANCE_SENTIMENT: dict[str, float] = {
    "allied": 1.0,
    "friendly": 0.5,
    "subject": -0.2,
    "occupier": -0.6,
    "wary": -0.2,
    "rival": -0.5,
    "hostile": -1.0,
    "neutral": 0.0,
}

#: Stances at which A is willing to take up arms against B (derived combat stance §0). A
#: ``subject`` overlord does not *fight* its subject by default (it polices it); open war is
#: ``hostile``. Read symmetrically by ``engine.is_hostile_to`` (either direction at war ⇒ fight).
COMBATIVE_STANCES: frozenset[str] = frozenset({"hostile"})


# --- Placeholder names (swap-point for worldbuilding, D1) ---------------------------
# These are deliberately the *only* place the Phase-0 faction names live, so they can be
# renamed in one edit when lore lands (and Phase C's world roll supplies real names per
# the fixed kingdom roster). Keep new placeholders here too.
EMPIRE_NAME = "the Grand Empire"
REBELLION_NAME = "the Unbound"

#: The Empire's defensive pool — the legions, patrols, sealed capital, and guard that keep
#: the emperor unreachable (D9, §0.5). Pressure (the player's imperial_threat) spends it
#: down each day; when it hits zero the path to the emperor opens. Small for the
#: fast-escalation start; Phase C/D calibrate it.
EMPIRE_DEFENSE_START = 20

#: Action resources factions *spend to act* (Phase D backlash, strategy §5.2): a crackdown
#: is not "fear > 70", it is "the Empire spends a patrol". Finite, with slow daily regen,
#: so reactions ebb and flow — an overspent faction goes quiet for a while.
EMPIRE_PATROLS_START = 3
REBELLION_CELLS_START = 3


#: Stable *roles* the emergent systems target, mapped to the faction kinds that fill them.
#: Downstream code (deed consequences, backlash, bonds, Phase F orgs) references roles, not
#: literal faction ids, so it generalizes the moment Phase C's world roll seeds a full
#: roster (multiple empire-bloc kingdoms, several resistances). "the Empire" is the bloc.
ROLE_TO_KINDS: dict[str, tuple[str, ...]] = {
    "empire": ("empire_core", "conquered", "proxy"),
    "resistance": ("resistance",),
    "rival": ("rival",),
    "independent": ("independent",),
    "player_org": ("player_org",),
}


def faction_anchor(faction_id: str) -> str:
    """Anchor key for this faction's notes in the semantic ledger (prose mirror)."""
    return f"faction:{faction_id}"


#: Aliases mapping a character's typed ``identity`` allegiance token to how it resolves against
#: the faction ledger. A token that is already a faction id or a role needs no alias; these
#: cover the human-readable allegiances spawners use (``"imperial"`` for the empire bloc,
#: ``"rebel"`` for the Unbound). Realm allegiances (e.g. ``"stalnaz"``) are faction ids and
#: resolve directly. New aliases are added here, never inferred from prose.
IDENTITY_ALIASES: dict[str, str] = {
    "imperial": "empire",
    "empire": "empire",
    "vigovia": "empire",
    "rebel": "rebellion",
    "rebellion": "rebellion",
    "unbound": "rebellion",
    "resistance": "rebellion",
}


def resolve_identity_token(token: str, ledger: "FactionLedger") -> str:
    """Resolve one typed ``identity`` allegiance token to a faction-ledger id (or ``""`` when it
    names no known faction). Checks the alias map, then a direct faction id, then a role's
    primary — so ``"imperial"`` → the empire bloc lead and ``"stalnaz"`` → the Stalnaz faction."""
    token = token.strip().lower()
    if not token:
        return ""
    canonical = IDENTITY_ALIASES.get(token, token)
    if canonical in ledger.factions:
        return canonical
    if canonical in ROLE_TO_KINDS:
        primary = ledger.primary(canonical)
        if primary is not None:
            return primary.id
    if token in ledger.factions:
        return token
    return ""


def resolve_faction(
    tags: set[str],
    kind: str,
    ledger: "FactionLedger",
    identity: list[str] | None = None,
) -> str:
    """Resolve a character to the faction whose member they are, for per-faction kill accounting
    (`FACTION_KILL_REPUTATION.md` K1/§0). The typed **`identity`** allegiance is the source of
    truth and is tried first (``["imperial"]`` → the empire bloc, ``["stalnaz"]`` → Stalnaz). It
    falls back to the loose **`tags`** bag for un-migrated spawners — a directly-tagged faction
    id, then a tagged role's primary — then the ``civilian`` bucket for an unaligned person, and
    ``""`` for an unaligned creature (beasts are not politics and stay tally-exempt). Pure:
    depends only on its inputs and the current roster, so it generalizes as the world roll seeds
    more factions."""
    for token in identity or []:
        resolved = resolve_identity_token(token, ledger)
        if resolved:
            return resolved
    for faction_id in ledger.factions:
        if faction_id in tags:
            return faction_id
    for role in ROLE_TO_KINDS:
        if role in tags:
            primary = ledger.primary(role)
            if primary is not None:
                return primary.id
    if kind == "npc" or "civilian" in tags:
        return "civilian"
    return ""


def identity_from_tags(tags: set[str]) -> list[str]:
    """Bridge for un-migrated spawners: infer the typed ``identity`` allegiance from a creature's
    loose combat tags (empire markers → ``"imperial"``, rebel markers → ``"rebel"``). Realm-id
    tags are left to ``resolve_faction``'s tag fallback. Empty when nothing political is tagged."""
    identity: list[str] = []
    if {"empire", "imperial"} & tags:
        identity.append("imperial")
    if {"rebel", "rebellion", "unbound", "resistance"} & tags:
        identity.append("rebel")
    return identity


@dataclass
class Faction:
    id: str
    name: str
    kind: str  # one of FACTION_KINDS
    standing: dict[str, float] = field(default_factory=dict)  # axis -> value (open set)
    mood: str = "watchful"
    resources: dict[str, int] = field(
        default_factory=dict
    )  # spendable pools (Phase B+)
    goals: list[str] = field(default_factory=list)
    home_zones: list[tuple[int, int]] = field(default_factory=list)
    player_rank: str | None = None  # set if the player leads/has climbed this org
    notes_anchor: str = ""

    def standing_of(self, axis: str) -> float:
        return self.standing.get(axis, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "standing": dict(self.standing),
            "mood": self.mood,
            "resources": dict(self.resources),
            "goals": list(self.goals),
            "home_zones": [list(z) for z in self.home_zones],
            "player_rank": self.player_rank,
            "notes_anchor": self.notes_anchor,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Faction":
        return cls(
            id=str(raw.get("id", "")),
            name=str(raw.get("name", "")),
            kind=str(raw.get("kind", "independent")),
            standing={
                str(axis): float(v) for axis, v in (raw.get("standing") or {}).items()
            },
            mood=str(raw.get("mood", "watchful")),
            resources={str(k): int(v) for k, v in (raw.get("resources") or {}).items()},
            goals=[str(g) for g in raw.get("goals", [])],
            home_zones=[
                (int(z[0]), int(z[1]))
                for z in raw.get("home_zones", [])
                if isinstance(z, (list, tuple)) and len(z) >= 2
            ],
            player_rank=(
                str(raw["player_rank"]) if raw.get("player_rank") is not None else None
            ),
            notes_anchor=str(raw.get("notes_anchor", "")),
        )


@dataclass
class FactionLedger:
    factions: dict[str, Faction] = field(default_factory=dict)
    #: Directed inter-faction stances: ``(a_id, b_id) -> stance`` (one of FACTION_STANCES) —
    #: how faction ``a`` regards faction ``b``. Absent pair ⇒ ``"neutral"``. Seeded by the
    #: world roll; read by relational reactions and combat-stance derivation. A pure data
    #: layer over the existing roster, so it serializes within a run and never between runs.
    relationships: dict[tuple[str, str], str] = field(default_factory=dict)

    def get(self, faction_id: str) -> Faction | None:
        return self.factions.get(faction_id)

    def add(self, faction: Faction) -> Faction:
        self.factions[faction.id] = faction
        return faction

    def by_kind(self, *kinds: str) -> list[Faction]:
        wanted = set(kinds)
        return sorted(
            (f for f in self.factions.values() if f.kind in wanted),
            key=lambda f: f.id,
        )

    def ids_by_role(self, role: str) -> list[str]:
        """All faction ids filling a stable role (§0.1). Deterministic order. Empty if no
        faction fills the role yet."""
        return [f.id for f in self.by_kind(*ROLE_TO_KINDS.get(role, ()))]

    def primary(self, role: str) -> Faction | None:
        """The lead faction for a role — e.g. the empire core, or the main resistance.
        Prefers the most-canonical kind for the role (the first kind in ``ROLE_TO_KINDS``,
        so ``empire`` resolves to the ``empire_core`` heartland, not an alphabetically-earlier
        conquered realm), then by id. Deterministic; None if the role is unfilled."""
        kinds = ROLE_TO_KINDS.get(role, ())
        members = self.by_kind(*kinds)
        if not members:
            return None
        kind_rank = {kind: index for index, kind in enumerate(kinds)}
        return min(members, key=lambda f: (kind_rank.get(f.kind, len(kinds)), f.id))

    def adjust_standing(self, faction_id: str, axis: str, delta: float) -> float:
        """Accumulate ``delta`` on a faction's standing axis. Axes are open scales in
        Phase 0 (clamping/normalization is Phase B). Returns the new value; a no-op for
        unknown factions."""
        faction = self.factions.get(faction_id)
        if faction is None:
            return 0.0
        faction.standing[axis] = faction.standing.get(axis, 0.0) + delta
        return faction.standing[axis]

    def spend(self, faction_id: str, resource: str, n: int) -> bool:
        """Spend ``n`` of a resource if available (Phase B+ uses this to gate events).
        Returns True if the spend succeeded."""
        faction = self.factions.get(faction_id)
        if faction is None or faction.resources.get(resource, 0) < n:
            return False
        faction.resources[resource] -= n
        return True

    # --- Inter-faction relationships (FACTION_KILL_REPUTATION.md §10) -----------------

    def set_relationship(
        self, a_id: str, b_id: str, stance: str, *, mutual: bool = False
    ) -> None:
        """Record that faction ``a`` regards faction ``b`` with ``stance``. ``mutual=True``
        also sets the reverse with the same stance (use for symmetric stances like
        ``hostile``/``allied``; set the two directions separately for asymmetric ones like
        ``subject``/``occupier``)."""
        if a_id == b_id:
            return
        self.relationships[(a_id, b_id)] = stance
        if mutual:
            self.relationships[(b_id, a_id)] = stance

    def stance(self, a_id: str, b_id: str) -> str:
        """How faction ``a`` regards faction ``b`` (one of FACTION_STANCES). ``"self"`` for a
        faction toward itself; ``"neutral"`` for any pair with no recorded relationship."""
        if a_id == b_id:
            return "self"
        return self.relationships.get((a_id, b_id), "neutral")

    def regard(self, a_id: str, b_id: str) -> float:
        """How warmly faction ``a`` regards faction ``b``, in [-1, 1] (self ⇒ +1). The signed
        sentiment relational kill reactions scale by."""
        if a_id == b_id:
            return 1.0
        return STANCE_SENTIMENT.get(self.stance(a_id, b_id), 0.0)

    def are_hostile(self, a_id: str, b_id: str) -> bool:
        """Whether factions ``a`` and ``b`` are at open war — true if *either* direction
        carries a combative stance (war is mutual even when only one side declared it)."""
        if a_id == b_id:
            return False
        return (
            self.stance(a_id, b_id) in COMBATIVE_STANCES
            or self.stance(b_id, a_id) in COMBATIVE_STANCES
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "factions": {
                fid: faction.to_dict() for fid, faction in self.factions.items()
            },
            # Tuple keys can't be JSON keys; store as a flat list of [a, b, stance] triples.
            "relationships": [
                [a, b, stance] for (a, b), stance in self.relationships.items()
            ],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "FactionLedger":
        relationships: dict[tuple[str, str], str] = {}
        for entry in (raw or {}).get("relationships", []):
            if isinstance(entry, (list, tuple)) and len(entry) >= 3:
                relationships[(str(entry[0]), str(entry[1]))] = str(entry[2])
        return cls(
            factions={
                str(fid): Faction.from_dict(item)
                for fid, item in (raw or {}).get("factions", {}).items()
                if isinstance(item, dict)
            },
            relationships=relationships,
        )


def seed_phase0_factions() -> FactionLedger:
    """The Phase-0 two-pole scaffold: the Empire bloc and one rebel pole, each with the
    single standing axis the micro-loop moves. Placeholder names (D1). Phase C's world
    roll replaces this with the full rolled roster."""
    ledger = FactionLedger()
    ledger.add(
        Faction(
            id="empire",
            name=EMPIRE_NAME,
            kind="empire_core",
            standing={"imperial_threat": 0.0},
            mood="orderly",
            resources={
                "defense": EMPIRE_DEFENSE_START,
                "patrols": EMPIRE_PATROLS_START,
            },
            notes_anchor=faction_anchor("empire"),
        )
    )
    ledger.add(
        Faction(
            id="rebellion",
            name=REBELLION_NAME,
            kind="resistance",
            standing={"gratitude": 0.0},
            mood="hopeful",
            resources={"cells": REBELLION_CELLS_START},
            notes_anchor=faction_anchor("rebellion"),
        )
    )
    # The one standing conflict of the two-pole scaffold (the world roll seeds the full graph).
    ledger.set_relationship("empire", "rebellion", "hostile", mutual=True)
    return ledger
