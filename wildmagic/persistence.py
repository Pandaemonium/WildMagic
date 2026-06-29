from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .bonds import Bond
from .deeds import DeedLedger
from .engine import GameEngine, GameState, LogMessage
from .factions import FactionLedger
from .legend import LegendLedger
from .models import (
    CanonRecord,
    CharacterProfile,
    Curse,
    Entity,
    GameStats,
    GossipEdge,
    NPCMemoryRecord,
    NPCProfile,
    RoomProfile,
    ZoneSnapshot,
)
from .promises import PromiseReservation, WorldPromise
from .semantics import SemanticLedger, WorldNote
from .worldgen import WorldMap


SAVE_FORMAT_VERSION = 1


def _save_value(value: Any) -> Any:
    """Return a JSON-compatible copy of generic engine-owned data."""

    if isinstance(value, LogMessage):
        return {"text": str(value), "is_danger": bool(value.is_danger)}
    if isinstance(value, dict):
        return {str(key): _save_value(item) for key, item in value.items()}
    if isinstance(value, set):
        return [_save_value(item) for item in sorted(value, key=str)]
    if isinstance(value, tuple):
        return [_save_value(item) for item in value]
    if isinstance(value, list):
        return [_save_value(item) for item in value]
    return value


def _pair_key(pair: tuple[int, int]) -> str:
    return f"{int(pair[0])},{int(pair[1])}"


def _parse_pair_key(key: Any) -> tuple[int, int]:
    try:
        sx, sy = str(key).split(",", 1)
        return int(sx), int(sy)
    except (TypeError, ValueError):
        return (0, 0)


def _rng_state_to_json(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_rng_state_to_json(item) for item in value]
    if isinstance(value, list):
        return [_rng_state_to_json(item) for item in value]
    return value


def _rng_state_from_json(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_rng_state_from_json(item) for item in value)
    return value


def character_profile_to_snapshot(
    profile: CharacterProfile | None,
) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "origin_id": profile.origin_id,
        "vigor": profile.vigor,
        "attunement": profile.attunement,
        "composure": profile.composure,
        "appearance": profile.appearance,
        "backstory": profile.backstory,
        "signature": profile.signature,
        "name": profile.name,
        "gender": profile.gender,
        "portrait_path": profile.portrait_path,
    }


def character_profile_from_snapshot(
    data: dict[str, Any] | None,
) -> CharacterProfile | None:
    if data is None:
        return None
    return CharacterProfile(
        origin_id=str(data.get("origin_id") or "wanderer"),
        vigor=int(data.get("vigor") or 3),
        attunement=int(data.get("attunement") or 3),
        composure=int(data.get("composure") or 3),
        appearance=str(data.get("appearance") or ""),
        backstory=str(data.get("backstory") or ""),
        signature=str(data.get("signature") or ""),
        name=str(data.get("name") or ""),
        gender=str(data.get("gender") or ""),
        portrait_path=str(data.get("portrait_path") or ""),
    )


def curse_to_snapshot(curse: Curse) -> dict[str, Any]:
    return {
        "id": curse.id,
        "name": curse.name,
        "description": curse.description,
        "stacks": curse.stacks,
        "semantic_prompt": curse.semantic_prompt,
        "mechanics": _save_value(curse.mechanics),
        "tags": sorted(curse.tags),
        "xp_to_clear": curse.xp_to_clear,
        "clear_progress": curse.clear_progress,
        "source_turn": curse.source_turn,
    }


def curse_from_snapshot(data: dict[str, Any]) -> Curse:
    return Curse(
        id=str(data.get("id") or ""),
        name=str(data.get("name") or ""),
        description=str(data.get("description") or ""),
        stacks=max(1, int(data.get("stacks") or 1)),
        semantic_prompt=str(data.get("semantic_prompt") or ""),
        mechanics=dict(data.get("mechanics") or {}),
        tags={str(tag) for tag in data.get("tags", [])},
        xp_to_clear=max(1, int(data.get("xp_to_clear") or 3)),
        clear_progress=max(0, int(data.get("clear_progress") or 0)),
        source_turn=int(data.get("source_turn") or 0),
    )


def entity_to_snapshot(entity: Entity) -> dict[str, Any]:
    return {
        "id": entity.id,
        "name": entity.name,
        "kind": entity.kind,
        "x": entity.x,
        "y": entity.y,
        "char": entity.char,
        "hp": entity.hp,
        "max_hp": entity.max_hp,
        "mana": entity.mana,
        "max_mana": entity.max_mana,
        "attack": entity.attack,
        "defense": entity.defense,
        "blocks": entity.blocks,
        "faction": entity.faction,
        "ai": entity.ai,
        "item_type": entity.item_type,
        "material": entity.material,
        "quantity": entity.quantity,
        "statuses": dict(entity.statuses),
        "status_display": dict(entity.status_display),
        "status_expiry_text": dict(entity.status_expiry_text),
        "tags": sorted(entity.tags),
        "identity": list(entity.identity),
        "role": entity.role,
        "affiliations": list(entity.affiliations),
        "soul_id": entity.soul_id,
        "resistances": dict(entity.resistances),
        "weaknesses": dict(entity.weaknesses),
        "auras": _save_value(entity.auras),
        "traits": list(entity.traits),
        "equipment": dict(entity.equipment),
        "focus_slots": list(entity.focus_slots),
        "description": entity.description,
        "details": _save_value(entity.details),
        "inventory": dict(entity.inventory),
        "protected_items": sorted(entity.protected_items),
        "curses": {
            curse_id: curse_to_snapshot(curse)
            for curse_id, curse in sorted(entity.curses.items())
        },
        "profile": character_profile_to_snapshot(entity.profile),
    }


def entity_from_snapshot(data: dict[str, Any]) -> Entity:
    return Entity(
        id=str(data.get("id") or ""),
        name=str(data.get("name") or ""),
        kind=str(data.get("kind") or "actor"),
        x=int(data.get("x") or 0),
        y=int(data.get("y") or 0),
        char=str(data.get("char") or "?")[:1],
        hp=int(data.get("hp") or 0),
        max_hp=int(data.get("max_hp") or 1),
        mana=int(data.get("mana") or 0),
        max_mana=int(data.get("max_mana") or 0),
        attack=int(data.get("attack") or 0),
        defense=int(data.get("defense") or 0),
        blocks=bool(data.get("blocks", False)),
        faction=str(data.get("faction") or "neutral"),
        ai=str(data["ai"]) if data.get("ai") is not None else None,
        item_type=str(data["item_type"]) if data.get("item_type") is not None else None,
        material=str(data["material"]) if data.get("material") is not None else None,
        quantity=int(data.get("quantity") or 1),
        statuses=dict(data.get("statuses") or {}),
        status_display=dict(data.get("status_display") or {}),
        status_expiry_text=dict(data.get("status_expiry_text") or {}),
        tags={str(tag) for tag in data.get("tags", [])},
        identity=[str(item) for item in data.get("identity", [])],
        role=str(data.get("role") or ""),
        affiliations=[str(item) for item in data.get("affiliations", [])],
        soul_id=str(data.get("soul_id") or ""),
        resistances={
            str(key): int(value)
            for key, value in (data.get("resistances") or {}).items()
        },
        weaknesses={
            str(key): int(value)
            for key, value in (data.get("weaknesses") or {}).items()
        },
        auras=[dict(aura) for aura in data.get("auras", [])],
        traits=[str(trait) for trait in data.get("traits", [])],
        equipment=dict(data.get("equipment") or {}),
        focus_slots=[str(slot) for slot in data.get("focus_slots", [])],
        description=(
            str(data["description"]) if data.get("description") is not None else None
        ),
        details=dict(data.get("details") or {}),
        inventory={
            str(key): int(value) for key, value in (data.get("inventory") or {}).items()
        },
        protected_items={str(item) for item in data.get("protected_items", [])},
        curses={
            str(curse_id): curse_from_snapshot(curse)
            for curse_id, curse in (data.get("curses") or {}).items()
            if isinstance(curse, dict)
        },
        profile=character_profile_from_snapshot(data.get("profile")),
    )


def npc_profile_to_snapshot(profile: NPCProfile) -> dict[str, Any]:
    return {
        "entity_id": profile.entity_id,
        "name": profile.name,
        "role": profile.role,
        "backstory": profile.backstory,
        "appearance": profile.appearance,
        "soul_id": profile.soul_id,
        "traits": list(profile.traits),
        "lore": dict(profile.lore),
        "memory": list(profile.memory),
        "memory_records": [record.to_dict() for record in profile.memory_records],
        "conversation": [dict(item) for item in profile.conversation],
        "wares": dict(profile.wares),
        "wanted_item": profile.wanted_item,
        "wanted_qty": profile.wanted_qty,
        "reward_gold": profile.reward_gold,
        "reward_item": profile.reward_item,
        "reward_qty": profile.reward_qty,
        "quest_completed": profile.quest_completed,
        "bond": profile.bond.to_dict(),
        "lead": _save_value(profile.lead),
        "concern": _save_value(profile.concern),
    }


def npc_profile_from_snapshot(data: dict[str, Any]) -> NPCProfile:
    return NPCProfile(
        entity_id=str(data.get("entity_id") or ""),
        name=str(data.get("name") or ""),
        role=str(data.get("role") or ""),
        backstory=str(data.get("backstory") or ""),
        appearance=str(data.get("appearance") or ""),
        soul_id=str(data.get("soul_id") or ""),
        traits=[str(trait) for trait in data.get("traits", [])],
        lore={str(key): int(value) for key, value in (data.get("lore") or {}).items()},
        memory=[str(item) for item in data.get("memory", [])],
        memory_records=[
            NPCMemoryRecord.from_dict(record)
            for record in data.get("memory_records", [])
            if isinstance(record, dict)
        ],
        conversation=[
            {
                "speaker": str(item.get("speaker") or ""),
                "text": str(item.get("text") or ""),
            }
            for item in data.get("conversation", [])
            if isinstance(item, dict)
        ],
        wares={
            str(key): int(value) for key, value in (data.get("wares") or {}).items()
        },
        wanted_item=(
            str(data["wanted_item"]) if data.get("wanted_item") is not None else None
        ),
        wanted_qty=int(data.get("wanted_qty") or 0),
        reward_gold=int(data.get("reward_gold") or 0),
        reward_item=(
            str(data["reward_item"]) if data.get("reward_item") is not None else None
        ),
        reward_qty=int(data.get("reward_qty") or 0),
        quest_completed=bool(data.get("quest_completed", False)),
        bond=Bond.from_dict(data.get("bond") or {}),
        lead=dict(data["lead"]) if isinstance(data.get("lead"), dict) else None,
        concern=dict(data["concern"])
        if isinstance(data.get("concern"), dict)
        else None,
    )


def game_stats_from_snapshot(data: dict[str, Any] | None) -> GameStats:
    data = data or {}
    return GameStats(
        enemies_killed=int(data.get("enemies_killed") or 0),
        spells_cast=int(data.get("spells_cast") or 0),
        spells_failed=int(data.get("spells_failed") or 0),
        items_used=int(data.get("items_used") or 0),
        items_collected=int(data.get("items_collected") or 0),
        curses_gained=int(data.get("curses_gained") or 0),
        deepest_floor=int(data.get("deepest_floor") or 1),
        damage_dealt=int(data.get("damage_dealt") or 0),
        damage_taken=int(data.get("damage_taken") or 0),
        hp_healed=int(data.get("hp_healed") or 0),
        experience_gained=int(data.get("experience_gained") or 0),
    )


def semantic_ledger_to_snapshot(ledger: SemanticLedger) -> dict[str, Any]:
    return {
        "per_anchor_cap": ledger.per_anchor_cap,
        "notes": {
            anchor: [
                {
                    "text": note.text,
                    "kind": note.kind,
                    "source": note.source,
                    "turn_created": note.turn_created,
                    "salience": note.salience,
                    "expires_turn": note.expires_turn,
                }
                for note in notes
            ]
            for anchor, notes in sorted(ledger.notes.items())
        },
    }


def semantic_ledger_from_snapshot(data: dict[str, Any] | None) -> SemanticLedger:
    data = data or {}
    ledger = SemanticLedger(per_anchor_cap=int(data.get("per_anchor_cap") or 6))
    for anchor, notes in (data.get("notes") or {}).items():
        ledger.notes[str(anchor)] = [
            WorldNote(
                text=str(note.get("text") or ""),
                kind=str(note.get("kind") or "trait"),
                source=str(note.get("source") or "unknown"),
                turn_created=int(note.get("turn_created") or 0),
                salience=int(note.get("salience") or 3),
                expires_turn=(
                    int(note["expires_turn"])
                    if note.get("expires_turn") is not None
                    else None
                ),
            )
            for note in notes
            if isinstance(note, dict)
        ]
    return ledger


def zone_snapshot_to_snapshot(snapshot: ZoneSnapshot) -> dict[str, Any]:
    return {
        "tiles": [list(row) for row in snapshot.tiles],
        "tile_tags": {
            key: list(value) for key, value in sorted(snapshot.tile_tags.items())
        },
        "tile_durations": dict(sorted(snapshot.tile_durations.items())),
        "tile_flows": {
            key: dict(value) for key, value in sorted(snapshot.tile_flows.items())
        },
        "entities": {
            entity_id: entity_to_snapshot(entity)
            for entity_id, entity in sorted(snapshot.entities.items())
        },
        "explored": sorted(snapshot.explored),
        "zone_type": snapshot.zone_type,
        "room_profiles": {
            room_id: room.to_public_dict(include_secrets=True)
            for room_id, room in sorted(snapshot.room_profiles.items())
        },
        "tile_rooms": dict(sorted(snapshot.tile_rooms.items())),
    }


def zone_snapshot_from_snapshot(data: dict[str, Any]) -> ZoneSnapshot:
    return ZoneSnapshot(
        tiles=[[str(tile) for tile in row] for row in data.get("tiles", [])],
        tile_tags={
            str(key): [str(tag) for tag in value]
            for key, value in (data.get("tile_tags") or {}).items()
        },
        tile_durations={
            str(key): int(value)
            for key, value in (data.get("tile_durations") or {}).items()
        },
        tile_flows={
            str(key): dict(value)
            for key, value in (data.get("tile_flows") or {}).items()
        },
        entities={
            str(entity_id): entity_from_snapshot(entity)
            for entity_id, entity in (data.get("entities") or {}).items()
            if isinstance(entity, dict)
        },
        explored={str(key) for key in data.get("explored", [])},
        zone_type=str(data.get("zone_type") or "frontier"),
        room_profiles={
            str(room_id): RoomProfile.from_dict(room)
            for room_id, room in (data.get("room_profiles") or {}).items()
            if isinstance(room, dict)
        },
        tile_rooms={
            str(key): str(value)
            for key, value in (data.get("tile_rooms") or {}).items()
        },
    )


def message_to_snapshot(message: str) -> dict[str, Any]:
    return {
        "text": str(message),
        "is_danger": bool(getattr(message, "is_danger", False)),
    }


def message_from_snapshot(data: dict[str, Any] | str) -> LogMessage:
    if isinstance(data, dict):
        return LogMessage(str(data.get("text") or ""), bool(data.get("is_danger")))
    return LogMessage(str(data), False)


def game_state_to_snapshot(state: GameState) -> dict[str, Any]:
    return {
        "width": state.width,
        "height": state.height,
        "tiles": [list(row) for row in state.tiles],
        "visible": sorted(state.visible),
        "visible_entity_ids": sorted(state.visible_entity_ids),
        "explored": sorted(state.explored),
        "entities": {
            entity_id: entity_to_snapshot(entity)
            for entity_id, entity in sorted(state.entities.items())
        },
        "player_id": state.player_id,
        "turn": state.turn,
        "messages": [message_to_snapshot(message) for message in state.messages],
        "message_count": state.message_count,
        "npc_profiles": {
            npc_id: npc_profile_to_snapshot(profile)
            for npc_id, profile in sorted(state.npc_profiles.items())
        },
        "gossip_edges": {
            edge_id: edge.to_dict()
            for edge_id, edge in sorted(state.gossip_edges.items())
        },
        "pending_trade": _save_value(state.pending_trade),
        "flags": _save_value(state.flags),
        "last_talked_npc_name": state.last_talked_npc_name,
        "target_x": state.target_x,
        "target_y": state.target_y,
        "target_entity_id": state.target_entity_id,
        "tile_tags": {
            key: list(value) for key, value in sorted(state.tile_tags.items())
        },
        "tile_durations": dict(sorted(state.tile_durations.items())),
        "tile_flows": {
            key: dict(value) for key, value in sorted(state.tile_flows.items())
        },
        "tile_auras": _save_value(state.tile_auras),
        "semantics": semantic_ledger_to_snapshot(state.semantics),
        "deed_ledger": state.deed_ledger.to_dict(),
        "faction_ledger": state.faction_ledger.to_dict(),
        "world_map": state.world_map.to_dict() if state.world_map is not None else None,
        "legend_ledger": state.legend_ledger.to_dict(),
        "simulated_through_turn": state.simulated_through_turn,
        "ticked_through_day": state.ticked_through_day,
        "pending_backlash": _save_value(state.pending_backlash),
        "gossip_spread_days": sorted(state.gossip_spread_days),
        "player_soul_id": state.player_soul_id,
        "event_timers": _save_value(state.event_timers),
        "triggers": _save_value(state.triggers),
        "player_steps": state.player_steps,
        "last_spell_text": state.last_spell_text,
        "same_spell_streak": state.same_spell_streak,
        "game_over": state.game_over,
        "victory": state.victory,
        "death_cause": state.death_cause,
        "region_id": state.region_id,
        "rng_seed": state.rng_seed,
        "scenario": state.scenario,
        "fov_radius": state.fov_radius,
        "depth": state.depth,
        "max_depth": state.max_depth,
        "stats": state.stats.to_dict(),
        "experience": state.experience,
        "zone_x": state.zone_x,
        "zone_y": state.zone_y,
        "zone_type": state.zone_type,
        "zones": {
            _pair_key(zone): zone_snapshot_to_snapshot(snapshot)
            for zone, snapshot in sorted(state.zones.items())
        },
        "dungeon_floors": {
            str(depth): zone_snapshot_to_snapshot(snapshot)
            for depth, snapshot in sorted(state.dungeon_floors.items())
        },
        "room_profiles": {
            room_id: room.to_public_dict(include_secrets=True)
            for room_id, room in sorted(state.room_profiles.items())
        },
        "tile_rooms": dict(sorted(state.tile_rooms.items())),
        "canon_records": {
            record_id: record.to_dict()
            for record_id, record in sorted(state.canon_records.items())
        },
        "item_lore": _save_value(state.item_lore),
        "_player_taking_damage": state._player_taking_damage,
        "_no_body_inventory": dict(state._no_body_inventory),
        "_no_body_curses": {
            curse_id: curse_to_snapshot(curse)
            for curse_id, curse in sorted(state._no_body_curses.items())
        },
        "promises": [promise.to_dict() for promise in state.promises],
        "promise_reservations": {
            _pair_key(zone): [reservation.to_dict() for reservation in reservations]
            for zone, reservations in sorted(state.promise_reservations.items())
        },
        "character": character_profile_to_snapshot(state.character),
    }


def game_state_from_snapshot(data: dict[str, Any]) -> GameState:
    state = GameState(
        width=int(data.get("width") or 0),
        height=int(data.get("height") or 0),
        rng_seed=data.get("rng_seed"),
        scenario=str(data.get("scenario") or "dungeon"),
    )
    state.tiles = [[str(tile) for tile in row] for row in data.get("tiles", [])]
    state.visible = {str(key) for key in data.get("visible", [])}
    state.visible_entity_ids = {
        str(entity_id) for entity_id in data.get("visible_entity_ids", [])
    }
    state.explored = {str(key) for key in data.get("explored", [])}
    state.entities = {
        str(entity_id): entity_from_snapshot(entity)
        for entity_id, entity in (data.get("entities") or {}).items()
        if isinstance(entity, dict)
    }
    state.player_id = str(data.get("player_id") or "player")
    state.turn = int(data.get("turn") or 0)
    state.messages = [message_from_snapshot(item) for item in data.get("messages", [])]
    state.message_count = int(data.get("message_count") or len(state.messages))
    state.npc_profiles = {
        str(npc_id): npc_profile_from_snapshot(profile)
        for npc_id, profile in (data.get("npc_profiles") or {}).items()
        if isinstance(profile, dict)
    }
    state.gossip_edges = {
        str(edge_id): GossipEdge.from_dict(edge)
        for edge_id, edge in (data.get("gossip_edges") or {}).items()
        if isinstance(edge, dict)
    }
    state.pending_trade = data.get("pending_trade")
    state.flags = dict(data.get("flags") or {})
    state.last_talked_npc_name = (
        str(data["last_talked_npc_name"])
        if data.get("last_talked_npc_name") is not None
        else None
    )
    state.target_x = int(data["target_x"]) if data.get("target_x") is not None else None
    state.target_y = int(data["target_y"]) if data.get("target_y") is not None else None
    state.target_entity_id = (
        str(data["target_entity_id"]) if data.get("target_entity_id") else None
    )
    state.tile_tags = {
        str(key): [str(tag) for tag in value]
        for key, value in (data.get("tile_tags") or {}).items()
    }
    state.tile_durations = {
        str(key): int(value)
        for key, value in (data.get("tile_durations") or {}).items()
    }
    state.tile_flows = {
        str(key): dict(value) for key, value in (data.get("tile_flows") or {}).items()
    }
    state.tile_auras = {
        str(key): [dict(aura) for aura in value]
        for key, value in (data.get("tile_auras") or {}).items()
    }
    state.semantics = semantic_ledger_from_snapshot(data.get("semantics"))
    state.deed_ledger = DeedLedger.from_dict(data.get("deed_ledger") or {})
    state.faction_ledger = FactionLedger.from_dict(data.get("faction_ledger") or {})
    state.world_map = (
        WorldMap.from_dict(data["world_map"])
        if isinstance(data.get("world_map"), dict)
        else None
    )
    state.legend_ledger = LegendLedger.from_dict(data.get("legend_ledger") or {})
    state.simulated_through_turn = int(data.get("simulated_through_turn") or 0)
    state.ticked_through_day = int(data.get("ticked_through_day") or 1)
    state.pending_backlash = [
        dict(event)
        for event in data.get("pending_backlash", [])
        if isinstance(event, dict)
    ]
    state.gossip_spread_days = {int(day) for day in data.get("gossip_spread_days", [])}
    state.player_soul_id = str(data.get("player_soul_id") or "player")
    state.event_timers = [
        dict(event) for event in data.get("event_timers", []) if isinstance(event, dict)
    ]
    state.triggers = [
        dict(trigger)
        for trigger in data.get("triggers", [])
        if isinstance(trigger, dict)
    ]
    state.player_steps = int(data.get("player_steps") or 0)
    state.last_spell_text = str(data.get("last_spell_text") or "")
    state.same_spell_streak = int(data.get("same_spell_streak") or 0)
    state.game_over = bool(data.get("game_over", False))
    state.victory = bool(data.get("victory", False))
    state.death_cause = (
        str(data["death_cause"]) if data.get("death_cause") is not None else None
    )
    state.region_id = str(data.get("region_id") or "frontier")
    state.fov_radius = int(data.get("fov_radius") or 9)
    state.depth = int(data.get("depth") or 1)
    state.max_depth = int(data.get("max_depth") or 3)
    state.stats = game_stats_from_snapshot(data.get("stats"))
    state.experience = int(data.get("experience") or 0)
    state.zone_x = int(data.get("zone_x") or 0)
    state.zone_y = int(data.get("zone_y") or 0)
    state.zone_type = str(data.get("zone_type") or "frontier")
    state.zones = {
        _parse_pair_key(zone): zone_snapshot_from_snapshot(snapshot)
        for zone, snapshot in (data.get("zones") or {}).items()
        if isinstance(snapshot, dict)
    }
    state.dungeon_floors = {
        int(depth): zone_snapshot_from_snapshot(snapshot)
        for depth, snapshot in (data.get("dungeon_floors") or {}).items()
        if isinstance(snapshot, dict)
    }
    state.room_profiles = {
        str(room_id): RoomProfile.from_dict(room)
        for room_id, room in (data.get("room_profiles") or {}).items()
        if isinstance(room, dict)
    }
    state.tile_rooms = {
        str(key): str(value) for key, value in (data.get("tile_rooms") or {}).items()
    }
    state.canon_records = {
        str(record_id): CanonRecord.from_dict(record)
        for record_id, record in (data.get("canon_records") or {}).items()
        if isinstance(record, dict)
    }
    state.item_lore = {
        str(key): dict(value)
        for key, value in (data.get("item_lore") or {}).items()
        if isinstance(value, dict)
    }
    state._player_taking_damage = bool(data.get("_player_taking_damage", False))
    state._no_body_inventory = {
        str(key): int(value)
        for key, value in (data.get("_no_body_inventory") or {}).items()
    }
    state._no_body_curses = {
        str(curse_id): curse_from_snapshot(curse)
        for curse_id, curse in (data.get("_no_body_curses") or {}).items()
        if isinstance(curse, dict)
    }
    state.promises = [
        WorldPromise.from_dict(promise)
        for promise in data.get("promises", [])
        if isinstance(promise, dict)
    ]
    state.promise_reservations = {
        _parse_pair_key(zone): [
            PromiseReservation.from_dict(reservation)
            for reservation in reservations
            if isinstance(reservation, dict)
        ]
        for zone, reservations in (data.get("promise_reservations") or {}).items()
    }
    state.character = character_profile_from_snapshot(data.get("character"))
    return state


def _infer_next_entity_number(state: GameState) -> int:
    highest = 0
    for entity_id in state.entities:
        try:
            highest = max(highest, int(str(entity_id).rsplit("_", 1)[1]))
        except (IndexError, ValueError):
            continue
    return highest + 1


def engine_to_snapshot(engine: GameEngine) -> dict[str, Any]:
    return {
        "version": SAVE_FORMAT_VERSION,
        "kind": "wildmagic.engine_snapshot",
        "state": game_state_to_snapshot(engine.state),
        "runtime": {
            "rng_state": _rng_state_to_json(engine.rng.getstate()),
            "next_entity_number": getattr(engine, "_next_entity_number", 1),
            "npc_perception_message_count": getattr(
                engine, "_npc_perception_message_count", 0
            ),
            "prop_rooms_done": sorted(getattr(engine, "_prop_rooms_done", set())),
        },
    }


def engine_from_snapshot(
    snapshot: dict[str, Any],
    *,
    provider_name: str | None = None,
) -> GameEngine:
    if int(snapshot.get("version") or 0) != SAVE_FORMAT_VERSION:
        raise ValueError(
            f"Unsupported save snapshot version {snapshot.get('version')!r}."
        )
    state = game_state_from_snapshot(snapshot.get("state") or {})
    engine = GameEngine(
        seed=state.rng_seed,
        scenario=state.scenario,
        provider_name=provider_name,
    )
    engine.close()
    runtime = snapshot.get("runtime") or {}
    engine.state = state
    if runtime.get("rng_state") is not None:
        engine.rng.setstate(_rng_state_from_json(runtime["rng_state"]))
    engine._next_entity_number = int(
        runtime.get("next_entity_number") or _infer_next_entity_number(state)
    )
    engine._conducting_lightning = False
    engine._npc_perception_message_count = int(
        runtime.get("npc_perception_message_count") or state.message_count
    )
    engine._delta_capture = False
    engine._delta_log = []
    engine._cast_ref_cache = {}
    engine._pending_towns = {}
    engine._pending_town_contexts = {}
    engine._pending_town_start_times = {}
    engine._pending_prop_rooms = {}
    engine._prop_rooms_done = {
        str(room_id) for room_id in runtime.get("prop_rooms_done", [])
    }
    return engine


def session_to_snapshot(session: Any) -> dict[str, Any]:
    """Freeze a session after draining completed background results into GameState."""

    session.drain_lore(block=True)
    session.drain_flesh(block=True)
    session.drain_canon_prewarm(block=True)
    return {
        "version": SAVE_FORMAT_VERSION,
        "kind": "wildmagic.session_snapshot",
        "engine": engine_to_snapshot(session.engine),
        "session": {
            "seed": session.seed,
            "scenario": session.scenario,
            "provider": session.provider_label,
            "dialogue_provider": session.dialogue_provider_label,
            "trade_provider": session.trade_provider_label,
            "lore_provider": session.lore_provider_label,
            "flesh_provider": session.flesh_provider_label,
            "canon_provider": session.canon_provider_label,
            "deed_interpreter_provider": session.deed_interpreter_label,
            "replay_mode": session.replay_mode,
            "queued_flesh_ids": sorted(session._queued_flesh_ids),
            "queued_canon_ids": sorted(session._queued_canon_ids),
            "records": _save_value(session.records),
        },
    }


def session_from_snapshot(
    snapshot: dict[str, Any],
    *,
    provider_name: str | None = None,
) -> Any:
    if int(snapshot.get("version") or 0) != SAVE_FORMAT_VERSION:
        raise ValueError(
            f"Unsupported save snapshot version {snapshot.get('version')!r}."
        )
    from .actions import GameSession

    session_info = snapshot.get("session") or {}
    engine = engine_from_snapshot(
        snapshot.get("engine") or {}, provider_name=provider_name
    )
    deed_provider = session_info.get("deed_interpreter_provider")
    if deed_provider == "fallback":
        deed_provider = "off"
    session = GameSession(
        seed=engine.state.rng_seed,
        scenario=engine.state.scenario,
        provider_name=provider_name or session_info.get("provider"),
        dialogue_provider_name=session_info.get("dialogue_provider"),
        trade_provider_name=session_info.get("trade_provider"),
        lore_provider_name=session_info.get("lore_provider"),
        flesh_provider_name=session_info.get("flesh_provider"),
        canon_provider_name=session_info.get("canon_provider"),
        deed_interpreter_provider_name=deed_provider,
        replay_mode=bool(session_info.get("replay_mode", False)),
    )
    session.engine.close()
    session.engine = engine
    session.seed = engine.state.rng_seed
    session.scenario = engine.state.scenario
    session._pending_lore = []
    session._pending_flesh = []
    session._pending_canon = []
    session._queued_flesh_ids = {
        str(item) for item in session_info.get("queued_flesh_ids", [])
    }
    session._queued_canon_ids = {
        str(item) for item in session_info.get("queued_canon_ids", [])
    }
    session._promise_apply_buffer = []
    session._flesh_apply_buffer = []
    session._canon_apply_buffer = []
    session.records = [
        dict(record)
        for record in session_info.get("records", [])
        if isinstance(record, dict)
    ]
    return session


def save_session_snapshot(session: Any, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(session_to_snapshot(session), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_session_snapshot(path: str | Path, *, provider_name: str | None = None) -> Any:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return session_from_snapshot(data, provider_name=provider_name)
