from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping

from .item_palettes import palette_label
from .normalize import normalize_id


@dataclass(frozen=True)
class SpellBias:
    """Lightweight spell-color metadata for an item used as a reagent."""

    damage_types: Mapping[str, int] = field(default_factory=dict)
    preferred_effects: tuple[str, ...] = ()
    side_effect_hints: tuple[str, ...] = ()
    affinity_tags: frozenset[str] = frozenset()

    def to_dict(self) -> dict[str, Any]:
        return {
            **({"damage_types": dict(self.damage_types)} if self.damage_types else {}),
            **(
                {"preferred_effects": list(self.preferred_effects)}
                if self.preferred_effects
                else {}
            ),
            **(
                {"side_effect_hints": list(self.side_effect_hints)}
                if self.side_effect_hints
                else {}
            ),
            **(
                {"affinity_tags": sorted(self.affinity_tags)}
                if self.affinity_tags
                else {}
            ),
        }


@dataclass(frozen=True)
class ItemDefinition:
    """Authoritative per-item metadata used by inventory views and spell reagents.

    Inventory is still fungible by name, so this catalog describes a stack key rather than
    a unique instance. Unknown generated curios fall through to an inferred definition.
    """

    id: str
    name: str
    char: str = "?"
    kind: str = "reagent"
    material: str = ""
    tags: frozenset[str] = frozenset()
    value: int = 1
    rarity: str = "common"
    use_profile: str = "inert"
    spell_bias: SpellBias | None = None

    def to_reagent_card(
        self,
        *,
        quantity: int,
        protected: bool = False,
        lore: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        card: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "quantity": int(quantity),
            "value": self.value,
            "total_value": self.value * max(0, int(quantity)),
            "kind": self.kind,
            "material": self.material,
            "tags": sorted(self.tags),
            "rarity": self.rarity,
            "use_profile": self.use_profile,
            "protected": bool(protected),
            "spendable": not protected,
        }
        if self.spell_bias is not None:
            card["spell_bias"] = self.spell_bias.to_dict()
        if lore:
            display_name = str(lore.get("display_name") or "").strip()
            description = str(lore.get("description") or "").strip()
            if display_name:
                card["display_name"] = display_name
            if description:
                card["description"] = description
        return card


def _tags(*values: str) -> frozenset[str]:
    return frozenset(normalize_id(value) for value in values if value)


def _bias(
    *,
    damage_types: Mapping[str, int] | None = None,
    effects: tuple[str, ...] = (),
    hints: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
) -> SpellBias:
    return SpellBias(
        damage_types={normalize_id(k): int(v) for k, v in (damage_types or {}).items()},
        preferred_effects=tuple(normalize_id(effect) for effect in effects),
        side_effect_hints=tuple(hints),
        affinity_tags=_tags(*tags),
    )


def _item(
    name: str,
    *,
    value: int,
    material: str = "",
    tags: tuple[str, ...] = (),
    kind: str = "reagent",
    rarity: str = "common",
    char: str = "?",
    use_profile: str = "inert",
    spell_bias: SpellBias | None = None,
) -> ItemDefinition:
    return ItemDefinition(
        id=normalize_id(name),
        name=name,
        char=char,
        kind=kind,
        material=material,
        tags=_tags(material, *tags),
        value=max(1, int(value)),
        rarity=rarity,
        use_profile=use_profile,
        spell_bias=spell_bias,
    )


ITEM_DEFINITIONS: dict[str, ItemDefinition] = {
    # Starter reagents and common consumables.
    "gold": _item(
        "gold",
        value=1,
        material="gold",
        tags=("coin", "currency", "valuable", "generic"),
        kind="currency",
        char="$",
        spell_bias=_bias(
            hints=("payment", "greed", "lawful exchange"), tags=("generic",)
        ),
    ),
    "chalk": _item(
        "chalk",
        value=2,
        material="chalk",
        tags=("mark", "circle", "ward", "ritual"),
        spell_bias=_bias(
            effects=("create_tiles", "create_trigger"), hints=("circles", "symbols")
        ),
    ),
    "grave salt": _item(
        "grave salt",
        value=4,
        material="salt",
        tags=("grave", "death", "ward", "binding", "purifying"),
        spell_bias=_bias(
            damage_types={"necrotic": 1},
            effects=("add_status", "curse"),
            hints=("white chains", "funeral stillness"),
            tags=("death", "binding"),
        ),
    ),
    "mana crystal": _item(
        "mana crystal",
        value=8,
        material="crystal",
        tags=("mana", "arcane", "volatile"),
        use_profile="restore_mana",
        spell_bias=_bias(
            damage_types={"arcane": 2},
            effects=("restore_mana", "add_resistance"),
            hints=("stored light", "crystal resonance"),
            tags=("arcane", "crystal"),
        ),
    ),
    "blood moss": _item(
        "blood moss",
        value=5,
        material="moss",
        tags=("blood", "plant", "healing", "wet"),
        use_profile="heal",
        spell_bias=_bias(
            effects=("heal", "add_status"),
            hints=("red growth", "regrowth"),
            tags=("healing", "blood"),
        ),
    ),
    "bone shard": _item(
        "bone shard",
        value=3,
        material="bone",
        tags=("death", "sharp", "body"),
        use_profile="damage_nearest",
        spell_bias=_bias(
            damage_types={"physical": 1, "necrotic": 1},
            effects=("damage", "summon"),
            hints=("clicking bone", "old marrow"),
            tags=("bone", "death"),
        ),
    ),
    "viscous residue": _item(
        "viscous residue",
        value=3,
        material="slime",
        tags=("sticky", "poison", "ooze"),
        use_profile="status_nearest",
        spell_bias=_bias(
            damage_types={"poison": 2},
            effects=("add_status", "create_tiles"),
            hints=("clinging slime", "sour fumes"),
            tags=("poison", "sticky"),
        ),
    ),
    "metal scrap": _item(
        "metal scrap",
        value=2,
        material="metal",
        tags=("iron", "conductive", "sharp"),
        use_profile="damage_nearest",
        spell_bias=_bias(
            damage_types={"physical": 1, "lightning": 1},
            hints=("sparks", "magnetism"),
            tags=("metal", "conductive"),
        ),
    ),
    "arcane residue": _item(
        "arcane residue",
        value=6,
        material="residue",
        tags=("arcane", "volatile", "spark"),
        use_profile="restore_mana",
        spell_bias=_bias(
            damage_types={"arcane": 2},
            effects=("restore_mana", "damage"),
            hints=("wild sparks", "afterimage"),
            tags=("arcane", "volatile"),
        ),
    ),
    "healing potion": _item(
        "healing potion",
        value=25,
        material="liquid",
        tags=("healing", "bottle", "red"),
        kind="consumable",
        use_profile="heal",
    ),
    "mana potion": _item(
        "mana potion",
        value=25,
        material="liquid",
        tags=("mana", "bottle", "blue"),
        kind="consumable",
        use_profile="restore_mana",
    ),
    "smoke vial": _item(
        "smoke vial",
        value=15,
        material="glass",
        tags=("smoke", "mist", "bottle"),
        kind="consumable",
        use_profile="create_tiles",
        spell_bias=_bias(
            effects=("create_tiles",), hints=("smoke", "concealment"), tags=("mist",)
        ),
    ),
    "blink scroll": _item(
        "blink scroll",
        value=40,
        material="paper",
        tags=("scroll", "travel", "space"),
        kind="consumable",
        rarity="uncommon",
        use_profile="teleport_explored",
        spell_bias=_bias(
            effects=("teleport", "push", "pull"),
            hints=("folded distance",),
            tags=("travel",),
        ),
    ),
    "beast claw": _item(
        "beast claw",
        value=8,
        material="claw",
        tags=("beast", "sharp", "hunt"),
        kind="consumable",
        use_profile="status",
    ),
    "bone charm": _item(
        "bone charm",
        value=30,
        material="bone",
        tags=("ward", "death", "charm"),
        kind="charm",
        rarity="uncommon",
        use_profile="ward",
    ),
    "stolen coin": _item(
        "stolen coin",
        value=10,
        material="gold",
        tags=("coin", "luck", "theft", "debt"),
        rarity="uncommon",
        use_profile="random",
        spell_bias=_bias(hints=("luck", "debt", "stolen shine"), tags=("luck", "debt")),
    ),
    # Keys and lock goods.
    "brass key": _item("brass key", value=10, material="brass", tags=("key", "lock")),
    "bone key": _item(
        "bone key", value=12, material="bone", tags=("key", "lock", "death")
    ),
    "rusted key": _item(
        "rusted key", value=8, material="iron", tags=("key", "lock", "rust")
    ),
    "engraved key": _item(
        "engraved key",
        value=18,
        material="metal",
        tags=("key", "lock", "engraved"),
        rarity="uncommon",
    ),
    # Equipment and curated foci.
    "tattered cloak": _item(
        "tattered cloak",
        value=1,
        material="cloth",
        tags=("clothing",),
        kind="equipment",
    ),
    "woolen trousers": _item(
        "woolen trousers",
        value=1,
        material="wool",
        tags=("clothing",),
        kind="equipment",
    ),
    "rusty sword": _item(
        "rusty sword",
        value=15,
        material="iron",
        tags=("weapon", "rust"),
        kind="equipment",
    ),
    "iron sword": _item(
        "iron sword",
        value=40,
        material="iron",
        tags=("weapon", "blade"),
        kind="equipment",
    ),
    "war pick": _item(
        "war pick",
        value=50,
        material="iron",
        tags=("weapon", "piercing"),
        kind="equipment",
    ),
    "hunting bow": _item(
        "hunting bow",
        value=35,
        material="wood",
        tags=("weapon", "hunt"),
        kind="equipment",
    ),
    "leather vest": _item(
        "leather vest", value=25, material="leather", tags=("armor",), kind="equipment"
    ),
    "iron breastplate": _item(
        "iron breastplate",
        value=60,
        material="iron",
        tags=("armor",),
        kind="equipment",
        rarity="uncommon",
    ),
    "wooden buckler": _item(
        "wooden buckler",
        value=20,
        material="wood",
        tags=("shield", "armor"),
        kind="equipment",
    ),
    "lucky coin charm": _item(
        "lucky coin charm",
        value=35,
        material="gold",
        tags=("charm", "luck", "coin"),
        kind="equipment",
        spell_bias=_bias(hints=("lucky glint", "coin-toss omen"), tags=("luck",)),
    ),
    "warding locket": _item(
        "warding locket",
        value=45,
        material="silver",
        tags=("charm", "ward", "memory"),
        kind="equipment",
    ),
    "wizards hat": _item(
        "wizards hat",
        value=20,
        material="cloth",
        tags=("hat", "arcane"),
        kind="equipment",
    ),
    "gilded crown": _item(
        "gilded crown",
        value=120,
        material="gold",
        tags=("crown", "authority", "valuable"),
        kind="equipment",
        rarity="rare",
    ),
    "silk robe": _item(
        "silk robe",
        value=55,
        material="silk",
        tags=("robe", "clothing", "luxury"),
        kind="equipment",
    ),
    "leather boots": _item(
        "leather boots",
        value=18,
        material="leather",
        tags=("boots", "travel"),
        kind="equipment",
    ),
    "leather gloves": _item(
        "leather gloves",
        value=8,
        material="leather",
        tags=("gloves",),
        kind="equipment",
    ),
    "whispering orb": _item(
        "whispering orb",
        value=90,
        material="glass",
        tags=("voices", "secrets", "mind", "divination"),
        kind="equipment",
        rarity="rare",
        spell_bias=_bias(
            effects=("reveal", "add_trait", "modify_memory"),
            hints=("whispers", "borrowed voices"),
            tags=("secrets", "mind"),
        ),
    ),
    "emberglass wand": _item(
        "emberglass wand",
        value=100,
        material="glass",
        tags=("fire", "light", "ruin", "focus"),
        kind="equipment",
        rarity="rare",
        spell_bias=_bias(
            damage_types={"fire": 2},
            effects=("damage", "create_tiles"),
            hints=("emberglass heat", "smouldering light"),
            tags=("fire", "light"),
        ),
    ),
    "saint's knucklebone": _item(
        "saint's knucklebone",
        value=80,
        material="bone",
        tags=("death", "mercy", "oath", "relic"),
        kind="equipment",
        rarity="rare",
        spell_bias=_bias(
            hints=("old prayers", "merciful bone"), tags=("death", "mercy")
        ),
    ),
    # Regional goods and foci.
    "charged stalnaz crystal": _item(
        "charged stalnaz crystal",
        value=70,
        material="crystal",
        tags=("charged", "song", "mana"),
        kind="equipment",
        rarity="rare",
    ),
    "brall scrimshaw charm": _item(
        "brall scrimshaw charm",
        value=45,
        material="bone",
        tags=("scrimshaw", "boast", "charm"),
        kind="equipment",
    ),
    "ryolan dueling sash": _item(
        "ryolan dueling sash",
        value=50,
        material="silk",
        tags=("duel", "honor", "blood"),
        kind="equipment",
    ),
    "vint woven charm": _item(
        "vint woven charm",
        value=45,
        material="thread",
        tags=("woven", "rumor", "charm"),
        kind="equipment",
    ),
    "threen canal locket": _item(
        "threen canal locket",
        value=55,
        material="silver",
        tags=("canal", "memory", "water"),
        kind="equipment",
    ),
    "monteary horsehair bow": _item(
        "monteary horsehair bow",
        value=65,
        material="wood",
        tags=("horsehair", "bow", "hunt"),
        kind="equipment",
    ),
    "ontrian culture gourd": _item(
        "ontrian culture gourd",
        value=35,
        material="gourd",
        tags=("culture", "seed", "charm"),
        kind="equipment",
    ),
    "gontark curse-knot": _item(
        "gontark curse-knot",
        value=55,
        material="thread",
        tags=("curse", "knot", "charm"),
        kind="equipment",
    ),
    "parn song-ink scarf": _item(
        "parn song-ink scarf",
        value=50,
        material="silk",
        tags=("song", "ink", "scarf"),
        kind="equipment",
    ),
    "birdfolk plume charm": _item(
        "birdfolk plume charm",
        value=45,
        material="feather",
        tags=("birdfolk", "air", "charm"),
        kind="equipment",
    ),
    "merfolk tide pearl": _item(
        "merfolk tide pearl",
        value=100,
        material="pearl",
        tags=("water", "moon", "tide", "beauty"),
        kind="equipment",
        rarity="rare",
    ),
    "rentacostan salt coin": _item(
        "rentacostan salt coin",
        value=60,
        material="salt",
        tags=("coin", "debt", "salt", "trade"),
        kind="equipment",
        rarity="uncommon",
    ),
}

ITEM_DEFINITIONS = {
    normalize_id(definition.name): definition
    for definition in ITEM_DEFINITIONS.values()
}


MATERIAL_TAGS: tuple[tuple[str, tuple[str, ...], int], ...] = (
    ("pearl", ("water", "moon", "beauty", "valuable"), 60),
    ("crystal", ("crystal", "arcane", "fragile"), 35),
    ("glass", ("glass", "fragile", "light"), 18),
    ("gold", ("gold", "valuable", "currency"), 25),
    ("silver", ("silver", "moon", "ward"), 20),
    ("salt", ("salt", "dry", "ward"), 4),
    ("sand", ("sand", "dry", "desert"), 2),
    ("bone", ("bone", "death", "body"), 5),
    ("blood", ("blood", "body", "life"), 6),
    ("moss", ("plant", "wet", "healing"), 4),
    ("iron", ("iron", "metal", "conductive"), 10),
    ("metal", ("metal", "conductive"), 8),
    ("brass", ("brass", "metal", "bell"), 8),
    ("wood", ("wood", "plant"), 4),
    ("leather", ("leather", "hide"), 5),
    ("silk", ("silk", "thread", "luxury"), 12),
    ("thread", ("thread", "woven"), 3),
    ("paper", ("paper", "writing"), 2),
    ("ink", ("ink", "writing"), 3),
    ("wax", ("wax", "seal"), 3),
    ("feather", ("feather", "air"), 3),
)

FORM_TAGS: tuple[tuple[str, tuple[str, ...], int], ...] = (
    ("crown", ("authority", "royal"), 80),
    ("orb", ("sphere", "divination"), 60),
    ("ball", ("sphere", "divination"), 40),
    ("pearl", ("gem",), 50),
    ("gem", ("gem", "valuable"), 50),
    ("locket", ("memory", "charm"), 35),
    ("charm", ("charm",), 25),
    ("wand", ("focus", "arcane"), 60),
    ("sword", ("weapon", "blade"), 35),
    ("bow", ("weapon", "hunt"), 30),
    ("armor", ("armor",), 35),
    ("breastplate", ("armor",), 45),
    ("robe", ("clothing",), 25),
    ("cloak", ("clothing",), 15),
    ("scroll", ("scroll", "writing"), 25),
    ("potion", ("potion", "bottle"), 20),
    ("vial", ("bottle",), 12),
    ("key", ("key", "lock"), 8),
    ("coin", ("coin", "trade"), 1),
    ("seal", ("law", "authority"), 20),
    ("ledger", ("law", "debt", "writing"), 35),
    ("contract", ("law", "debt", "writing"), 30),
    ("relic", ("relic", "holy"), 60),
    ("bone", ("bone",), 4),
    ("shard", ("sharp", "fragment"), 3),
    ("sand", ("grain",), 1),
    ("salt", ("grain",), 2),
)


def inferred_item_definition(name: str) -> ItemDefinition:
    """Build a stable metadata card for arbitrary semantic items.

    This is intentionally heuristic rather than authoritative economy math. It gives
    generated curios enough value and spell color to participate until a durable generated
    item definition store exists.
    """

    clean_name = str(name or "curio").strip() or "curio"
    key = normalize_id(clean_name)
    words = key.split("_")
    tags: set[str] = {"curio"}
    material = ""
    value = 1

    for word, material_tags, material_value in MATERIAL_TAGS:
        if word in words or word in key:
            material = word
            tags.update(material_tags)
            value = max(value, material_value)
            break

    for word, form_tags, form_value in FORM_TAGS:
        if word in words or word in key:
            tags.update(form_tags)
            value += form_value
            break

    if not material:
        material = words[0].replace("_", " ") if words else "unknown"

    if {"valuable", "gem", "relic"} & tags:
        rarity = "rare" if value >= 80 else "uncommon"
    elif value >= 45:
        rarity = "uncommon"
    else:
        rarity = "common"

    bias = _bias(
        damage_types=_damage_bias_for_tags(tags),
        effects=_effect_bias_for_tags(tags),
        hints=tuple(sorted(_hints_for_tags(tags)))[:4],
        tags=tuple(sorted(tags)),
    )
    return ItemDefinition(
        id=key,
        name=clean_name,
        material=material,
        tags=frozenset(sorted(tags)),
        value=max(1, value),
        rarity=rarity,
        spell_bias=bias,
    )


def _damage_bias_for_tags(tags: set[str]) -> dict[str, int]:
    damage: dict[str, int] = {}
    if tags & {"fire", "ember", "sun"}:
        damage["fire"] = 2
    if tags & {"water", "tide", "moon"}:
        damage["frost"] = 1
    if tags & {"poison", "ooze"}:
        damage["poison"] = 2
    if tags & {"bone", "death", "relic"}:
        damage["necrotic"] = 1
    if tags & {"iron", "metal", "conductive", "brass"}:
        damage["lightning"] = 1
    return damage


def _effect_bias_for_tags(tags: set[str]) -> tuple[str, ...]:
    effects: list[str] = []
    if tags & {"ward", "lock", "key", "seal"}:
        effects.append("add_status")
    if tags & {"divination", "sphere", "moon", "memory"}:
        effects.append("reveal")
    if tags & {"debt", "law", "contract", "ledger"}:
        effects.append("curse")
    if tags & {"plant", "healing", "life"}:
        effects.append("heal")
    if tags & {"dry", "sand", "salt"}:
        effects.append("create_tiles")
    return tuple(effects)


def _hints_for_tags(tags: set[str]) -> set[str]:
    hints: set[str] = set()
    if "water" in tags or "tide" in tags:
        hints.add("mist and tides")
    if "moon" in tags:
        hints.add("moonlit afterimages")
    if "death" in tags or "bone" in tags:
        hints.add("old bones")
    if "debt" in tags or "law" in tags:
        hints.add("debts coming due")
    if "sand" in tags or "dry" in tags:
        hints.add("dry heat and glass grit")
    if "divination" in tags:
        hints.add("omens")
    if "coin" in tags or "gold" in tags:
        hints.add("paid power")
    return hints


def item_definition(name: str) -> ItemDefinition:
    return ITEM_DEFINITIONS.get(normalize_id(name)) or inferred_item_definition(name)


def item_value(name: str) -> int:
    return item_definition(name).value


def item_tags(name: str) -> frozenset[str]:
    return item_definition(name).tags


def reagent_card(
    name: str,
    quantity: int,
    *,
    protected: bool = False,
    lore: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    definition = item_definition(name)
    if definition.name != name:
        definition = replace(definition, name=name, id=normalize_id(name))
    card = definition.to_reagent_card(
        quantity=quantity,
        protected=protected,
        lore=lore,
    )
    if lore:
        if lore.get("value") is not None:
            try:
                card["value"] = max(1, int(lore["value"]))
            except (TypeError, ValueError):
                pass
        if lore.get("material"):
            card["material"] = str(lore["material"])
        lore_tags = {
            normalize_id(str(tag)) for tag in lore.get("tags", []) if str(tag).strip()
        }
        if lore_tags:
            if lore.get("generated"):
                card["tags"] = sorted({*lore_tags, "curio"})
            else:
                card["tags"] = sorted({*card.get("tags", []), *lore_tags})
        if lore.get("rarity"):
            card["rarity"] = str(lore["rarity"])
        if lore.get("generated"):
            card["generated"] = True
        if lore.get("identified"):
            card["identified"] = True
            for key in (
                "descriptor",
                "palette_id",
                "ability_summary",
                "ability_card_id",
            ):
                value = str(lore.get(key) or "").strip()
                if value:
                    card[key] = value
            if card.get("palette_id"):
                card["palette_label"] = palette_label(card["palette_id"])
        card["total_value"] = card["value"] * max(0, int(quantity))
    return card
