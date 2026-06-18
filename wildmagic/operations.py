"""Engine operation primitives + state deltas (Stage 6 of the state-surface plan).

Wild-magic effects ultimately bottom out in a handful of shared mutations: damage or heal an
entity, write a tile, move or create an entity, apply a status, schedule an event. This module
is the typed surface for those primitives, and `StateDelta` is the compact, observable record
each one produces.

Capture is owned by the engine: while a wild-magic cast is applying, the engine records a
`StateDelta` for each mutation that flows through its shared mutators (`damage_entity`,
`heal_entity`, `set_tile`, `teleport_entity`, `spawn_actor`, `spawn_item`) and through
`apply_status` here. The collected deltas ride out on `WildMagicOutcome.deltas`, so a
multi-effect spell can be explained as a sequence of bound operations and tests can assert what
happened without parsing message text. The existing snapshot/rollback is untouched: deltas are
transient engine metadata, discarded when a cast rolls back.

These primitives delegate to the engine's existing mutators (which already clamp and message),
so behavior is unchanged; they are the path handlers should migrate onto over time. Pure
runtime helpers — imports only `models` types under TYPE_CHECKING, never `engine`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .semantics import WORLD_ANCHOR, entity_anchor, faction_anchor, place_anchor

if TYPE_CHECKING:
    from .engine import GameEngine
    from .models import Entity


@dataclass(frozen=True)
class StateDelta:
    """One observable mutation. `op` names the operation (``"damage"``, ``"heal"``,
    ``"create_tile"``, ``"move"``, ``"create_entity"``, ``"status"``, ``"schedule_event"``);
    `target` is an entity id or a ``"x,y"`` tile key; `details` carries the before/after."""

    op: str
    target: str | None = None
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "target": self.target,
            "summary": self.summary,
            "details": dict(self.details),
        }


def apply_damage(
    engine: "GameEngine",
    entity: "Entity",
    amount: int,
    damage_type: str = "arcane",
    source: "Entity | None" = None,
) -> int:
    """Damage an entity; the engine records a `damage` delta. Returns HP actually lost."""
    return engine.damage_entity(entity, amount, damage_type, source=source)


def heal(engine: "GameEngine", entity: "Entity", amount: int) -> int:
    """Heal an entity; the engine records a `heal` delta. Returns HP actually restored."""
    return engine.heal_entity(entity, amount)


def apply_status(
    engine: "GameEngine", entity: "Entity", status: str, duration: "int | str"
) -> StateDelta:
    """Apply a status to an entity and record a `status` delta. Statuses have no single engine
    mutator, so this primitive performs the write itself."""
    before = entity.statuses.get(status)
    entity.statuses[status] = duration
    delta = StateDelta(
        op="status",
        target=entity.id,
        summary=f"{entity.name} gained status {status}",
        details={"status": status, "duration": duration, "previous": before},
    )
    engine.record_delta(delta)
    return delta


def create_tile(
    engine: "GameEngine",
    x: int,
    y: int,
    tile: str,
    duration: "int | None" = None,
    tags: "set[str] | None" = None,
) -> bool:
    """Write a tile; the engine records a `create_tile` delta when it changes."""
    return engine.set_tile(x, y, tile, duration, tags)


def move_entity(engine: "GameEngine", entity: "Entity", x: int, y: int) -> bool:
    """Teleport an entity; the engine records a `move` delta on success."""
    return engine.teleport_entity(entity, x, y)


def create_actor(engine: "GameEngine", *args: Any, **kwargs: Any) -> "Entity":
    """Spawn an actor; the engine records a `create_entity` delta."""
    return engine.spawn_actor(*args, **kwargs)


def create_item(engine: "GameEngine", *args: Any, **kwargs: Any) -> "Entity":
    """Spawn a floor item; the engine records a `create_entity` delta."""
    return engine.spawn_item(*args, **kwargs)


# ----------------------------------------------------------------------------------------
# Durable world-memory lanes (Stage 7). Each kind of lasting world change has its own lane,
# so set_flag and free-text traits don't become catch-all substitutes for the simulation:
#
# - write_trait        : a soft descriptive fact attached to an entity/item; rides in context.
# - write_semantic_note: a soft fact about a place / faction / the world; retrieved by anchor.
# - adjust_faction     : a mechanical standing/reputation consequence.
# - emit_deed          : a consequential action judged by the bounded deed rules.
#
# Promises (future/rumored commitments) and canon records (materialized descriptions) have
# their own effect handlers (create_promise, canon resolution) and are reached through those.
# The engine still decides whether any of these create mechanical obligations; semantic-only
# writes (traits/notes) never gate critical-path progression. See docs §"Durable Memory Lanes".
# ----------------------------------------------------------------------------------------
def write_trait(
    engine: "GameEngine", entity: "Entity", text: str, *, salience: int = 4
) -> StateDelta:
    """Attach a soft narrative trait to an entity: stored on the entity (so it rides into
    prompts) and in the semantic ledger (so place/faction queries find it). Deduped + capped."""
    text = " ".join(str(text).split())[:120]
    if text and text.lower() not in {t.lower() for t in entity.traits}:
        entity.traits.append(text)
        entity.traits[:] = entity.traits[-8:]
    engine.record_note(
        entity_anchor(entity.id),
        text,
        kind="trait",
        source="spell:add_trait",
        salience=salience,
    )
    delta = StateDelta(
        op="trait",
        target=entity.id,
        summary=f"{entity.name}: {text}",
        details={"text": text},
    )
    engine.record_delta(delta)
    return delta


def write_semantic_note(
    engine: "GameEngine",
    anchor: str,
    text: str,
    *,
    kind: str = "note",
    source: str = "spell",
    salience: int = 3,
) -> StateDelta:
    """Deposit a soft fact into the semantic ledger under an anchor. Use the anchor helpers
    (place_anchor/faction_anchor/WORLD_ANCHOR) or write_place_note/_faction_note/_world_note."""
    text = " ".join(str(text).split())[:240]
    engine.record_note(anchor, text, kind=kind, source=source, salience=salience)
    delta = StateDelta(
        op="note",
        target=anchor,
        summary=text,
        details={"anchor": anchor, "kind": kind},
    )
    engine.record_delta(delta)
    return delta


def write_place_note(
    engine: "GameEngine", x: int, y: int, text: str, **kwargs: Any
) -> StateDelta:
    """A place remembers something ('make this room remember my name')."""
    return write_semantic_note(engine, place_anchor(x, y), text, **kwargs)


def write_faction_note(
    engine: "GameEngine", faction: str, text: str, **kwargs: Any
) -> StateDelta:
    return write_semantic_note(engine, faction_anchor(faction), text, **kwargs)


def write_world_note(engine: "GameEngine", text: str, **kwargs: Any) -> StateDelta:
    return write_semantic_note(engine, WORLD_ANCHOR, text, **kwargs)


def adjust_faction(
    engine: "GameEngine", faction_id: str, axis: str, amount: float
) -> StateDelta:
    """Shift a faction's standing on one axis (a mechanical reputation consequence)."""
    after = engine.state.faction_ledger.adjust_standing(faction_id, axis, amount)
    delta = StateDelta(
        op="faction",
        target=faction_id,
        summary=f"{faction_id} {axis} {amount:+g}",
        details={"axis": axis, "delta": amount, "after": after},
    )
    engine.record_delta(delta)
    return delta


def emit_deed(
    engine: "GameEngine",
    deed_type: str,
    *,
    magnitude: float,
    summary: str,
    **kwargs: Any,
) -> StateDelta:
    """Emit a consequential deed; the bounded rules interpreter decides its standing/legend
    consequences. Returns a `deed` delta (the deed itself may be None if nothing qualified)."""
    deed = engine.record_deed(deed_type, magnitude=magnitude, summary=summary, **kwargs)
    delta = StateDelta(
        op="deed",
        target=deed.id if deed is not None else None,
        summary=summary,
        details={"deed_type": deed_type, "magnitude": magnitude},
    )
    engine.record_delta(delta)
    return delta
