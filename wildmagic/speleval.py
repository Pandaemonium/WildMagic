"""Spell-resolution eval harness: every prompt/model/normalization change gets a
number instead of a vibe. See docs/EXECUTION_PLAN.md Phase 8 item 3.

Live mode (runs the corpus through the full pipeline: resolve -> validate ->
normalize -> apply, on a fresh deterministic session per spell):

    python -m wildmagic.speleval                       # mock provider (fast sanity)
    python -m wildmagic.speleval --provider ollama     # live model run
    python -m wildmagic.speleval --kinds exploit       # just the exploit set
    python -m wildmagic.speleval --limit 20 --json logs/speleval_report.json

Audit-replay mode (offline; re-parses recorded raw model responses through the
CURRENT parse/validation code, so contract/normalization changes get a
regression number against ~2k real historical casts):

    python -m wildmagic.speleval --from-audit logs/wild_magic_audit.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from typing import Any

# Keep eval traffic out of the main audit log unless the caller overrides.
os.environ.setdefault("WILDMAGIC_AUDIT_DIR", os.path.join("logs", "speleval"))

from .config import get_config_value  # noqa: E402
from .speleval_corpus import CORPUS  # noqa: E402

SYMBOLIC_TARGETS = {
    "player",
    "self",
    "caster",
    "nearest_enemy",
    "all_enemies",
    "enemies",
    "all",
    "non_player",
    "allies",
    "any",
    "trigger_target",
    "trigger_source",
}


def _valid_target_names(context: dict[str, Any] | None) -> set[str]:
    valid = set(SYMBOLIC_TARGETS)
    if not context:
        return valid
    for entity in context.get("nearby_entities") or []:
        if isinstance(entity, dict):
            for key in ("id", "name"):
                value = entity.get(key)
                if isinstance(value, str):
                    valid.add(value.lower())
    return valid


def _hallucinated_targets(
    data: dict[str, Any] | None, context: dict[str, Any] | None
) -> list[str]:
    if not data:
        return []
    valid = _valid_target_names(context)
    bad: list[str] = []
    for effect in data.get("effects") or []:
        if not isinstance(effect, dict):
            continue
        target = effect.get("target")
        if isinstance(target, str) and target.strip() and target.lower() not in valid:
            bad.append(target)
    return bad


def _numeric_amounts(data: dict[str, Any]) -> list[float]:
    amounts: list[float] = []
    for effect in data.get("effects") or []:
        if isinstance(effect, dict) and isinstance(effect.get("amount"), (int, float)):
            amounts.append(float(effect["amount"]))
    return amounts


def _exploit_leaks(spell: str, data: dict[str, Any] | None) -> list[str]:
    """Heuristics for an exploit spell that resolved too generously. The design
    contract allows crazy spells WITH commensurate costs; it forbids free or
    literal-numbered wins."""
    if not data or data.get("accepted") is False:
        return []
    leaks: list[str] = []
    costs = data.get("costs") or []
    if not costs:
        leaks.append("accepted with zero costs")
    amounts = _numeric_amounts(data)
    if any(a >= 100 for a in amounts):
        leaks.append(f"huge effect amount ({max(amounts):.0f})")
    named_numbers = [float(n) for n in re.findall(r"\d+", spell) if float(n) >= 15]
    if named_numbers and any(a in named_numbers for a in amounts):
        leaks.append("player-named number honored literally")
    return leaks


def run_live(
    provider_name: str, kinds: set[str], limit: int | None, seed: int
) -> dict[str, Any]:
    from .actions import GameSession

    entries = [e for e in CORPUS if e[1] in kinds]
    if limit:
        entries = entries[:limit]

    rows: list[dict[str, Any]] = []
    for index, (spell, kind, intent) in enumerate(entries, 1):
        session = GameSession(
            seed=seed, scenario="test_chamber", provider_name=provider_name
        )
        started = time.perf_counter()
        result = session.cast_wild(spell, record=False)
        latency = time.perf_counter() - started

        record = result.wild_magic or {}
        data = record.get("data")
        technical = bool(record.get("technical_failure"))
        accepted = bool(data) and data.get("accepted") is not False and not technical
        rejected = bool(data) and data.get("accepted") is False
        halluc = _hallucinated_targets(data, result.llm_context) if accepted else []
        leaks = (
            _exploit_leaks(spell, data) if kind == "exploit" and not technical else []
        )

        rows.append(
            {
                "spell": spell,
                "kind": kind,
                "intent": intent,
                "technical_failure": technical,
                "accepted": accepted,
                "rejected": rejected,
                "error": record.get("error"),
                "effect_types": [
                    str(e.get("type"))
                    for e in (data.get("effects") or [])
                    if isinstance(e, dict)
                ]
                if data
                else [],
                "n_costs": len(data.get("costs") or []) if data else 0,
                "hallucinated_targets": halluc,
                "exploit_leaks": leaks,
                "latency_s": round(latency, 3),
            }
        )
        status = "TECH " if technical else ("rej  " if rejected else "ok   ")
        flags = (" HALLUC" if halluc else "") + (" LEAK" if leaks else "")
        print(
            f"[{index:3d}/{len(entries)}] {status}{latency:6.2f}s  {kind:8s} {intent:11s} {spell[:58]!r}{flags}",
            flush=True,
        )

    return {"mode": "live", "provider": provider_name, "rows": rows}


def summarize_live(report: dict[str, Any]) -> None:
    rows = report["rows"]
    n = len(rows)
    if not n:
        print("no rows")
        return

    def pct(count: int) -> str:
        return f"{100.0 * count / n:5.1f}%"

    accepted = sum(r["accepted"] for r in rows)
    rejected = sum(r["rejected"] for r in rows)
    technical = sum(r["technical_failure"] for r in rows)
    halluc = sum(bool(r["hallucinated_targets"]) for r in rows)
    latencies = sorted(r["latency_s"] for r in rows)
    p90 = latencies[max(0, int(0.9 * n) - 1)]

    print()
    print(f"SPELL EVAL REPORT  provider={report['provider']}  n={n}")
    print(
        f"  resolved {pct(accepted)}   rejected {pct(rejected)}   technical {pct(technical)}   hallucinated-target rows {halluc}"
    )
    print(f"  latency mean {sum(latencies) / n:.2f}s   p90 {p90:.2f}s")

    by_group: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        for group_key in (f"kind:{r['kind']}", f"intent:{r['intent']}"):
            counter = by_group[group_key]
            counter["n"] += 1
            counter["ok"] += r["accepted"]
            counter["rej"] += r["rejected"]
            counter["tech"] += r["technical_failure"]
    print()
    print(f"  {'group':22s} {'n':>3s} {'ok':>4s} {'rej':>4s} {'tech':>4s}")
    for key in sorted(by_group):
        c = by_group[key]
        print(f"  {key:22s} {c['n']:3d} {c['ok']:4d} {c['rej']:4d} {c['tech']:4d}")

    effect_types = Counter(t for r in rows for t in r["effect_types"])
    print()
    print(
        "  top effect types:",
        ", ".join(f"{t} x{c}" for t, c in effect_types.most_common(10)),
    )

    exploit_rows = [r for r in rows if r["kind"] == "exploit"]
    if exploit_rows:
        leaked = [r for r in exploit_rows if r["exploit_leaks"]]
        print()
        print(f"  EXPLOIT SET: {len(exploit_rows)} spells, {len(leaked)} leaked")
        for r in leaked:
            print(f"    LEAK {r['spell'][:60]!r}: {'; '.join(r['exploit_leaks'])}")
    halluc_rows = [r for r in rows if r["hallucinated_targets"]]
    for r in halluc_rows:
        print(f"  HALLUC {r['spell'][:60]!r}: targets {r['hallucinated_targets']}")


def run_audit_replay(path: str) -> dict[str, Any]:
    """Re-parse recorded raw responses with the CURRENT contract code."""
    from .wild_magic import parse_resolution_json
    from .spell_contract import validate_resolution

    total = 0
    no_raw = 0
    now_ok = 0
    regressions: list[tuple[str, str]] = []
    improvements = 0
    validation_errors = Counter()

    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            raw = record.get("raw_response")
            if not raw:
                no_raw += 1
                continue
            total += 1
            was_failure = bool(record.get("technical_failure"))
            try:
                parsed = parse_resolution_json(raw)
                error = validate_resolution(parsed)
            except Exception as exc:  # parse failure
                error = str(exc)
            if error is None:
                now_ok += 1
                if was_failure:
                    improvements += 1
            else:
                validation_errors[error.split(":")[0][:60]] += 1
                if not was_failure:
                    regressions.append((record.get("spell", "")[:60], error[:80]))

    print(f"AUDIT REPLAY  {path}")
    print(f"  records with raw response: {total} (skipped {no_raw} without one)")
    print(
        f"  parse+validate OK under current code: {now_ok} ({100.0 * now_ok / max(total, 1):.1f}%)"
    )
    print(f"  improvements (failed then, passes now): {improvements}")
    print(f"  REGRESSIONS (passed then, fails now): {len(regressions)}")
    for spell, error in regressions[:15]:
        print(f"    {spell!r}: {error}")
    if validation_errors:
        print("  current failure reasons:")
        for reason, count in validation_errors.most_common(8):
            print(f"    {count:4d}  {reason}")
    return {
        "mode": "audit",
        "total": total,
        "now_ok": now_ok,
        "improvements": improvements,
        "regressions": len(regressions),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--provider", default=get_config_value("WILDMAGIC_PROVIDER", "mock")
    )
    parser.add_argument(
        "--kinds",
        default="common,creative,exploit",
        help="comma-separated subset of: common,creative,exploit",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument(
        "--json",
        dest="json_path",
        default=None,
        help="also write the full report as JSON",
    )
    parser.add_argument(
        "--from-audit",
        dest="audit_path",
        default=None,
        help="offline mode: re-validate recorded raw responses from this JSONL file",
    )
    args = parser.parse_args(argv)

    if args.audit_path:
        report = run_audit_replay(args.audit_path)
    else:
        kinds = {k.strip() for k in args.kinds.split(",") if k.strip()}
        report = run_live(args.provider, kinds, args.limit, args.seed)
        summarize_live(report)

    if args.json_path:
        os.makedirs(os.path.dirname(args.json_path) or ".", exist_ok=True)
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(f"\nreport written to {args.json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
