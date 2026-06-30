from __future__ import annotations

import pygame

from wildmagic.rendering.llm_debug_state import LlmDebugState
from wildmagic.ui import GameUI


def _ui() -> GameUI:
    ui = GameUI.__new__(GameUI)
    ui.llm_debug = LlmDebugState.create()
    return ui


def test_game_ui_llm_debug_compatibility_properties_share_state() -> None:
    ui = _ui()

    ui.llm_debug_entries = [{"call_type": "dialogue"}]
    ui._llm_lines_cache = [("line", (1, 2, 3))]
    ui.llm_selection_anchor = 4
    ui.llm_selection_focus = 6
    ui.llm_scroll_offset = 9
    ui.llm_content_rect = pygame.Rect(1, 2, 3, 4)
    ui.dragging_llm_selection = True

    assert ui.llm_debug.entries == [{"call_type": "dialogue"}]
    assert ui.llm_debug.lines_cache == [("line", (1, 2, 3))]
    assert ui.llm_debug.selection_anchor == 4
    assert ui.llm_debug.selection_focus == 6
    assert ui.llm_debug.scroll_offset == 9
    assert ui.llm_debug.content_rect == pygame.Rect(1, 2, 3, 4)
    assert ui.llm_debug.dragging_selection is True


def test_game_ui_llm_debug_state_reset_restores_compatibility_defaults() -> None:
    ui = _ui()
    ui.llm_debug_entries = [{"call_type": "dialogue"}]
    ui._llm_lines_cache = [("line", (1, 2, 3))]
    ui.llm_selection_anchor = 4
    ui.llm_autoscroll = False

    ui.llm_debug.reset()

    assert ui.llm_debug_entries == []
    assert ui._llm_lines_cache is None
    assert ui.llm_selection_anchor is None
    assert ui.llm_autoscroll is True
