from __future__ import annotations

from datetime import timezone
from types import SimpleNamespace

import pygame

from wildmagic.rendering import llm_panel


def _host(**overrides):
    host = SimpleNamespace(
        llm_debug_entries=[],
        llm_debug_seen=set(),
        _llm_lines_cache=None,
        llm_block_ranges=[],
        llm_entry_block_ranges={},
        llm_selection_anchor=None,
        llm_selection_focus=None,
        llm_content_rect=pygame.Rect(0, 0, 200, 60),
        llm_scroll_offset=0,
        llm_autoscroll=True,
        llm_selected_call_index=None,
        llm_selected_call_part="response",
        small_font=SimpleNamespace(get_linesize=lambda: 10),
        engine=SimpleNamespace(_pending_towns={}),
    )
    for key, value in overrides.items():
        setattr(host, key, value)
    return host


def test_parse_audit_timestamp_normalizes_to_utc() -> None:
    parsed = llm_panel.parse_audit_timestamp("2026-01-02T03:04:05Z")

    assert parsed is not None
    assert parsed.tzinfo == timezone.utc
    assert parsed.hour == 3


def test_format_audit_prompt_prefers_chat_messages() -> None:
    prompt = llm_panel.format_audit_prompt(
        {
            "prompt": {
                "messages": [
                    {"role": "system", "content": "rules"},
                    {"role": "user", "content": "spell"},
                ]
            }
        }
    )

    assert prompt == "SYSTEM:\nrules\n\nUSER:\nspell"


def test_format_audit_response_uses_raw_response_first() -> None:
    response = llm_panel.format_audit_response(
        {"raw_response": "raw text", "reply": "ignored"}
    )

    assert response == "raw text"


def test_audit_record_to_debug_entry_labels_wild_magic() -> None:
    entry = llm_panel.audit_record_to_debug_entry(
        "wild_magic_audit.jsonl",
        {
            "timestamp": "now",
            "provider": "mock",
            "model": "test",
            "prompt": {"context": {"a": 1}},
            "parsed_resolution": {"ok": True},
        },
    )

    assert entry["call_type"] == "wild magic"
    assert entry["provider"] == "mock"
    assert entry["technical_failure"] is False
    assert '"ok": true' in entry["response"]


def test_call_kind_normalizes_wild_magic_to_spell() -> None:
    assert llm_panel.call_kind({"call_type": "wild magic"}) == "spell"
    assert llm_panel.call_kind({"call_type": "dialogue"}) == "dialogue"


def test_build_lines_populates_prompt_response_ranges(monkeypatch) -> None:
    host = _host(
        llm_debug_entries=[
            {
                "call_type": "dialogue",
                "provider": "mock",
                "model": "m",
                "timestamp": "t",
                "technical_failure": False,
                "prompt": "hello",
                "response": "world",
            }
        ]
    )
    monkeypatch.setattr(llm_panel, "refresh_debug_entries", lambda _host: None)

    lines = llm_panel.build_lines(host, 80)

    assert ("Prompt", llm_panel.ACCENT) in lines
    assert ("Response", llm_panel.ACCENT) in lines
    assert host.llm_block_ranges
    assert set(host.llm_entry_block_ranges[0]) == {"prompt", "response"}


def test_selected_lines_returns_ordered_selection() -> None:
    host = _host(
        _llm_lines_cache=[
            ("first", (1, 1, 1)),
            ("second", (1, 1, 1)),
            ("third", (1, 1, 1)),
        ],
        llm_selection_anchor=2,
        llm_selection_focus=1,
    )

    assert llm_panel.selected_lines(host) == ["second", "third"]
