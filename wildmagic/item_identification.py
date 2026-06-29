"""Structured LLM service for turning semantic items into functional items."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import copy
import json
import re
import urllib.error
from typing import Any, Protocol

from .config import (
    audit_dir,
    fallbacks_enabled,
    get_item_model,
    get_item_provider,
    ollama_host,
    ollama_item_num_predict,
    ollama_item_temperature,
    ollama_json_format_enabled,
    ollama_keep_alive,
    ollama_num_ctx,
    ollama_num_gpu,
    ollama_thinking_enabled,
    ollama_timeout_seconds,
)
from .equipment import EQUIPMENT_SLOTS
from .item_ability_cards import select_item_ability_cards
from .llm_client import (
    _post_ollama_chat_with_json_retry,
    normalize_ollama_url,
    strip_thinking,
)
from .llm_resolver import _write_jsonl_audit
from .models import DAMAGE_TYPES, MECHANICAL_STATUSES, MIST, TILE_ALIASES
from .normalize import clamp_int, coerce_list, normalize_id
from .item_palettes import (
    descriptor_for_palette,
    palette_by_id,
    palette_exists,
    palette_for_item,
    palette_prompt_cards,
)
from .prompts import ITEM_IDENTIFICATION_SYSTEM_PROMPT


@dataclass
class ItemIdentificationResolution:
    data: dict[str, Any] | None
    technical_failure: bool
    error: str | None = None
    provider_name: str = "unknown"
    raw_response: str | None = None
    audit_path: str | None = None


class ItemIdentificationProvider(Protocol):
    name: str

    def identify(self, context: dict[str, Any]) -> str: ...


class OllamaItemIdentificationProvider:
    name = "ollama"
    purpose = "item"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._model_override = model
        self.model = model or get_item_model()
        self.base_url = (
            normalize_ollama_url(base_url) if base_url else ollama_host(self.purpose)
        )
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else ollama_timeout_seconds(self.purpose)
        )

    def identify(self, context: dict[str, Any]) -> str:
        payload = {
            "model": self._model_override or get_item_model(),
            "stream": False,
            "think": ollama_thinking_enabled(self.purpose),
            "messages": [
                {"role": "system", "content": ITEM_IDENTIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context, ensure_ascii=True)},
            ],
            "options": {
                "temperature": ollama_item_temperature(),
                "top_p": 0.9,
                "num_predict": ollama_item_num_predict(),
                "num_ctx": ollama_num_ctx(self.purpose),
                "num_gpu": ollama_num_gpu(self.purpose),
            },
            "keep_alive": ollama_keep_alive(self.purpose),
        }
        if ollama_json_format_enabled(self.purpose):
            payload["format"] = "json"
        data = _post_ollama_chat_with_json_retry(
            self.base_url, payload, self.timeout_seconds
        )
        content = data.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama response did not include message.content")
        return content


class MockItemIdentificationProvider:
    name = "mock"

    def identify(self, context: dict[str, Any]) -> str:
        item = context.get("item") or {}
        name = str(item.get("name") or "odd item").strip() or "odd item"
        value_after = int((context.get("identification") or {}).get("value_after") or 1)
        cards = context.get("ability_cards") or []
        chosen = cards[0] if cards and isinstance(cards[0], dict) else {}
        shape = copy.deepcopy(chosen.get("json_shape") or {})
        use_spec = (
            shape.get("use_spec") if isinstance(shape.get("use_spec"), dict) else {}
        )
        for effect in coerce_list(use_spec.get("effects")):
            if isinstance(effect, dict):
                if "amount" in effect:
                    effect["amount"] = _scaled_amount(
                        value_after, base=int(effect["amount"])
                    )
                if "amount_min" in effect:
                    effect["amount_min"] = _scaled_amount(
                        value_after, base=int(effect["amount_min"])
                    )
                if "amount_max" in effect:
                    effect["amount_max"] = max(
                        int(effect["amount_min"]),
                        _scaled_amount(value_after, base=int(effect["amount_max"])),
                    )
        tags = list(item.get("tags") or [])[:4]
        tags.extend(str(tag) for tag in chosen.get("tags", [])[:2])
        palette = palette_for_item(item)
        descriptor = descriptor_for_palette(palette)
        display_name = _apply_descriptor(
            _base_identified_display_name(name), descriptor
        )
        ability_summary = _summarize_ability(
            shape.get("ability_kind") or "active",
            shape.get("equipment_slot"),
            shape.get("equipment_spec"),
            use_spec,
        )
        return json.dumps(
            {
                "identified": True,
                "descriptor": descriptor,
                "palette_id": palette["id"],
                "display_name": display_name,
                "description": (
                    f"{display_name} has been coaxed into a usable charm. "
                    f"Its old nature still colors the magic it gives off."
                ),
                "ability_summary": ability_summary,
                "ability_card_id": chosen.get("id"),
                "tags": sorted({normalize_id(tag) for tag in tags if str(tag).strip()}),
                "ability_kind": shape.get("ability_kind") or "active",
                "equipment_slot": shape.get("equipment_slot"),
                "equipment_spec": shape.get("equipment_spec"),
                "use_spec": use_spec,
            }
        )


class AutoItemIdentificationProvider:
    name = "auto"

    def __init__(self) -> None:
        self.ollama = OllamaItemIdentificationProvider()
        self.mock = MockItemIdentificationProvider()
        self.last_provider_name = "ollama"

    def identify(self, context: dict[str, Any]) -> str:
        try:
            self.last_provider_name = self.ollama.name
            return self.ollama.identify(context)
        except (OSError, TimeoutError, urllib.error.URLError, ValueError):
            if not fallbacks_enabled():
                raise
            self.last_provider_name = self.mock.name
            return self.mock.identify(context)


def make_item_identification_provider(
    provider_name: str | None = None,
) -> ItemIdentificationProvider:
    provider = (provider_name or get_item_provider()).lower().strip()
    if provider == "mock":
        return MockItemIdentificationProvider()
    if provider == "ollama":
        return OllamaItemIdentificationProvider()
    return AutoItemIdentificationProvider()


def identification_fee(base_value: int, npc_role: str = "") -> int:
    """Gold cost paid before the item ability is known."""

    role = normalize_id(npc_role)
    multiplier = (
        1.0 if role in {"merchant", "trader", "shopkeeper", "appraiser"} else 1.2
    )
    return max(5, int(round(max(1, base_value) * 0.5 * multiplier)))


def identified_item_value(base_value: int, fee: int) -> int:
    return max(1, int(base_value) + int(round(max(0, fee) * 0.75)))


def item_identification_context(
    *,
    item_card: dict[str, Any],
    npc_card: dict[str, Any],
    fee: int,
    value_after: int,
) -> dict[str, Any]:
    cards = select_item_ability_cards(item_card, npc_card)
    return {
        "item": item_card,
        "npc": npc_card,
        "identification": {
            "fee_gold_paid_before_reveal": fee,
            "value_after": value_after,
            "value_rule": "engine sets value_after = previous value + 3/4 of the identification fee",
        },
        "ability_cards": cards,
        "color_palettes": palette_prompt_cards(),
    }


def resolve_item_identification(
    provider: ItemIdentificationProvider,
    npc_name: str,
    context: dict[str, Any],
) -> ItemIdentificationResolution:
    resolved_provider_name = _item_provider_name(provider)
    active_context = context
    raw: str | None = None
    for attempt in range(2):
        try:
            raw = provider.identify(active_context)
        except (OSError, TimeoutError, urllib.error.URLError, ValueError) as exc:
            error = str(exc)
            resolved_provider_name = _item_provider_name(provider)
            audit_path = write_item_identification_audit_log(
                provider,
                npc_name,
                active_context,
                raw,
                None,
                True,
                error,
                resolved_provider_name,
            )
            return ItemIdentificationResolution(
                None, True, error, resolved_provider_name, raw, audit_path
            )

        resolved_provider_name = _item_provider_name(provider)
        try:
            parsed = parse_item_identification_json(raw)
            parsed = normalize_item_identification(parsed, context)
            error = validate_item_identification(parsed)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            parsed = None
            error = str(exc)

        if error is None:
            audit_path = write_item_identification_audit_log(
                provider,
                npc_name,
                active_context,
                raw,
                parsed,
                False,
                None,
                resolved_provider_name,
            )
            return ItemIdentificationResolution(
                parsed, False, None, resolved_provider_name, raw, audit_path
            )

        can_retry = attempt == 0 and resolved_provider_name == "ollama"
        if can_retry:
            write_item_identification_audit_log(
                provider,
                npc_name,
                active_context,
                raw,
                parsed,
                True,
                f"{error}; retrying once",
                resolved_provider_name,
            )
            active_context = _item_retry_context(context, raw, error)
            continue

        audit_path = write_item_identification_audit_log(
            provider,
            npc_name,
            active_context,
            raw,
            parsed,
            True,
            error,
            resolved_provider_name,
        )
        return ItemIdentificationResolution(
            None, True, error, resolved_provider_name, raw, audit_path
        )

    raise AssertionError("unreachable")


def parse_item_identification_json(raw: str) -> dict[str, Any]:
    cleaned = strip_thinking(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise TypeError("item identification response was not a JSON object")
    return parsed


def normalize_item_identification(
    data: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    item = context.get("item") or {}
    value_after = int((context.get("identification") or {}).get("value_after") or 1)
    palette_id = _normalize_palette_id(data.get("palette_id"), context)
    descriptor = _clean_descriptor(data.get("descriptor"))
    if not descriptor:
        descriptor = descriptor_for_palette(palette_by_id(palette_id))
    display_name = _clean_text(
        data.get("display_name")
    ) or _base_identified_display_name(str(item.get("name") or "identified item"))
    display_name = _apply_descriptor(display_name, descriptor)
    description = _clean_text(data.get("description"), limit=320)
    if not description:
        description = f"{display_name} has been identified and can now be used."

    card_shape, ability_card_id, card_tags = _selected_card_shape(data, context)
    shaped = _merge_card_shape(card_shape, data)
    shaped = _apply_effect_overrides(shaped, data)
    tags = [
        normalize_id(str(tag))
        for tag in coerce_list(data.get("tags"))
        if str(tag).strip()
    ][:8]
    tags.extend(card_tags[:2])
    ability_kind = normalize_id(str(shaped.get("ability_kind") or "active"))
    if ability_kind not in {"active", "slot_passive"}:
        ability_kind = "active"
    slot = normalize_id(str(shaped.get("equipment_slot") or ""))
    if ability_kind != "slot_passive" or slot not in EQUIPMENT_SLOTS:
        slot = None
    equipment_spec = _normalize_equipment_spec(shaped.get("equipment_spec"), slot)
    use_spec = _normalize_use_spec(shaped.get("use_spec"), value_after)
    ability_summary = _clean_text(data.get("ability_summary"), limit=180)
    if not ability_summary:
        ability_summary = _summarize_ability(
            ability_kind,
            slot,
            equipment_spec,
            use_spec,
        )
    return {
        "identified": True,
        "descriptor": descriptor,
        "palette_id": palette_id,
        "display_name": display_name,
        "description": description,
        "ability_summary": ability_summary,
        "ability_card_id": ability_card_id,
        "tags": sorted({tag for tag in tags if tag}),
        "ability_kind": ability_kind,
        "equipment_slot": slot,
        "equipment_spec": equipment_spec,
        "use_spec": use_spec,
    }


def validate_item_identification(data: dict[str, Any]) -> str | None:
    if data.get("identified") is not True:
        return "identified must be true"
    if not str(data.get("display_name") or "").strip():
        return "display_name is required"
    if not str(data.get("description") or "").strip():
        return "description is required"
    if not str(data.get("descriptor") or "").strip():
        return "descriptor is required"
    if not palette_exists(data.get("palette_id")):
        return "palette_id is not supported"
    if not str(data.get("ability_summary") or "").strip():
        return "ability_summary is required"
    use_spec = data.get("use_spec")
    if not isinstance(use_spec, dict):
        return "use_spec must be an object"
    effects = use_spec.get("effects")
    if not isinstance(effects, list) or not effects:
        return "use_spec.effects must be a non-empty list"
    if len(effects) > 2:
        return "use_spec.effects may include at most 2 effects"
    for index, effect in enumerate(effects):
        if not isinstance(effect, dict):
            return f"use_spec.effects[{index}] must be an object"
        if normalize_id(str(effect.get("kind") or "")) not in _ALLOWED_EFFECT_KINDS:
            return f"use_spec.effects[{index}] has unsupported kind"
    if data.get("ability_kind") == "slot_passive":
        if data.get("equipment_slot") not in EQUIPMENT_SLOTS:
            return "slot_passive items need a supported equipment_slot"
        if not isinstance(data.get("equipment_spec"), dict):
            return "slot_passive items need equipment_spec"
    return None


def write_item_identification_audit_log(
    provider: ItemIdentificationProvider,
    npc_name: str,
    context: dict[str, Any],
    raw_response: str | None,
    parsed: dict[str, Any] | None,
    technical_failure: bool,
    error: str | None,
    resolved_provider_name: str,
) -> str | None:
    audit_path = audit_dir() / "item_identification_audit.jsonl"
    prompt_messages = [
        {"role": "system", "content": ITEM_IDENTIFICATION_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(context, ensure_ascii=True)},
    ]
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "npc": npc_name,
        "provider": resolved_provider_name,
        "provider_requested": getattr(provider, "name", "unknown"),
        "model": getattr(provider, "model", None),
        "ollama_base_url": getattr(provider, "base_url", None),
        "prompt": {"messages": prompt_messages, "context": context},
        "raw_response": raw_response,
        "parsed_resolution": parsed,
        "technical_failure": technical_failure,
        "error": error,
    }
    return _write_jsonl_audit(audit_path, record)


_ALLOWED_EFFECT_KINDS = {
    "restore_mana",
    "heal",
    "status",
    "resistance",
    "create_tiles",
    "teleport_explored",
    "damage_nearest",
    "status_nearest",
}


def _item_provider_name(provider: ItemIdentificationProvider) -> str:
    if isinstance(provider, AutoItemIdentificationProvider):
        return provider.last_provider_name
    return getattr(provider, "name", "unknown")


def _item_retry_context(
    context: dict[str, Any], raw_response: str | None, error: str
) -> dict[str, Any]:
    updated = dict(context)
    updated["retry_after_invalid_resolution"] = {
        "error": error,
        "instruction": "Reply again with one valid JSON object in the exact item-identification shape. Do not include markdown, commentary, or <think> text.",
        "previous_response_prefix": (raw_response or "")[:600],
    }
    return updated


def _normalize_use_spec(value: Any, value_after: int) -> dict[str, Any]:
    spec = value if isinstance(value, dict) else {}
    effects = [
        _normalize_effect(effect, value_after)
        for effect in coerce_list(spec.get("effects"))
        if isinstance(effect, dict)
    ][:2]
    if not effects:
        effects = [{"kind": "restore_mana", "amount": _scaled_amount(value_after)}]
    consume_on_use = bool(spec.get("consume_on_use", False))
    charges = clamp_int(spec.get("charges"), 1, 9)
    if consume_on_use:
        charges = 1
    return {
        "effects": effects,
        "message": _clean_text(spec.get("message"), limit=180) or "You use the {item}.",
        "failure": _clean_text(spec.get("failure"), limit=160) or "Nothing happens.",
        "consume_on_use": consume_on_use,
        "charges": charges,
    }


def _normalize_effect(effect: dict[str, Any], value_after: int) -> dict[str, Any]:
    kind = normalize_id(str(effect.get("kind") or "restore_mana"))
    if kind not in _ALLOWED_EFFECT_KINDS:
        kind = "restore_mana"
    result: dict[str, Any] = {"kind": kind}
    max_amount = _scaled_amount(value_after, base=6)
    if "amount_min" in effect or "amount_max" in effect:
        minimum = clamp_int(effect.get("amount_min"), 0, max_amount)
        maximum = clamp_int(effect.get("amount_max"), minimum, max_amount)
        result["amount_min"] = minimum
        result["amount_max"] = maximum
    elif kind in {
        "restore_mana",
        "heal",
        "resistance",
        "damage_nearest",
    }:
        result["amount"] = clamp_int(effect.get("amount"), 1, max_amount)
    if kind in {"damage_nearest", "status_nearest"}:
        result["range"] = clamp_int(effect.get("range"), 1, 15)
        result["required"] = bool(effect.get("required", True))
    if kind in {"status", "status_nearest"}:
        status = normalize_id(str(effect.get("status") or "marked"))
        if status not in MECHANICAL_STATUSES:
            status = "marked"
        result["status"] = status
        result["duration"] = clamp_int(effect.get("duration"), 1, 12)
    if kind == "resistance":
        damage_type = normalize_id(str(effect.get("damage_type") or "physical"))
        result["damage_type"] = (
            damage_type if damage_type in DAMAGE_TYPES else "physical"
        )
    if kind == "damage_nearest":
        damage_type = normalize_id(str(effect.get("damage_type") or "arcane"))
        result["damage_type"] = damage_type if damage_type in DAMAGE_TYPES else "arcane"
    if kind == "create_tiles":
        tile_key = normalize_id(str(effect.get("tile") or "mist"))
        result["tile"] = TILE_ALIASES.get(tile_key, MIST)
        result["radius"] = clamp_int(effect.get("radius"), 0, 3)
        result["duration"] = clamp_int(effect.get("duration"), 1, 8)
    return result


def _normalize_equipment_spec(value: Any, slot: str | None) -> dict[str, int] | None:
    if slot is None:
        return None
    spec = value if isinstance(value, dict) else {}
    attack = clamp_int(spec.get("attack"), 0, 2)
    defense = clamp_int(spec.get("defense"), 0, 2)
    if attack <= 0 and defense <= 0:
        defense = (
            1
            if slot in {"armor", "charm", "head", "chest", "legs", "feet", "hands"}
            else 0
        )
        attack = 1 if defense == 0 else 0
    result: dict[str, int] = {}
    if attack:
        result["attack"] = attack
    if defense:
        result["defense"] = defense
    return result


def _selected_card_shape(
    data: dict[str, Any], context: dict[str, Any]
) -> tuple[dict[str, Any], str | None, list[str]]:
    card_id = normalize_id(
        str(
            data.get("ability_card_id")
            or data.get("card_id")
            or data.get("ability_id")
            or ""
        )
    )
    cards = [
        card
        for card in coerce_list(context.get("ability_cards"))
        if isinstance(card, dict)
    ]
    for card in cards:
        if normalize_id(str(card.get("id") or "")) == card_id:
            tags = [
                normalize_id(str(tag))
                for tag in coerce_list(card.get("tags"))
                if str(tag).strip()
            ]
            return (
                copy.deepcopy(card.get("json_shape") or {}),
                str(card.get("id")),
                tags,
            )
    if data.get("use_spec") is None and cards:
        card = cards[0]
        tags = [
            normalize_id(str(tag))
            for tag in coerce_list(card.get("tags"))
            if str(tag).strip()
        ]
        return copy.deepcopy(card.get("json_shape") or {}), str(card.get("id")), tags
    return {}, None, []


def _merge_card_shape(
    card_shape: dict[str, Any], data: dict[str, Any]
) -> dict[str, Any]:
    shaped = copy.deepcopy(card_shape)
    for key in ("ability_kind", "equipment_slot", "equipment_spec", "use_spec"):
        value = data.get(key)
        if value is not None:
            shaped[key] = value
    return shaped


def _apply_effect_overrides(
    shaped: dict[str, Any], data: dict[str, Any]
) -> dict[str, Any]:
    overrides = data.get("effect_overrides")
    if not isinstance(overrides, dict):
        overrides = data.get("overrides")
    if not isinstance(overrides, dict):
        return shaped
    result = copy.deepcopy(shaped)
    use_spec = dict(result.get("use_spec") or {})
    for key in ("message", "failure", "consume_on_use", "charges"):
        if key in overrides:
            use_spec[key] = overrides[key]
    effects = [
        dict(effect)
        for effect in coerce_list(use_spec.get("effects"))
        if isinstance(effect, dict)
    ]
    if effects:
        effect_overrides = (
            overrides.get("effect")
            if isinstance(overrides.get("effect"), dict)
            else overrides
        )
        for key in (
            "amount",
            "amount_min",
            "amount_max",
            "damage_type",
            "status",
            "tile",
            "radius",
            "duration",
            "range",
            "required",
        ):
            if key in effect_overrides:
                effects[0][key] = effect_overrides[key]
        use_spec["effects"] = effects
    result["use_spec"] = use_spec
    return result


def _normalize_palette_id(value: Any, context: dict[str, Any]) -> str:
    palette_id = normalize_id(str(value or ""))
    if palette_exists(palette_id):
        return palette_id
    return str(palette_for_item(context.get("item") or {})["id"])


def _clean_descriptor(value: Any) -> str:
    text = _clean_text(value, limit=28).lower()
    text = re.sub(r"[^a-z0-9 '\-]", "", text)
    return text.strip(" '-")


def _apply_descriptor(display_name: str, descriptor: str) -> str:
    cleaned = _clean_text(display_name, limit=64) or "item"
    descriptor = _clean_descriptor(descriptor)
    if not descriptor:
        descriptor = "awakened"
    descriptor_id = normalize_id(descriptor)
    cleaned_id = normalize_id(cleaned)
    if cleaned_id == descriptor_id or cleaned_id.startswith(f"{descriptor_id}_"):
        return cleaned[:80]
    return _clean_text(f"{descriptor} {cleaned}", limit=80)


def _summarize_ability(
    ability_kind: str,
    equipment_slot: Any,
    equipment_spec: Any,
    use_spec: dict[str, Any],
) -> str:
    if ability_kind == "slot_passive" and isinstance(equipment_spec, dict):
        bonuses = []
        attack = equipment_spec.get("attack")
        defense = equipment_spec.get("defense")
        if attack:
            bonuses.append(f"+{int(attack)} attack")
        if defense:
            bonuses.append(f"+{int(defense)} defense")
        bonus_text = " and ".join(bonuses) or "a small protection"
        slot = normalize_id(str(equipment_slot or "charm"))
        return f"Equip it in your {slot} slot for {bonus_text}."

    effect = next(
        (
            effect
            for effect in coerce_list(use_spec.get("effects"))
            if isinstance(effect, dict)
        ),
        {},
    )
    kind = normalize_id(str(effect.get("kind") or ""))
    charges = use_spec.get("charges")
    charge_text = ""
    try:
        charge_count = int(charges)
        charge_text = f" ({charge_count} charge{'s' if charge_count != 1 else ''})"
    except (TypeError, ValueError):
        pass
    if kind == "restore_mana":
        return f"Use it to restore mana{charge_text}."
    if kind == "heal":
        return f"Use it to heal wounds{charge_text}."
    if kind == "status":
        status = str(effect.get("status") or "marked").replace("_", " ")
        return f"Use it to give yourself {status}{charge_text}."
    if kind == "resistance":
        damage_type = str(effect.get("damage_type") or "damage").replace("_", " ")
        return f"Use it to gain {damage_type} resistance{charge_text}."
    if kind == "create_tiles":
        return f"Use it to spill temporary terrain nearby{charge_text}."
    if kind == "teleport_explored":
        return f"Use it to blink to a random explored place{charge_text}."
    if kind == "damage_nearest":
        return f"Use it to strike the nearest enemy in range{charge_text}."
    if kind == "status_nearest":
        status = str(effect.get("status") or "marked").replace("_", " ")
        return f"Use it to make the nearest enemy {status}{charge_text}."
    return f"Use it to release a small stored magic{charge_text}."


def _scaled_amount(value_after: int, *, base: int = 4) -> int:
    value_after = max(1, int(value_after))
    return clamp_int(base + value_after // 35, 1, 12)


def _base_identified_display_name(name: str) -> str:
    cleaned = " ".join(str(name or "identified item").replace("_", " ").split())
    if not cleaned:
        cleaned = "identified item"
    return cleaned[:64]


def _clean_text(value: Any, *, limit: int = 80) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] or text[:limit]
    return text
