from __future__ import annotations

from typing import Any

from .models import MIST


MAP_WIDTH = 42
MAP_HEIGHT = 28

# How far an NPC can notice events near the player.
NPC_PERCEPTION_RADIUS = 6


# (name, char, hp, attack, defense, ai, tags, resistances, weaknesses)
WILD_ENEMY_TEMPLATES: list[tuple[str, str, int, int, int, str, set[str], dict[str, int], dict[str, int]]] = [
    ("goblin cutpurse", "g", 8, 3, 0, "goblin", {"goblin", "humanoid", "flesh"}, {}, {}),
    ("glass bat", "b", 5, 2, 0, "bat", {"beast", "glass"}, {"poison": 25}, {"force": 25}),
    ("ash slime", "s", 10, 2, 1, "slime", {"slime", "ash"}, {"fire": 35, "poison": 50}, {"frost": 25}),
    ("bone skeleton", "k", 7, 3, 1, "simple", {"undead", "bone"}, {"poison": 100, "frost": 50}, {"force": 50, "radiant": 50}),
    ("cave spider", "x", 6, 2, 0, "simple", {"beast", "spider"}, {}, {"fire": 25}),
    ("shadow wraith", "W", 4, 4, 0, "simple", {"undead", "shadow"}, {"physical": 25, "poison": 100}, {"radiant": 75, "fire": 25}),
    ("fungal crawler", "c", 9, 2, 0, "simple", {"beast", "fungus"}, {"acid": 50}, {"fire": 50}),
    ("fen archer", "a", 6, 3, 0, "goblin", {"goblin", "humanoid", "flesh", "ranged"}, {}, {"fire": 25}),
    ("husk sentinel", "n", 14, 3, 3, "simple", {"construct", "stone", "stationary"}, {"physical": 25, "poison": 100}, {"force": 50}),
    ("carrion rat", "r", 4, 2, 0, "simple", {"beast", "vermin", "scavenger"}, {"poison": 50}, {}),
    ("bog hexweaver", "v", 7, 2, 0, "goblin", {"goblin", "humanoid", "caster", "summoner"}, {}, {"physical": 10}),
]

LEGION_ENEMY_TEMPLATES: list[tuple[str, str, int, int, int, str, set[str], dict[str, int], dict[str, int]]] = [
    ("drill initiate", "i", 6, 2, 0, "legion", {"empire", "human", "soldier", "disciplined"}, {}, {"force": 25}),
    ("legion spearman", "l", 9, 3, 1, "legion", {"empire", "human", "soldier", "disciplined"}, {"physical": 15}, {}),
    ("wall sergeant", "m", 10, 3, 2, "legion", {"empire", "human", "soldier", "officer", "disciplined"}, {"physical": 15}, {}),
    ("iron chaplain", "h", 7, 2, 1, "legion", {"empire", "human", "priest", "disciplined"}, {"radiant": 25}, {"poison": 25}),
    ("exemplar of the line", "e", 12, 4, 2, "legion", {"empire", "human", "soldier", "elite", "disciplined"}, {"physical": 25}, {}),
]

# Tag-pairs whose bearers are mutually hostile, on top of the baseline
# enemy-vs-(player & allies) opposition every "enemy"-faction entity already has.
FACTION_HOSTILITIES: list[tuple[set[str], set[str]]] = [
    ({"empire"}, {"hollowmere_townsfolk"}),
]


ITEM_USE_SPECS: dict[str, dict[str, Any]] = {
    "mana_crystal": {
        "effects": [{"kind": "restore_mana", "amount": 6}],
        "message": "The {item} dissolves. You recover {amount} mana.",
    },
    "blood_moss": {
        "effects": [{"kind": "heal", "amount": 5}],
        "message": "You chew the {item}. You heal {amount} HP.",
    },
    "bone_charm": {
        "effects": [
            {"kind": "status", "status": "warded", "duration": 8},
            {"kind": "resistance", "damage_type": "physical", "amount": 20},
        ],
        "message": "The {item} crumbles. You feel warded and resistant.",
    },
    "healing_potion": {
        "effects": [{"kind": "heal", "amount": 10}],
        "message": "The {item} works. You heal {amount} HP.",
    },
    "mana_potion": {
        "effects": [{"kind": "restore_mana", "amount": 10}],
        "message": "The {item} restores {amount} mana.",
    },
    "smoke_vial": {
        "effects": [{"kind": "create_tiles", "tile": MIST, "radius": 2, "duration": 5}],
        "message": "A cloud of mist erupts around you.",
    },
    "blink_scroll": {
        "effects": [{"kind": "teleport_explored"}],
        "message": "You blink to an explored tile.",
        "failure": "The scroll finds nowhere to send you.",
    },
    "beast_claw": {
        "effects": [{"kind": "status", "status": "empowered", "duration": 4}],
        "message": "You drag the {item} across your palm. Your strikes feel sharper.",
    },
    "bone_shard": {
        "effects": [{"kind": "damage_nearest", "range": 12, "amount": 4, "damage_type": "physical", "required": True}],
        "message": "You hurl the {item}. {target} takes {amount} damage.",
        "failure": "No enemy is close enough to throw at.",
    },
    "viscous_residue": {
        "effects": [{"kind": "status_nearest", "range": 8, "status": "poisoned", "duration": 4, "required": True}],
        "message": "You fling the {item}. {target} is poisoned.",
        "failure": "No enemy to throw this at.",
    },
    "metal_scrap": {
        "effects": [{"kind": "damage_nearest", "range": 6, "amount_min": 3, "amount_max": 6, "damage_type": "physical", "required": True}],
        "message": "You bash with the {item}. {target} takes {amount} damage.",
        "failure": "No enemy nearby.",
    },
    "arcane_residue": {
        "effects": [
            {"kind": "restore_mana", "amount": 3},
            {"kind": "damage_nearest", "range": 8, "amount": 3, "damage_type": "arcane"},
        ],
        "message": "The {item} sparks. You gain {mana} mana. {target_clause}",
    },
    "stolen_coin": {
        "choices": [
            {
                "effects": [{"kind": "restore_mana", "amount_min": 4, "amount_max": 8}],
                "message": "The {item} lands lucky side up. You gain {amount} mana.",
            },
            {
                "effects": [{"kind": "heal", "amount_min": 2, "amount_max": 5}],
                "message": "The {item} lands fair. You heal {amount} HP.",
            },
            {
                "effects": [{"kind": "status", "status": "marked", "duration": 4}],
                "message": "The {item} lands cursed side up. You are marked.",
            },
        ],
    },
}

TRAP_SPECS: dict[str, dict[str, Any]] = {
    "trap_spike": {
        "damage": 4, "damage_type": "physical", "status": "bleeding", "duration": 3,
        "message": "Hidden spikes punch up through the floor!",
        "message_other": "Hidden spikes punch up under {name}!",
    },
    "trap_gas": {
        "damage": 2, "damage_type": "poison", "status": "poisoned", "duration": 4,
        "message": "A hidden vent hisses open, choking you in foul gas!",
        "message_other": "A hidden vent chokes {name} in foul gas!",
    },
    "trap_flame": {
        "damage": 3, "damage_type": "fire", "status": "burning", "duration": 3,
        "message": "A hidden nozzle roars, washing you in flame!",
        "message_other": "A hidden nozzle washes {name} in flame!",
    },
    "trap_frost": {
        "damage": 2, "damage_type": "frost", "status": "slowed", "duration": 3,
        "message": "A hidden rune flares, and killing frost bites into you!",
        "message_other": "A hidden rune bites {name} with killing frost!",
    },
}

LOCKED_DOOR_KEYS = ["brass key", "bone key", "rusted key", "engraved key"]
for _key_name in LOCKED_DOOR_KEYS:
    ITEM_USE_SPECS[_key_name.replace(" ", "_")] = {
        "effects": [{"kind": "inert", "required": True}],
        "failure": "This key is meant for a particular lock. Try it on the door itself.",
    }
del _key_name

EQUIPMENT_SPECS: dict[str, dict[str, Any]] = {
    "rusty sword": {"slot": "weapon", "attack": 2},
    "iron sword": {"slot": "weapon", "attack": 4},
    "war pick": {"slot": "weapon", "attack": 5},
    "hunting bow": {"slot": "weapon", "attack": 3},
    "leather vest": {"slot": "armor", "defense": 2},
    "iron breastplate": {"slot": "armor", "defense": 4},
    "wooden buckler": {"slot": "armor", "attack": 1, "defense": 1},
    "lucky coin charm": {"slot": "charm", "attack": 1},
    "warding locket": {"slot": "charm", "defense": 1},
}
for _gear_name in EQUIPMENT_SPECS:
    ITEM_USE_SPECS[_gear_name.replace(" ", "_")] = {
        "effects": [{"kind": "inert", "required": True}],
        "failure": "This isn't something to consume -- try 'equip' or 'wear' instead.",
    }
del _gear_name

DEFAULT_ITEM_USE_SPEC: dict[str, Any] = {
    "effects": [{"kind": "restore_mana", "amount": 2}],
    "message": "You consume the {item}. It restores {amount} mana.",
}


TRADE_KEYWORDS = frozenset({
    "trade", "trades", "traded", "trading",
    "sell", "sells", "sold", "selling",
    "buy", "buys", "bought", "buying",
    "barter", "bartering",
    "deal", "deals",
    "offer", "offers", "offered", "offering",
    "exchange", "exchanges", "exchanging",
    "swap", "swaps", "swapping",
    "purchase", "purchases", "purchasing",
    "haggle", "haggling",
    "wares", "goods", "merchandise",
    "gold", "coin", "coins",
    "price", "prices", "priced",
})


def scan_for_trade_intent(message: str, reply: str) -> bool:
    """Cheap, in-process first pass: does either side of this exchange even sound
    trade-flavored? Scanning BOTH the player's message and the NPC's reply matters
    -- "I'll trade you my dagger for that lockpick" might draw a reply that never
    repeats a trade-ish word at all. This is intentionally crude (a keyword scan,
    not LLM judgment) -- it exists purely to keep the expensive structuring call
    (resolve_trade_proposal) rare, since false positives just cost one quick no-op
    LLM round trip while false negatives would silently swallow real offers."""
    text = f"{message} {reply}".lower()
    return any(keyword in text for keyword in TRADE_KEYWORDS)


# Building dimensions (w, h) keyed by building type name from LLM output.
_BUILDING_SIZES: dict[str, tuple[int, int]] = {
    "tavern": (8, 6),
    "inn": (8, 6),
    "market": (7, 5),
    "shop": (7, 5),
    "shrine": (5, 5),
    "temple": (6, 5),
    "home": (4, 4),
    "house": (4, 4),
    "smithy": (5, 4),
    "forge": (5, 4),
    "barracks": (8, 5),
    "stable": (6, 4),
}
_DEFAULT_BUILDING_SIZE = (5, 4)

# Override stats for NPC roles that should be able to fight back.
_ROLE_STATS: dict[str, dict[str, int]] = {
    "guard": {"hp": 18, "attack": 4, "defense": 1},
    "soldier": {"hp": 20, "attack": 5, "defense": 2},
    "captain": {"hp": 22, "attack": 5, "defense": 2},
    "militia": {"hp": 15, "attack": 3, "defense": 1},
    "mercenary": {"hp": 16, "attack": 4, "defense": 1},
}
_DEFAULT_NPC_STATS: dict[str, int] = {"hp": 10, "attack": 1, "defense": 0}

# Procedural town context seeds — picked deterministically per zone so the
# same zone always generates the same town, but different zones feel distinct.
_TOWN_LOCATIONS: list[str] = [
    "at a river crossing that floods each spring",
    "on the edge of a worked-out mine",
    "where two old Imperial roads meet",
    "built into the ruins of something much older",
    "on the only high ground for miles around",
    "at the base of a collapsed watchtower",
    "hidden in a fold of the hills, hard to find from the road",
    "at the mouth of a steep ravine",
    "beside a spring that never runs dry even in drought",
    "in the shadow of a long-dead volcano",
    "at the edge of a near-impassable marsh",
    "along a stretch of road known for ambushes",
    "near a stone circle that the locals won't discuss",
    "at a crossroads with a history of violence",
    "on a bluff above a wide, slow-moving river",
    "where the forest thins and the plain begins",
    "sheltered in a natural hollow that traps fog",
    "at the end of a road that used to go further",
]

_TOWN_DEFINING_TRAITS: list[str] = [
    "Everyone here owes something to someone else",
    "The town was founded by deserters who never went home",
    "People come here to disappear, and most do",
    "The locals have survived three changes of ruler in ten years",
    "Something was found here once; people still come looking",
    "No one asks where you came from or what you left behind",
    "Every family here has someone buried under the foundations",
    "The town exists because of one trade, and it is slowly dying",
    "There is one person here that everyone else defers to, for reasons no one states openly",
    "The town had a different name before; no one uses it anymore",
    "Outsiders are welcome for exactly as long as their money lasts",
    "A pact of some kind holds this community together — ask the wrong questions and you feel it",
    "The young leave as soon as they can; those who stay have their reasons",
    "The Empire ignores this place, which is precisely why it survives",
    "Strange things happen here at certain times of year; the locals call it ordinary",
    "Everyone here is running from something, and everyone knows it",
    "The town has a good reputation in the region, built on one lie told consistently for years",
    "The founding family still runs everything, though the last of them is very old",
]

_TOWN_SITUATIONS: list[str] = [
    "A caravan has been stranded here for two weeks and the mood is souring",
    "Someone important died last month and no one agrees on what comes next",
    "A new Imperial tax collector arrived and shows no sign of leaving",
    "A rumor is spreading about something valuable hidden in the hills nearby",
    "Winter came early and the stores are already running low",
    "A sickness passed through recently — most recovered, a few didn't, and no one knows why",
    "An old grudge between two families has resurfaced over something trivial",
    "A merchant passed through last week with strange news from further east",
    "Someone has been leaving offerings at the edge of town each night",
    "A group of refugees arrived and the welcome is wearing thin",
    "A fire took one of the buildings last month; the cause was never settled",
    "Imperial patrols have been passing through more frequently than usual",
    "A traveling performer arrived six days ago and has not moved on",
    "The well started tasting wrong and no one will say anything definitive about it",
    "Two residents vanished last month; one body was found, the other wasn't",
    "An unexpected early thaw has flooded the lower roads; people are stuck here",
    "A large debt came due recently and everyone is feeling the pressure",
    "Someone new arrived claiming to own something here, and the paperwork looks real",
]

_TOWN_GEN_TIMEOUT = 90  # seconds to wait for background LLM town generation before falling back to mock

_TOWN_SETTLEMENT_TYPES: list[tuple[str, int, int]] = [
    ("hamlet", 2, 3),
    ("waypost", 2, 4),
    ("rough camp", 2, 3),
    ("settlement", 3, 5),
    ("crossroads town", 4, 6),
    ("trading post", 3, 5),
    ("refuge", 3, 5),
    ("outpost", 2, 4),
]
