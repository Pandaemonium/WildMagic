from __future__ import annotations

from typing import Any

from .game_data import DEFAULT_ITEM_USE_SPEC, EQUIPMENT_SPECS, ITEM_USE_SPECS
from .models import MIST, Entity
from .normalize import clamp_int, coerce_list, normalize_id, optional_duration, status_duration


def infer_equipment_slot(item_name: str) -> str | None:
    name_lower = item_name.strip().lower()
    
    # Substring weapon checks
    weapon_subs = ["sword", "blade", "dagger", "axe", "pick", "bow", "staff", "mace", "hammer", "whip", "spear", "rapier", "scythe", "club", "wand"]
    if any(sub in name_lower for sub in weapon_subs):
        return "weapon"
        
    # Substring head checks
    head_subs = ["hat", "helmet", "cowl", "crown", "hood", "circlet", "mask", "visor", "helm", "coif"]
    if any(sub in name_lower for sub in head_subs) or "cap" in name_lower.split():
        return "head"
        
    # Substring feet checks
    feet_subs = ["boot", "shoe", "slipper", "sabaton", "footwear"]
    if any(sub in name_lower for sub in feet_subs):
        return "feet"
        
    # Substring legs checks
    legs_subs = ["trouser", "pant", "legging", "breeches", "greaves", "cuisses", "skirt", "kilt", "hosen"]
    if any(sub in name_lower for sub in legs_subs):
        return "legs"
        
    # Substring hands checks
    hands_subs = ["glove", "gauntlet", "mitt", "bracer"]
    if any(sub in name_lower for sub in hands_subs):
        return "hands"
        
    # Substring chest checks
    chest_subs = ["cloak", "robe", "tunic", "shirt", "coat", "jacket", "cape", "shroud", "doublet", "jerkin"]
    if any(sub in name_lower for sub in chest_subs):
        return "chest"
        
    # Substring charm checks
    charm_subs = ["charm", "trinket", "amulet", "ring", "talisman", "necklace", "locket", "pendant"]
    if any(sub in name_lower for sub in charm_subs):
        return "charm"
        
    # Substring armor checks
    armor_subs = ["shield", "buckler", "armor", "armour", "cuirass", "breastplate", "vest", "mail"]
    if any(sub in name_lower for sub in armor_subs):
        return "armor"
        
    return None


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
        return entity

    def use_item(self, item_name: str) -> bool:
        if self.state.game_over:
            return False
        matched = self.find_inventory_item(item_name)
        if matched is None or self.state.inventory.get(matched, 0) < 1:
            self.state.add_message(f"You don't have any {item_name.strip().lower()}.")
            return False
        spec = ITEM_USE_SPECS.get(normalize_id(matched), DEFAULT_ITEM_USE_SPEC)
        consumed = self._apply_item_use_spec(matched, spec)
        if consumed:
            self.consume_inventory_item(matched, 1)
            self.state.stats.items_used += 1
            self.finish_player_turn()
        return consumed

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

    def find_inventory_item(self, item_name: str) -> str | None:
        return self.find_item_in(self.state.inventory, item_name)

    def find_item_in(self, container: dict[str, int], item_name: str) -> str | None:
        """Fuzzy name lookup against any item-quantity dict (player inventory, NPC
        wares, ...) -- the same dict shape, so the same matching rules apply."""
        wanted = normalize_id(item_name)
        for key in container:
            if key.lower() == item_name.strip().lower() or normalize_id(key) == wanted:
                return key
        return None

    def consume_inventory_item(self, item_name: str, amount: int, container: dict[str, int] | None = None) -> int:
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
        return spent

    def add_inventory_item(self, container: dict[str, int], item_name: str, amount: int) -> None:
        """The symmetric counterpart to `consume_inventory_item` -- stacks `amount`
        of `item_name` onto an existing entry (matched fuzzily, so "Gold" and "gold"
        accumulate together) or creates a new one."""
        if amount <= 0:
            return
        existing = self.find_item_in(container, item_name)
        key = existing if existing is not None else item_name
        container[key] = container.get(key, 0) + amount

    def _apply_item_use_spec(self, item_name: str, spec: dict[str, Any]) -> bool:
        if "choices" in spec:
            choices = [choice for choice in coerce_list(spec.get("choices")) if isinstance(choice, dict)]
            if choices:
                spec = self.rng.choice(choices)
        context: dict[str, Any] = {"item": item_name.replace("_", " ")}
        target_clause = ""
        for effect in coerce_list(spec.get("effects")):
            if not isinstance(effect, dict):
                continue
            success, updates = self._apply_item_effect(effect)
            context.update(updates)
            if "target" in updates and "amount" in updates and "damage_type" in updates:
                target_clause = f"{updates['target']} takes {updates['amount']} {updates['damage_type']}."
            if not success and effect.get("required"):
                self.state.add_message(str(spec.get("failure") or "Nothing happens."))
                return False
        context["target_clause"] = target_clause or "No enemy is close enough to be caught in it."
        self.state.add_message(str(spec.get("message") or "You use the {item}.").format(**context))
        return True

    def _apply_item_effect(self, effect: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        player = self.state.player
        kind = normalize_id(str(effect.get("kind") or ""))
        amount = self._roll_item_amount(effect)
        if kind == "inert":
            return False, {}
        if kind == "restore_mana":
            gained = min(amount, player.max_mana - player.mana)
            player.mana += gained
            return True, {"amount": gained, "mana": gained}
        if kind == "heal":
            healed = self.heal_entity(player, amount)
            return True, {"amount": healed}
        if kind == "status":
            status = normalize_id(str(effect.get("status") or "marked"))
            player.statuses[status] = max(status_duration(player.statuses.get(status)), clamp_int(effect.get("duration"), 1, 999))
            return True, {"status": status, "duration": player.statuses[status]}
        if kind == "resistance":
            damage_type = normalize_id(str(effect.get("damage_type") or "physical"))
            player.resistances[damage_type] = clamp_int(player.resistances.get(damage_type, 0) + amount, 0, 95)
            return True, {"damage_type": damage_type, "amount": amount}
        if kind == "create_tiles":
            tile = str(effect.get("tile") or MIST)
            for tx, ty in self.points_in_radius(player.x, player.y, clamp_int(effect.get("radius"), 0, 6)):
                self.set_tile(tx, ty, tile, optional_duration(effect.get("duration")))
            return True, {"tile": tile}
        if kind == "teleport_explored":
            candidates = [
                (x, y)
                for x, y in (
                    (self.rng.randint(0, self.state.width - 1), self.rng.randint(0, self.state.height - 1))
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
            target = self.nearest_enemy(max_distance=clamp_int(effect.get("range"), 1, 99))
            if not target:
                return False, {}
            if kind == "damage_nearest":
                damage_type = normalize_id(str(effect.get("damage_type") or "physical"))
                actual = self.damage_entity(target, amount, damage_type)
                return True, {"target": target.name, "amount": actual, "damage_type": damage_type}
            status = normalize_id(str(effect.get("status") or "poisoned"))
            target.statuses[status] = max(status_duration(target.statuses.get(status)), clamp_int(effect.get("duration"), 1, 999))
            return True, {"target": target.name, "status": status}
        return True, {}

    def _roll_item_amount(self, effect: dict[str, Any]) -> int:
        if "amount_min" in effect or "amount_max" in effect:
            return self.rng.randint(clamp_int(effect.get("amount_min"), 0, 99), clamp_int(effect.get("amount_max"), 0, 99))
        return clamp_int(effect.get("amount"), 0, 99)

    _EQUIPMENT_SLOT_ALIASES = {
        "weapon": "weapon", "wielded": "weapon", "hand": "weapon", "sword": "weapon", "blade": "weapon",
        "armor": "armor", "armour": "armor", "body": "armor", "vest": "armor", "shield": "armor",
        "charm": "charm", "trinket": "charm", "amulet": "charm", "ring": "charm",
        "head": "head", "hat": "head", "helmet": "head", "cowl": "head", "crown": "head", "hood": "head", "circlet": "head", "cap": "head", "mask": "head", "helm": "head",
        "chest": "chest", "cloak": "chest", "robe": "chest", "tunic": "chest", "shirt": "chest", "cape": "chest",
        "legs": "legs", "trousers": "legs", "pants": "legs", "leggings": "legs", "breeches": "legs",
        "feet": "feet", "boots": "feet", "shoes": "feet",
        "hands": "hands", "gloves": "hands", "gauntlets": "hands",
    }


    def equip_item(self, item_name: str) -> bool:
        if self.state.game_over:
            return False
        matched = self.find_inventory_item(item_name)
        if matched is None or self.state.inventory.get(matched, 0) < 1:
            self.state.add_message(f"You don't have any {item_name.strip().lower()}.")
            return False
        spec = EQUIPMENT_SPECS.get(matched.strip().lower())
        if spec:
            slot = str(spec["slot"])
        else:
            slot = infer_equipment_slot(matched)
            if not slot:
                self.state.add_message(f"The {matched} isn't something you can wear or wield.")
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

    def unequip_item(self, slot_name: str) -> bool:
        if self.state.game_over:
            return False
        player = self.state.player
        slot = self._EQUIPMENT_SLOT_ALIASES.get(normalize_id(slot_name))
        if slot is None:
            matched = self.find_inventory_item(slot_name) or slot_name
            slot = next((s for s, item in player.equipment.items() if item and normalize_id(item) == normalize_id(matched)), None)
        if slot is None:
            slot = next((s for s, item in player.equipment.items() if item and normalize_id(slot_name) in normalize_id(item)), None)
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

    def pick_up_items_at_player(self) -> None:
        player = self.state.player
        for entity in list(self.entities_at(player.x, player.y)):
            if entity.kind != "item":
                continue
            item_type = entity.item_type or entity.name
            self.state.inventory[item_type] = self.state.inventory.get(item_type, 0) + entity.quantity
            self.state.add_message(f"You pick up {entity.name}.")
            self.state.stats.items_collected += 1
            del self.state.entities[entity.id]

