"""Emergent quests — the deed → objective matcher (EMERGENT_QUESTS §5).

A quest is a :class:`~wildmagic.promises.WorldPromise` carrying an
:class:`~wildmagic.promises.Objective`, opened by what an NPC says or what the player observes,
and **closed by a deed** rather than by walking an item back to a giver. This module is the one
general function that ties the existing deed ledger to open quest objectives: after a deed is
recorded, scan open quest promises and advance any whose explicit match spec the deed satisfies.

No per-quest scripting; pure and replay-safe (no LLM, no RNG). The deterministic skeleton
produces, satisfies, and mutates quests with zero model calls (EMERGENT_QUESTS §9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .promises import Objective

if TYPE_CHECKING:
    from .deeds import Deed
    from .promises import WorldPromise


#: objective type → the deed types that can satisfy it (EMERGENT_QUESTS §3.1). ``fetch`` keeps
#: its existing trade path (a synthetic ``acquired_item`` deed folds it in later, Q1b).
OBJECTIVE_DEEDS: dict[str, frozenset[str]] = {
    "rescue": frozenset({"freed_captive"}),
    "defend": frozenset({"defended_townsfolk"}),
    "slay": frozenset({"killed_imperials", "killed_combatant", "killed_civilians"}),
    "clear": frozenset({"killed_imperials", "killed_combatant"}),
    "avenge": frozenset({"killed_imperials", "killed_combatant", "killed_civilians"}),
}

#: Quest promise statuses no longer open to deed matching (objective already met or closed).
CLOSED_STATUSES: frozenset[str] = frozenset(
    {"objective_met", "fulfilled", "changed", "failed", "redeemed", "realized"}
)


def deed_satisfies(objective: Objective, deed: "Deed") -> bool:
    """Whether a deed satisfies an objective's explicit match spec (EMERGENT_QUESTS §5). The
    spec is read from ``objective.data``: ``deed_types`` (else the type's default set),
    ``subject_refs`` (the strongest signal — a specific soul), ``required_tags`` / ``any_tags``
    / ``excluded_tags`` over the deed's target tags, ``victim_faction``, and ``zone``."""
    spec: dict[str, Any] = objective.data or {}
    allowed = set(spec.get("deed_types") or OBJECTIVE_DEEDS.get(objective.type, ()))
    if not allowed or deed.type not in allowed:
        return False
    target_tags = set(deed.target_tags)
    required = set(spec.get("required_tags") or [])
    if required and not required.issubset(target_tags):
        return False
    any_tags = set(spec.get("any_tags") or [])
    if any_tags and not (any_tags & target_tags):
        return False
    excluded = set(spec.get("excluded_tags") or [])
    if excluded and (excluded & target_tags):
        return False
    subject_refs = set(spec.get("subject_refs") or [])
    if subject_refs and not (subject_refs & set(deed.subject_refs)):
        return False
    victim_faction = spec.get("victim_faction")
    if victim_faction and deed.victim_faction != victim_faction:
        return False
    zone = spec.get("zone")
    if zone is not None and tuple(zone) != tuple(deed.zone):
        return False
    return True


def advance_quests_with_deed(
    deed: "Deed", promises: list["WorldPromise"]
) -> list["WorldPromise"]:
    """Advance every open quest objective the deed satisfies, returning the promises whose
    objective just **completed** (reached its ``count``). Mutates each matched promise's
    objective ``progress`` and, on completion, sets status to ``objective_met`` — the reward is
    granted later by the world tick (the hybrid two-stage timing of §5)."""
    completed: list["WorldPromise"] = []
    for promise in promises:
        if (
            promise.kind != "quest"
            or promise.status in CLOSED_STATUSES
            or promise.objective is None
        ):
            continue
        if not deed_satisfies(promise.objective, deed):
            continue
        data = dict(promise.objective.data)
        count = int(data.get("count", 1) or 1)
        data["progress"] = int(data.get("progress", 0)) + 1
        promise.objective = Objective(promise.objective.type, data)
        if data["progress"] >= count:
            promise.status = "objective_met"
            completed.append(promise)
    return completed


def rescue_quests_for_dead_subjects(
    promises: list["WorldPromise"], dead_souls: set[str]
) -> list["WorldPromise"]:
    """Open ``rescue`` quests whose subject soul is among ``dead_souls`` — the person to be
    rescued was killed before the player reached them. These transform to ``avenge`` on the
    world tick (EMERGENT_QUESTS §6 mutation: rescue → avenge)."""
    affected: list["WorldPromise"] = []
    for promise in promises:
        if (
            promise.kind != "quest"
            or promise.status in CLOSED_STATUSES
            or promise.objective is None
            or promise.objective.type != "rescue"
        ):
            continue
        refs = set(promise.objective.data.get("subject_refs") or [])
        if refs & dead_souls:
            affected.append(promise)
    return affected
