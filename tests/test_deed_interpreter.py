"""Phase A.2 — the LLM deed interpreter for ambiguous spell outcomes.

Combat kills become deeds by rule (A.1); non-lethal wild magic (raising the dead, razing a
place, desecration, atrocity) is ambiguous and read by the interpreter (D5). The
interpreter only classifies into the bounded vocabulary; consequences still come from the
deterministic rules table. A cheap gate keeps ordinary spells a zero-call path, a
deterministic fallback runs offline/in tests/in replay, and the verdict rides on the
wild-magic action record so replays reproduce the deed with no model call.

See docs/EMERGENT_WORLD_IMPLEMENTATION.md §3 (Phase A.2).
"""

from __future__ import annotations

import json
from pathlib import Path

from wildmagic.actions import GameSession
from wildmagic.deed_interpreter import (
    MockDeedInterpreterProvider,
    fallback_classify,
    make_deed_interpreter_provider,
    outcome_is_deed_candidate,
    resolve_deed_interpretation,
)
from wildmagic.replay import run_replay, save_replay


# --- the cheap gate + deterministic fallback -------------------------------------


def test_gate_skips_ordinary_spells() -> None:
    assert outcome_is_deed_candidate("raise the dead to fight for me")
    assert outcome_is_deed_candidate("the watchtower collapses into rubble")
    assert not outcome_is_deed_candidate("a gentle warmth mends your wounds")
    assert not outcome_is_deed_candidate("a spark leaps to the nearest foe")


def test_fallback_is_conservative_but_classifies_strong_signals() -> None:
    assert fallback_classify({"spell": "raise the dead", "outcome": ""}).deed_type == (
        "raised_dead"
    )
    assert (
        fallback_classify(
            {"spell": "", "outcome": "you desecrate the roadside shrine"}
        ).deed_type
        == "desecration"
    )
    # No strong phrase -> not a deed.
    assert (
        fallback_classify({"spell": "ward me", "outcome": "a shield forms"}).deed_type
        is None
    )


def test_off_provider_uses_fallback_only() -> None:
    assert make_deed_interpreter_provider("off") is None
    verdict = resolve_deed_interpretation(
        None, {"spell": "raise the dead", "outcome": ""}
    )
    assert verdict.deed_type == "raised_dead"
    assert verdict.interpretation_source == "fallback"


# --- the full session path -------------------------------------------------------


def test_spell_outcome_becomes_a_deed_via_the_interpreter() -> None:
    session = GameSession(
        seed=7,
        scenario="test_chamber",
        provider_name="mock",
        deed_interpreter_provider=MockDeedInterpreterProvider(),
    )
    try:
        session.execute_command("cast raise the dead to walk")
        deeds = session.engine.state.deed_ledger.deeds
        assert len(deeds) == 1
        assert deeds[0].type == "raised_dead"
        assert deeds[0].source == "spell"
        assert deeds[0].interpretation_source == "llm"
        # Consequences still come from the bounded rules table (uncanniness + legend).
        session.execute_command("tick")
        assert "uncanny" in session.engine.legend_words(
            session.engine.state.player_soul_id
        )
    finally:
        session.close()


def test_ordinary_spell_records_no_deed_and_makes_no_call() -> None:
    session = GameSession(
        seed=7,
        scenario="test_chamber",
        provider_name="mock",
        deed_interpreter_provider=MockDeedInterpreterProvider(),
    )
    try:
        session.execute_command("cast a soft light to read by")
        assert session.engine.state.deed_ledger.deeds == []
    finally:
        session.close()


# --- replay fidelity (the verdict rides on the wild-magic record) ----------------


def test_replay_reproduces_the_interpreted_deed(tmp_path: Path) -> None:
    session = GameSession(
        seed=7,
        scenario="test_chamber",
        provider_name="mock",
        deed_interpreter_provider=MockDeedInterpreterProvider(),
    )
    try:
        session.execute_command("cast raze the watchtower to rubble")
        session.execute_command("tick")
        assert any(
            deed.type == "razed_building"
            for deed in session.engine.state.deed_ledger.deeds
        )
        replay_path = tmp_path / "interp.json"
        save_replay(session, replay_path)
    finally:
        session.close()

    result = run_replay(replay_path)
    assert result.matched, json.dumps(
        {"expected": result.expected_summary, "actual": result.final_summary},
        indent=2,
        sort_keys=True,
        default=str,
    )
