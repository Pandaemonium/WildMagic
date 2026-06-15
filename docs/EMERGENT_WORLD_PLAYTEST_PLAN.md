# Emergent World — playtest plan

How to exercise the Phase 0–F systems (deeds → legend → standing → daily Simulator →
backlash + consequence props + bonds/followers). Two tracks: hands-on CLI, then an
overnight Qwen3.5 auto-playtest. See `EMERGENT_WORLD_PRIMER.md` for what the systems are.

## Key facts that shape testing
- **The Simulator runs once per in-game day at 05:00.** A day is `TURNS_PER_DAY = 1440`
  turns, so in normal play the daily tick (pressure depletion, backlash, bond drift)
  **almost never fires unless you `rest`/`camp`** (which jumps ~8h, crossing 05:00) or use
  the debug `tick`. *This is the single most important thing to make the autoplayer do.*
- **Best scenarios:** `empire_compound` (imperial enemies → kill deeds → standing/legend/
  backlash), `frontier` (zone crossings → consequence renderer + backlash arrival),
  `bazaar`/`archive` (NPCs present → bonds/followers).
- **Deterministic vs LLM:** the spine is deterministic (`--provider mock` exercises it
  fully). The **deed interpreter** (ambiguous spell outcomes) only runs under
  `--provider auto/ollama` with `WILDMAGIC_DEEDS_PROVIDER` not `off`.

## Track A — hands-on CLI (deterministic, fast, run first)

Use `python -m wildmagic.cli --scenario <s> --provider mock --no-render --command "..."`
(repeat `--command`), or pipe a script. Self-check signals via the `standing` / `followers`
readouts and the log lines.

1. **Deeds → standing → legend → kill-emperor gate** (`empire_compound`): move into imperial
   enemies to kill them; `standing` (expect `imperial_threat`/`fear` up on the Empire,
   `gratitude`/`legitimacy` on the resistance, a `defiant` legend); `rest until dawn` a few
   times; `standing` again (Empire **defenses** should tick down toward "within reach").
2. **Backlash** (`empire_compound` → then move to a fresh room/zone): after threat ≥ ~1.0,
   `rest until dawn` to let the Empire spend a patrol; on entering a zone expect "An
   Imperial patrol has tracked you here" + an `Imperial enforcer`. High resistance gratitude
   → a "sworn sympathizer" ally instead.
3. **Consequence renderer** (`frontier`): kill an imperial in a zone, cross a map edge and
   come back → expect a `bloodstained ground` prop + an `Imperial wanted poster` (and a
   "Word on the road" rumor). Confirm they are **not** regenerated/overwritten each move
   (the bug we just fixed).
4. **Deed interpreter** (`--provider auto`, Ollama up): `cast raise the dead to walk`, then
   `tick`, then `standing` → expect an `uncanny` legend + a `raised_dead` deed. Try
   `cast bring the tower down in rubble` (razed_building). Ordinary spells must record no
   deed.
5. **Bonds / followers / orgs** (`bazaar`/`archive`, has NPCs): `found the Ashen Hand`;
   build a pro-people legend; `rest until dawn` repeatedly; `followers` → expect an NPC to
   come to follow you and (if a believer) pledge to the org. (Natural legend-building is
   slow; this one is most convincing via a longer session.)
6. **Replay safety:** add `--record logs/pt.json` to any of the above, then
   `python -m wildmagic.replay logs/pt.json` → "Final summary matched: True".

Acceptance: each system shows its signal; no tracebacks; replay matches.

## Track B — overnight Qwen3.5 auto-playtest

**Prep (code, do first — the autoplayer can't reach these systems yet):** in
`wildmagic/autoplay.py`, teach the chooser the new verbs and when to use them:
- Add to `COMMAND_SURFACE` and `EXACT_VERBS`: `standing`, `followers`, `found <name>`,
  `rest` / `rest until dawn`, and the debug `tick`.
- Add a coverage-goal bullet: *"Periodically `rest until dawn` to let a day pass so the
  world reacts; check `standing` and `followers` to read consequences; on `empire_compound`
  fight imperial soldiers to build a legend; once notable, `found` an organization."*
- Keep `rest` rate-limited in guidance (it skips time) so episodes still see live play.
- Re-run the trim test suite after editing.

**Invocation (example — tune hours/scenarios to the box):**
```
python -m wildmagic.autoplay --agent ollama --provider auto --hours 8 \
  --scenario empire_compound --scenario frontier --scenario bazaar \
  --max-turns 400 --episode-minutes 20 --drain-background \
  --run-id emergent_overnight
```
- `--agent ollama` = Qwen3.5 chooses commands; `--provider auto` = real wild-magic + deed
  interpreter (tests the LLM paths). Use `--provider mock` for a deterministic spine-only
  soak.
- `--max-turns 400` (up from 120) gives episodes long enough that a few `rest`s cross
  multiple days and the Simulator actually runs.
- Mind the A750 + the **localhost→127.0.0.1** stall (see memory) — point Ollama hosts at
  `127.0.0.1` or expect ~2s/LLM-call overhead.

**What to review** (under `logs/autoplay/emergent_overnight/`): the Markdown report +
per-step JSONL. Grep the logs for evidence each system fired and stayed sane:
- deeds/standing: `imperial_threat`, `defiant`, `Word on the road`, `defenses`
- backlash: `Imperial patrol has tracked`, `sworn sympathizer`, faction mood (`alarmed`,
  `rising`)
- consequence renderer: `bloodstained`, `wanted poster`
- bonds/orgs: `has come to follow you`, `pledges to`, `can no longer walk`
- the invariant checker's findings (confirmed bugs vs. agent leads), any tracebacks,
  and per-move latency (watch for the prop-gen/deed-interpreter Ollama hitch).

Acceptance: systems show up in the logs across episodes, the invariant checker reports no
new confirmed bugs, and nothing crashes or runs away (e.g., unbounded backlash, followers
flapping, standing exploding).
