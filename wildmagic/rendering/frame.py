from __future__ import annotations

from typing import Any

from wildmagic import rendering
from wildmagic.rendering.theme import BACKGROUND


def draw_game_frame(host: Any) -> None:
    """Compose the main in-game frame for the Pygame host.

    Full-screen scenes draw themselves before the game frame is considered. The host
    remains responsible for input/controller state; this module owns only presentation
    ordering for the normal game view.
    """
    scene = host._active_scene()
    if scene is not None:
        scene.draw()
        return

    context = rendering.RenderContext.from_host(host)
    host.screen.fill(BACKGROUND)
    if host._llm_debug_embedded():
        rendering.draw_llm_panel(host)
    rendering.draw_map_layer(context)
    rendering.draw_hud_panel(host)
    rendering.draw_autoplay_overlay_layer(context)
    if host._awaiting_command():
        rendering.draw_resolving_indicator_layer(context)
    if host.inspect_tile is not None:
        rendering.draw_inspect_tooltip(host)
    rendering.draw_curse_tooltip(host)
    if host.menu_active:
        host.draw_menu()
    if host.book_popup is not None:
        rendering.draw_book_popup(host)
    if host.queue_debug_active:
        rendering.draw_queue_debug(host)
