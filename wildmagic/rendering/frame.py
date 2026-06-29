from __future__ import annotations

from typing import Any

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

    host.screen.fill(BACKGROUND)
    host.draw_llm_panel()
    host.draw_map()
    host.draw_panel()
    host.draw_autoplay_overlay()
    if host._awaiting_command():
        host.draw_resolving_indicator()
    if host.inspect_tile is not None:
        host.draw_inspect_tooltip()
    host.draw_curse_tooltip()
    if host.menu_active:
        host.draw_menu()
    if host.book_popup is not None:
        host.draw_book_popup()
    if host.queue_debug_active:
        host.draw_queue_debug()
