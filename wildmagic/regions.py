from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .game_data import WILD_ENEMY_TEMPLATES

# A region bundles everything about "where you are": the narrative voice fed to
# the LLM, the creatures and props that spawn, the ambient lines the place
# speaks in, and how strange reality is allowed to get. Regions are geography
# (the overworld zone grid maps onto them); wildness is an orthogonal axis —
# effective wildness = region.wildness_base + dungeon depth — so any region
# gets stranger the deeper you go, and some regions start strange.
#
# Adding a region should mean adding an entry to REGIONS, not touching engine
# code. See docs/EXECUTION_PLAN.md Phase 13 and docs/AESTHETICS_AND_TONE.md.

EnemyTemplate = tuple[str, str, int, int, int, str, set[str], dict[str, int], dict[str, int]]


@dataclass(frozen=True)
class Region:
    id: str
    name: str
    # -- Voice (style line + example swap, injected into the wild-magic prompt) --
    voice: str
    example_outcomes: tuple[str, ...]
    # -- Population --
    enemy_templates: tuple[EnemyTemplate, ...]
    # Probability that an enemy spawn draws from the imperial legion pool
    # instead of the region's own bestiary. Also gates how reliably the
    # Censorate's posted notices appear.
    imperial_presence: float
    # -- Places: (max_depth_inclusive, {prop_category: weight}); first match wins --
    floor_themes: tuple[tuple[int, dict[str, int]], ...]
    # -- Ambience --
    ambient_by_tag: dict[str, tuple[str, ...]]
    ambient_default: tuple[str, ...]
    # (max_wildness_inclusive, lines); first match wins. Spoken when no threat
    # is near — the place itself talking.
    wonder_by_wildness: tuple[tuple[int, tuple[str, ...]], ...]
    # -- The strangeness axis --
    wildness_base: int = 0

    def effective_wildness(self, depth: int) -> int:
        return self.wildness_base + max(0, depth)

    def wonder_lines(self, depth: int) -> tuple[str, ...]:
        wildness = self.effective_wildness(depth)
        for threshold, lines in self.wonder_by_wildness:
            if wildness <= threshold:
                return lines
        return self.wonder_by_wildness[-1][1]

    def prompt_style(self) -> dict[str, Any]:
        """The slice of the region the wild-magic prompt builder consumes."""
        return {"name": self.name, "voice": self.voice, "examples": list(self.example_outcomes)}


# Creature sounds shared across regions; a region can override per tag.
_COMMON_SOUNDS_BY_TAG: dict[str, tuple[str, ...]] = {
    "undead": ("Somewhere unseen, dry joints click in a slow rhythm.", "A voice hums a lullaby with no breath behind it.", "Dust sifts from the ceiling in time with footsteps that are not yours."),
    "beast": ("Claws click on stone somewhere, unhurried.", "Something large yawns in the dark and settles again.", "You hear sniffing, then a thoughtful pause."),
    "slime": ("A wet gurgle sounds in the distance, almost musical.", "Something drips upward, once.", "You hear a slow, patient sliding."),
    "spider": ("Silk creaks like ship's rigging somewhere overhead.", "You hear many legs cross the ceiling, perfectly in step.", "A plucked strand of web rings a single soft note."),
    "construct": ("Gears turn somewhere unseen, patient as a clock.", "A low hum swells and fades, like something remembering its purpose.", "Metal settles with a satisfied tick."),
    "shadow": ("The light here leans away from one corner.", "Something cold is counting your footsteps.", "Your shadow arrives half a step late."),
    "empire": ("You hear the rhythmic stamp of boots in unison.", "A horn sounds three precise notes, then falls silent.", "Iron scrapes against iron in perfect time."),
}


_FRONTIER = Region(
    id="frontier",
    name="the Hollowmere frontier",
    voice=(
        "This is frontier country under imperial eyes: hedgerows, market roads, old shrines, "
        "buried strata of older magic below. Keep outcomes earthy and vivid -- wonder with mud on its boots."
    ),
    example_outcomes=(
        "The hedge-wind takes your spell and runs with it, laughing through the brambles.",
        "Sparks settle over the old road like seeds deciding where to land.",
        "The shrine-stones lean in to watch, and the moss between them glows ember-orange.",
    ),
    enemy_templates=tuple(WILD_ENEMY_TEMPLATES),
    imperial_presence=0.3,
    floor_themes=(
        (2, {"imperial": 4, "infrastructure": 3, "ruined": 2, "furniture": 1}),
        (4, {"ruined": 3, "natural": 3, "traditions": 2, "infrastructure": 1, "imperial": 1}),
        (6, {"traditions": 3, "arcane": 3, "natural": 2, "alchemical": 1, "religious": 1}),
        (999, {"arcane": 4, "traditions": 3, "religious": 2, "alchemical": 2, "natural": 2}),
    ),
    ambient_by_tag=dict(_COMMON_SOUNDS_BY_TAG),
    ambient_default=(
        "Something moves in the dark, curious.",
        "The deep places are listening, politely.",
        "Far off, water finds a new way down.",
    ),
    wonder_by_wildness=(
        (2, (
            "A draft carries a smell of lamp oil and fresh paper.",
            "Chalk survey lines cross the floor and stop mid-stroke.",
            "Somewhere above, a bell rings the hour, exactly.",
        )),
        (4, (
            "Somewhere above, a market bell rings on the wrong day.",
            "The air tastes faintly of spice and coming rain.",
            "A snatch of song arrives from no particular direction.",
        )),
        (6, (
            "The walls hold yesterday's light a moment too long.",
            "A breeze passes, carrying pollen from nothing that grows here.",
            "Very faintly, you hear applause.",
        )),
        (999, (
            "The stone underfoot is warm, like something sleeping.",
            "The colors at the edge of your vision rearrange themselves when you turn.",
            "The dark ahead hums a note you almost know.",
        )),
    ),
    wildness_base=0,
)


_GLASSWILD = Region(
    id="glasswild",
    name="the Glasswild",
    voice=(
        "This is the Glasswild, deep wild country: dreamlike, gently impossible, jewel-bright. "
        "Light lingers, glass grows, distances disagree -- describe outcomes with strange, vivid beauty."
    ),
    example_outcomes=(
        "The spell blooms into a stand of singing glass, each stalk holding a different hour of light.",
        "Your magic pours uphill, delighted, and the moss turns every color it knows.",
        "The wound in the air heals over with crystal, humming your name back at you.",
    ),
    enemy_templates=(
        ("glass stag", "S", 12, 3, 1, "simple", {"beast", "glass", "fragile"}, {"poison": 50}, {"force": 50}),
        ("chime swarm", "w", 6, 2, 0, "bat", {"swarm", "music", "magic"}, {"physical": 25}, {"force": 25}),
        ("prism serpent", "j", 9, 3, 0, "simple", {"beast", "crystal", "light"}, {"radiant": 50}, {"shadow": 25}),
        ("dream-fed slime", "s", 11, 2, 1, "slime", {"slime", "magic"}, {"poison": 50}, {"frost": 25}),
        ("hollow chorister", "h", 7, 3, 0, "simple", {"spirit", "music", "undead"}, {"physical": 25, "poison": 100}, {"radiant": 50}),
        ("loam shepherd", "n", 14, 3, 3, "simple", {"construct", "plant", "stationary"}, {"poison": 100}, {"fire": 50}),
        ("hare of hours", "r", 5, 2, 0, "bat", {"beast", "magic", "swift"}, {}, {"frost": 25}),
        ("bramble cantor", "v", 8, 2, 0, "goblin", {"plant", "music", "caster", "summoner"}, {"poison": 50}, {"fire": 25}),
    ),
    imperial_presence=0.05,
    floor_themes=(
        (999, {"arcane": 4, "traditions": 4, "natural": 3, "religious": 1}),
    ),
    ambient_by_tag={
        **_COMMON_SOUNDS_BY_TAG,
        "beast": ("Hooves of glass ring once on stone, far off, like a struck bell.", "Something many-antlered moves between here and elsewhere.", "You hear grazing. There is nothing to graze on. There is now."),
        "music": ("A chord assembles itself from the dripping water.", "Something is tuning the air.", "The echo of your last step comes back harmonized."),
    },
    ambient_default=(
        "The Glasswild rearranges something, out of politeness, while you are not looking.",
        "A bright thread of birdsong unspools from underground.",
        "Petals drift past. There are no flowers. The petals seem unbothered.",
    ),
    wonder_by_wildness=(
        (999, (
            "A second horizon shows briefly above the first, then thinks better of it.",
            "Glass grows here. You can hear it practicing.",
            "Your footprints fill with pale light, then wander off on their own.",
            "Somewhere near, a festival is being remembered by the stones.",
        )),
    ),
    wildness_base=6,
)


REGIONS: dict[str, Region] = {
    _FRONTIER.id: _FRONTIER,
    _GLASSWILD.id: _GLASSWILD,
}

DEFAULT_REGION_ID = _FRONTIER.id


def get_region(region_id: str | None) -> Region:
    return REGIONS.get(region_id or "", REGIONS[DEFAULT_REGION_ID])


def region_for_zone(zx: int, zy: int) -> str:
    """Geography: the frontier holds wherever the imperial road network reaches;
    the deep wild begins past it. Crude ring for now — a real region map can
    replace this without touching callers."""
    return _GLASSWILD.id if abs(zx) + abs(zy) >= 3 else _FRONTIER.id
