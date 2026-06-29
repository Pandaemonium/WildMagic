# Items And Reagents

Wild Magic needs a richer item layer. Items should make exploration, trade, theft,
quests, and spellcasting all feed the same loop: the world is full of strange things,
and every strange thing can become magical fuel.

The core design rule still applies:

> The LLM may propose magical consequences, but the engine remains authoritative.

Items should therefore add expressive spell inputs, not a hidden second spell engine.
The resolver may choose to spend a pearl, a saint's knucklebone, or a sack of desert
sand, but the engine decides whether the item exists, how much value it contributes,
how much spell power that pays for, and what state actually changes.

## Goals

- Make the dungeon, towns, markets, and promises produce many more interesting items.
- Let most items be semantic curios until the player uses them or burns them in a spell.
- Give every item one visible value that matters for both trade and spell power.
- Let item material and tags color wild-magic outcomes.
- Keep casting latency flat: no extra LLM call during ordinary spell resolution.
- Keep CLI and GUI inventory behavior in sync through the shared action/state layer.
- Preserve replayability and save/load readiness.

## Current Starting Point

Relevant existing systems:

- `wildmagic/items.py` owns inventory mutation, item use, pickup/drop, equipment, and
  spell-focus marking.
- `wildmagic/equipment.py` owns equipment slot policy.
- `wildmagic/templates.py` owns template-backed conjured item and creature creation.
- `wildmagic/game_data.py` owns authored item use specs, equipment specs, and focus specs.
- `wildmagic/state_view.py` owns inventory/equipment presentation and resolver context.
- `wildmagic/effects.py` already supports item costs, item spawning, item conjuration,
  item transformation, and inventory modification.
- `GameState.item_lore` already lets item descriptions survive pickup, keyed by the same
  inventory key used by the current fungible inventory model.
- `docs/SPELL_FOCUS_PLAN.md` documents the current focus and item-lore design.

The main limitation is that inventory is still mostly `name -> quantity`. That is good
for stackable reagents, but weak for unique relics, item-specific triggers, and items
whose generated identity should survive stacking.

Current implementation notes:

- The resolver context exposes both raw `inventory` for compatibility and rich `reagents`
  cards for wild-magic item costs.
- `protected_inventory` exposes stacks the player has kept out of ordinary spell costs.
- `protect <item>`, `unprotect <item>`, and `reagents` are shared action-layer commands, so
  they work from CLI and the GUI command prompt.
- Item costs now fuzzy-match carried stacks, report paid value, and refuse protected stacks
  unless the resolution explicitly authorizes protected inventory.
- Accepted spell resolutions now preflight item costs before effects apply. A protected or
  unavailable item cost is a technical validation failure, not a free spell.
- `wildmagic/item_generation.py` now creates lightweight semantic curios from material,
  form, oddity, and theme tags. Secrets, occasional monster drops, trader wares, and some
  procedural quest rewards can introduce these items without a direct-use mechanic or an
  extra LLM call.
- Generated curio value/material/tags are stored in `item_lore`, so reagent cards and item
  costs use their generated metadata instead of relying only on name inference.
- The live resolver can still describe an item being burned or spent without emitting an
  engine-applied item cost. Prompt guidance now discourages this, but engine cost scoring is
  still the durable fix for underpaid accepted spells.
- Accepted wild-magic resolutions can currently have no meaningful cost if the model emits
  none. The planned spell power economy should close this by topping up underpaid spells.
- Direct-use consumables should not be wasted when they have no effect. For example, a
  mana crystal at full mana or blood moss at full health should remain in inventory.

## Core Rule: One Item Value

Use one primary value:

```text
item.value = what the world thinks this thing is worth
```

That same value drives:

- market/trade value
- quest reward value
- wild-magic sacrifice power
- treasure scoring
- rough rarity and spawn weight

Do not split `market_value` and `reagent_value` by default. If a player burns an
expensive pearl in a spell, the spell should get an expensive-pearl amount of power.
The player should not have to learn that some valuable things are secretly poor
reagents.

Materials and tags determine how value expresses itself, not whether the value counts.

Examples:

- `pearl`, value 40, tags `water`, `moon`, `beauty`
  - contributes about 40 points of spell budget
  - colors effects toward water, mist, healing, glamour, reflection, or moonlight
- `crystal ball`, value 120, tags `crystal`, `divination`, `fragile`
  - contributes about 120 points of spell budget
  - colors effects toward reveal, prophecy, omen, tracking, or brittle light
- `desert sand`, value 2, tags `sand`, `dry`, `desert`
  - contributes a small budget
  - colors effects toward heat, glass, erosion, blinding grit, or dry wind

Affinity bonuses may exist, but only upward:

```text
spell_budget = item.value + affinity_bonus
```

Never reduce the paid value because the item is thematically mismatched. A pearl spent on
fire still pays its full value; it may express as steam, white flame, boiling water,
glass heat, or moonlit radiance.

Gold is also valid spell fuel. It should have real value in the reagent economy, but it
should carry weak generic bias compared with tagged objects. Burning a pile of coins can
pay for power; burning a pearl, relic, seal, or debtor coin should usually be more
interesting because its tags give the spell a stronger direction.

## Item Definition

Add a single item metadata source, probably `wildmagic/item_catalog.py`.

Suggested data shape:

```python
@dataclass(frozen=True)
class ItemDefinition:
    id: str
    name: str
    char: str
    kind: str
    material: str
    tags: frozenset[str]
    value: int
    rarity: str
    use_profile: str = "inert"
    spell_bias: SpellBias | None = None
```

Suggested spell-bias shape:

```python
@dataclass(frozen=True)
class SpellBias:
    damage_types: dict[str, int]
    preferred_effects: tuple[str, ...]
    side_effect_hints: tuple[str, ...]
    affinity_tags: frozenset[str]
```

`ItemDefinition` should become the shared source for authored items, equipment, trade
goods, reagents, and generated semantic curios where possible. Existing `ITEM_USE_SPECS`,
`EQUIPMENT_SPECS`, and `FOCUS_SPECS` can migrate gradually by looking up the same item
definition instead of remaining parallel metadata islands.

## Inventory Model

Use a two-lane model in the long run:

- Stackable item stacks: `grave salt x5`, `desert sand x3`, `glass bead x2`
- Item instances: named relics, generated curios, authored artifacts, unique quest items,
  books, cursed equipment, and anything with item-owned triggers or history

Do not do the full instance migration first. A safe path:

- Keep current `inventory: dict[str, int]` for stackables.
- Add item metadata lookup by inventory key.
- Continue using `GameState.item_lore` for picked-up item descriptions.
- Require generators to give unique inventory keys to items whose identities must not stack.
- Add item instances later when item-owned triggers, durability, curse ownership, or
  trade history need them.

This preserves current UI/CLI behavior while creating a clear escape hatch for richer
items.

### Protected Inventory

The player needs a "safe space" inside their inventory: a protected pouch, lockbox,
keepsake slot, or similar command-facing concept for items they do not want wild magic to
consume.

Rules:

- Wild-magic item costs should only consume unprotected items by default.
- The resolver context should mark protected items separately or omit them from ordinary
  reagent cards.
- A spell can consume protected items only when the player explicitly names or authorizes
  them.
- CLI and GUI must both support moving items into and out of protected storage.
- Protected items still count as carried for ordinary inventory, trade, quest, and
  equipment purposes unless a future encumbrance rule says otherwise.

Possible commands:

- `protect <item>` / `unprotect <item>`
- `lock <item>` / `unlock <item>`
- `reagents` to list what wild magic is currently allowed to spend

The key player promise: if an item is protected, a generic wild spell will not burn it as
a surprise cost.

## Reagent Cards In Spell Context

The resolver should not see only raw inventory counts. It should see compact reagent
cards derived by `state_view.py`.

Example:

```json
{
  "name": "crystal ball",
  "quantity": 1,
  "value": 120,
  "material": "crystal",
  "tags": ["crystal", "divination", "fragile"],
  "spell_bias": {
    "preferred_effects": ["reveal", "create_promise", "add_trait"],
    "side_effect_hints": ["omens", "prophecy", "tracking"]
  }
}
```

Prompt guidance should say:

- Item costs may spend only items shown in reagent cards.
- Higher-value items can justify stronger effects.
- Item tags and materials should color the spell.
- If spending a valuable item, make the result feel worth that sacrifice.
- Do not invent unavailable item costs.
- Do not consume protected items unless the player explicitly names or authorizes them.
- Do not consume high-value items for trivial effects unless the player explicitly asks
  for a wasteful sacrifice.

## Spell Power And Item Costs

Item costs should plug into the planned engine-side spell economy.

The engine computes:

```text
actual_spell_power = score(effects)
paid_spell_budget = score(costs)
```

For item costs:

```text
item_budget = item.value * quantity_spent + affinity_bonus
```

Then the engine enforces one of these outcomes:

- If paid budget covers actual spell power, apply normally.
- If spell power exceeds paid budget, top up with mana, health, max-stat loss, or curse.
- If item value greatly exceeds actual spell power, apply overpayment protection.

The LLM can still choose item costs, but the engine owns the math.

## Overpayment Protection

Players should not feel cheated when a valuable item is consumed.

If a high-value item pays for a weak result, the engine can deterministically improve or
preserve value without another LLM call:

- Boost safe numeric fields such as damage, healing, radius, duration, summon count, or
  status duration within validated caps.
- Add a small tag-derived rider, such as mist from a pearl, reveal from a crystal, or a
  curse mark from grave salt.
- Leave residue, such as `pearl ash`, `spent crystal dust`, or `warm glass sand`.
- Store leftover budget as a short-lived `wild charge` for the next spell.

Preferred order:

1. Boost the current spell if the effect type is safe to scale.
2. Add a small deterministic tag rider if the spell has an obvious affinity.
3. Leave residue if no safe boost exists.
4. Use `wild charge` only if residue proves unsatisfying in playtests.

## Item Color Without Extra Cast Latency

Wild magic can incorporate item color in two layers.

LLM layer:

- Reagent cards influence the first and only spell-resolution call.
- Outcome text and proposed effects can use the item tags.
- This is best for poetry and strange combinations.

Engine layer:

- Deterministic reagent rules can add safe boosts or riders.
- This is best for fairness, overpayment protection, and replay-stable outcomes.

Do not add a second LLM call during casting just to rewrite narration or decide item
color. Casting latency is already scarce.

## Random Semantic Items

Most new items can be generated from composable parts:

```text
region + tradition + material + form + oddity
```

Examples:

- `vint saffron thread`
- `brall carved knucklebone`
- `glasswild noon shard`
- `imperial blue-wax chit`
- `saltmarket debtor coin`
- `hollowmere river pearl`
- `merfolk tide button`
- `parn song-ink scarf`

Each generated item gets:

- name
- material
- tags
- value
- short description
- optional use profile
- optional spell bias

Most can be inert when used directly, while still mattering as spell reagents.

Current simple implementation:

- `generate_curio()` combines material, form, and oddity tables with loose theme tags.
- Curios can appear through secret rewards, creature loot drops, trader wares, and optional
  procedural NPC quest rewards.
- Curios are still ordinary stack keys in the current inventory model.
- Their durable metadata lives in `GameState.item_lore`, not in a separate item-instance
  store.
- They deliberately do not get bespoke direct-use mechanics by default. Their main purpose
  is to make the reagent list strange, tempting, and spell-colorful until an NPC identifies
  one into a functional object.

## NPC Identification Into Functional Items

Some items can have unknown use effects. Resolve these lazily and cache them.

Current trigger:

- `identify <item>` asks a visible NPC to identify one carried item.
- The player pays gold before the ability is revealed.
- Identification consumes one turn when it succeeds.
- Technical LLM/provider failures do not consume a turn or gold.
- The engine, not the model, sets the identified item's market value:

```text
identified_value = previous_value + roughly 3/4 of the identification fee
```

Current implementation:

- `wildmagic/item_ability_cards.py` defines reusable property/ability cards such as healing,
  mana, resistance, debt-binding, revealing lenses, self-veils, hazards, and terrain bottles.
- `wildmagic/item_identification.py` asks the provider to choose one `ability_card_id`, then
  expand that card locally into a bounded item-use/equipment spec. The model still supplies
  the vivid description, player-facing ability summary, palette-backed adjective descriptor,
  and small optional effect overrides.
- `GameEngine.identify_inventory_item()` applies the validated result, spends the fee,
  splits one item out of a stack when necessary, writes durable `item_lore`, and advances
  the turn.
- Identified names use the selected descriptor as a prefix, such as `opalescent moon glass`
  or `ivory bone seal`, rather than an out-of-world `(identified)` suffix.
- The selected descriptor has a named color palette. The GUI colors the descriptor's letters
  with that palette; text-only summaries expose the palette label.
- The reveal message tells the player the new name, description, and mechanical ability.
- Identified active items use existing `ITEM_USE_SPECS`-style effect shapes.
- Identified slot passives can occupy ordinary equipment slots and grant small attack or
  defense bonuses through item lore.
- Identified items do not stack with their previous unidentified stack.
- Compact `ability_card_id` responses are preferred over full nested `use_spec` responses
  because they are faster and less likely to truncate. Full `use_spec` remains accepted for
  compatibility.

Future possible triggers:

- first `use strange item`
- first deep `investigate item`
- shopkeeper appraises a rare item

The item-effect resolver should return a bounded `ITEM_USE_SPECS`-style profile using
existing engine operations. Store the result in durable item metadata so replays and saves
do not call the model again.

Do not call this resolver as part of normal wild-magic casting.

## Relationship To Spell Focus

Spell focus and reagent sacrifice should share item metadata but remain different choices.

- Focus: keep the item, heavily color casts while equipped and marked.
- Reagent sacrifice: spend the item, add its value to the spell budget, and color this cast.

The same item can support both paths. A crystal ball could be a strong focus while kept,
or a powerful one-shot reagent when shattered.

## Learned Spells And Preferred Reagents

Learned spells may remember a preferred reagent.

When the player learns a successful wild spell, store:

- original spell text
- normalized effects
- fixed/discounted base costs
- optional preferred reagent name or tag set
- whether the reagent is required, optional, or substitutable

On recast:

- If the preferred reagent is available and unprotected, use it or offer it first.
- If unavailable, allow a tag-compatible substitute when the learned spell marks the
  reagent as substitutable.
- If the reagent is required and unavailable, reject the deterministic recast with a clear
  message.
- If the reagent is optional, recast the lower-power version without it or ask for
  confirmation if that distinction matters.

This lets a spell keep its identity: a glass-fire charm may want `desert sand`, while a
future-debt spell may want `coin`, `contract`, or `ledger` tags. The spellbook should not
silently burn protected items.

## Trade And Economy

Because value is shared, trade and magic become one loop:

- Buying a rare object is also buying future spell power.
- Selling a relic gives up magical fuel for money.
- Stealing valuables from the Empire can directly empower rebellion.
- Quest rewards can be tuned as either gold, items, or both because both convert to
  meaningful spell opportunity.

Gold itself should be handled carefully. If gold can be spent directly as spell fuel, it
may flatten item flavor unless tagged objects stay more expressive. Prefer:

- ordinary gold has value and can be consumed, but carries weak generic bias
- special coins, ledgers, seals, pearls, relics, and regional goods have stronger tags
- high-value tagged items are more interesting than raw gold

### Shopkeeper Knowledge

Different shopkeepers may understand items at different levels.

Shopkeepers can vary by:

- mundane appraisal skill: whether they know ordinary market value
- magical literacy: whether they recognize reagent value and spell bias
- local tradition: whether they overvalue familiar regional goods or miss foreign ones
- honesty: whether they reveal what they know
- risk tolerance: whether they charge more for outlawed or dangerous magic goods

This means pricing can differ without violating the one-value rule:

- The item's true value is still one engine-owned number.
- A shopkeeper's asking price is their perception, markup, ignorance, or opportunism.
- A magically literate shopkeeper may charge a premium for powerful reagent tags.
- An ignorant shopkeeper may sell a potent curio cheaply.
- Dialogue, examine, appraisal, or reputation can reveal the difference.

This is an excellent place for local color: an imperial clerk prices by tariff schedule,
a hedge-witch knows bone and salt, a bazaar broker knows debts and seals, and a frontier
peddler may only know what someone once paid for something similar.

## UI And CLI Requirements

Both front ends must show the same item facts through shared state views.

Minimum display:

- item name
- quantity
- value
- material/tags when known
- protected/unprotected reagent status
- whether it is equippable
- whether it is a focus
- whether it has a known direct use

Useful commands:

- `inspect` should show compact inventory values.
- `inventory` should show richer item metadata.
- `examine` or `investigate <item>` should reveal semantic/lore details.
- `identify <item>` should pay an NPC to turn one carried semantic item into a functional
  item.
- `use <item>` should invoke known item use.
- `focus <item>` should continue to work for equipped items.
- `protect <item>` and `unprotect <item>` should control whether wild magic may spend it.
- `reagents` should show the unprotected items currently available as spell fuel.

Wild-magic cost messages should include value when helpful:

```text
Cost: crystal ball (value 120).
Cost: 3 desert sand (value 6).
```

## Save, Replay, And Audit

Durable state must include:

- item definitions for generated items
- item lore
- item values
- protected inventory markers
- cached item-use specs
- instance identity for any unique items once instances exist
- item-identification replay records, so replays do not call the provider

Wild-magic audit records should include:

- reagent cards sent to the model
- item costs proposed by the model
- normalized item costs actually paid
- item budget contribution
- any deterministic overpayment boost or residue

Replays should never require an LLM call to reconstruct an item effect or generated item.

## Build Order

Recommended order:

- Add `ItemDefinition` and lookup helpers with one `value`. Done for the fungible
  inventory model in `wildmagic/item_catalog.py`, with inferred metadata for unknown
  semantic items.
- Backfill definitions for existing consumables, reagents, equipment, keys, quest items,
  trade goods, and focus items. Started with all starter reagents, common consumables,
  equipment, keys, gold, and regional focus goods; inferred definitions cover the rest.
- Add protected inventory markers and shared CLI/GUI commands. Done for stack-level
  protection on the controlled entity.
- Add reagent cards to the spell context. Done as `reagents` plus `protected_inventory`.
- Teach the prompt to spend available item costs and respect value. Started with resolver
  guidance; this should keep being tuned from audit logs.
- Change item-cost normalization to fuzzy-match against inventory and item definitions. Done
  for engine cost application.
- Add cost-value scoring for item costs.
- Add deterministic overpayment protection.
- Add region/material/form tables for random semantic item generation. Started with the
  lightweight `item_generation.py` curio path and broad hooks into secrets, loot, traders,
  and occasional quest rewards.
- Surface item value/tags in shared inventory views. Started: inventory views show compact
  values/protection, and `reagents` shows material/tags.
- Add learned-spell preferred reagent storage when the spellbook lands.
- Add cached NPC identification/use resolution for semantic curios. Started with
  `identify <item>` and item-ability cards.
- Add item instances only when item-owned persistence requires it.

## Tests

Important tests:

- item definitions resolve for all existing inventory, equipment, and quest items
- item value appears in spell context reagent cards
- gold appears as a valid low-bias reagent
- item cost consumes the right quantity
- protected item costs are not proposed or applied unless explicitly authorized
- unavailable item cost cannot produce a free spell
- high-value item cost contributes more budget than low-value item cost
- mismatched expensive item still contributes full value
- affinity bonus only increases value; it never discounts a paid item
- overpayment protection boosts or preserves value deterministically
- generated semantic items serialize and replay
- NPC identification costs gold and a turn, writes durable item lore, and is replay-safe
- identified active items use cached direct-use specs and charges
- identified slot passives can be equipped through shared CLI/GUI inventory flows
- learned spells remember and respect preferred reagent rules
- shopkeeper appraisal can differ from true value without changing true value
- CLI and GUI inventory views draw from the same state projection

## Open Questions

- Should the player be warned before a very high-value item is consumed?
- When item instances arrive, which items stop stacking first: relics, books, cursed gear,
  generated curios, or all non-consumables?

## Stacking Discussion Needed

Stacking is not settled.

The current inventory model stacks by inventory key. That is fine for true commodities:
gold, chalk, grave salt, desert sand, glass beads, ordinary arrows, common food, and other
items where one unit is intentionally interchangeable with another.

It is not fine for items whose identity matters:

- generated curios with unique descriptions
- books
- quest items
- cursed or blessed gear
- items with cached LLM use specs
- items that have been used as a spell focus
- items with ownership, provenance, kill history, debts, promises, or item-owned triggers

Likely future rule:

- commodities stack
- authored/common equipment may stack only while unmodified
- any item with unique lore, use effects, protection state, history, or magical ownership
  becomes an instance

This needs further design before implementation because it affects inventory UI, trade,
save/load, replay, item costs, and learned-spell reagent matching.
