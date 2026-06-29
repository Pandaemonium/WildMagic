from __future__ import annotations

from typing import Any

from .equipment import EQUIPMENT_SLOTS, equipment_slot_for_item
from .game_data import DEFAULT_ITEM_USE_SPEC, ITEM_USE_SPECS
from .item_catalog import reagent_card
from .models import MIST, Entity
from .operations import StateDelta
from .normalize import (
    clamp_int,
    coerce_list,
    normalize_id,
    optional_duration,
    status_duration,
)


class _ItemsMixin:
    """Item/inventory methods mixed into GameEngine."""

    def spawn_item(
        self,
        name: str,
        char: str,
        x: int,
        y: int,
        item_type: str,
        quantity: int = 1,
        material: str | None = None,
        tags: set[str] | None = None,
    ) -> Entity:
        entity = Entity(
            id=self.next_entity_id("item"),
            name=name,
            kind="item",
            x=x,
            y=y,
            char=char,
            item_type=item_type,
            material=material,
            quantity=quantity,
            blocks=False,
            tags=set(tags or ()),
        )
        self.state.entities[entity.id] = entity
        if self._delta_capture:
            self.record_delta(
                StateDelta(
                    op="create_entity",
                    target=entity.id,
                    summary=f"{name} appeared at {x},{y}",
                    details={
                        "kind": "item",
                        "name": name,
                        "item_type": item_type,
                        "x": x,
                        "y": y,
                    },
                )
            )
        return entity

    def use_item(self, item_name: str) -> bool:
        if self.state.game_over:
            return False
        matched = self.find_inventory_item(item_name)
        if matched is None or self.state.inventory.get(matched, 0) < 1:
            self.state.add_message(f"You don't have any {item_name.strip().lower()}.")
            return False
        spec = self.item_use_spec(matched)
        charges = spec.get("charges")
        if charges is not None:
            try:
                charge_count = int(charges)
            except (TypeError, ValueError):
                charge_count = 0
            if charge_count <= 0:
                self.state.add_message(f"The {matched} has no charge left.")
                return False
        consumed = self._apply_item_use_spec(matched, spec)
        if consumed:
            if bool(spec.get("consume_on_use", True)):
                self.consume_inventory_item(matched, 1)
            elif charges is not None:
                self._set_item_use_charges(matched, max(0, int(charges) - 1))
            self.state.stats.items_used += 1
            self.finish_player_turn()
        return consumed

    def item_use_spec(self, item_name: str) -> dict[str, Any]:
        lore = self.state.item_lore.get(normalize_id(item_name)) or {}
        spec = lore.get("use_spec")
        if lore.get("identified") and isinstance(spec, dict):
            return dict(spec)
        return ITEM_USE_SPECS.get(normalize_id(item_name), DEFAULT_ITEM_USE_SPEC)

    def _set_item_use_charges(self, item_name: str, charges: int) -> None:
        key = normalize_id(item_name)
        lore = dict(self.state.item_lore.get(key) or {})
        spec = dict(lore.get("use_spec") or {})
        spec["charges"] = max(0, charges)
        lore["use_spec"] = spec
        self.state.item_lore[key] = lore

    def identify_inventory_item(
        self,
        item_name: str,
        resolution: dict[str, Any],
        *,
        npc_name: str,
        fee: int,
        value_after: int,
        base_value: int,
    ) -> str | None:
        if self.state.game_over:
            return None
        matched = self.find_inventory_item(item_name)
        if matched is None or self.state.inventory.get(matched, 0) < 1:
            self.state.add_message(f"You don't have any {item_name.strip().lower()}.")
            return None
        if normalize_id(matched) == "gold":
            self.state.add_message("Gold is already exactly as mysterious as it looks.")
            return None
        lore = self.state.item_lore.get(normalize_id(matched)) or {}
        if lore.get("identified"):
            self.state.add_message(f"The {matched} has already been identified.")
            return None
        gold_key = self.find_inventory_item("gold")
        gold = self.state.inventory.get(gold_key, 0) if gold_key else 0
        if gold < fee:
            self.state.add_message(
                f"{npc_name} asks {fee} gold to identify it, but you have only {gold}."
            )
            return None

        descriptor = _clean_item_descriptor(resolution.get("descriptor"))
        display_name = self._identified_display_name(
            matched,
            resolution.get("display_name"),
            descriptor,
        )
        identified_key = self._identified_inventory_key(
            matched,
            display_name,
            descriptor=descriptor,
        )
        was_protected = self.is_item_protected(matched)
        self.consume_inventory_item(matched, 1)
        if gold_key is not None:
            self.consume_inventory_item(gold_key, fee)
        self.state.inventory[identified_key] = (
            self.state.inventory.get(identified_key, 0) + 1
        )
        if was_protected:
            self.state.player.protected_items.add(identified_key)

        tags = {
            normalize_id(str(tag))
            for tag in resolution.get("tags", [])
            if str(tag).strip()
        }
        if isinstance(lore.get("tags"), list):
            tags.update(normalize_id(str(tag)) for tag in lore["tags"])
        metadata = {
            "identified": True,
            "descriptor": descriptor or "awakened",
            "palette_id": normalize_id(str(resolution.get("palette_id") or "")),
            "value": value_after,
            "base_item": matched,
            "base_value": base_value,
            "identification_fee": fee,
            "identified_by": npc_name,
            "identified_turn": self.state.turn,
            "tags": sorted(tags),
            "ability_summary": _clean_message_text(resolution.get("ability_summary"))
            or _item_ability_summary(resolution),
            "ability_card_id": normalize_id(
                str(resolution.get("ability_card_id") or "")
            ),
            "ability_kind": resolution.get("ability_kind") or "active",
            "use_spec": dict(resolution.get("use_spec") or {}),
        }
        if lore.get("material"):
            metadata["material"] = lore["material"]
        if lore.get("rarity"):
            metadata["rarity"] = lore["rarity"]
        if resolution.get("equipment_slot"):
            metadata["equipment_slot"] = resolution["equipment_slot"]
        if isinstance(resolution.get("equipment_spec"), dict):
            metadata["equipment_spec"] = dict(resolution["equipment_spec"])
        self.set_item_lore(
            identified_key,
            display_name,
            str(resolution.get("description") or ""),
            source="identified",
            metadata=metadata,
        )
        self.state.add_message(f"{npc_name} identifies the {matched}: {display_name}.")
        description = _clean_message_text(resolution.get("description"))
        if description:
            self.state.add_message(description)
        ability_summary = str(metadata.get("ability_summary") or "").strip()
        if ability_summary:
            self.state.add_message(f"Ability: {ability_summary}")
        self.state.add_message(
            f"You pay {fee} gold. It is now worth about {value_after} gold."
        )
        self.finish_player_turn()
        return identified_key

    def _identified_display_name(
        self,
        source_key: str,
        display_name: object,
        descriptor: str,
    ) -> str:
        base = _clean_item_name(display_name or source_key)
        prefix = _clean_item_descriptor(descriptor) or "awakened"
        if _name_has_prefix(base, prefix):
            return base
        return _clean_item_name(f"{prefix} {base}")

    def _identified_inventory_key(
        self,
        source_key: str,
        display_name: str,
        *,
        descriptor: str = "",
    ) -> str:
        base = _clean_item_name(display_name)
        remaining_source = self.state.inventory.get(source_key, 0) > 1
        if normalize_id(base) == normalize_id(source_key):
            base = _clean_item_name(
                f"{_clean_item_descriptor(descriptor) or 'awakened'} {base}"
            )
        candidate = base
        suffix = 2
        while candidate in self.state.inventory and (
            remaining_source or candidate != source_key
        ):
            candidate = f"{base} {suffix}"
            suffix += 1
        return candidate

    def drop_item(self, item_name: str) -> bool:
        if self.state.game_over:
            return False
        matched = self.find_inventory_item(item_name)
        if matched is None or self.state.inventory.get(matched, 0) < 1:
            self.state.add_message(f"You don't have any {item_name.strip().lower()}.")
            return False
        self.consume_inventory_item(matched, 1)
        player = self.state.player
        self.spawn_item(matched, "?", player.x, player.y, item_type=matched)
        self.state.add_message(f"You drop {matched}.")
        self.finish_player_turn()
        return True

    def find_inventory_item(
        self, item_name: str, *, include_lore_aliases: bool = True
    ) -> str | None:
        return self.find_item_in(
            self.state.inventory,
            item_name,
            include_lore_aliases=include_lore_aliases,
        )

    def protected_inventory_key(self, item_name: str) -> str | None:
        """Return the protected carried stack matching `item_name`, if any."""
        matched = self.find_inventory_item(item_name)
        if matched is None:
            return None
        wanted = normalize_id(matched)
        player = self.state.player
        for protected in set(player.protected_items):
            if protected == matched or normalize_id(protected) == wanted:
                return protected
        return None

    def is_item_protected(self, item_name: str) -> bool:
        return self.protected_inventory_key(item_name) is not None

    def protect_item(self, item_name: str) -> bool:
        """Move a carried stack into the spell-safe part of inventory.

        Protection only blocks wild-magic item costs. Manual actions such as use, drop,
        equip, and trade still operate normally because the player is explicitly choosing
        that item.
        """
        if self.state.game_over:
            return False
        matched = self.find_inventory_item(item_name)
        if matched is None or self.state.inventory.get(matched, 0) < 1:
            self.state.add_message(f"You don't have any {item_name.strip().lower()}.")
            return False
        player = self.state.player
        if self.is_item_protected(matched):
            self.state.add_message(f"{matched} is already protected from wild magic.")
            return True
        player.protected_items.add(matched)
        self.state.add_message(f"You protect {matched} from wild-magic costs.")
        return True

    def unprotect_item(self, item_name: str) -> bool:
        """Return a carried stack to the ordinary reagent pool."""
        if self.state.game_over:
            return False
        matched = self.find_inventory_item(item_name)
        if matched is None:
            self.state.add_message(f"You don't have any {item_name.strip().lower()}.")
            return False
        protected = self.protected_inventory_key(matched)
        if protected is None:
            self.state.add_message(f"{matched} is not protected.")
            return True
        self.state.player.protected_items.discard(protected)
        self.state.add_message(f"{matched} can be spent by wild magic again.")
        return True

    def reagent_cards(self, *, include_protected: bool = False) -> list[dict[str, Any]]:
        """Carried item stacks formatted as spell-fuel cards."""
        cards: list[dict[str, Any]] = []
        protected_ids = {
            normalize_id(name)
            for name in self.state.player.protected_items
            if name in self.state.inventory
        }
        for name, quantity in sorted(self.state.inventory.items()):
            if quantity <= 0:
                continue
            protected = normalize_id(name) in protected_ids
            if protected and not include_protected:
                continue
            lore = self.state.item_lore.get(normalize_id(name)) or {}
            cards.append(
                reagent_card(
                    name,
                    quantity,
                    protected=protected,
                    lore=lore,
                )
            )
        return cards

    def find_item_in(
        self,
        container: dict[str, int],
        item_name: str,
        *,
        include_lore_aliases: bool = True,
    ) -> str | None:
        """Fuzzy name lookup against any item-quantity dict (player inventory, NPC
        wares, ...) -- the same dict shape, so the same matching rules apply."""
        wanted = normalize_id(item_name)
        for key in container:
            if key.lower() == item_name.strip().lower() or normalize_id(key) == wanted:
                return key
        if include_lore_aliases and container is self.state.inventory:
            alias_match = self._find_inventory_item_by_lore_alias(wanted)
            if alias_match is not None:
                return alias_match
        return None

    def _find_inventory_item_by_lore_alias(self, wanted: str) -> str | None:
        if not wanted:
            return None
        matches: list[str] = []
        for key in self.state.inventory:
            lore = self.state.item_lore.get(normalize_id(key)) or {}
            aliases = [
                lore.get("display_name"),
                lore.get("base_item"),
            ]
            if lore.get("identified"):
                descriptor = _clean_item_descriptor(lore.get("descriptor"))
                aliases.extend(
                    [
                        f"identified {lore.get('base_item') or ''}",
                        f"identified {lore.get('display_name') or ''}",
                        f"{descriptor} {lore.get('base_item') or ''}",
                    ]
                )
            alias_ids = {
                normalize_id(str(alias))
                for alias in aliases
                if str(alias or "").strip()
            }
            if wanted in alias_ids:
                matches.append(key)
        return matches[0] if len(matches) == 1 else None

    def consume_inventory_item(
        self, item_name: str, amount: int, container: dict[str, int] | None = None
    ) -> int:
        """Remove up to `amount` of `item_name` from `container` (defaults to the
        player's inventory), auto-deleting the entry once it reaches zero. Works
        identically on `state.inventory` and any `NPCProfile.wares` dict -- both are
        plain item-name -> quantity maps, so trades reuse this without special-casing."""
        target = self.state.inventory if container is None else container
        current = target.get(item_name, 0)
        spent = min(current, max(0, amount))
        remaining = current - spent
        if remaining:
            target[item_name] = remaining
        else:
            target.pop(item_name, None)
            if target is self.state.inventory:
                self.state.player.protected_items.discard(item_name)
        return spent

    def add_inventory_item(
        self, container: dict[str, int], item_name: str, amount: int
    ) -> None:
        """The symmetric counterpart to `consume_inventory_item` -- stacks `amount`
        of `item_name` onto an existing entry (matched fuzzily, so "Gold" and "gold"
        accumulate together) or creates a new one."""
        if amount <= 0:
            return
        existing = self.find_item_in(
            container,
            item_name,
            include_lore_aliases=False,
        )
        key = existing if existing is not None else item_name
        container[key] = container.get(key, 0) + amount

    def _apply_item_use_spec(self, item_name: str, spec: dict[str, Any]) -> bool:
        if "choices" in spec:
            choices = [
                choice
                for choice in coerce_list(spec.get("choices"))
                if isinstance(choice, dict)
            ]
            if choices:
                spec = self.rng.choice(choices)
        context: dict[str, Any] = {"item": item_name.replace("_", " ")}
        target_clause = ""
        any_success = False
        fallback_reason = str(spec.get("failure") or "")
        for effect in coerce_list(spec.get("effects")):
            if not isinstance(effect, dict):
                continue
            success, updates = self._apply_item_effect(effect)
            context.update(updates)
            if "reason" in updates and not fallback_reason:
                fallback_reason = str(updates["reason"])
            if "target" in updates and "amount" in updates and "damage_type" in updates:
                target_clause = f"{updates['target']} takes {updates['amount']} {updates['damage_type']}."
            if not success and effect.get("required"):
                self.state.add_message(str(spec.get("failure") or "Nothing happens."))
                return False
            any_success = any_success or success
        if not any_success:
            self.state.add_message(fallback_reason or "Nothing happens.")
            return False
        context["target_clause"] = (
            target_clause or "No enemy is close enough to be caught in it."
        )
        message = str(spec.get("message") or "You use the {item}.")
        try:
            rendered = message.format(**context)
        except (KeyError, ValueError):
            rendered = message
        self.state.add_message(rendered)
        return True

    def _apply_item_effect(self, effect: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        player = self.state.player
        kind = normalize_id(str(effect.get("kind") or ""))
        amount = self._roll_item_amount(effect)
        if kind == "inert":
            return False, {}
        if kind == "restore_mana":
            gained = min(amount, player.max_mana - player.mana)
            if gained <= 0:
                return False, {"reason": "Your mana is already full."}
            player.mana += gained
            return True, {"amount": gained, "mana": gained}
        if kind == "heal":
            healed = self.heal_entity(player, amount)
            if healed <= 0:
                return False, {"reason": "You are already unhurt."}
            return True, {"amount": healed}
        if kind == "status":
            status = normalize_id(str(effect.get("status") or "marked"))
            player.statuses[status] = max(
                status_duration(player.statuses.get(status)),
                clamp_int(effect.get("duration"), 1, 999),
            )
            return True, {"status": status, "duration": player.statuses[status]}
        if kind == "resistance":
            damage_type = normalize_id(str(effect.get("damage_type") or "physical"))
            player.resistances[damage_type] = clamp_int(
                player.resistances.get(damage_type, 0) + amount, 0, 95
            )
            return True, {"damage_type": damage_type, "amount": amount}
        if kind == "create_tiles":
            tile = str(effect.get("tile") or MIST)
            for tx, ty in self.points_in_radius(
                player.x, player.y, clamp_int(effect.get("radius"), 0, 6)
            ):
                self.set_tile(tx, ty, tile, optional_duration(effect.get("duration")))
            return True, {"tile": tile}
        if kind == "teleport_explored":
            candidates = [
                (x, y)
                for x, y in (
                    (
                        self.rng.randint(0, self.state.width - 1),
                        self.rng.randint(0, self.state.height - 1),
                    )
                    for _ in range(40)
                )
                if self.can_occupy(x, y) and self.is_explored(x, y)
            ]
            if not candidates:
                return False, {}
            x, y = self.rng.choice(candidates)
            self.teleport_entity(player, x, y)
            return True, {"x": x, "y": y}
        if kind in {"damage_nearest", "status_nearest"}:
            target = self.nearest_enemy(
                max_distance=clamp_int(effect.get("range"), 1, 99)
            )
            if not target:
                return False, {}
            if kind == "damage_nearest":
                damage_type = normalize_id(str(effect.get("damage_type") or "physical"))
                actual = self.damage_entity(
                    target, amount, damage_type, source=self.state.player
                )
                return True, {
                    "target": target.name,
                    "amount": actual,
                    "damage_type": damage_type,
                }
            status = normalize_id(str(effect.get("status") or "poisoned"))
            target.statuses[status] = max(
                status_duration(target.statuses.get(status)),
                clamp_int(effect.get("duration"), 1, 999),
            )
            return True, {"target": target.name, "status": status}
        return True, {}

    def _roll_item_amount(self, effect: dict[str, Any]) -> int:
        if "amount_min" in effect or "amount_max" in effect:
            return self.rng.randint(
                clamp_int(effect.get("amount_min"), 0, 99),
                clamp_int(effect.get("amount_max"), 0, 99),
            )
        return clamp_int(effect.get("amount"), 0, 99)

    _EQUIPMENT_SLOT_ALIASES = {
        "weapon": "weapon",
        "wielded": "weapon",
        "hand": "weapon",
        "sword": "weapon",
        "blade": "weapon",
        "armor": "armor",
        "armour": "armor",
        "body": "armor",
        "vest": "armor",
        "shield": "armor",
        "charm": "charm",
        "trinket": "charm",
        "amulet": "charm",
        "ring": "charm",
        "head": "head",
        "hat": "head",
        "helmet": "head",
        "cowl": "head",
        "crown": "head",
        "hood": "head",
        "circlet": "head",
        "cap": "head",
        "mask": "head",
        "helm": "head",
        "chest": "chest",
        "cloak": "chest",
        "robe": "chest",
        "tunic": "chest",
        "shirt": "chest",
        "cape": "chest",
        "legs": "legs",
        "trousers": "legs",
        "pants": "legs",
        "leggings": "legs",
        "breeches": "legs",
        "feet": "feet",
        "boots": "feet",
        "shoes": "feet",
        "hands": "hands",
        "gloves": "hands",
        "gauntlets": "hands",
    }

    def equip_item(self, item_name: str) -> bool:
        if self.state.game_over:
            return False
        matched = self.find_inventory_item(item_name)
        if matched is None or self.state.inventory.get(matched, 0) < 1:
            self.state.add_message(f"You don't have any {item_name.strip().lower()}.")
            return False
        slot = self.equipment_slot_for_inventory_item(matched)
        if not slot:
            self.state.add_message(
                f"The {matched} isn't something you can wear or wield."
            )
            return False
        player = self.state.player
        previous = player.equipment.get(slot)
        self.consume_inventory_item(matched, 1)
        player.equipment[slot] = matched
        if previous:
            self.state.inventory[previous] = self.state.inventory.get(previous, 0) + 1
            self.state.add_message(f"You stow the {previous} and equip the {matched}.")
        else:
            self.state.add_message(f"You equip the {matched}.")
        self.finish_player_turn()
        return True

    def equipment_slot_for_inventory_item(self, item_name: str) -> str | None:
        slot = equipment_slot_for_item(item_name)
        if slot:
            return slot
        lore = self.state.item_lore.get(normalize_id(item_name)) or {}
        if not lore.get("identified"):
            return None
        lore_slot = normalize_id(str(lore.get("equipment_slot") or ""))
        return lore_slot if lore_slot in EQUIPMENT_SLOTS else None

    def unequip_item(self, slot_name: str) -> bool:
        if self.state.game_over:
            return False
        player = self.state.player
        slot = self._EQUIPMENT_SLOT_ALIASES.get(normalize_id(slot_name))
        if slot is None:
            matched = self.find_inventory_item(slot_name) or slot_name
            slot = next(
                (
                    s
                    for s, item in player.equipment.items()
                    if item and normalize_id(item) == normalize_id(matched)
                ),
                None,
            )
        if slot is None:
            slot = next(
                (
                    s
                    for s, item in player.equipment.items()
                    if item and normalize_id(slot_name) in normalize_id(item)
                ),
                None,
            )
        if slot is None or slot not in player.equipment:
            self.state.add_message("That isn't something you have equipped.")
            return False
        current = player.equipment.get(slot)
        if not current:
            self.state.add_message(f"You have nothing equipped in your {slot} slot.")
            return False
        player.equipment[slot] = None
        self.state.inventory[current] = self.state.inventory.get(current, 0) + 1
        self.state.add_message(f"You unequip the {current}.")
        self.finish_player_turn()
        return True

    def _equipped_slot_by_item(self, name: str) -> str | None:
        """Find the equipment slot holding an item matching `name` (exact normalized first,
        then a substring fall-back), or None. Mirrors how unequip resolves an item to a slot."""
        player = self.state.player
        wanted = normalize_id(name)
        if not wanted:
            return None
        for slot, item in player.equipment.items():
            if item and normalize_id(item) == wanted:
                return slot
        for slot, item in player.equipment.items():
            if item and wanted in normalize_id(item):
                return slot
        return None

    def set_focus(self, target: str) -> bool:
        """Mark an already-equipped item as the spell focus. `target` may name a slot
        (via the slot aliases) or an equipped item. A focus is a mark on existing gear, so
        nothing is equipped/unequipped here. v1 carries a single focus, so a new mark replaces
        the old; `Entity.focus_slots` is a list to leave multi-focus a later policy change."""
        if self.state.game_over:
            return False
        player = self.state.player
        arg = (target or "").strip()
        if not arg:
            self.state.add_message("Focus through what? Name an equipped item or slot.")
            return False
        alias = self._EQUIPMENT_SLOT_ALIASES.get(normalize_id(arg))
        slot = alias if alias is not None else self._equipped_slot_by_item(arg)
        if slot is None:
            self.state.add_message(
                f"You aren't wearing or wielding any '{arg}' to channel through."
            )
            return False
        item = player.equipment.get(slot)
        if not item:
            self.state.add_message(
                f"You have nothing equipped in your {slot} slot to channel through."
            )
            return False
        if player.focus_slots == [slot]:
            self.state.add_message(f"The {item} is already your spell focus.")
            return False
        player.focus_slots = [slot]
        self.state.add_message(f"You attune to the {item} as your spell focus.")
        self.finish_player_turn()
        return True

    def clear_focus(self, target: str | None = None) -> bool:
        """Release a spell focus. With no target, release whatever is marked; with a target,
        release only that slot/item if it is currently the focus."""
        if self.state.game_over:
            return False
        player = self.state.player
        if not player.focus_slots:
            self.state.add_message("You have no spell focus to release.")
            return False
        arg = (target or "").strip()
        if arg:
            alias = self._EQUIPMENT_SLOT_ALIASES.get(normalize_id(arg))
            slot = alias if alias is not None else self._equipped_slot_by_item(arg)
            if slot is None or slot not in player.focus_slots:
                self.state.add_message(f"'{arg}' is not your spell focus.")
                return False
            player.focus_slots = [s for s in player.focus_slots if s != slot]
        else:
            player.focus_slots = []
        self.state.add_message("You let your spell focus go quiet.")
        self.finish_player_turn()
        return True

    def pick_up_items_at_player(self) -> bool:
        player = self.state.player
        picked_up = False
        for entity in list(self.entities_at(player.x, player.y)):
            if entity.kind != "item":
                continue
            item_type = entity.item_type or entity.name
            inventory_key = self.find_inventory_item(item_type) or item_type
            self.add_inventory_item(self.state.inventory, item_type, entity.quantity)
            metadata = dict(entity.details.get("item_metadata") or {})
            # Preserve the item's flavor before the Entity (and its description) is gone, so a
            # picked-up item can still be a meaningful spell focus. Keyed by the inventory key;
            # a prior Investigate description outranks this and is kept (see set_item_lore).
            if entity.description or metadata:
                self.set_item_lore(
                    inventory_key,
                    entity.name,
                    entity.description or metadata.get("description", ""),
                    source="description",
                    metadata=metadata,
                )
            self.state.add_message(f"You pick up {entity.name}.")
            self.state.stats.items_collected += 1
            del self.state.entities[entity.id]
            picked_up = True
        return picked_up


def _clean_item_name(value: object) -> str:
    cleaned = " ".join(str(value or "identified item").replace("_", " ").split())
    return cleaned[:80] or "identified item"


def _clean_item_descriptor(value: object) -> str:
    cleaned = " ".join(str(value or "").replace("_", " ").split()).lower()
    cleaned = "".join(
        char for char in cleaned if char.isascii() and (char.isalnum() or char in " -'")
    )
    return cleaned.strip(" -'")[:28]


def _name_has_prefix(name: str, prefix: str) -> bool:
    prefix_id = normalize_id(prefix)
    name_id = normalize_id(name)
    return bool(prefix_id) and (
        name_id == prefix_id or name_id.startswith(f"{prefix_id}_")
    )


def _clean_message_text(value: object, *, limit: int = 240) -> str:
    cleaned = " ".join(str(value or "").split())
    if len(cleaned) > limit:
        cleaned = cleaned[:limit].rsplit(" ", 1)[0] or cleaned[:limit]
    return cleaned


def _item_ability_summary(resolution: dict[str, Any]) -> str:
    if resolution.get("ability_kind") == "slot_passive":
        slot = normalize_id(str(resolution.get("equipment_slot") or "charm"))
        spec = resolution.get("equipment_spec")
        bonuses: list[str] = []
        if isinstance(spec, dict):
            try:
                attack = int(spec.get("attack") or 0)
            except (TypeError, ValueError):
                attack = 0
            try:
                defense = int(spec.get("defense") or 0)
            except (TypeError, ValueError):
                defense = 0
            if attack:
                bonuses.append(f"+{attack} attack")
            if defense:
                bonuses.append(f"+{defense} defense")
        bonus_text = " and ".join(bonuses) or "a small bonus"
        return f"Equip it in your {slot} slot for {bonus_text}."

    use_spec = resolution.get("use_spec")
    if not isinstance(use_spec, dict):
        return "Use it to release a small stored magic."
    effect = next(
        (
            effect
            for effect in coerce_list(use_spec.get("effects"))
            if isinstance(effect, dict)
        ),
        {},
    )
    kind = normalize_id(str(effect.get("kind") or ""))
    if kind == "restore_mana":
        return "Use it to restore mana."
    if kind == "heal":
        return "Use it to heal wounds."
    if kind == "status":
        status = str(effect.get("status") or "marked").replace("_", " ")
        return f"Use it to give yourself {status}."
    if kind == "resistance":
        damage_type = str(effect.get("damage_type") or "damage").replace("_", " ")
        return f"Use it to gain {damage_type} resistance."
    if kind == "create_tiles":
        return "Use it to spill temporary terrain nearby."
    if kind == "teleport_explored":
        return "Use it to blink to a random explored place."
    if kind == "damage_nearest":
        return "Use it to strike the nearest enemy in range."
    if kind == "status_nearest":
        status = str(effect.get("status") or "marked").replace("_", " ")
        return f"Use it to make the nearest enemy {status}."
    return "Use it to release a small stored magic."
