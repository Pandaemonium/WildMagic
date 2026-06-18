"""Normalized references and selectors for wild-magic JSON (Stage 3 of the state-surface plan).

Resolver JSON refers to things in the world in many ways: legacy strings (`"player"`,
`"nearest_enemy"`, `"there"`, a bare entity id), and — going forward — typed refs:

    {"kind": "entity", "id": "actor_3"}
    {"kind": "tile", "x": 12, "y": 8}
    {"kind": "room", "id": "room_2"}
    {"kind": "faction", "id": "empire"}
    {"selector": "nearest_enemy"}
    {"selector": "selected_target"}

`normalize_ref` turns any of those into a single `Ref`. The `bind_*` functions are the engine
authority that resolves a `Ref` against live state — to an entity, a position, or a group.
Legacy strings are preserved verbatim inside a `raw` ref and bound through the exact same logic
the engine used before, so existing JSON keeps working unchanged; the typed forms add explicit
entity/tile/room/faction targeting on top.

This module is pure resolution: it reads the engine but never mutates state. It takes the live
`GameEngine` as a parameter and only uses its public queries, so it sits below the engine in the
import order (no `engine` import at module load).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .normalize import normalize_id, singular_target_tag

if TYPE_CHECKING:
    from .engine import GameEngine
    from .models import Entity


# Legacy single-target string sets, kept verbatim from the engine so raw refs bind
# identically to the old resolve_target / resolve_target_group.
_PLAYER_KEYWORDS = frozenset({"player", "self", "@", "you", "me"})
_NEAREST_ENEMY_KEYWORDS = frozenset(
    {
        "nearest_enemy",
        "nearest enemy",
        "enemy",
        "nearest_foe",
        "nearest_entity",
        "nearest_target",
        "closest_enemy",
        "target",
        "foe",
        "nearest_actor",
    }
)
_ALL_LIVING_KEYWORDS = frozenset(
    {"all", "everyone", "all_entities", "all_nearby", "everything"}
)
_ALL_ENEMIES_KEYWORDS = frozenset(
    {
        "all_enemies",
        "enemies",
        "all_foes",
        "all_hostiles",
        "nearby_enemies",
        "every_enemy",
    }
)
_ALLIES_KEYWORDS = frozenset({"allies", "all_allies", "friends", "friendlies"})
_KNOWN_SELECTOR_KEYWORDS = frozenset(
    normalize_id(item)
    for item in (
        _PLAYER_KEYWORDS
        | _NEAREST_ENEMY_KEYWORDS
        | _ALL_LIVING_KEYWORDS
        | _ALL_ENEMIES_KEYWORDS
        | _ALLIES_KEYWORDS
        | {"selected_target", "marked_target", "marked_square", "there", "that_square"}
    )
)


@dataclass(frozen=True)
class Ref:
    """A normalized reference. `kind` is one of:

    - ``"raw"``: a legacy string (in ``raw``), bound through the old engine logic.
    - ``"entity"``: an explicit entity id (in ``id``).
    - ``"tile"``: explicit coordinates (in ``x``/``y``); either may be None if uncoercible.
    - ``"room"``: a room id (in ``id``).
    - ``"faction"``: a faction id (in ``id``).
    - ``"selector"``: a named selector (in ``selector``), e.g. ``"nearest_enemy"``.
    """

    kind: str
    raw: str = ""
    id: str | None = None
    x: int | None = None
    y: int | None = None
    selector: str | None = None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_ref(value: Any) -> Ref:
    """Translate a JSON target/center/placement value into a normalized `Ref`.

    Accepts legacy strings (preserved verbatim for the raw binder), already-built `Ref`s,
    and the typed dict forms. Unknown/empty shapes become an empty raw ref, which binds to
    the player for single targets and to nothing for groups — matching the legacy fallbacks."""
    if isinstance(value, Ref):
        return value
    if value is None:
        return Ref(kind="raw", raw="")
    if isinstance(value, dict):
        kind = value.get("kind")
        if kind == "entity":
            ident = value.get("id")
            return Ref(kind="entity", id=None if ident is None else str(ident))
        if kind == "tile":
            return Ref(
                kind="tile",
                x=_coerce_int(value.get("x")),
                y=_coerce_int(value.get("y")),
            )
        if kind == "room":
            ident = value.get("id")
            return Ref(kind="room", id=None if ident is None else str(ident))
        if kind == "faction":
            ident = value.get("id")
            return Ref(
                kind="faction",
                id=None if ident is None else normalize_id(str(ident)),
            )
        if kind == "selector":
            sel = value.get("selector") or value.get("id") or ""
            return Ref(kind="selector", selector=normalize_id(str(sel)))
        # Untagged dicts: infer from the keys present.
        if "selector" in value:
            return Ref(kind="selector", selector=normalize_id(str(value["selector"])))
        if "x" in value and "y" in value:
            return Ref(
                kind="tile",
                x=_coerce_int(value.get("x")),
                y=_coerce_int(value.get("y")),
            )
        if value.get("id") is not None:
            return Ref(kind="entity", id=str(value["id"]))
        return Ref(kind="raw", raw="")
    if isinstance(value, str):
        return Ref(kind="raw", raw=value)
    return Ref(kind="raw", raw=str(value))


# --- raw (legacy string) binders ---------------------------------------------------------
def _bind_raw_entity(engine: "GameEngine", raw: str | None) -> "Entity | None":
    """The pre-refs `resolve_target` logic, kept exact so legacy JSON is unchanged."""
    if not raw or raw in _PLAYER_KEYWORDS:
        return engine.state.player
    # An explicit player-marked target overrides the nearest-enemy auto-aim. For a
    # bare-tile mark this returns None (no occupant); position-needing callers fall back
    # to the marked tile via bind_position.
    if engine.has_target() and engine.references_selected_target(raw):
        return engine.selected_target_entity()
    if raw in _NEAREST_ENEMY_KEYWORDS:
        return engine.nearest_enemy()
    return engine.state.entities.get(raw)


def _bind_raw_group(engine: "GameEngine", raw: str | None) -> "list[Entity]":
    """The pre-refs `resolve_target_group` logic, kept exact."""
    target = normalize_id(str(raw or ""))
    if target in _ALL_LIVING_KEYWORDS:
        return [
            entity
            for entity in engine.state.entities.values()
            if entity.kind in {"actor", "npc"} and entity.hp > 0
        ]
    if target in _ALL_ENEMIES_KEYWORDS:
        return engine.living_enemies()
    if target in _ALLIES_KEYWORDS:
        return [
            entity
            for entity in engine.state.entities.values()
            if entity.kind in {"actor", "npc"}
            and entity.hp > 0
            and entity.faction in {"ally", "player"}
        ]
    singular = singular_target_tag(target)
    if not singular:
        return []
    return [
        entity
        for entity in engine.state.entities.values()
        if entity.kind in {"actor", "npc"}
        and entity.hp > 0
        and entity.id != engine.state.player_id
        and (
            singular in entity.tags or singular in normalize_id(entity.name).split("_")
        )
    ]


def _bind_raw_position(
    engine: "GameEngine", raw: str | None
) -> "tuple[int, int] | None":
    """Position for a legacy string: the marked square (live occupant's current tile, else
    the bare mark) for selected-target keywords, otherwise the bound entity's tile."""
    if engine.has_target() and engine.references_selected_target(raw):
        occupant = engine.selected_target_entity()
        if occupant is not None:
            return occupant.x, occupant.y
        return engine.selected_target_tile()
    entity = _bind_raw_entity(engine, raw)
    if entity is not None:
        return entity.x, entity.y
    return None


def _clamp_tile(engine: "GameEngine", x: int, y: int) -> "tuple[int, int]":
    cx = max(0, min(x, engine.state.width - 1))
    cy = max(0, min(y, engine.state.height - 1))
    return cx, cy


# --- public binders ----------------------------------------------------------------------
def bind_ref(engine: "GameEngine", ref: Ref) -> "Entity | None":
    """Resolve a ref to a single entity (or None). Tile refs bind to the living occupant
    of that square; room/faction refs are not single entities and bind to None."""
    if ref.kind == "raw":
        return _bind_raw_entity(engine, ref.raw)
    if ref.kind == "selector":
        return _bind_raw_entity(engine, ref.selector)
    if ref.kind == "entity":
        return None if ref.id is None else engine.state.entities.get(ref.id)
    if ref.kind == "tile":
        if ref.x is None or ref.y is None:
            return None
        x, y = _clamp_tile(engine, ref.x, ref.y)
        return engine._target_entity_at(x, y)
    return None


def bind_position(engine: "GameEngine", ref: Ref) -> "tuple[int, int] | None":
    """Resolve a ref to a tile position (or None when it cannot be placed)."""
    if ref.kind == "tile":
        if ref.x is None or ref.y is None:
            return None
        return _clamp_tile(engine, ref.x, ref.y)
    if ref.kind == "entity":
        entity = bind_ref(engine, ref)
        return None if entity is None else (entity.x, entity.y)
    if ref.kind == "room":
        room = _room_by_id(engine, ref.id)
        return None if room is None else (room.center[0], room.center[1])
    if ref.kind == "selector":
        return _bind_raw_position(engine, ref.selector)
    if ref.kind == "raw":
        return _bind_raw_position(engine, ref.raw)
    return None


def bind_group(engine: "GameEngine", ref: Ref) -> "list[Entity]":
    """Resolve a ref to a list of entities."""
    if ref.kind == "raw":
        return _bind_raw_group(engine, ref.raw)
    if ref.kind == "selector":
        return _bind_raw_group(engine, ref.selector)
    if ref.kind == "faction":
        if not ref.id:
            return []
        return [
            entity
            for entity in engine.state.entities.values()
            if entity.kind in {"actor", "npc"}
            and entity.hp > 0
            and normalize_id(entity.faction) == ref.id
        ]
    if ref.kind in {"entity", "tile"}:
        entity = bind_ref(engine, ref)
        return [entity] if entity is not None else []
    return []


def typed_ref_error(engine: "GameEngine", value: Any) -> str | None:
    """Return an error for an explicit typed ref that cannot bind.

    Legacy strings intentionally stay permissive; this only checks dict-shaped refs the
    resolver chose to make explicit. Invalid typed refs are contract failures, not silent
    retargeting opportunities.
    """
    if not isinstance(value, dict):
        return None
    ref = normalize_ref(value)
    if ref.kind == "raw":
        return None
    if ref.kind == "entity":
        if not ref.id:
            return "entity ref is missing id"
        if ref.id not in engine.state.entities:
            return f"unknown entity ref: {ref.id}"
        return None
    if ref.kind == "tile":
        if ref.x is None or ref.y is None:
            return "tile ref needs integer x and y"
        if not engine.in_bounds(ref.x, ref.y):
            return f"tile ref out of bounds: {ref.x},{ref.y}"
        return None
    if ref.kind == "room":
        if not ref.id:
            return "room ref is missing id"
        if ref.id not in engine.state.room_profiles:
            return f"unknown room ref: {ref.id}"
        return None
    if ref.kind == "faction":
        if not ref.id:
            return "faction ref is missing id"
        if ref.id not in engine.state.faction_ledger.factions:
            return f"unknown faction ref: {ref.id}"
        return None
    if ref.kind == "selector":
        if not ref.selector:
            return "selector ref is missing selector"
        if ref.selector not in _KNOWN_SELECTOR_KEYWORDS:
            return f"unknown selector ref: {ref.selector}"
        return None
    return f"unknown ref kind: {ref.kind}"


def _room_by_id(engine: "GameEngine", room_id: str | None):
    if not room_id:
        return None
    return engine.state.room_profiles.get(room_id)
