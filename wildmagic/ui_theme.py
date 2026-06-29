"""Compatibility import surface for the rendering theme.

Rendering code should import from `wildmagic.rendering.theme`. This module remains
temporarily so any external/local imports keep working while the rendering package is
being consolidated.
"""

from __future__ import annotations

from wildmagic.rendering.theme import (
    ACCENT,
    BACKGROUND,
    DANGER,
    GOLD,
    MANA,
    MODE_COLORS,
    MODE_GREEN,
    MODE_ORANGE,
    MODE_PURPLE,
    MODE_YELLOW,
    MUTED,
    PANEL,
    PANEL_EDGE,
    SELECTED,
    TEXT,
    blend_color,
    wrap_text,
)
