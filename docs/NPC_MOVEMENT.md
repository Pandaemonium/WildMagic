# NPC Movement and Escort Strategy

NPC movement should make the world feel inhabited without creating a brittle "party
system" or a second game engine. Characters move because of general motives,
relationships, physical constraints, perception, faction conflict, fear, orders, and local
terrain. The player may persuade someone to travel with them, but the engine remains the
authority over who can move, what they can sense, where they can stand, and how far a
relationship can bend.

The goal is not to script special cases. The goal is to make small movement primitives that
combine well:

- follow a moving person
- hold a place
- avoid danger
- engage a sensed threat
- flee from a sensed threat
- yield space to someone with priority
- cross a boundary with someone already following
- remember a movement relationship across save/load

Every new movement rule should be judged by whether it supports many future situations:
escorts, freed captives, hired guides, frightened civilians, faction patrols, summoned
helpers, bodyguards, deserters, spies, prisoners, and magically influenced behavior.

## Design Principles

The engine owns movement truth. LLM systems may judge persuasion or provide flavor, but
they do not directly move NPCs, create escort authority, override collision, or decide
combat legality.

NPC movement should be relationship-aware but not relationship-only. A devoted scholar may
follow but avoid combat. A neutral guard may agree to escort you and still keep their own
faction identity. A fighter may defend a follower without becoming a universal ally. A
summoned entity may be tactically allied without having a social bond.

The system should prefer derived behavior over stored flags when the derivation is stable:
combat stance from role/traits/tags, faction hostility from identity and faction ledgers,
noncombatant behavior from role, and recruitment willingness from bond. Store state only
when the world has made a durable commitment, such as an accepted escort relationship or a
stay anchor.

Movement must be perception-gated unless there is a specific engine-owned reason not to
be. Ordinary followers should not have through-wall radar. If an NPC acts on a threat, the
threat should be sensed, adjacent, remembered through a declared faction conflict, or
otherwise exposed through an explicit state primitive.

The GUI and CLI must stay synced. Any player-facing movement command, recruitment prompt,
escort toggle, pending appeal, or readout must route through `wildmagic.actions.GameSession`
and be reachable from both front ends.

## Existing Layers

Wild Magic already separates character relationships into layers:

- `Entity.faction`: tactical combat alignment and player-relative hostility scaffolding.
- `Entity.identity` and `Entity.role`: typed character identity used by faction and combat
  interpretation.
- `NPCProfile.bond`: personal relationship with the player.
- `Bond.affiliations`: organization or faction membership.
- `Entity.tags` and `Entity.traits`: broad descriptive and semantic labels.
- `Entity.details`: engine-owned per-entity state for feature-specific data.

Escort movement should add another layer rather than overloading one of these. A person
can be neutral, sympathetic, a member of a faction, personally loyal, afraid of the player,
and currently under a "stay here" order all at once.

## Escort State

The authoritative escort relationship should live in `Entity.details["escort"]`, not in a
plain tag or narrative trait. Wild magic can add tags and traits, so neither should be the
source of authority for "this character accepts direct movement commands."

Recommended shape:

```json
{
  "relationship": "escort",
  "mode": "follow",
  "anchor": {
    "x": 12,
    "y": 8,
    "place_key": "0,0@1"
  },
  "source": "recruited",
  "joined_turn": 42
}
```

`relationship` means the character has accepted direct escort commands. Once set, the
player may toggle follow/stay without another LLM call.

`mode` controls movement:

- `follow`: the NPC tries to remain near the player and may cross boundaries with them.
- `stay`: the NPC holds an anchor in the current place and does not follow across
  boundaries.

`anchor` records where a staying NPC should return or hold. Use `GameState.current_place_key()`
or an equivalent depth-aware place key, not only overworld zone coordinates.

`source` is optional but useful for debugging and future content. Examples: `recruited`,
`freed`, `summoned`, `scripted`, `hired`.

Tags may still be used for presentation if useful, but any such tag must be treated as a
display or flavor label. It must not grant command authority by itself.

## Relationship and Recruitment

The bond remains the social gauge. It should affect willingness, drift-away risk, and
future reactions, but it should not be identical to escort state.

Recruitment should use three bands:

- clear yes: the engine accepts immediately
- clear no: the engine refuses immediately
- marginal: the NPC asks why they should join, and the player's free-text appeal is judged
  by a structured provider

The deterministic score should come from stable state: loyalty, admiration, ideology,
resentment, fear, disposition, memory, role, and possibly immediate context. The score is a
gate, not a final source of mutation. Only engine code sets escort state.

Marginal appeals should use one model call for the judgment, not one call to generate the
question and another to judge the answer. The question can be engine-templated from role,
bond, fear, and current danger. This keeps the flow fast, replayable, and easier to test.

The appeal provider should return bounded structured JSON. The engine should clamp any
bond delta, apply it transactionally, and then decide whether escort state changes.

## Movement Modes

### Follow

A following escort tries to stay close to the player without occupying the player's tile.
The ideal distance is adjacent or near-adjacent, with enough slack to avoid jitter in narrow
spaces.

Follow movement should:

- path toward the player when too far away
- avoid stepping onto blocked or dangerous tiles unless a rule explicitly allows it
- yield or swap when blocking the player's next movement would be frustrating
- respect rooted, webbed, stunned, frozen, slowed, and similar status constraints
- update `last_move_delta` like other actors so behavior modifiers remain consistent
- avoid double-acting through generic ally/NPC passes

### Stay

A staying escort holds an anchor. They may drift a small distance to avoid danger or defend
themselves, but their default movement is back toward the anchor, not toward the player.

Stay movement should:

- keep the place/depth anchor stable
- re-anchor when the player explicitly issues `stayhere`
- avoid crossing zone or floor boundaries
- defend or flee according to stance if a sensed threat closes
- degrade gracefully if the anchor is blocked, out of bounds, or no longer walkable

## Combat Stance

Come/stay controls movement intent. The NPC's nature controls fighting.

Recommended stance values:

- `aggressive`: actively pursues or attacks sensed threats within a leash
- `balanced`: engages nearby sensed threats, otherwise preserves escort movement
- `timid`: does not initiate; flees from sensed danger or stays close to the player

Stance should be derived from role, traits, tags, and noncombatant checks. It should not
require bespoke NPC classes.

Examples:

- soldiers, guards, rebels, hunters, mercenaries: aggressive
- ordinary capable adults, guides, traders with weapons: balanced
- scholars, beggars, children, frail characters, explicit noncombatants: timid

Neutral escorts need a companion-specific threat selector. Current faction hostility does
not automatically make a neutral escort hostile to the player's enemies. For escort AI,
"threat" should include sensed actors hostile to the escort, hostile to the player, or
currently attacking either of them.

## Movement Priority and Collision

Companions can easily become frustrating if they block doors, stairs, corridors, or the
player's target tile. Movement priority should be explicit.

Suggested priority order:

1. Player action.
2. Immediate hostile attacks.
3. Escorts yielding or keeping formation.
4. Ordinary enemy and ally turns.
5. Neutral civilian movement.

When the player tries to move into a following escort, the engine should prefer a yield or
swap before reporting that the escort is in the way. This should be conservative: only for
established escorts, only when the destination is safe enough, and never through walls or
locked doors.

## Boundary Travel

Following escorts should travel with the player across boundaries when they are in the
same active place and reasonably close enough to count as present. Staying escorts remain
behind.

Boundary travel must be snapshot-safe:

- collect following escorts before saving the old zone or floor
- remove them from the old active entity table before the snapshot is written
- load or generate the destination
- place escorts on open tiles near the player's entry point
- avoid duplicating an escort in both the old snapshot and the new active zone
- preserve their `NPCProfile`, bond, inventory, statuses, details, and identity

This applies to overworld edge crossings and should also apply to stairs unless the design
explicitly documents that vertical escort travel is deferred.

## Save, Replay, and Inspection

Escort state should survive normal entity serialization because `Entity.details` is already
serialized. Persistence still needs tests because movement state crosses zone and floor
snapshots, where duplication bugs are easy to introduce.

Replay records must include any LLM persuasion verdict at the action record where it is
applied. Replay must not call the persuasion provider again.

`state_view.py` should expose escort state in structured summaries so CLI inspection, GUI
inspection, replay summaries, and future model contexts read one shared representation.

Suggested summary fields:

```json
{
  "escorts": [
    {
      "id": "npc_12",
      "name": "Mara",
      "mode": "follow",
      "stance": "timid",
      "faction": "neutral",
      "anchor": {"x": 12, "y": 8, "place_key": "0,0@1"}
    }
  ]
}
```

## Player Commands

Commands should live in `actions.py` and call engine helpers. The GUI should route buttons
to the same commands.

Recommended commands:

- `comewith <target>`: ask or order a character to follow.
- `stayhere <target>`: set an established escort to stay at the current tile or their tile.
- `appeal <text>`: answer a pending recruitment appeal.
- `followers` or `retinue`: list social followers, escorts, and player organizations.

Free toggles should be free only after the escort relationship exists. A new recruitment
attempt should have an explicit turn contract. If an appeal is pending, settling it should
consume exactly one turn on an intentional join/refusal outcome, while technical provider
failure should not consume a turn.

`pending_appeal` should follow the same discipline as `pending_trade`: a paused player beat
with clear ownership of the eventual turn settlement. If multiple pending interaction types
become common, replace separate slots with a single typed pending-interaction state.

## UI Expectations

The GUI inspect panel should expose the same commands as the CLI:

- show `Come with me` when a character is recruitable or currently staying
- show `Stay here` when an established escort is following
- show appeal prompts in the log and route the next appeal input through `appeal`

If appeal judgment can call Ollama, the GUI must treat `appeal` as a blocking LLM command
and run it on the existing worker path. The interface should not freeze while waiting.

## Validation

`GameEngine.validate_state()` should catch escort-specific corruption:

- escort data is not a dict
- mode is not `follow` or `stay`
- anchor is malformed
- anchor place does not match any sensible location format
- dead or non-character entities have active escort state
- an escort appears both in an old snapshot and the current active entity table
- a following escort is stored in a different place than the player without being in a
  snapshot intentionally

Validation should be strict enough to catch duplication and malformed state, but not so
strict that old saves or unusual magic-created characters cannot be repaired.

## Implementation Plan

Remove this section after the NPC movement work lands and the permanent strategy above has
been updated to reflect the shipped behavior.

### 1. Companion Helpers and State

Add `wildmagic/companions.py`.

Core helpers:

- `escort_state(entity) -> dict | None`
- `is_escort(entity) -> bool`
- `escort_mode(entity) -> str | None`
- `set_follow(engine, entity, source="command")`
- `set_stay(engine, entity, anchor=None)`
- `clear_escort(entity)`
- `combat_stance(entity, profile=None) -> str`
- `recruitment_score(profile, entity) -> float`
- `escort_summary(entity, engine) -> dict`

Keep the module leaf-like. It may import `models`, `bonds`, and pure normalization helpers,
but should not import UI or provider modules.

Add state validation for malformed escort details.

### 2. Engine Commands

Add engine methods:

- `find_escort_target(selector: str) -> Entity | None`
- `command_follow(selector: str) -> bool`
- `command_stay(selector: str) -> bool`
- `start_recruitment(entity) -> RecruitmentOutcome`
- `resolve_pending_appeal(text, verdict=None) -> AppealOutcome`

Mode toggles for existing escorts should not call an LLM. Recruitment should use score
bands and only enter pending appeal for marginal cases.

### 3. Action Layer and Replay

Add command parsing in `actions.py`:

- `comewith`, `come`, `followme`, `join`
- `stayhere`, `stay`, `waitthere`
- `appeal`

Add an `appeal` field to `ActionResult` and replay records, or a generic
`structured_interaction` field if that better fits the existing record shape.

Make replay inject recorded appeal verdicts rather than calling the provider.

Update `command_help()` and `describe_followers()`.

### 4. Persuasion Provider

Add `wildmagic/persuasion.py`, modeled on `trade.py`.

Provider shape:

- `AppealResolution`
- `AppealProvider`
- `OllamaAppealProvider`
- `MockAppealProvider`
- `AutoAppealProvider`
- `make_appeal_provider`
- `resolve_appeal`
- `write_appeal_audit_log`

JSON fields:

- `decision`: `join` or `refuse`
- `reply`: short NPC line shown to the player
- `bond_delta`: bounded map of bond axes
- `reason`: concise audit/debug reason

Technical failures must not consume a turn. Intentional refusals should consume the pending
appeal turn.

Update `config.py` and `docs/MODEL_CONFIG.md` for provider/model routing. The simplest
default is to inherit dialogue provider/model settings unless `WILDMAGIC_APPEAL_*` is set.

### 5. Companion AI

Add `_companion_turns()` in `ai.py` and call it before ordinary ally/NPC turns.

Ensure generic `_ally_turns()` and `_npc_turns()` skip established escorts so companions do
not act twice.

Implement:

- sensed threat collection
- stance-based engagement/fleeing
- follow-distance movement
- stay-anchor movement
- leash limits
- status constraints
- no through-wall targeting

Add a conservative yield/swap helper for the player moving into a following escort.

### 6. Boundary Travel

Add shared carry helpers in generation/engine code:

- collect following escorts near the player
- remove them before `_save_current_zone()` or `_save_dungeon_floor()`
- restore them after `_load_or_generate_zone()` or `_load_dungeon_floor()`
- place them near entry with stable ordering

Cover both overworld edges and stairs unless explicitly deferred.

### 7. State Views and UI

Update `state_view.py` summaries with escort data.

Update CLI `inspect` output as needed.

Update GUI inspect buttons:

- `Come with me`
- `Stay here`
- appeal prompt/input behavior

Add `appeal` to the GUI blocking command list if it can call Ollama.

### 8. Tests

Add or extend focused tests:

- recruitment clear yes/no/marginal banding
- mode toggles do not call providers after escort state exists
- pending appeal turn contract
- appeal replay does not call provider
- save/load preserves escort details
- following escorts cross zone edges without duplication
- following escorts cross stairs without duplication
- staying escorts remain behind
- stance derivation
- companion targeting is perception-gated
- companions do not act twice
- neutral combat-capable escorts defend without becoming globally allied
- timid escorts flee or stay close instead of initiating
- player movement can yield/swap with following escorts

### 9. Playtest

Run:

```powershell
python -m wildmagic.smoke_test
python -m wildmagic.cli --provider mock --scenario test_chamber --seed 7 --no-render --command "inspect" --command "comewith <target>" --command "appeal I can keep you alive and I need your eyes" --command "move east" --command "stayhere <target>" --command "inspect"
```

Also run a short Ollama appeal test after the mock flow is stable, then inspect the appeal
audit log for parse failures, excessive bond deltas, and generic replies.
