from __future__ import annotations

from datetime import timezone

import pygame

from wildmagic.rendering.layout import LLM_PANEL_WIDTH, WINDOW_HEIGHT
from wildmagic.rendering.llm_debug_state import LlmDebugState


def test_llm_debug_state_initializes_panel_defaults() -> None:
    state = LlmDebugState.create()

    assert state.entries == []
    assert state.started_at.tzinfo == timezone.utc
    assert state.seen == set()
    assert state.lines_cache is None
    assert state.block_ranges == []
    assert state.entry_block_ranges == {}
    assert state.call_button_rects == []
    assert state.selected_call_index is None
    assert state.selected_call_part == "response"
    assert state.scroll_offset == 0
    assert state.autoscroll is True
    assert state.dragging_scrollbar is False
    assert state.drag_grab_dy == 0
    assert state.content_rect == pygame.Rect(0, 0, LLM_PANEL_WIDTH, WINDOW_HEIGHT)
    assert state.scrollbar_track_rect is None
    assert state.scrollbar_thumb_rect is None
    assert state.max_scroll == 0
    assert state.line_rects == []
    assert state.selection_anchor is None
    assert state.selection_focus is None
    assert state.dragging_selection is False


def test_llm_debug_state_invalidates_line_cache() -> None:
    state = LlmDebugState.create()
    state.lines_cache = [("line", (1, 2, 3))]

    state.invalidate_lines()

    assert state.lines_cache is None


def test_llm_debug_state_reset_restores_defaults() -> None:
    state = LlmDebugState.create()
    original_started_at = state.started_at
    state.entries.append({"call_type": "wild magic"})
    state.seen.add("audit:1")
    state.lines_cache = [("line", (1, 2, 3))]
    state.block_ranges = [(1, 2)]
    state.entry_block_ranges = {0: {"prompt": (1, 2)}}
    state.call_button_rects = [(pygame.Rect(1, 2, 3, 4), 0)]
    state.selected_call_index = 0
    state.selected_call_part = "prompt"
    state.scroll_offset = 12
    state.autoscroll = False
    state.dragging_scrollbar = True
    state.drag_grab_dy = 7
    state.content_rect = pygame.Rect(4, 5, 6, 7)
    state.scrollbar_track_rect = pygame.Rect(1, 1, 1, 1)
    state.scrollbar_thumb_rect = pygame.Rect(2, 2, 2, 2)
    state.max_scroll = 42
    state.line_rects = [(pygame.Rect(1, 2, 3, 4), 9)]
    state.selection_anchor = 3
    state.selection_focus = 4
    state.dragging_selection = True

    state.reset()

    assert state.entries == []
    assert state.started_at >= original_started_at
    assert state.seen == set()
    assert state.lines_cache is None
    assert state.block_ranges == []
    assert state.entry_block_ranges == {}
    assert state.call_button_rects == []
    assert state.selected_call_index is None
    assert state.selected_call_part == "response"
    assert state.scroll_offset == 0
    assert state.autoscroll is True
    assert state.dragging_scrollbar is False
    assert state.drag_grab_dy == 0
    assert state.content_rect == pygame.Rect(0, 0, LLM_PANEL_WIDTH, WINDOW_HEIGHT)
    assert state.scrollbar_track_rect is None
    assert state.scrollbar_thumb_rect is None
    assert state.max_scroll == 0
    assert state.line_rects == []
    assert state.selection_anchor is None
    assert state.selection_focus is None
    assert state.dragging_selection is False
