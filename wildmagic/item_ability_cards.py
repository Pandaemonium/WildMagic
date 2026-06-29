from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .normalize import normalize_id


@dataclass(frozen=True)
class ItemAbilityCard:
    """A compact, promptable item-ability primitive.

    Identification uses cards rather than free-form mechanics so the LLM can make an
    evocative object while the engine still receives one of the item-use/equipment shapes
    it already knows how to validate and apply.
    """

    id: str
    title: str
    description: str
    json_shape: dict[str, Any]
    tags: frozenset[str] = frozenset()

    def to_prompt_card(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "json_shape": self.json_shape,
            "tags": sorted(self.tags),
        }


ABILITY_CARDS: tuple[ItemAbilityCard, ...] = (
    ItemAbilityCard(
        id="small_healing",
        title="Small Healing",
        description="An active item restores health or knits a wound.",
        tags=frozenset({"life", "plant", "blood", "bone", "body", "mercy"}),
        json_shape={
            "ability_kind": "active",
            "use_spec": {
                "effects": [{"kind": "heal", "amount": 4}],
                "message": "The {item} warms in your hand. You heal {amount} HP.",
                "failure": "You are already unhurt; the item stays quiet.",
                "consume_on_use": False,
                "charges": 3,
            },
        },
    ),
    ItemAbilityCard(
        id="small_mana",
        title="Small Mana",
        description="An active item restores mana or steadies the caster's spell-breath.",
        tags=frozenset({"crystal", "arcane", "memory", "moon", "song", "magic"}),
        json_shape={
            "ability_kind": "active",
            "use_spec": {
                "effects": [{"kind": "restore_mana", "amount": 4}],
                "message": "The {item} gives up a clear note. You recover {amount} mana.",
                "failure": "Your mana is already full; the item waits.",
                "consume_on_use": False,
                "charges": 3,
            },
        },
    ),
    ItemAbilityCard(
        id="protective_charm",
        title="Protective Charm",
        description="A charm-slot passive item grants a small defense bonus while worn.",
        tags=frozenset({"ward", "seal", "law", "bone", "charm", "shell", "coin"}),
        json_shape={
            "ability_kind": "slot_passive",
            "equipment_slot": "charm",
            "equipment_spec": {"defense": 1},
            "use_spec": {
                "effects": [{"kind": "status", "status": "warded", "duration": 5}],
                "message": "The {item} clicks shut around you. You are warded.",
                "failure": "The item refuses to wake.",
                "consume_on_use": False,
                "charges": 2,
            },
        },
    ),
    ItemAbilityCard(
        id="battle_token",
        title="Battle Token",
        description="A weapon or charm gives a small attack bonus while worn.",
        tags=frozenset({"tooth", "claw", "iron", "fire", "anger", "war", "weapon"}),
        json_shape={
            "ability_kind": "slot_passive",
            "equipment_slot": "charm",
            "equipment_spec": {"attack": 1},
            "use_spec": {
                "effects": [{"kind": "status", "status": "empowered", "duration": 4}],
                "message": "The {item} bites your palm. Your strikes feel sharper.",
                "failure": "The item has no blood for this moment.",
                "consume_on_use": False,
                "charges": 2,
            },
        },
    ),
    ItemAbilityCard(
        id="throwing_hex",
        title="Throwing Hex",
        description="An active item damages or curses the nearest enemy in range.",
        tags=frozenset({"curse", "death", "ash", "thorn", "glass", "storm", "fire"}),
        json_shape={
            "ability_kind": "active",
            "use_spec": {
                "effects": [
                    {
                        "kind": "damage_nearest",
                        "range": 8,
                        "amount": 4,
                        "damage_type": "arcane",
                        "required": True,
                    }
                ],
                "message": "You loose the {item}'s spite. {target} takes {amount} {damage_type}.",
                "failure": "No enemy is close enough to catch the hex.",
                "consume_on_use": False,
                "charges": 2,
            },
        },
    ),
    ItemAbilityCard(
        id="elemental_spite",
        title="Elemental Spite",
        description="An active item lashes the nearest enemy with a themed damage type.",
        tags=frozenset(
            {
                "fire",
                "ice",
                "frost",
                "storm",
                "lightning",
                "acid",
                "glass",
                "thorn",
                "venom",
                "radiant",
                "shadow",
            }
        ),
        json_shape={
            "ability_kind": "active",
            "use_spec": {
                "effects": [
                    {
                        "kind": "damage_nearest",
                        "range": 7,
                        "amount": 5,
                        "damage_type": "fire",
                        "required": True,
                    }
                ],
                "message": "The {item} spits power. {target} takes {amount} {damage_type}.",
                "failure": "No enemy is close enough for the item to bite.",
                "consume_on_use": False,
                "charges": 2,
            },
        },
    ),
    ItemAbilityCard(
        id="hindering_token",
        title="Hindering Token",
        description="An active item marks, slows, poisons, or otherwise hinders an enemy.",
        tags=frozenset({"web", "salt", "slime", "poison", "mud", "root", "debt"}),
        json_shape={
            "ability_kind": "active",
            "use_spec": {
                "effects": [
                    {
                        "kind": "status_nearest",
                        "range": 8,
                        "status": "slowed",
                        "duration": 4,
                        "required": True,
                    }
                ],
                "message": "The {item} snags fate. {target} is {status}.",
                "failure": "No enemy is close enough to be bound.",
                "consume_on_use": False,
                "charges": 2,
            },
        },
    ),
    ItemAbilityCard(
        id="debt_binding",
        title="Debt Binding",
        description="An active item makes the nearest enemy jinxed, cursed, weakened, or bound by obligation.",
        tags=frozenset(
            {
                "debt",
                "coin",
                "contract",
                "ledger",
                "law",
                "tax",
                "curse",
                "bargain",
                "oath",
            }
        ),
        json_shape={
            "ability_kind": "active",
            "use_spec": {
                "effects": [
                    {
                        "kind": "status_nearest",
                        "range": 8,
                        "status": "jinxed",
                        "duration": 5,
                        "required": True,
                    }
                ],
                "message": "The {item} comes due. {target} is {status}.",
                "failure": "No enemy is close enough to be named in the debt.",
                "consume_on_use": False,
                "charges": 2,
            },
        },
    ),
    ItemAbilityCard(
        id="silencing_token",
        title="Silencing Token",
        description="An active item silences, frightens, reveals, or weakens the nearest enemy.",
        tags=frozenset(
            {
                "bell",
                "silence",
                "mask",
                "fear",
                "mirror",
                "lens",
                "truth",
                "curse",
                "night",
                "dream",
            }
        ),
        json_shape={
            "ability_kind": "active",
            "use_spec": {
                "effects": [
                    {
                        "kind": "status_nearest",
                        "range": 8,
                        "status": "silenced",
                        "duration": 4,
                        "required": True,
                    }
                ],
                "message": "The {item} imposes a hush. {target} is {status}.",
                "failure": "No enemy is close enough to hear it.",
                "consume_on_use": False,
                "charges": 2,
            },
        },
    ),
    ItemAbilityCard(
        id="revealing_lens",
        title="Revealing Lens",
        description="An active item marks or reveals the nearest enemy through omen, glare, or reflected truth.",
        tags=frozenset(
            {
                "lens",
                "mirror",
                "crystal",
                "glass",
                "eye",
                "prophecy",
                "truth",
                "star",
                "moon",
            }
        ),
        json_shape={
            "ability_kind": "active",
            "use_spec": {
                "effects": [
                    {
                        "kind": "status_nearest",
                        "range": 10,
                        "status": "revealed",
                        "duration": 5,
                        "required": True,
                    }
                ],
                "message": "The {item} shows the shape of {target}. They are {status}.",
                "failure": "The item finds no hidden thread to illuminate.",
                "consume_on_use": False,
                "charges": 2,
            },
        },
    ),
    ItemAbilityCard(
        id="self_veil",
        title="Self Veil",
        description="An active item briefly hides, hastes, empowers, or otherwise marks the player.",
        tags=frozenset(
            {
                "cloak",
                "veil",
                "smoke",
                "shadow",
                "feather",
                "wind",
                "speed",
                "mask",
                "dream",
            }
        ),
        json_shape={
            "ability_kind": "active",
            "use_spec": {
                "effects": [{"kind": "status", "status": "invisible", "duration": 4}],
                "message": "The {item} folds around you. You are {status}.",
                "failure": "The item cannot find an edge to hide you behind.",
                "consume_on_use": False,
                "charges": 2,
            },
        },
    ),
    ItemAbilityCard(
        id="body_boon",
        title="Body Boon",
        description="An active item grants regeneration, warding, empowerment, or other short self magic.",
        tags=frozenset(
            {
                "blood",
                "heart",
                "moss",
                "seed",
                "body",
                "marrow",
                "sun",
                "blessing",
                "feast",
            }
        ),
        json_shape={
            "ability_kind": "active",
            "use_spec": {
                "effects": [
                    {"kind": "status", "status": "regenerating", "duration": 5}
                ],
                "message": "The {item} settles into your pulse. You are {status}.",
                "failure": "Your body refuses the item's rhythm.",
                "consume_on_use": False,
                "charges": 2,
            },
        },
    ),
    ItemAbilityCard(
        id="resistance_token",
        title="Resistance Token",
        description="An active item grants brief resistance to a themed damage type.",
        tags=frozenset(
            {
                "scale",
                "shell",
                "ward",
                "salt",
                "iron",
                "water",
                "ice",
                "fire",
                "storm",
                "armor",
            }
        ),
        json_shape={
            "ability_kind": "active",
            "use_spec": {
                "effects": [{"kind": "resistance", "damage_type": "fire", "amount": 5}],
                "message": "The {item} hardens your skin against {damage_type}.",
                "failure": "The item finds no threat to answer.",
                "consume_on_use": False,
                "charges": 2,
            },
        },
    ),
    ItemAbilityCard(
        id="weather_bottle",
        title="Weather Bottle",
        description="An active item briefly creates mist, ice, fire, rubble, or other terrain.",
        tags=frozenset({"water", "mist", "sand", "ice", "fire", "storm", "smoke"}),
        json_shape={
            "ability_kind": "active",
            "use_spec": {
                "effects": [
                    {
                        "kind": "create_tiles",
                        "tile": ":",
                        "radius": 2,
                        "duration": 4,
                    }
                ],
                "message": "Weather spills out of the {item}.",
                "failure": "The item cannot find a crack in the air.",
                "consume_on_use": False,
                "charges": 2,
            },
        },
    ),
    ItemAbilityCard(
        id="hazard_seed",
        title="Hazard Seed",
        description="An active item spills a small patch of fire, poison, rubble, mist, or ice.",
        tags=frozenset(
            {
                "seed",
                "bottle",
                "jar",
                "ash",
                "venom",
                "spore",
                "rubble",
                "bone",
                "sand",
                "ice",
            }
        ),
        json_shape={
            "ability_kind": "active",
            "use_spec": {
                "effects": [
                    {
                        "kind": "create_tiles",
                        "tile": "^",
                        "radius": 1,
                        "duration": 3,
                    }
                ],
                "message": "The {item} breaks open and changes the ground.",
                "failure": "The ground refuses the item.",
                "consume_on_use": False,
                "charges": 2,
            },
        },
    ),
    ItemAbilityCard(
        id="blink_relic",
        title="Blink Relic",
        description="An active item teleports the player to a random explored tile.",
        tags=frozenset({"key", "door", "mirror", "map", "road", "moon", "strange"}),
        json_shape={
            "ability_kind": "active",
            "use_spec": {
                "effects": [{"kind": "teleport_explored"}],
                "message": "The {item} folds the path under your feet.",
                "failure": "The item finds no explored place to pull you toward.",
                "consume_on_use": False,
                "charges": 1,
            },
        },
    ),
)

_DEFAULT_CARD_IDS = (
    "small_mana",
    "protective_charm",
    "throwing_hex",
    "self_veil",
)


def select_item_ability_cards(
    item_card: dict[str, Any], npc_card: dict[str, Any] | None = None, *, limit: int = 5
) -> list[dict[str, Any]]:
    """Choose a small card set for a specific item.

    The matching is intentionally loose: tags, material, name words, and NPC role all
    contribute to a broad semantic read, while a few default cards keep any object
    identifiable even if it is just "odd spoon" with no metadata.
    """

    words = {
        normalize_id(str(bit))
        for bit in str(item_card.get("name") or "").replace("_", " ").split()
        if str(bit).strip()
    }
    tags = {
        normalize_id(str(tag)) for tag in item_card.get("tags", []) if str(tag).strip()
    }
    material = normalize_id(str(item_card.get("material") or ""))
    role = normalize_id(str((npc_card or {}).get("role") or ""))
    signal = {word for word in words if word}
    signal.update(tag for tag in tags if tag)
    if material:
        signal.add(material)
    if role:
        signal.add(role)

    scored: list[tuple[int, str, ItemAbilityCard]] = []
    for card in ABILITY_CARDS:
        score = len(signal & set(card.tags))
        if card.id in _DEFAULT_CARD_IDS:
            score += 1
        scored.append((score, card.id, card))
    scored.sort(key=lambda entry: (-entry[0], entry[1]))
    return [card.to_prompt_card() for _score, _id, card in scored[: max(1, limit)]]
