"""Legend — the mechanical characterization of a soul, distilled from its deeds.

The strategy doc is explicit that the legend is "the connective tissue: dialogue, rumors,
faction reactions, and follower decisions all read it" — and that it must live in two
forms (EMERGENT_WORLD_STRATEGY.md §4, §5.1):

  * **`LegendLedger` (this module, mechanical):** bounded-vocab weighted tags the
    engine/simulator/scores read to decide outcomes. Keyed by **actor soul id** (§1.7).
    This is real game state.
  * **Prose mirror (the existing `SemanticLedger`):** a human-readable note per
    significant legend shift, for prompts (dialogue, narrator) to read — pure flavor,
    never consumed for outcomes.

Keeping the engine-truth tags out of the semantic ledger preserves the ledger's contract
("the hard engine never reads notes to decide outcomes"). See `EMERGENT_WORLD_IMPLEMENTATION.md`
§1.3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


#: The bounded vocabulary of legend tags (§1.8). Each is a *character* the world reads off
#: a soul — distinct from the standing axes (notoriety/fear/…), which measure how powers
#: *feel* about them. Curated and small; additions are deliberate.
LEGEND_VOCAB: tuple[str, ...] = (
    "defiant",  # strikes at the Empire
    "butcher",  # kills the helpless
    "merciful",  # spares the beaten
    "protector",  # shields the weak
    "liberator",  # frees captives
    "destroyer",  # razes places
    "uncanny",  # wields strange / forbidden magic
)


@dataclass
class LegendLedger:
    """Weighted legend tags per actor soul. ``add_tag`` accumulates; readers take the
    highest-weighted tags as the soul's reputation in shorthand."""

    legend_tags_by_actor: dict[str, dict[str, float]] = field(default_factory=dict)

    def add_tag(self, actor: str, tag: str, weight: float) -> float:
        tags = self.legend_tags_by_actor.setdefault(actor, {})
        tags[tag] = tags.get(tag, 0.0) + weight
        return tags[tag]

    def tags_for(self, actor: str) -> dict[str, float]:
        """All legend tags for a soul (the accessor the simulator/scores read)."""
        return dict(self.legend_tags_by_actor.get(actor, {}))

    def top_tags(self, actor: str, n: int = 3) -> list[tuple[str, float]]:
        """The soul's most-earned legend tags, strongest first (ties broken by name)."""
        tags = self.legend_tags_by_actor.get(actor, {})
        ranked = sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))
        return [(tag, weight) for tag, weight in ranked if weight > 0][:n]

    def to_dict(self) -> dict[str, Any]:
        return {
            "legend_tags_by_actor": {
                actor: dict(tags) for actor, tags in self.legend_tags_by_actor.items()
            }
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "LegendLedger":
        return cls(
            legend_tags_by_actor={
                str(actor): {str(tag): float(w) for tag, w in (tags or {}).items()}
                for actor, tags in (raw or {}).get("legend_tags_by_actor", {}).items()
            }
        )
