# Agent Session Log

## Goal
Implement EMERGENT_WORLD_IMPLEMENTATION.md in goal mode, starting at Phase 0
(the micro-loop). Note decisions/assumptions/questions here as I go.

## Current Plan
- **Phase 0 — DONE (2026-06-14).** Full micro-loop shipped. Details below.
- **Phase 0.5 — DONE (2026-06-14).** Lateral-first overworld + time foundations. Details below.
- **Phase A.1 — DONE (2026-06-14).** Deterministic deed breadth, legend ledger, declarative
  consequence rules, causal compression. Details below.
- **Phase A.2 — DONE (2026-06-14).** LLM deed interpreter for ambiguous spell outcomes
  (raise-dead / raze / desecrate / atrocity), with a cheap gate, deterministic fallback,
  and replay fidelity. Details below. Suite **294 passing**.
- **Phase B — DONE (2026-06-14).** Standing consumed: Empire `defense` pool, daily pressure
  depletion, emperor reachability gate + kill-emperor victory, `Reward.reputation` wired.
  Kept deliberately minimal (per Mark). Details below. Suite **301 passing**.
- **Phase E — DONE (2026-06-14).** Consequence renderer: returning to a zone you changed
  looks changed. Details below. Suite **305 passing**.
- **Phase D — DONE (2026-06-14).** Backlash: factions spend finite resources to send
  crackdown patrols / resistance allies in reaction to your standing. Details below.
  Suite **313 passing**.
- **Codex review fixes — DONE (2026-06-14).** Stable faction-**role** abstraction (deeds/
  backlash/pressure now target roles, not literal ids); deed `place_key` (zone+depth, no
  blur); backlash cap guarded per-append; floor-clear no longer sets run victory + GUI
  "THE EMPIRE FALLS"; causal-attribution seam (`owner_soul_id`). Details below.
- **Phase F — DONE (2026-06-14).** Bonds, organizations & followers, bound to roles.
  Details below. Suite **323 passing**.
- **Remaining: Phase C** (fresh geopolitics; the full world roll + region refactor — the
  risky one, best behind a flag with review) and the larger **causal-attribution plumbing**
  (owner-stamping through summons/triggers/timers) + site-local depth rekey.

## Codex review fixes — completed
- **Stable role abstraction (the key one):** `factions.ROLE_TO_KINDS`,
  `FactionLedger.by_kind/ids_by_role/primary`; `DEED_RULES` keyed by **role**
  (`empire`/`resistance`); `engine._resolve_role_deltas` maps a role's deltas onto every
  faction filling it (1:1 on the scaffold, the whole bloc once Phase C seeds the roster);
  pressure/backlash/readouts read the empire/resistance via `primary(role)`. Phase F binds
  to roles + `player_org` kind, **not** placeholder ids — so deep social logic won't set in
  the wrong concrete.
- **Deed location precision:** `Deed.place_key = "<zx>,<zy>@<depth>"`; consequence renderer
  matches on it (dungeon levels no longer blur with the surface).
- **Backlash cap:** the `MAX_PENDING_BACKLASH` guard is now checked before *each* append
  (could previously overshoot by one).
- **Victory presentation split:** clearing local enemies no longer sets `state.victory`
  (that's the run win = toppling the Empire); GUI win copy is now "THE EMPIRE FALLS".
- **Causal attribution seam:** `_deed_attributed_to_player` also credits a kill whose
  source carries `owner_soul_id == player_soul_id`. *Tracked follow-up:* actually stamping
  that owner through summons/triggers/timers/terrain (a real cross-cutting job) — direct
  kills are captured today.
- **Deferred (acknowledged):** full indirect-attribution plumbing; the full Phase C world
  roll + region refactor; site-local `(site_id, level)` snapshots; tighter ambient-provider
  isolation for `smoke_test.py`.

## Phase F — completed (bonds/orgs/followers)
- **New module `bonds.py`:** `Bond` (loyalty/fear/admiration/resentment/ideology +
  `hidden_pressure` + `affiliations`) + `drift_bond` (legend × traits → bond, with a
  `personal` multiplier for first-hand memory) + thresholds.
- **models.py:** `NPCProfile.bond`; `bond_feeling()` (math → words, never numbers); bond +
  affiliations in the dialogue context.
- **engine.py:** `_simulate_bonds` in the daily tick (drift + join/depart **moments** via
  the persistent `follower` trait, with memory write-back; true believers rally to your
  org); `found_organization` (plural `player_org` factions); `followers()`.
- **actions.py / ui.py:** `followers`/`found <name>` commands; `describe_followers`;
  `followers` in `summarize_state`; a retinue line in the GUI panel.
- **Three layers kept orthogonal** (combat faction / `Bond.affiliations` / personal bond),
  per strategy §5.3 — a reeve can be neutral, guild-affiliated, and loyalty 90.
- **tests/test_bonds_and_followers.py** (7 tests): orthogonality; same legend lands
  opposite on rebel vs loyalist; crossing the follow line is a moment; turning butcher
  loses a believer (with memory write-back); memory makes reputation land harder; founding
  an org draws a true believer; followers readout.
- **Note:** bond drift magnitudes are first-pass; tuning is a calibration follow-up (the
  general primitive is what matters — the sample stories emerge from it).

## Phase D — completed (backlash, on the two-pole scaffold)
- **factions.py:** action resources `patrols` (empire) / `cells` (rebellion), seeded.
- **engine.py:** `CRACKDOWN_THRESHOLD`/`UPRISING_THRESHOLD`/`MAX_PENDING_BACKLASH`;
  `_simulate_backlash` (daily: regen + mood drift, then spend a resource to queue an intent
  when standing crosses a threshold; capped queue → self-limiting); `pending_backlash` on
  `GameState`; `_realize_backlash` on zone entry spawns a real Imperial enforcer
  (`crackdown`) or a sworn sympathizer ally (`resistance`) + a situation report;
  `_find_open_prop_tile` gained min/max radius.
- **actions.py / ui.py:** faction **mood** shown in the standing readout; `pending_backlash`
  in `summarize_state`.
- **tests/test_backlash.py** (8 tests): high threat spends a patrol → crackdown; high
  gratitude → resistance; calm → nothing; queue capped (self-limits); mood drifts;
  realize spawns enforcer/ally and clears the queue; end-to-end deeds→standing→crackdown
  arrives in the world.
- **Note (general system):** reactions are "a faction *spends* to act," not threshold
  flips — finite resources with slow regen make pressure ebb and flow.

## Phase E — completed
- **engine.py:** `_DEED_CONSEQUENCE_PROPS` table (bloodstain / memorial / ruin / disturbed
  graves / defiled ground / blasted ground / broken shackles / chalked thanks);
  `_render_deed_consequences` (one mark per kind of public deed per zone, placed once,
  deterministic; notes when it happened ≥3×); folds in the wanted poster;
  `_find_open_prop_tile` (renamed from `_find_poster_tile`). Hooked into `_on_enter_location`.
- **Additive** — the existing LLM flavor-prop generation is untouched (per the decision row).
- **tests/test_consequence_renderer.py** (4 tests): public deed leaves a mark on entry;
  placed once per zone+type (with "more than once" note); secret deed leaves no mark;
  deterministic across runs.

## Phase B — completed (minimal, per Mark)
- **factions.py:** `EMPIRE_DEFENSE_START=20`; the Empire seeds with a `defense` resource pool.
- **engine.py:** `EMPIRE_PRESSURE_RATE`; `_simulate_empire_pressure` (daily, cursor-guarded
  in `_maybe_run_daily_tick` so it can't double-spend) depletes `defense` by the player's
  imperial_threat; `emperor_reachable()`; `_grant_reward_reputation` (consumes
  `Reward.reputation`, keys `faction` → gratitude or `faction.axis`) on quest completion.
- **combat.py:** an `emperor`-tagged entity is protected (blow can't land) while sealed;
  once reachable, killing it sets victory + game_over.
- **actions.py / ui.py:** the Empire-defenses / emperor-reachability read in
  `describe_standing` and the GUI standing panel.
- **tests/test_faction_pressure.py** (7 tests): daily depletion scales with threat; no
  threat → no depletion; gate flips at 0; emperor survives while sealed then dies when
  reachable + wins; full pressure loop opens the road; reward reputation applies (bare id
  and faction.axis); spend depletes and blocks when empty.

## Phase 0 — completed
- **New modules:** `wildmagic/deeds.py` (Deed [mutable], DeedLedger, `DEED_TYPES`/
  `TARGET_TAGS`/`VISIBILITY` vocab), `wildmagic/factions.py` (Faction, FactionLedger,
  `STANDING_AXES`, `FACTION_KINDS`, `seed_phase0_factions`, swap-point name constants).
- **engine.py:** `GameState` gains `deed_ledger`, `faction_ledger`,
  `simulated_through_turn`, `player_soul_id`. New engine methods: `_deed_witnesses`,
  `_record_kill_deed`, `run_world_tick` (idempotent), `_on_enter_location`,
  `_announce_deed_rumors`, `_maybe_place_wanted_poster`, `_find_poster_tile`. Transition
  hooks call `_on_enter_location` (descend/ascend + frontier `_cross_zone_edge`).
- **combat.py:** actor-death path calls `_record_kill_deed` (real combat path → deed).
- **actions.py:** `standing`/`tick` commands in `execute_command`; `describe_standing`;
  `command_help` line; deeds + factions + cursor surfaced in `summarize_state` (this is
  the replay/serialization check).
- **cli.py:** `standing_summary` footer line. **ui.py:** `draw_standing` panel.
- **tests/test_emergent_phase0.py** (11 tests): witnessed kill records a deed; non-
  imperial kill records none; tick applies once + idempotent; secret deed still shifts
  standing; public deed → rumor + wanted poster on entry; command-path kill→tick→standing;
  soul id survives body swap; ledger to_dict/from_dict round-trip; frontier replay
  round-trip; scripted CLI standing readout.
- **Verified manually:** headless GUI `draw_panel`/`draw_standing` render; CLI footer.

## Phase 0.5 — completed
- **engine.py:** tick-model constants `TICKS_PER_ROUND=10` / `TURNS_PER_DAY=1440` /
  `TICKS_PER_DAY=14400` + `DAWN_HOUR=5`; `GameState` clock properties
  `day`/`turn_of_day`/`hour_of_day`/`day_phase` + `clock_label()` (all derived from
  `turn`); `ticked_through_day` cursor; `run_world_tick(day=…)`; `_maybe_run_daily_tick`
  (fires the 05:00 tick per day boundary, called from `finish_player_turn` +
  `_on_enter_location`); `camp_rest(hours=8, until_hour=None)`; **victory decoupled from
  descent** — `descend_stairs` now caps at `max_depth` ("bottoms out") instead of winning.
- **actions.py:** `rest`/`camp`/`sleep` command with `_parse_rest_arg` (8h default,
  `rest <hours>`, `rest until <named time | HH:MM>`); clock in `describe_state`;
  `command_help` updated; time fields in `summarize_state`.
- **cli.py / ui.py:** clock in the CLI footer and the GUI panel.
- **tests/test_time_and_verticality.py** (7 tests): normal descent doesn't win; descent
  bounded + never wins at the cap; clock derives from turn; rest defaults to 8h + recovers;
  rest-until-a-named-time; daily tick fires once/day; same seed → same tick outcome. Plus
  `rest` added to the frontier replay round-trip.
- **Verified manually:** GUI panel + CLI footer clock; `rest`/`rest until dawn`/`rest 2`/
  `rest until 9:30`/bad-arg all behave via the command path.

## Phase A.1 — completed
- **New module `legend.py`:** `LegendLedger` (weighted legend tags per actor soul) +
  `LEGEND_VOCAB` (defiant/butcher/merciful/protector/liberator/destroyer/uncanny) +
  `top_tags`/`tags_for` accessors. Mechanical truth, mirrored to prose in the semantic
  ledger (§1.3).
- **deeds.py:** expanded `DEED_TYPES`; declarative `DeedRule`/`DEED_RULES` table +
  `interpret_deed_rules` (multi-axis standing + legend, scaled by magnitude); `StoryBeat`
  + `DeedLedger.compress()` (additive, clusters same-type deeds into beats); beats
  serialized.
- **engine.py:** general `record_deed(...)` (emit → interpret → record → witnesses
  remember); `_record_kill_deed` now emits `killed_imperials` *and* `killed_civilians`;
  `legend_ledger` on `GameState`; the daily tick applies legend tags + writes a prose
  mirror note + runs `compress()`; `legend_words` helper; player legend added to the
  dialogue context.
- **combat.py:** NPC-death path now records the civilian-kill deed.
- **actions.py / ui.py:** legend in `describe_standing`, the GUI standing panel, and
  `summarize_state` (`story_beats` + `legend`).
- **tests/test_deeds_and_legend.py** (9 tests): multi-axis split + legend; civilian kill
  costs legitimacy + brands butcher; legend accumulates; rules scale by magnitude;
  unknown type → no rule consequences (left for A.2); compress mints a beat without
  mutating deeds; sub-threshold makes none; legend reaches dialogue context; legend
  serialization round-trip.

## Phase A.2 — completed
- **New module `deed_interpreter.py`:** `DeedInterpreterProvider` protocol + Ollama / Mock
  / Auto + `make_deed_interpreter_provider` (off→None); `resolve_deed_interpretation` with
  JSONL audit; `outcome_is_deed_candidate` (cheap gate); `fallback_classify` (conservative
  deterministic classifier); bounded `INTERPRETABLE_DEED_TYPES`.
- **prompts.py / config.py:** `DEED_INTERPRETER_SYSTEM_PROMPT`; `deeds` purpose
  (`get_deeds_provider`/`get_deeds_model`/`ollama_deeds_num_predict`).
- **engine.py:** `record_deed` gains an `interpretation_source` override (rules/llm/fallback).
- **actions.py:** `GameSession` builds the interpreter provider (None in replay); `_cast_wild`
  routes the outcome through `_interpret_spell_deed` (replay reuses the recorded verdict);
  `_record_spell_deed` records the deed (`source="spell"`).
- **conftest.py:** `WILDMAGIC_DEEDS_PROVIDER=off`. **ui.py:** `deed_interp_audit.jsonl` in
  `LLM_AUDIT_FILES`.
- **tests/test_deed_interpreter.py** (6 tests): gate skips ordinary spells; fallback
  conservative; off→fallback; spell→deed via interpreter (+ rules consequences/legend);
  ordinary spell → no deed; replay reproduces the interpreted deed.

## Decisions Made
| Time | Decision | Reason |
|---|---|---|
| Phase B/E | **Keep victory + Empire-depletion mechanics minimal** (per Mark): a single `defense` pool, linear pressure depletion, one reachability gate, one kill check. No richer multi-route gating for now — victory is a distant-horizon concern. **Prioritize the emergent *story* layers** (E consequence renderer, D backlash, F bonds) over victory polish. | Mark: "go a little light on mechanics for victory and empire depletion … mostly interested in the emergent story elements." |
| Phase E | The consequence renderer is **additive and deterministic**: it places deed-driven consequence props (bloodstains/memorials/ruin/uncanny residue/posters) when you enter a zone where a public deed happened. It does **not** remove or demote the existing LLM flavor-prop generation (which Mark liked) — the two layers coexist. | Delivers "the world remembers" with zero new LLM risk; doesn't tear out a feature Mark valued. Demoting flavor props is available later if wanted. |
| Phase 0.5 | Time model (per Mark): the floor unit is a **tick**; **10 ticks = 1 round** (~1 minute, a standard action), **1440 rounds = 14400 ticks = 1 day**. Constants `TICKS_PER_ROUND=10`, `TURNS_PER_DAY=1440` (rounds), `TICKS_PER_DAY=14400`. `turn_of_day 0 = 05:00` (dawn). Clock fields (`day`/`turn_of_day`/`hour_of_day`/`day_phase`) are **derived properties** of `state.turn`. | Several code paths bump `state.turn` directly; deriving the clock keeps them in sync and replay-safe. Tick-floor leaves headroom for actions up to 10x faster than a move; until such sub-round actions exist the clock counts rounds (1 action = 1 round), then moves to a real tick accumulator. |
| Phase 0.5 | `rest`/`camp` defaults to **8 hours** (per Mark), or `rest <hours>` / `rest until <dawn\|noon\|HH:MM\|…>`. It restores MP fully + HP proportional to time rested, and fires the daily tick only if the rest crosses 05:00. | Matches the real-world "8h sleep" feel; the simulator still runs once daily at dawn, so resting past 05:00 is what triggers it. |
| Phase A.1 | Deed consequences live in a **declarative `DEED_RULES` table** (deed type → per-faction per-axis coefficients + legend coefficients, scaled by magnitude). Emission sites only describe *what happened*; `interpret_deed_rules` decides *what it means*. | The general system the strategy asks for: "one deed → different consequences along different axes" lives as data, not bespoke code; adding a deed type is a table entry. The same seam is where the A.2 LLM plugs in (it classifies; the table still scores). |
| Phase A.1 | **Spell-outcome deeds** (`cast_atrocity`/`raised_dead`/`desecration`) are **not** rules-emitted from `effects.py` — there is no clean deterministic signal (effect types are `summon`/`transform_entity`/… and outcomes are LLM-generated). They're routed to the **A.2 LLM interpreter**, which is the right tool for ambiguous/novel outcomes (D5). The rule table already defines their consequences for when the LLM classifies one. | Avoids brittle effect-type sniffing; matches "rules for clear-cut, LLM for ambiguous." A.1 rules-emits only the unambiguous combat deeds (imperial kills, civilian kills). |
| Phase A.1 | `spared_enemy` deed type exists in the table but has **no emission trigger yet** (no surrender/disengage mechanic to detect cleanly). | Deferred until there's a reliable signal; noted so it's not mistaken for a gap. |
| Phase A.2 | The deed interpreter **classifies into the bounded `INTERPRETABLE_DEED_TYPES`** (raised_dead/razed_building/desecration/cast_atrocity); consequences still come from the deterministic `DEED_RULES` table, not from LLM-invented numbers. | Keeps the world coherent and bounded, and keeps consequences replay-safe (the LLM supplies only the semantic judgment it's good at). |
| Phase A.2 | The verdict is recorded on the **existing `wild_magic` action record** (`wild_magic["deed"]`) and replayed from there — **no new replay channel / version bump**. | Reuses the established record-at-apply-point pattern with minimal surface; replays reproduce the deed with zero model calls. |
| Phase A.2 | The interpreter runs **synchronously**, gated by a cheap keyword check so ordinary spells never call it. | The gate makes calls rare, and the spell command is already an LLM pause point; simpler + replay-trivial vs. a background executor. Can move to background if latency bites — noted. |
| Phase A.2 | The deterministic **fallback is conservative** (only strong, specific phrasing classifies a deed) while the **gate is broad**. | Offline/test/replay output stays low-false-positive and deterministic; the live LLM adds recall on borderline cases. `MockDeedInterpreterProvider` mirrors the fallback so the LLM path is testable without a backend. |
| Phase 0.5 | The daily 05:00 tick fires automatically on each day-boundary crossing, tracked by a `ticked_through_day` cursor (init 1), checked in `finish_player_turn` and on location entry. The debug `tick` command stays. | Matches D4 (tick at 05:00, not zone-cross). The cursor is stateful so it catches up even if a turn advance bypassed the hook; `run_world_tick` is idempotent so an extra debug tick can't double-apply. |
| Phase 0.5 | `camp`/`rest` jumps to the next morning, restores MP fully + 1/4 HP, and runs the due daily tick. Encounter-during-rest ("vulnerability window") is **not** simulated yet. | Keeps the action simple and deterministic for now; the danger flavor is aspirational and can layer on later. |
| Phase 0.5 | **Deferred:** the site-local `(site_id, level)` snapshot rekey (§1.8). Victory is decoupled from descent and descent is **capped at `max_depth`** (the per-site cap → "bottoms out"), so depth is already bounded/non-ever-deepening today. | The multi-site storage rekey is only needed once the overworld has multiple independent vertical sites (Phase C); doing it now is speculative refactoring against the current single-stack model. Bounding + victory-decoupling deliver 0.5's *behavioral* commitment without it. |
| Phase 0 | `player_soul_id` defaults to the constant `"player"` (a GameState field). | The starting player entity always has `id="player"`, and body-swap turns the old body into a husk that still exists — the id is already a stable soul handle. Deeds/legend key off it; `player_id` keeps following the controlled body. |
| Phase 0 | Seeded factions: `empire` ("the Grand Empire", kind `empire_core`) and `rebellion` ("the Unbound", kind `resistance`). 2 active axes: `imperial_threat` (on empire), `gratitude` (on rebellion). | Matches Phase-0 spec (Empire bloc + one rebel pole, 2-axis standing). Names are placeholders per D1. Full `STANDING_AXES` constant defined for later phases. |
| Phase 0 | Standing readout is a shared `standing` command in `actions.execute_command` (not a CLI-only path) plus a GUI panel line and a CLI footer line. | Both GUI and CLI dispatch through `execute_command`; one command satisfies T6 parity. |
| Phase 0 | The daily tick is triggered by a debug `tick`/`simulate` command (free action, no turn). | Phase 0 spec: temporary debug trigger; the real 05:00 cadence lands in Phase 0.5. |

## Assumptions
| Assumption | Confidence | What would invalidate it |
|---|---|---|
| New ledger state is "serialized" via `summarize_state` + deterministic replay (the repo has no save/load; replay re-runs the command sequence). `to_dict`/`from_dict` exist on the new types for hygiene and the summary. | High | If a real save/load is added later it must (de)serialize these ledgers; the methods are already there. |

**Confirmed with Mark (2026-06-14):** `Deed` is mutable (not frozen). Every imperial kill
records a deed and shifts standing — even unwitnessed ("secret") ones; `visibility` only
gates rumor/poster legibility. Witness detection is a simple distance check for Phase 0.
Faction names "the Grand Empire" / "the Unbound" are placeholders — kept swappable as
`EMPIRE_NAME` / `REBELLION_NAME` constants at the top of `factions.py`.

## Questions for Mark
### Blocking
_(none)_

### Non-blocking
_(none open)_

## Deviations from Original Plan
| Deviation | Reason | Risk |
|---|---|---|
| `Deed` mutable instead of `frozen=True`. | Idempotency `applied` flag + `rumored` flag need mutation. | Low — both flags are write-once-ish and only touched by the simulator/legibility layer. |
| No `StoryBeat`/`compress()` in Phase 0. | They belong to Phase A (causal compression); Phase 0 stays minimal. | None — additive later. |

## CLI Playtest 2026-06-14 (Track A)

Ran the whole Phase 0–F spine end-to-end via CLI + small real-engine drivers (real code
paths only — teleport-to-foe + real `spark`/`rest`/zone-entry, no logic reimplemented).

**Result: spine is sound.** Confirmed working: deeds→standing→legend, the kill-emperor
pressure gate (defenses deplete one/day at threat 0.2), backlash (5 kills → threat 1.0 →
patrol spent, mood `alarmed`, crackdown realizes on floor entry: "An Imperial patrol has
tracked you here" + enforcer + rumor), the consequence renderer (witnessed kill → bloodstain
+ wanted poster on return, **persist across moves** — the set_dressing-overwrite fix holds),
the **live LLM deed interpreter** (`--provider auto`: wild "raise the dead" → Ollama verdict
`raised_dead` mag 0.6 → `uncanny` legend; audited, no technical failure), and bonds/orgs
(found org → liberator legend → NPCs cross the follow line, believers pledge; `personal`
memory multiplier shows as a day-9-vs-13 split). Replay round-trip: **Final summary matched:
True**. Suite **324 passing** (added a spark-kill regression test).

### Bug FIXED — ranged/standard offensive spells didn't attribute kills (high impact)
`cast_standard_bolt` (spark), `cast_standard_frost` (frost), and the `damage_nearest` item
effect called `damage_entity(...)` **without `source=player`**. `_record_kill_deed` gates on
`_deed_attributed_to_player(source)`, so **kills via the most common ranged attack produced
no deed at all** — no standing, no legend, no pressure, no backlash. The entire emergent loop
was unreachable unless you killed everything in melee. Fixed by threading `source=player`
(engine.py spark/frost; items.py `damage_nearest`). Deterministic + replay-safe (replay still
matches). Left untouched (genuinely ambiguous, = the tracked indirect-attribution follow-up):
environmental fire/poison tiles, DoT status ticks, and traps — those carry no owner yet.

### FINDING (design, needs Mark) — bond differentiation is unwired
The bond drift seam reads `NPCProfile.traits` against `_TRAIT_AFFINITY` (downtrodden/
oppressed/rebel/poor/faithful_friend) and `_TRAIT_AVERSION` (loyalist/imperial/pious/devout/
fearful) — but **no seeded NPC anywhere carries one of those traits** (their traits are
open-ended flavor: "shrewd", "warm", "talkative", "hopeful", "quietly subversive"). So
affinity=aversion=1.0 for everyone and **every NPC drifts identically** — a positive legend
turns the whole town into maxed-out (100/100/100) devoted followers in lockstep. The
documented emergence ("the same legend makes a rebel adore you and a loyalist fear you")
cannot occur. The *mechanism* is correct; it just has no differentiated **input**.
Recommended fix (deferred — it's a world-design call about who leans which way, and ties
into the Phase C faction roster): seed each NPC with one disposition trait from the
affinity/aversion vocab, distributed (some loyalists/pious, some downtrodden/rebel), derived
from role + region (occupied frontier folk lean oppressed; garrison/clergy lean loyalist/
pious). Until then, bonds work but are uniform. *No code changed for this — surfaced for a
distribution decision.*
