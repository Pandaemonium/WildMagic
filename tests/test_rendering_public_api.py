from __future__ import annotations

import wildmagic.rendering as rendering
from wildmagic.rendering import hud_panel, llm_panel, map_view
from wildmagic.rendering.context import RenderContext
from wildmagic.rendering.fonts import GameFonts
from wildmagic.rendering.llm_debug_state import LlmDebugHostAdapter, LlmDebugState
from wildmagic.rendering.overlays import (
    draw_autoplay_overlay_layer,
    draw_resolving_indicator_layer,
)
from wildmagic.rendering.window import GameWindow


def test_rendering_package_exposes_stable_host_api() -> None:
    assert rendering.GameFonts is GameFonts
    assert rendering.GameWindow is GameWindow
    assert rendering.LlmDebugHostAdapter is LlmDebugHostAdapter
    assert rendering.LlmDebugState is LlmDebugState
    assert rendering.RenderContext is RenderContext
    assert rendering.draw_map is map_view.draw_map
    assert rendering.draw_map_layer is map_view.draw_map_layer
    assert rendering.draw_autoplay_overlay_layer is draw_autoplay_overlay_layer
    assert rendering.draw_resolving_indicator_layer is draw_resolving_indicator_layer
    assert rendering.draw_hud_panel is hud_panel.draw_panel
    assert rendering.draw_curse_tooltip is hud_panel.draw_curse_tooltip
    assert rendering.draw_llm_panel is llm_panel.draw_panel
    assert rendering.draw_llm_call_buttons is llm_panel.draw_call_buttons
    assert rendering.build_llm_lines is llm_panel.build_lines
    assert rendering.llm_line_index_at is llm_panel.line_index_at
    assert rendering.llm_scrollbar_fraction_at is llm_panel.scrollbar_fraction_at
