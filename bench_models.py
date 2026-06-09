"""
Benchmark qwen3:8b vs qwen3.5:9b-q4_K_M for Wild Magic use cases.
Tests wild magic resolution, NPC dialogue, and town generation.
Run: python bench_models.py
"""
from __future__ import annotations
import json
import sys
import textwrap
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost:11434"
MODELS = ["qwen3:8b", "qwen3.5:9b-q4_K_M"]
THINKING_MODES = [True, False]

# ---------------------------------------------------------------------------
# Prompts (same as the game)
# ---------------------------------------------------------------------------

WILD_MAGIC_SYSTEM = open("wildmagic/wild_magic.py").read().split('SYSTEM_PROMPT = """')[1].split('"""')[0]

DIALOGUE_SYSTEM = """You are voicing a single NPC in a dark-fantasy roguelike.
Reply in 1-3 short sentences, in character. Be specific to your role and what you know.
Never break character. Do not narrate actions."""

TOWN_SYSTEM = """You are a world-builder for a dark fantasy roguelike. Generate a small frontier settlement.
Respond with ONLY a JSON object — no prose, no markdown:
{"town_name": "2-4 word name", "description": "1-2 sentences", "buildings": [{"type": "tavern|inn|shrine|market|smithy|home", "name": "Name or null"}], "npcs": [{"name": "Full Name", "role": "occupation", "backstory": "1-2 sentences", "traits": ["trait1"], "building": "type or null", "wares": {"item": qty} }]}
Generate 3-5 NPCs. Settlement type: waypost. Location: at a river crossing that floods each spring. Defining trait: people come here to disappear. Current situation: a caravan has been stranded here two weeks."""

TESTS = [
    {
        "id": "wildmagic_simple",
        "label": "Wild Magic: fireball",
        "system": WILD_MAGIC_SYSTEM,
        "user": json.dumps({
            "spell": "fireball",
            "player": {"hp": 14, "max_hp": 14, "mana": 8, "max_mana": 10,
                       "inventory": {"chalk": 2, "mana crystal": 1}},
            "nearest_enemy": {"id": "goblin_1", "name": "goblin", "hp": 6, "distance": 3},
            "floor": 2
        }),
        "expect_json": True,
        "quality_checks": ["accepted", "effects", "costs", "outcome_text"],
    },
    {
        "id": "wildmagic_creative",
        "label": "Wild Magic: turn my shadow into a knife",
        "system": WILD_MAGIC_SYSTEM,
        "user": json.dumps({
            "spell": "turn my shadow into a knife",
            "player": {"hp": 10, "max_hp": 14, "mana": 6, "max_mana": 10,
                       "inventory": {"chalk": 1}},
            "nearest_enemy": {"id": "skeleton_1", "name": "skeleton", "hp": 8, "distance": 2},
            "floor": 3
        }),
        "expect_json": True,
        "quality_checks": ["accepted", "effects", "costs", "severity"],
    },
    {
        "id": "wildmagic_complex",
        "label": "Wild Magic: rain blood from the ceiling to heal me",
        "system": WILD_MAGIC_SYSTEM,
        "user": json.dumps({
            "spell": "rain blood from the ceiling to heal me",
            "player": {"hp": 5, "max_hp": 14, "mana": 9, "max_mana": 10,
                       "inventory": {"chalk": 2, "bone fragment": 1}},
            "nearest_enemy": {"id": "orc_1", "name": "orc", "hp": 12, "distance": 4},
            "floor": 4
        }),
        "expect_json": True,
        "quality_checks": ["accepted", "effects", "costs"],
    },
    {
        "id": "dialogue_merchant",
        "label": "Dialogue: merchant asked about wares",
        "system": DIALOGUE_SYSTEM,
        "user": json.dumps({
            "npc": {"name": "Brix", "role": "merchant", "backstory": "Fled the capital after a debt went bad.",
                    "traits": ["nervous", "overcharges"]},
            "player_says": "What are you selling?",
            "conversation_history": []
        }),
        "expect_json": False,
        "quality_checks": [],
    },
    {
        "id": "town_generation",
        "label": "Town Generation",
        "system": TOWN_SYSTEM,
        "user": json.dumps({"zone": {"x": 5, "y": -3}, "world_seed": 42,
                            "npc_count_range": [3, 5],
                            "settlement_type": "waypost",
                            "location": "at a river crossing that floods each spring",
                            "defining_trait": "people come here to disappear",
                            "current_situation": "a caravan has been stranded here two weeks"}),
        "expect_json": True,
        "quality_checks": ["town_name", "buildings", "npcs"],
    },
]

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def call_ollama(model: str, system: str, user: str, think: bool) -> dict:
    payload = {
        "model": model,
        "stream": False,
        "think": think,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_predict": 1024,
            "num_ctx": 8192,
            "num_gpu": 999,
        },
        "keep_alive": "10m",
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode())
    elapsed = time.monotonic() - t0
    return {"data": data, "wall_seconds": elapsed}


def strip_think(text: str) -> str:
    import re
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def extract_think(text: str) -> str:
    import re
    m = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def parse_stats(data: dict, wall: float) -> dict:
    content = data.get("message", {}).get("content", "")
    eval_count = data.get("eval_count", 0)
    eval_ns = data.get("eval_duration", 0)
    prompt_count = data.get("prompt_eval_count", 0)
    prompt_ns = data.get("prompt_eval_duration", 0)
    tok_per_sec = eval_count / (eval_ns / 1e9) if eval_ns > 0 else 0
    return {
        "content": content,
        "thinking": extract_think(content),
        "response": strip_think(content),
        "tok_per_sec": tok_per_sec,
        "eval_tokens": eval_count,
        "prompt_tokens": prompt_count,
        "prompt_ms": prompt_ns / 1e6,
        "wall_seconds": wall,
    }


def quality_score(stats: dict, test: dict) -> tuple[int, list[str]]:
    response = stats["response"]
    checks = test["quality_checks"]
    passed = []
    failed = []
    if test["expect_json"]:
        try:
            obj = json.loads(response)
            for key in checks:
                if key in obj:
                    passed.append(key)
                else:
                    failed.append(f"missing '{key}'")
        except json.JSONDecodeError as e:
            failed.append(f"invalid JSON: {e}")
    else:
        # Prose: just check it's non-empty and not a refusal
        if len(response) > 20:
            passed.append("non-empty response")
        else:
            failed.append("response too short")
        if "cannot" in response.lower() or "i'm an ai" in response.lower():
            failed.append("apparent refusal")
    return len(passed), passed, failed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

results: list[dict] = []

total_runs = len(MODELS) * len(THINKING_MODES) * len(TESTS)
run_num = 0

for model in MODELS:
    for think in THINKING_MODES:
        label_think = "think=ON " if think else "think=OFF"
        print(f"\n{'='*70}")
        print(f"  MODEL: {model}  |  {label_think}")
        print(f"{'='*70}")
        for test in TESTS:
            run_num += 1
            print(f"\n  [{run_num}/{total_runs}] {test['label']} ...", end="", flush=True)
            try:
                raw = call_ollama(model, test["system"], test["user"], think)
                stats = parse_stats(raw["data"], raw["wall_seconds"])
                score, passed, failed = quality_score(stats, test)
                status = "OK" if not failed else f"WARN({', '.join(failed)})"
                print(f"  {stats['wall_seconds']:.1f}s  {stats['tok_per_sec']:.0f} tok/s  {status}")
                if stats["thinking"]:
                    think_preview = stats["thinking"][:120].replace("\n", " ")
                    print(f"    <think> {think_preview}...")
                resp_preview = stats["response"][:200].replace("\n", " ")
                print(f"    => {resp_preview}")
                results.append({
                    "model": model, "think": think, "test_id": test["id"],
                    "label": test["label"], "wall_seconds": stats["wall_seconds"],
                    "tok_per_sec": stats["tok_per_sec"], "eval_tokens": stats["eval_tokens"],
                    "prompt_tokens": stats["prompt_tokens"], "passed": passed, "failed": failed,
                    "response": stats["response"], "thinking_len": len(stats["thinking"]),
                })
            except Exception as exc:
                print(f"  ERROR: {exc}")
                results.append({
                    "model": model, "think": think, "test_id": test["id"],
                    "label": test["label"], "wall_seconds": None, "tok_per_sec": None,
                    "eval_tokens": None, "prompt_tokens": None,
                    "passed": [], "failed": [str(exc)], "response": "", "thinking_len": 0,
                })

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

print(f"\n\n{'='*90}")
print("SUMMARY")
print(f"{'='*90}")
header = f"{'Model':<28} {'Think':<6} {'Test':<28} {'Time':>6} {'Tok/s':>6} {'Quality'}"
print(header)
print("-" * 90)
for r in results:
    t = f"{r['wall_seconds']:.1f}s" if r["wall_seconds"] is not None else "ERR"
    tps = f"{r['tok_per_sec']:.0f}" if r["tok_per_sec"] is not None else "ERR"
    quality = "PASS" if not r["failed"] else f"FAIL: {r['failed'][0]}"
    think_flag = "Y" if r["think"] else "N"
    print(f"{r['model']:<28} {think_flag:<6} {r['test_id']:<28} {t:>6} {tps:>6}  {quality}")

# ---------------------------------------------------------------------------
# Per-model averages
# ---------------------------------------------------------------------------

print(f"\n{'='*90}")
print("AVERAGES (excluding errors)")
print(f"{'='*90}")
for model in MODELS:
    for think in THINKING_MODES:
        runs = [r for r in results if r["model"] == model and r["think"] == think
                and r["wall_seconds"] is not None]
        if not runs:
            continue
        avg_time = sum(r["wall_seconds"] for r in runs) / len(runs)
        avg_tps = sum(r["tok_per_sec"] for r in runs) / len(runs)
        pass_rate = sum(1 for r in runs if not r["failed"]) / len(runs) * 100
        avg_think_chars = sum(r["thinking_len"] for r in runs) / len(runs)
        think_flag = "think=ON " if think else "think=OFF"
        print(f"  {model:<28} {think_flag}  avg_time={avg_time:.1f}s  avg_tok/s={avg_tps:.0f}  pass={pass_rate:.0f}%  avg_think_chars={avg_think_chars:.0f}")

print("\nDone.")
