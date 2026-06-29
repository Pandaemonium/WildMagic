from __future__ import annotations

from typing import Any

from .normalize import coerce_list, normalize_id

RGB = tuple[int, int, int]


ITEM_COLOR_PALETTES: tuple[dict[str, Any], ...] = (
    {
        "id": "salt_ivory",
        "label": "salt ivory",
        "color_names": ("ivory", "bone white", "pale gold"),
        "colors": ((236, 230, 203), (204, 196, 166), (245, 211, 122)),
        "descriptor_examples": ("ivory", "salt-white", "bone-gold"),
        "tags": ("salt", "bone", "shell", "law", "ward", "grave"),
    },
    {
        "id": "ember_glass",
        "label": "ember glass",
        "color_names": ("coal black", "ember red", "hot orange"),
        "colors": ((72, 49, 42), (224, 65, 43), (255, 142, 43)),
        "descriptor_examples": ("embered", "cinder-black", "coal-red"),
        "tags": ("fire", "ash", "iron", "anger", "war", "tooth"),
    },
    {
        "id": "moon_opal",
        "label": "moon opal",
        "color_names": ("moon white", "soft blue", "opal pink"),
        "colors": ((232, 238, 244), (88, 195, 238), (238, 144, 204)),
        "descriptor_examples": ("opalescent", "moonlit", "pearl-blue"),
        "tags": ("moon", "crystal", "glass", "mana", "memory", "song"),
    },
    {
        "id": "viridian_moss",
        "label": "viridian moss",
        "color_names": ("deep green", "sap yellow", "black loam"),
        "colors": ((36, 166, 93), (171, 219, 73), (58, 72, 44)),
        "descriptor_examples": ("viridian", "moss-green", "sap-bright"),
        "tags": ("plant", "moss", "life", "poison", "root", "healing"),
    },
    {
        "id": "storm_copper",
        "label": "storm copper",
        "color_names": ("verdigris", "bright copper", "storm blue"),
        "colors": ((74, 197, 172), (214, 126, 59), (79, 151, 224)),
        "descriptor_examples": ("verdigris", "copper-blue", "storm-bright"),
        "tags": ("storm", "metal", "copper", "brass", "sky", "lightning"),
    },
    {
        "id": "violet_ink",
        "label": "violet ink",
        "color_names": ("deep violet", "ink black", "star white"),
        "colors": ((156, 83, 219), (48, 38, 78), (225, 218, 246)),
        "descriptor_examples": ("violet", "ink-dark", "star-violet"),
        "tags": ("curse", "magic", "dream", "night", "prophecy", "book"),
    },
    {
        "id": "desert_ochre",
        "label": "desert ochre",
        "color_names": ("ochre", "sun gold", "dust brown"),
        "colors": ((197, 132, 48), (245, 194, 71), (142, 105, 72)),
        "descriptor_examples": ("ochre", "sun-baked", "amber-dust"),
        "tags": ("sand", "desert", "heat", "dust", "glass", "dry"),
    },
    {
        "id": "blood_ruby",
        "label": "blood ruby",
        "color_names": ("ruby red", "marrow pink", "dark brown"),
        "colors": ((214, 40, 62), (239, 127, 141), (86, 45, 39)),
        "descriptor_examples": ("ruby", "blood-red", "marrow-red"),
        "tags": ("blood", "body", "death", "claw", "tooth", "wound"),
    },
    {
        "id": "fresh_water",
        "label": "fresh water",
        "color_names": ("deep teal", "clear blue", "foam white"),
        "colors": ((0, 143, 132), (38, 202, 238), (212, 248, 244)),
        "descriptor_examples": ("fresh-water", "foam-blue", "clear"),
        "tags": ("water", "tide", "rain", "river", "mist", "clean"),
    },
    {
        "id": "honey_hulk",
        "label": "honey hulk",
        "color_names": ("honey gold", "leaf green", "wax brown"),
        "colors": ((242, 180, 49), (88, 174, 72), (137, 91, 47)),
        "descriptor_examples": ("honeyed", "wax-gold", "hulk-green"),
        "tags": ("honey", "wax", "insect", "amber", "sweet", "plant"),
    },
)


_PALETTE_BY_ID = {str(palette["id"]): palette for palette in ITEM_COLOR_PALETTES}


def palette_by_id(palette_id: Any) -> dict[str, Any]:
    normalized = normalize_id(str(palette_id or ""))
    return _PALETTE_BY_ID.get(normalized) or ITEM_COLOR_PALETTES[0]


def palette_exists(palette_id: Any) -> bool:
    return normalize_id(str(palette_id or "")) in _PALETTE_BY_ID


def palette_label(palette_id: Any) -> str:
    return str(palette_by_id(palette_id)["label"])


def palette_colors(palette_id: Any) -> tuple[RGB, ...]:
    return tuple(palette_by_id(palette_id)["colors"])


def palette_prompt_cards() -> list[dict[str, Any]]:
    return [
        {
            "id": palette["id"],
            "label": palette["label"],
            "colors": list(palette["color_names"]),
            "descriptor_examples": list(palette["descriptor_examples"]),
            "tags": list(palette["tags"]),
        }
        for palette in ITEM_COLOR_PALETTES
    ]


def palette_for_item(item: dict[str, Any]) -> dict[str, Any]:
    signal = {
        normalize_id(str(bit))
        for bit in str(item.get("name") or "").replace("_", " ").split()
        if str(bit).strip()
    }
    signal.update(
        normalize_id(str(tag))
        for tag in coerce_list(item.get("tags"))
        if str(tag).strip()
    )
    material = normalize_id(str(item.get("material") or ""))
    if material:
        signal.add(material)
    best_score = -1
    best = ITEM_COLOR_PALETTES[0]
    for palette in ITEM_COLOR_PALETTES:
        score = len(signal & {normalize_id(str(tag)) for tag in palette["tags"]})
        if score > best_score:
            best_score = score
            best = palette
    return best


def descriptor_for_palette(palette: dict[str, Any]) -> str:
    for example in palette.get("descriptor_examples") or ():
        descriptor = " ".join(str(example or "").replace("_", " ").split()).lower()
        descriptor = "".join(
            char
            for char in descriptor
            if char.isascii() and (char.isalnum() or char in " -'")
        ).strip(" '-")
        if descriptor:
            return descriptor
    return "awakened"
