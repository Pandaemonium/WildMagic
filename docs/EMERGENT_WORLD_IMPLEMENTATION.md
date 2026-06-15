# Emergent World — Implementation Plan

The build companion to `EMERGENT_WORLD_STRATEGY.md`. That document is the *why* and the
*what*; this one is the *how* and the *in-what-order*. It turns the strategy's four layers
(ledgers → simulator → interpreter → narrator) and its phases into concrete data models,
sequenced milestones, the dependent changes each milestone drags in, and a file-by-file
change index.

Read `EMERGENT_WORLD_STRATEGY.md` first for rationale; §-references below point into it.

**Guiding disciplines (inherited, non-negotiable):**

1. The deterministic skeleton runs with **zero LLM calls**. LLM output is recorded at its
   apply point so replays are free (existing flesh/lore/canon pattern).
2. All new state is **serializable** and lands in `GameState` / `ZoneSnapshot` / replay.
3. Emergent LLM work is **background, batched at pause points**, and routed so most ticks
   make zero calls. Foreground LLM stays reserved for spells and dialogue.
4. Tests force LLM providers to **mock/off** (`tests/conftest.py`); systems exercise the
   real deterministic path.
5. Build the **primitives that generate stories**, not bespoke event scripts.

---

## 0. Decisions (settled 2026-06-14)

Recorded here because they shape the data model and milestone order. **All names are
placeholders** — worldbuilding comes later; keep everything stripped down for now and get
the mechanics in first.

- **D1 — World structure (see §0.1).** A **fixed roster of named kingdoms** with persistent
  character. Their *geopolitical roles* (rival / conquered / independent) and their *rulers*
  are rolled per run; the imperial **founding heartland**, the **proxy client kingdom**, and
  the **emperor** are constant. Kingdoms keep their names and character between runs — only
  status and (non-emperor) rulers change.
- **D2 — Win condition: topple the Empire.** Victory is a standing/coalition outcome
  resolved within a single run; **descent and ascent are never victory or progression
  conditions.** Vertical movement still exists — buildings with basements, caves, small
  dungeons — but it is **bounded and local** (a place has a few levels, like the real
  world), *not* an endless underworld or a "descend-to-progress" spine. **Most movement is
  lateral** across the overworld zone grid. See §0.2.
- **D3 — Four entry points, stable.** Four starting cities with stable identities/names
  run-to-run. The current `town`/`bazaar`/`warren`/`archive` hubs are **playtest
  scaffolding, not final** — they'll be reworked into the real four later.
- **D4 — Day/night cycle + camp/rest; the Simulator advances daily at 05:00 (see §0.3).**
  Time of day is modeled; a camp/rest action passes time. The world tick fires once per
  in-game day at 5am — explicitly **not** on zone crossing (crossing already does enough
  work).
- **D5 — LLM-first, harden to rules over time.** Lean on the LLM for interpretation and
  flavor from the start; progressively promote stable patterns to deterministic rules as
  they prove out. The determinism discipline still holds: every LLM output has a
  deterministic **fallback** (so the skeleton, tests, and replays stand without a backend)
  and is **recorded at its apply point**.
- **D6 — Permadeath.** On death the run ends and a brand-new world is rolled; nothing
  carries forward (consistent with the no-meta-progression stance). Body-swap is a *mid-run*
  tactic, never an automatic death-save. See §0.6.
- **D7 — Bounded finite map.** The overworld is a finite, knowable map per run (edges are
  edges), not the current unbounded sprawl — you can't besiege something unbounded. See §0.4.
- **D8 — The four entry cities sit in different kingdoms.** Your start drops you into a
  different polity (and, because roles are rolled, a different geopolitical situation each
  run), so start choice is a strategic choice. See §0.4.
- **D9 — Victory is to kill the emperor — unlocked by pressure.** The emperor (a fixed
  entity, §0.1) is the best-guarded target in the world; **geopolitical pressure depletes
  the Empire's finite resources** until he becomes reachable. The standing/coalition game
  and the assassination are *one* system, not two win paths. Run length: 15+ hours
  eventually, but **start shorter with faster escalation**. See §0.5.

### 0.1 World structure (D1)

The geopolitics are a **fixed cast in rolled roles** — not procedural nations. Concretely:

- **The Empire** = an imperial **founding heartland** (fixed identity, the emperor's seat)
  plus **three conquered** major kingdoms. *Which three* are conquered varies per run.
- **One proxy / client kingdom** — de facto ruled by the Empire — **always the same**
  (fixed identity and status).
- **One rival** — a major kingdom that is the Empire's main military threat, never
  conquered. *Which* kingdom plays the rival varies per run.
- **Several independent city-states / minor kingdoms** — usually deferent to the Empire;
  whichever major kingdoms aren't conquered or rival end up here, plus the minor pool.
- **The emperor is constant.** Every *other* kingdom's ruler is **rolled per run** — name,
  disposition, character traits — so the same kingdom can be led by a zealot one run and a
  pragmatist the next.

So a run is a **deterministic role assignment over a fixed roster**: founding + proxy are
pinned; from the remaining major-kingdom pool, pick 3 conquered and 1 rival, the rest fall
to independent; then roll each non-emperor ruler. Map adjacency/placement may also be
rolled, but identities and character never are. Data shape (placeholders only):

```python
@dataclass(frozen=True)
class Kingdom:
    id: str
    name: str                 # PLACEHOLDER for now
    character_tags: list[str] # persistent flavor/tradition (e.g. "bone", "maritime")
    pinned_role: str | None   # "founding" / "proxy" for the two fixed ones, else None

KINGDOM_ROSTER: tuple[Kingdom, ...] = (...)   # fixed; placeholder names
EMPEROR = Ruler(...)                          # fixed

@dataclass(frozen=True)
class Ruler:
    name: str                 # PLACEHOLDER; rolled per run except the emperor
    disposition: str
    traits: list[str]
```

Each kingdom becomes a `Faction` (§1.2) with `kind` in
`empire_core | conquered | proxy | rival | independent`; **"the Empire" is the bloc** of
core+conquered+proxy, and Empire-level standing aggregates its members. The win condition
(D2) is defined against the Empire bloc.

### 0.2 Bounded, lateral-first verticality (D2)

Toppling the Empire makes this an overworld/geopolitical game, but **vertical places stay**
— this is not a flat world, it's a world where up/down is real but limited, like life.
Keep ascent/descent, basements, caves, and small dungeons; change only how they relate to
progression and victory:

- **Decouple victory from descent.** Remove the "descend past the last stair → win" logic
  in `engine.py`; victory is killing the emperor, unlocked by pressure (§0.5). Reaching the
  bottom of a cave is never a win.
- **Bound and localize verticality.** Verticality belongs to a *site* (a building's
  basement, a cave with a few levels), with a small fixed number of levels — *not* a single
  global, ever-deepening `depth` counter and *not* an unlimited underworld. Most of the
  world is the lateral **zone grid**; the four cities and their interiors sit on it.
- **Keep the floor-stack machinery.** `descend_stairs`/`ascend_stairs` and per-floor
  snapshots can largely stay; what changes is (a) victory decoupling, (b) capping descent
  per place, and (c) treating "depth" as *local to a site* rather than the run's
  progression axis.
- **Wildness stays mixed.** Geography (region / distance from the imperial core) is the
  primary driver, but bounded local depth may still add a touch — the bible's "buried
  strata of older magic below" — so `effective_wildness` keeps a *small, capped* depth term
  rather than dropping it.

This is a focused change (victory decoupling + caps + localizing), not a teardown; do it
early so everything else assumes the lateral-first, bounded-vertical model.

### 0.3 Time, rest, and the daily tick (D4)

- **TimeOfDay** on `GameState`: a day is a fixed number of turns (TBD by feel); track the
  current day number and a phase (dawn/day/dusk/night). NPC schedules and region skin may
  later read it.
- **Camp/rest** action advances time to the next morning (a deliberate vulnerability
  window — resting in the open invites trouble).
- **The Simulator tick fires once per day at 05:00** — the single "between beats" world
  update (standing drift, faction resource spend → events, off-screen assignments,
  region re-skin). Seeded by `stable_seed(rng_seed, "sim", day_number)` for determinism.
  Not on zone crossing.

### 0.4 The overworld map (D7, D8)

- **Bounded and finite per run.** A fixed-extent map of regions/zones with real edges,
  grouped into the kingdoms of §0.1. This replaces the current unbounded `region_for_zone`
  ring; `region_for_zone` becomes a lookup into the rolled finite map. Finite is required:
  the player must be able to *survey* the geopolitical board and plan a campaign toward the
  capital.
- **Kingdoms occupy contiguous territory**, with the imperial core/capital somewhere
  reachable-but-defended. Adjacency/placement may be rolled; extent is always bounded.
- **Four entry cities, one per polity (D8).** The cities keep stable identities/names
  run-to-run, but each sits in a *different* kingdom, and — because roles are rolled
  (§0.1) — your home city's geopolitical situation changes between runs (conquered this
  run, independent the next, the rival's seat another). Start choice = strategic posture.
- Built by the world roll (Phase C); seeded, so a given seed yields the same map.

### 0.5 Victory: reach and kill the emperor (D9)

- The win is concrete: **kill the emperor** (the one fixed ruler, §0.1). Not an abstract
  standing number — a body in the world.
- **Pressure is the key, not a parallel win.** The emperor is the best-defended target
  alive; you cannot simply march in. The whole emergent loop — deeds → standing shifts →
  backlash → the Simulator spending down the Empire's finite **resources** (legions,
  patrols, informants, the capital guard) — is what *thins his defenses and opens the
  routes*. Coalitions, revolts, crippled legions, defecting kingdoms, or a daring
  infiltration once defenses are thin are all valid pressure. The geopolitics and the
  assassination are one system.
- **Mechanism:** an Empire-resource pool gates the emperor's reachability (guards, sealed
  capital, interceptors). As pressure depletes it, the path opens; at the end he is
  killable. v1 can use a single pool; richer multi-route gating layers on later.
- **Run length:** target 15+ hours eventually; **start with small resource pools and steep
  depletion** so a full loop is reachable and testable now.

### 0.6 Death & the run loop (D6)

- **Permadeath.** On death the run ends and a brand-new world is rolled (fresh roles,
  rulers, and map per §0.1/§0.4). Nothing carries forward.
- **Body-swap is a mid-run tactic** (a spell/choice), never an automatic death-save.

---

## 1. The core data model

All new types are plain dataclasses, serializable, and live in new modules so the engine
stays readable. Field lists are the intended shape, not final code.

### 1.1 Deed (`wildmagic/deeds.py` — NEW)

```python
@dataclass(frozen=True)
class Deed:
    id: str
    turn: int
    zone: tuple[int, int]
    type: str                 # DEED_TYPES vocab (§1.8): killed_imperials, freed_captive,
                              #   razed_building, cast_atrocity, spared_enemy, ...
    magnitude: float          # normalized 0..1 (n killed, structure size, severity)
    target_tags: list[str]    # TARGET_TAGS vocab: empire, civilian, shrine, ...
    actor: str                # the SOUL id (player_soul_id), never the body — §1.7
    source: str               # ACTION source only: combat | spell | interaction
    interpretation_source: str  # who set the consequences: rules | llm | fallback
    # Knowledge model (strategy §5.1):
    visibility: str           # VISIBILITY vocab: secret | witnessed | public | mythic
    witnesses: list[str]      # entity ids that perceived it
    evidence_tags: list[str]  # bloodstain, burned_market, survivor_testimony
    # Proposed consequences (recorded here; APPLIED once by the daily tick, §1.8):
    standing_deltas: dict[str, dict[str, float]]  # faction_id -> axis -> delta
    legend_tags: dict[str, float]                 # LEGEND_VOCAB tags (§1.3)
    applied: bool = False     # set true when the simulator has consumed it (idempotency)
    summary: str = ""         # one line for chronicle / named voices
```

`source` is the *action* that produced the deed; `interpretation_source` records whether
its consequences came from the rules path, the LLM, or the offline fallback (so we can see
how much is still LLM-driven and harden over time, D5).

`DeedLedger` is an append-only list on `GameState` with helpers: `record(deed)`,
`recent(since_turn)`, `by_visibility(...)`, and `compress()` (causal compression → story
beats, §1.5).

### 1.2 Faction (`wildmagic/factions.py` — NEW)

```python
@dataclass
class Faction:
    id: str
    name: str
    kind: str                 # empire_core | conquered | proxy | rival | independent
                              #   | resistance | guild | cult | player_org  (§0.1)
    standing: dict[str, float]   # MULTIDIMENSIONAL, open set (strategy §5.1):
                                 #   notoriety, fear, gratitude, legitimacy,
                                 #   uncanniness, imperial_threat (+ run-rolled axes)
    mood: str
    resources: dict[str, int]    # spendable: patrols, informants, recruits, relics, gold
    goals: list[str]
    home_zones: list[tuple[int, int]]
    player_rank: str | None      # set if the player leads or has climbed this org
    notes_anchor: str            # faction_anchor(id) into the existing semantic ledger
```

`FactionLedger` on `GameState`: `get(id)`, `adjust_standing(id, axis, delta)`,
`spend(id, resource, n) -> bool`, `seed_for_run(seed)` (§Phase C). **Never persisted
between runs.**

### 1.3 Legend — a mechanical ledger, mirrored into prose

The semantic ledger's contract is explicit: *the hard engine never reads notes to decide
outcomes.* Legend tags **are** read by the simulator and by scores, so they must **not**
live only in `SemanticLedger` — that would break the contract. Split it:

- **`LegendLedger` (NEW, mechanical):** `legend_tags_by_actor: dict[str, dict[str, float]]`
  — bounded-vocab (`LEGEND_VOCAB`, §1.8) weighted tags the engine/simulator/scores read.
  Keyed by **actor soul id** (§1.7). This is real game state.
- **Prose mirror (existing `SemanticLedger`):** a human-readable note per significant
  legend shift, anchored to the player, for the *prompts* (dialogue, narrator) to read —
  pure flavor, never consumed for outcomes.

So a legend change writes the tag to `LegendLedger` (engine-truth) and optionally a prose
note to `SemanticLedger` (prompt-flavor). Accessor: `legend_tags(state, actor) -> dict`.

### 1.4 Bond & affiliation (`wildmagic/bonds.py` — NEW; stored on `NPCProfile`)

```python
@dataclass
class Bond:
    loyalty: float = 0.0      # -100..100
    fear: float = 0.0         # 0..100
    admiration: float = 0.0   # 0..100
    resentment: float = 0.0   # 0..100
    ideology: float = 0.0     # -100..100, alignment with the player's cause
    hidden_pressure: str | None = None   # secret agenda / prior loyalty (double agent)
    affiliations: list[str] = field(default_factory=list)  # org/faction ids
```

**Three orthogonal layers, never conflated** (strategy §5.3): combat allegiance is the
existing `entity.faction` string; org membership is `Bond.affiliations`; the personal bond
is the scalars above. A reeve can be `faction="neutral"`, affiliated with your guild, and
loyalty 90.

### 1.5 StoryBeat (causal compression, `wildmagic/deeds.py`)

```python
@dataclass(frozen=True)
class StoryBeat:
    id: str
    summary: str              # "a three-zone guerrilla campaign against the Censorate"
    source_deeds: list[str]
    salience: float
    factions_affected: list[str]
    tags: list[str]
```

Produced by the Simulator tick when deed volume grows; chronicle and named voices
summarize from beats, not raw deeds (keeps prompts small on the A750). **Compression is
additive:** the deed ledger stays append-only and untouched — `compress()` only *creates*
beats that reference deed ids (`source_deeds`); it never deletes or rewrites deeds.

### 1.6 Time (`GameState`, §0.3)

```python
day: int = 1
turn_of_day: int = 0          # 0..TURNS_PER_DAY-1
TURNS_PER_DAY: int            # tuned by feel
# phase(turn_of_day) -> dawn | day | dusk | night ; 05:00 maps to a fixed turn_of_day
```

The daily Simulator tick fires when the clock rolls past 05:00. Camp/rest advances
`turn_of_day`/`day` to the next morning.

### 1.7 Cross-cutting model rules

- **Stable soul identity (prerequisite for Phase 0).** Today `player_id` follows the
  *possessed body* (engine.py: "player means the currently controlled entity; body-swap
  reassigns `player_id`"). Deeds and legend must key off an identity that **never changes on
  a body swap**, so add a `player_soul_id` (a.k.a. `legend_actor_id`) set once at run start
  and used by `Deed.actor` and `LegendLedger`. The controlled-body pointer stays `player_id`.
- **Determinism.** Every roll (world roll, simulator outcomes) draws from
  `stable_seed(state.rng_seed, "<purpose>", ...)` (the daily tick uses `day` as a key). No
  wall-clock, no unseeded `random`.
- **LLM-first with a deterministic fallback (D5).** Where the LLM *interprets meaning*,
  there is always a rules fallback that runs offline/in tests/in replay, and the LLM result
  is recorded at its apply point (`interpretation_source` records which path ran). Note this
  applies to *interpretation*, not *emission*: known deed types are emitted and mapped by
  rules (see Phase A split); the LLM is for ambiguous/novel meaning.
- **Serialization (within a run).** Each new container gets `to_dict`/`from_dict` and is in
  `GameState` (de)serialization and `replay.py` — i.e. the `FactionLedger`, `DeedLedger`,
  `LegendLedger`, bonds, and time **are fully serialized inside saves/replays**. "Never
  carried between runs" (no meta-progression) is about a *new run rolling fresh state*, not
  about skipping serialization of the current run.
- **Zone/site state** rides in the per-location snapshots (see §1.8 verticality).

### 1.8 Idempotency, verticality shape & bounded vocabularies

- **Deed application is once-only (idempotency).** Deeds *record* proposed `standing_deltas`
  / `legend_tags`; the **daily 05:00 tick applies them exactly once**, setting `applied=True`
  (and/or advancing a `simulated_through_turn` cursor on `GameState`). Repeated ticks, a
  reload, or a replay boundary must never double-apply. Tested explicitly (tick twice → one
  application).
- **Site-local verticality (the real Phase 0.5 shape).** Global `depth` +
  `dungeon_floors[depth]` becomes site-local: `GameState.current_site_id` +
  `site_depth`, and floor snapshots keyed by **`(site_id, level)`** with a per-site level
  cap. This is a genuine data-model change (acknowledged), just a bounded one — most places
  have 0–1 sub-levels.
- **Bounded vocabularies, defined early.** Curated constants (small, like the prop
  mechanical-tag list), so emergent state can't sprawl: `DEED_TYPES`, `TARGET_TAGS`,
  `VISIBILITY` (`secret|witnessed|public|mythic`), `LEGEND_VOCAB`, `STANDING_AXES`
  (`notoriety, fear, gratitude, legitimacy, uncanniness, imperial_threat`, open-ended).
  Land them in Phase 0/A and treat additions as deliberate.

---

## 2. Cross-cutting tracks (run through every milestone)

These are not phases; they are checklists each milestone must satisfy.

- **T1 — Serialization & replay.** New state serializes; a replay reproduces it with zero
  model calls; round-trip test added.
- **T2 — LLM purpose & audit.** Each new LLM use gets a scoped config purpose
  (`WILDMAGIC_<PURPOSE>_*` via `config.py`, like `props`), a system prompt in `prompts.py`,
  an `<purpose>_audit.jsonl`, and an entry in the UI debug log (`LLM_AUDIT_FILES`).
  Background work probes reachability (no autostart on the hot path) and degrades to the
  deterministic result. Tests gate it off in `conftest.py`.
- **T3 — Legibility.** Every milestone that changes world state ships the surface that
  *shows* it (strategy §5.5). No silent simulation.
- **T4 — Performance.** New LLM work is background + batched at pause points; routed so the
  common case is zero calls; consequences applied via freeze-once-seen where they mutate
  things the player may be looking at.
- **T5 — Determinism/test.** Deterministic path covered by unit tests independent of any
  provider.
- **T6 — Interface parity.** Every player-facing capability (action, screen, readout)
  ships through **`GameSession`**, the **GUI** (`ui.py`), **and the CLI** (`cli.py`):
  a command, command help, CLI rendering, and at least one **scripted CLI playtest**, plus
  replay support where it changes state. The CLI is the repo's strongest interface rule — a
  GUI-only feature is a regression. (The plan names `ui.py` a lot; read every such mention
  as "GUI **and** CLI.")

---

## 3. The milestones

Phase labels match `EMERGENT_WORLD_STRATEGY.md` §8. Each milestone lists Goal, State,
Rules, LLM, Legibility, Files, Tests, and **Exit criteria** (the bar for "done").

### Phase 0 — The micro-loop (proof of aliveness)

**Goal.** One deed type end-to-end through the *real* abstractions — validates the spine's
shape before any breadth, and is the anti-throwaway insurance.

- **Prerequisite — stable soul id (§1.7).** Add `player_soul_id` set once at run start;
  `Deed.actor`/`LegendLedger` key off it, not `player_id`. Do this first or deeds bind to
  the wrong identity the moment body-swap is used.
- **State.** Minimal `DeedLedger` + `FactionLedger` with two seeded factions (the Empire
  bloc, one rebel pole) and a 2-axis standing (`imperial_threat`, `gratitude`); a
  `simulated_through_turn` cursor for idempotency (§1.8). Add all to `GameState` +
  serialization (T1).
- **Rules.** On a witnessed imperial kill in `combat.py`, emit one `Deed` with proposed
  deltas; a trivial tick **applies unapplied deeds once** (`applied=True` / advance cursor)
  → `+imperial_threat` / `+gratitude`. Trigger the tick from a **temporary debug
  command/hook** for now (the real 05:00 cadence lands in Phase 0.5 — *not* zone-change, D4).
- **LLM.** None yet (keep the slice deterministic; the LLM interpreter arrives in A).
- **Legibility (T6 — GUI *and* CLI).** One rumor line on next zone entry; one NPC memory
  line referencing it; one wanted-poster prop; a minimal standing readout — exposed in both
  the GUI and via a CLI command, with a scripted CLI playtest.
- **Files.** `deeds.py`, `factions.py` (new); `combat.py`, `engine.py` (soul id, tick hook,
  cursor), `generation.py` (poster), `ui.py` + **`cli.py`** (readout + command), `actions.py`
  (`GameSession` debug-tick command).
- **Tests.** Kill → deed recorded → standing shifted → poster present; **tick twice → one
  application** (idempotency); serialization + replay round-trip; soul id survives a body
  swap; scripted CLI run shows the standing readout.
- **Exit criteria.** **act → record → simulate → narrate → show → affect play** runs for
  one deed type, in **both GUI and CLI**, fully deterministic and replay-safe.

### Phase 0.5 — Lateral-first overworld & time foundations (D2, D4)

**Goal.** Commit to lateral-first traversal with bounded verticality, and to the clock the
Simulator runs on, before breadth is built on either.

- **Decouple victory from descent + bound verticality (§0.2).** Remove the descend-past-
  last-stair win; cap descent per site and treat depth as site-local (no global ever-
  deepening counter, no unlimited underworld). Keep `descend_stairs`/`ascend_stairs`,
  basements, caves, and small dungeons working. Keep `effective_wildness` mostly geographic
  with a *small capped* depth term.
- **Time & rest (§0.3).** Add `day`/`turn_of_day`/`TURNS_PER_DAY` + a day/night phase to
  `GameState`; add a **camp/rest** action that advances to the next morning. Move the
  Phase-0 tick onto the real cadence: it fires once per day at **05:00**, seeded by `day`.
  For now the tick still only does the trivial standing drift — Phase D fills it.
- **Files.** `engine.py` (victory decoupling; cap/localize depth; time fields; 05:00 tick),
  `actions.py` (rest), `regions.py` (geography-primary wildness, capped depth term),
  `ui.py` (clock/day indicator), `replay.py` (time state).
- **Tests.** Descent never triggers victory; verticality is bounded (cannot descend past a
  site's level cap); rest advances the clock; the tick fires exactly once per day at 05:00;
  same seed → same tick.
- **Exit criteria.** A run is a lateral-first overworld with working *bounded* up/down, a
  day/night clock, and a deterministic daily tick; no win or progression is tied to depth.

### Phase A — Deeds & Legend (two sub-steps: rules breadth, then LLM meaning)

**Goal.** Generalize deed capture deterministically, then add LLM interpretation for the
parts that actually need meaning. Emission of *known* deeds is always rules-first; the LLM
is for ambiguous/novel meaning (this refines D5: LLM-first applies to *interpretation*, not
*capture*).

**Phase A.1 — Deterministic deed breadth (no LLM).**
- **State.** Full `Deed` schema (visibility/witnesses/evidence; `interpretation_source`);
  `LegendLedger` + `LEGEND_VOCAB`; `StoryBeat` + `compress()` (additive, §1.5); bounded
  vocab constants (§1.8).
- **Rules.** Emit deeds from `combat.py` (kills by faction, collateral civilian deaths,
  spared enemies), `effects.py`/`wild_magic.py` (catastrophic severities, raise-dead,
  desecration), and interactions (free captive, defend townsfolk). **Witness detection**
  reuses FOV + NPC perception at the deed moment. A **deterministic deed→legend/standing
  mapping** for the known types (`interpretation_source="rules"`).
- **Legibility (T6).** Dialogue/trade context gains the legend (read from `LegendLedger` +
  prose mirror); a CLI legend/standing readout too.

**Phase A.2 — LLM interpretation for ambiguous deeds (D5).**
- **LLM.** The Interpreter classifies only *ambiguous/novel* deeds (a strange wild-magic
  outcome, an unprecedented social act) → `{legend_tags, standing_deltas, summary}`
  (generalize `lore.py`), `interpretation_source="llm"`, with the A.1 rules path as the
  recorded **fallback** for offline/tests/replay. Routed like capabilities so plain deeds
  skip it. Track the rules/llm/fallback split to harden over time.
- **Files.** `deeds.py`, `lore.py` (generalize), `combat.py`, `effects.py`,
  `wild_magic.py`, `dialogue.py`/`trade.py` (context), `ui.py`/`cli.py` (readout),
  `prompts.py` + `config.py` (deed-Interpreter purpose, T2).
- **Tests.** Each deed type emits correctly (rules); visibility gates legend entry;
  compression creates a beat without mutating the deed ledger; dialogue/CLI context includes
  legend tags; offline run uses the rules fallback and stays deterministic.
- **Exit criteria.** The world *references the player's deeds* in dialogue and rumors
  (GUI + CLI) with no bespoke per-deed code; known deeds need no model call.

### Phase B — Multidimensional factions & reputation

**Goal.** Make standing real, multidimensional, and consumed; factions act by spending.

- **State.** Promote `Faction` to first-class with the open multidimensional `standing`
  and spendable `resources`. Wire up `Reward.reputation` (promises.py) to deltas. **Bloc
  membership is provisional here:** seed a small fixed Empire bloc + a couple of poles so
  the standing/resource/victory mechanics can be built and tested; the **full rolled roster
  (§0.1) replaces this scaffold in Phase C.** (Mirrors the stub-emperor approach — build the
  mechanism now, plug the real cast in at C.)
- **Rules.** Deed→standing rules across axes (one deed splits across notoriety/fear/
  gratitude/legitimacy/uncanniness/imperial_threat). Faction `spend()` maps onto the
  promise system's existing `PromiseReservation.capacity_cost` + per-zone caps. Empire
  pressure keys off the `imperial_threat` axis specifically.
- **Victory mechanism (D9, §0.5).** Implement the **kill-the-emperor** win: an
  Empire-**resource pool** gates the emperor's reachability, depleted by pressure (deeds →
  standing → backlash → spend-down). The literal win check is the emperor's death; this
  phase builds the *gate* (resources → reachability) and the death-check, testable against a
  **stub emperor** until the world roll (Phase C) places the real one. No
  descent/standing-threshold *as* the win.
- **LLM.** Interpreter continues LLM-first (D5); start measuring which deed types can move
  to the rules fallback.
- **Legibility.** A real **faction/standing screen** (T3) — each kingdom/power's
  disposition, its role in the bloc, the axes driving it, and **how close the emperor's
  defenses are to breaking** (the resource gate as a progress read).
- **Files.** `factions.py`, `promises.py` (consume reputation), `engine.py` (resource gate
  + emperor death victory), `ui.py` (standing screen).
- **Tests.** Multi-axis deltas; resource spend depletes and blocks when empty; reputation
  reward applied; emperor unreachable while resources high, reachable when depleted; killing
  the (stub) emperor wins.
- **Exit criteria.** A single deed produces *different* consequences on different axes, and
  factions visibly react within their means.

### Phase C — Fresh geopolitics at run start (D1, D3)

**Goal.** Every run is a new, *legible* world — a fixed cast in rolled roles.

- **State.** A run-start **world roll** (`wildmagic/world_roll.py` — NEW) seeded from
  `rng_seed`, per §0.1: take the fixed `KINGDOM_ROSTER`, pin founding + proxy, assign
  **3 conquered + 1 rival** from the major-kingdom pool, the rest independent; roll each
  non-emperor **ruler** (name/disposition/traits, placeholders for now); lay out the
  **bounded finite map** (§0.4) and place the imperial capital + the **real emperor** (the
  Phase-B stub's replacement). Seed the `FactionLedger` from the result (one `Faction` per
  kingdom; the Empire is the bloc).
- **Rules.** **Regions parameterized:** `regions.py` becomes templates whose
  *control / tradition / imperial grip* are assigned from the roll; `region_for_zone`
  becomes a lookup into the **bounded finite map** and `imperial_presence` derives from the
  rolled map and live standing (not constants). Each rolled feature emits a **tactical
  affordance** (strategy §5.4) so the player can reason over it. The four entry cities stay
  fixed (D3) with stable names but each sits in a **different kingdom** (D8); their
  *situation* (who controls, local mood) comes from the roll.
- **LLM (Narrator).** Flavor the roll within the fixed identities — a rolled ruler's
  manner, a kingdom's current grievance, a province's mood — and a short,
  affordance-bearing **opening briefing**. (Kingdom names are fixed placeholders, so the
  LLM flavors *rulers and situations*, not the cast.) Factor the folk/Latinate naming
  convention out of `TOWN_SYSTEM_PROMPT` into a shared helper for the rolled ruler names.
- **Legibility.** The run-start briefing screen ("who holds what, who's the rival, where
  wild magic is tolerated"); region control/mood visible on the map.
- **Files.** `world_roll.py` (new), `factions.py` (roster + role assignment),
  `regions.py` (parameterize; geographic wildness), `generation.py` (entry-city
  situation), `prompts.py`/`config.py` (world-roll Narrator purpose), `ui.py` (briefing),
  `AESTHETICS_AND_TONE.md` (reframe open-question names as a fixed-placeholder roster in
  rolled roles).
- **Tests.** Same seed → same role assignment + rulers (determinism); founding/proxy/
  emperor invariant across seeds; every rolled feature carries ≥1 affordance;
  `imperial_presence` derives from standing.
- **Exit criteria.** Two seeds produce recognizably different, strategically distinct
  worlds — same kingdoms, different roles and rulers — readable at a glance.

### Phase D — Backlash events

**Goal.** Standing + spent resources become felt world events.

- **State.** Fill the **05:00 daily tick** (the `wildmagic/simulator.py` scaffold from
  Phase 0.5) with real logic; it consumes deeds/standing and mints promises.
- **Rules.** Faction goals → resource expenditure → promise-ledger events: resistance
  cells (allied `inhabited_site`), riots/crackdowns (hostile events), province tipping
  (standing change re-skinning regions). Off-screen follower assignments resolve in the
  same tick (stub until Phase F).
- **LLM (Narrator).** Situation reports on zone entry; escalate the **named voices** —
  generalize `CLERK_NOTICES` (game_data.py) from a static table into a Narrator chorus
  (clerk, pamphleteer, criers, envoy) keyed to the ledgers and the rolled rulers.
- **Legibility.** Zone-entry situation report; the named-voice documents as found props.
- **Files.** `simulator.py`, `promises.py`, `generation.py` (event realization + voices),
  `game_data.py` (retire static clerk table), `prompts.py`/`config.py` (named-voice
  purpose).
- **Tests.** Threshold + sufficient resources → event minted; insufficient resources →
  no event (escalation self-limits); region re-skin on revolt.
- **Exit criteria.** Pushing the Empire or the people visibly changes the map and the
  voices, and pressure ebbs when factions overspend.

### Phase E — Consequence renderer (props re-aimed)

**Goal.** The world *shows* it remembers — cheap, high perceived-responsiveness.

- **State.** None new; reads the deed ledger + zone history (already in `ZoneSnapshot`).
- **Rules/LLM.** Re-aim `prop_gen.py` from random flavor to **deed-driven detail**:
  memorials/bloodstains where you slaughtered, wanted posters bearing your legend, graffiti
  for/against you, damage in places you wrecked. Reuse the existing background +
  freeze-once-seen swap. Demote pure-flavor prop gen to off/occasional.
- **Legibility.** This *is* legibility, rendered in the world itself.
- **Files.** `prop_gen.py`, `generation.py`.
- **Tests.** A recorded deed in a zone produces the matching consequence prop on revisit;
  freeze-once-seen respected; deterministic/mocked.
- **Exit criteria.** Returning to a zone you changed looks changed.
- **Note.** Deliberately *before* Phase F: cheap, and buys the "world remembers me" feeling
  while the social spine finishes settling.

### Phase F — Bonds, organizations & followers (full ambition, last on purpose)

**Goal.** The deep social system — kept at full scope (strategy §5.3), sequenced last so it
is built **once** on a stable legend/standing/faction spine, not rebuilt.

- **State.** `Bond` on every `NPCProfile`; player-founded **organizations** as
  `Faction(kind=player_org)` (multiple, distinct identities); affiliation graph + ranks;
  follower **postures/assignments**.
- **Rules.** Deterministic bond scoring (traits × legend × personal memory); thresholds
  trigger moments (join/drift/defect/betray/depart); off-screen assignments resolved in the
  Simulator (reeve→taxes, librarian→knowledge, spy→intel). Consequences written back as
  durable traits/notes (`add_trait` + semantic ledger) so they color all future behavior.
- **LLM.** Interpreter only when a heart is on the cusp; Narrator voices the moment and
  fleshes lieutenants. **Math kept invisible** — surfaces as character, never approval bars.
- **Legibility.** A followers/orgs screen; assignment outcomes reported at rest/return.
- **Files.** `bonds.py` (new), `models.py` (NPCProfile.bond), `factions.py` (player orgs),
  `dialogue.py` (bond in context), `simulator.py` (assignments), `effects.py`
  (`change_faction`/`add_trait` already exist), `character.py` + creation scene (origins
  seed starting bonds/standing), `ui.py`.
- **Tests.** Bond thresholds fire the right moments; affiliation ≠ combat faction ≠ bond;
  a love-memory note measurably changes later bond checks; off-screen assignment yields its
  resource.
- **Exit criteria.** The strategy §5.3 sample stories (betrayal, double agent, love-leaves-
  or-stays-changed, promoted-rival) all *emerge* with no bespoke event code.

### Anytime — Run-end chronicle

A Narrator capstone summarizing the run from story beats. No carry-forward. Shippable once
deeds exist (Phase A+); pure legibility/closure.

---

## 4. Dependency graph & sequencing

```
        Phase 0   (micro-loop: Deed+Faction skeleton, debug-triggered tick)
            ▼
        Phase 0.5 (lateral-first: victory decoupled from descent, bounded verticality;
                   day/night + rest + 05:00 tick)                              ← D2,D4
            ▼
        Phase A   (A.1 deterministic deed breadth → A.2 LLM interpretation of ambiguous)
            ▼
        Phase B   (multidim standing, resources, kill-emperor gate) ── spine ends here
            ▼
        Phase C   (world roll: fixed roster / rolled roles+rulers; bounded map; dynamic regions)
            ▼
        Phase D   (backlash: fill the 05:00 tick — resource spend → events, voices)
            ▼
        Phase E   (consequence renderer)   ← cheap; can slot any time after A
            ▼
        Phase F   (bonds/orgs/followers)   ← LAST, full ambition, on the stable spine

   Cross-cutting (every phase): T1 serialize/replay · T2 LLM purpose+audit · T3 legibility
                                T4 perf/batching · T5 tests · T6 GUI+CLI parity
```

Critical path: **0 → 0.5 → A → B** is the spine; nothing downstream is safe to build until
it is stable. 0.5 (lateral-first + the clock) is foundational because the win condition and
the Simulator cadence both depend on it. C is the highest-delight add once B exists. E can
jump earlier for a quick responsiveness win. F is intentionally terminal.

---

## 5. Implementation risks specific to the build

- **Spine churn invalidating F.** *Mitigation:* the whole ordering exists to prevent this;
  do not start F until A/B/C have shipped and their schemas have stopped changing.
- **Deed spam / prompt bloat.** *Mitigation:* causal compression (§1.5) lands in Phase A,
  not deferred; named voices/chronicle read beats, not raw deeds.
- **Decoupling victory from descent + bounding verticality.** Smaller than a teardown — the
  floor-stack machinery stays; we change victory, cap descent per site, and localize depth
  (Phase 0.5). *Mitigation:* do it early with the "descent-never-wins" + "descent-is-bounded"
  invariant tests before breadth assumes the lateral-first model.
- **Region rework breaking existing scenarios.** *Mitigation:* keep region *templates* with
  fixed kingdom identities (D1); only roles/control/grip become dynamic. Land Phase C behind
  a flag and keep the static path until parity; the four entry cities stay stable.
- **Illegible emergence.** *Mitigation:* T3 is a per-phase exit criterion, not a later
  pass.
- **Latency.** *Mitigation:* T4; all new LLM purposes background + batched; reachability
  probe gating (as in `prop_gen`); zero-call common path.
- **Determinism regressions.** *Mitigation:* every phase ships a same-seed reproducibility
  test and a replay round-trip (T1/T5).

---

## 6. File-by-file change index

**New modules:** `deeds.py` (Deed, DeedLedger, StoryBeat), `factions.py` (Faction,
FactionLedger), `legend.py` (LegendLedger + `LEGEND_VOCAB`, §1.3), `bonds.py` (Bond),
`world_roll.py` (run-start geopolitics; the fixed `KINGDOM_ROSTER` + `EMPEROR` + per-run
role/ruler assignment, §0.1), `simulator.py` (the deterministic daily world tick).

| File | Change | Phase |
|---|---|---|
| `engine.py` | `GameState` fields for new ledgers + time (`day`/`turn_of_day`) + **`player_soul_id`** (§1.7) + `simulated_through_turn` cursor (§1.8); 05:00 daily tick hook; **decouple victory from descent**; site-local depth (`current_site_id`, `(site_id, level)` snapshots, §1.8); **kill-emperor victory + Empire-resource gate** (D9); **permadeath → fresh roll** (D6); (de)serialization | 0,0.5,A,B,D |
| `cli.py` | a CLI command + help + rendering for every new player-facing capability; scripted CLI playtests (T6) | all (T6) |
| `actions.py` | **camp/rest** action that advances the clock (D4) | 0.5 |
| `combat.py` | emit deeds (kills by faction, collateral, spared); witness capture | 0,A |
| `effects.py` / `wild_magic.py` | emit deeds from spell outcomes; Interpreter feed | A |
| `lore.py` | generalize extraction → deed *interpretation* of ambiguous deeds (A.2); LLM w/ rules fallback recorded via `interpretation_source` (D5) | A |
| `regions.py` | wildness primarily geographic (keep a small *capped* depth term); parameterize templates; **bounded finite map** (D7) — `region_for_zone` becomes a lookup; `imperial_presence` from rolled map & standing | 0.5,C |
| `generation.py` | bound/localize dungeon-floor gen (no infinite descent); place capital + emperor; entry cities in different kingdoms (D8); consequence/voice props; event realization | 0,0.5,C,D,E |
| `prop_gen.py` | re-aim to deed-driven consequence detail; demote flavor | E |
| `models.py` | `NPCProfile.bond`; bond in dialogue context dict | F |
| `dialogue.py` / `trade.py` | legend + standing + bond in prompt context; price/disposition shifts | A,B,F |
| `promises.py` | consume `Reward.reputation`; faction-minted promises; `capacity_cost` as resource | B,D |
| `npc_quests.py` | faction-driven quests; objective types | B,D |
| `game_data.py` | retire static `CLERK_NOTICES` → dynamic named voices | D |
| `character.py` / creation scene | origins seed starting standing/bonds | F |
| `config.py` / `prompts.py` | new LLM purposes (deed-interpreter, world-roll, named-voices, chronicle) + system prompts | A,C,D |
| `ui.py` (GUI) | clock/day indicator; standing screen; rumor feed; world-roll briefing; followers/orgs screen; run chronicle; `LLM_AUDIT_FILES` — **each mirrored in `cli.py` (T6)** | all (T3,T6) |
| `replay.py` | (de)serialize new ledgers + time; recorded-at-apply-point for new LLM calls | all (T1) |
| `autoplay.py` | exercise deed→standing→backlash; regression checks for illegibility/runaway; descent-never-wins/bounded | 0.5,A,B,D |
| `tests/conftest.py` | gate new LLM purposes to mock/off | all (T2) |
| `AESTHETICS_AND_TONE.md` | reframe open-question names as a fixed placeholder roster in rolled roles | C |

---

## 7. First concrete step

Build **Phase 0** exactly as specified: a stable `player_soul_id`, `Deed` + `Faction`
skeletons, one witnessed-kill deed from `combat.py`, an **idempotent** trivial tick, and the
four legibility touches **in both GUI and CLI** — all serialized and replay-tested. It is
small, it is throwaway-proof (it exercises the real abstractions, including soul identity,
idempotency, and interface parity), and finishing it tells us whether the spine's shape is
right before we build anything on it.
