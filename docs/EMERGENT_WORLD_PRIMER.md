# Emergent World — a 5-minute primer

A quick orientation to the systems that make the world *react to what the player does*. For
the full design see `EMERGENT_WORLD_STRATEGY.md`; for the build/decisions see
`EMERGENT_WORLD_IMPLEMENTATION.md` and `implementation_session_log.md`.

## The one big idea

> The player's **deeds** build a **legend**, the legend moves **standing** with the world's
> powers and **bonds** with its people, and once a day a deterministic **Simulator** turns
> all of that into felt consequences — backlash, allies, a world that visibly remembers.

Nothing here is a scripted event. We built **general primitives**; the stories (a province
revolting, a follower leaving over what you became, the Empire hunting you) *emerge* from
their interaction.

## The loop

```
   act  ──▶  Deed  ──▶  interpret  ──▶  Simulator (daily, 05:00)  ──▶  show  ──▶  affects play
 (kill,    (recorded   (rules, or     · standing shifts            (rumors,    (harder/easier,
  spell,    fact)       LLM for the    · Empire defenses spent       posters,    new foes/allies,
  free a               ambiguous)      · backlash minted             memorials,  who helps you)
  captive)                             · every NPC's bond drifts     followers)
```

## The pieces (and where they live)

- **Deed** (`deeds.py`) — the atom: *what happened*, plus its proposed consequences. Bound
  to the player's **soul**, not the body they're wearing (body-swap doesn't launder your
  reputation). Recorded the instant it happens; applied **once** by the daily tick.
- **Consequences are a table, not code** (`DEED_RULES`) — one deed lands differently on
  different axes: killing imperials raises rebel *gratitude*, imperial *threat*, and your
  *defiant* legend all at once. Add a deed type = add a table row.
- **Legend** (`legend.py`) — a few weighted tags (defiant, butcher, merciful, uncanny…) that
  are *the connective tissue*: dialogue, rumors, and NPC feelings all read it.
- **Standing is multidimensional** (`factions.py`) — never one "reputation" number. Powers
  are tracked by **role** (the Empire bloc, the resistance, your own orgs), so it all
  generalizes when the world gets richer.
- **The Simulator** (the daily 05:00 tick in `engine.py`) — the single heartbeat. It applies
  deeds, spends the Empire's finite defenses toward the win, mints **backlash** (a crackdown
  is "the Empire *spends a patrol*", not "fear > 70"), and drifts every NPC's bond.
- **Bonds & followers** (`bonds.py`) — each NPC has a *personal* relationship to the player,
  separate from their combat side and their guild. The same legend makes a rebel adore you
  and a loyalist fear you; cross a threshold and they follow — or, if you turn butcher, leave
  (and *remember* leaving, which colours them forever).
- **The world shows it** (Phase E + D) — revisit a place you changed and find bloodstains,
  ruin, or a wanted poster bearing your legend; enter a zone and an Imperial patrol may be
  waiting, or a sympathizer may join you.

## Where the LLM fits (and where it doesn't)

The **deterministic skeleton runs with zero model calls.** The LLM is used only for what
it's best at and always has a deterministic fallback:
- **Interpreter** — judges *ambiguous* spell outcomes ("was that an atrocity? a
  desecration?"). Clear-cut deeds (a kill) never call it.
- **Narrator** (prose) — rumor lines, an NPC greeting you by reputation.

Everything the LLM decides is **recorded at its apply point**, so replays are free and the
tests/skeleton never need a backend.

## See it / poke it

In the GUI side panel or via CLI commands (both go through the same path):
- `standing` — how each power regards you, your legend, and how close the Empire's defenses
  are to breaking.
- `followers` — who follows you and the organizations you've founded; `found <name>` raises
  your own banner.
- `rest` / `camp` — pass time (the Simulator runs at 05:00); `tick` is a debug shortcut to
  run it now.

## Guardrails we kept

Determinism + replay-safety, GUI **and** CLI parity for every reader, finite resources so
pressure ebbs and flows, and a strict split between three orthogonal layers (combat side ≠
org membership ≠ personal bond). Victory (toppling the Empire) is deliberately kept minimal
for now — the focus is the emergent story, not the endgame math.
