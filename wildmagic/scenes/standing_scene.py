"""Full-screen standing readout for the pygame client."""

from __future__ import annotations

import pygame

from ..actions import describe_standing
from ..rendering.theme import (
    ACCENT,
    BACKGROUND,
    DANGER,
    GOLD,
    MUTED,
    PANEL_EDGE,
    TEXT,
    wrap_text,
)


class StandingScene:
    def __init__(self, host) -> None:
        self.host = host
        self.active = False
        self.scroll = 0
        self._max_scroll = 0

    def start(self) -> None:
        self.active = True
        self.scroll = 0
        self.host.input_active = False

    def close(self) -> None:
        self.active = False
        self.host.input_active = True

    def update(self) -> None:
        return

    def handle_key(self, event: pygame.event.Event) -> None:
        if event.key in (pygame.K_ESCAPE, pygame.K_t):
            self.close()
        elif event.key in (pygame.K_UP, pygame.K_k, pygame.K_w):
            self.scroll = max(0, self.scroll - 1)
        elif event.key in (pygame.K_DOWN, pygame.K_j, pygame.K_s):
            self.scroll = min(self._max_scroll, self.scroll + 1)
        elif event.key == pygame.K_PAGEUP:
            self.scroll = max(0, self.scroll - 8)
        elif event.key == pygame.K_PAGEDOWN:
            self.scroll = min(self._max_scroll, self.scroll + 8)
        elif event.key == pygame.K_HOME:
            self.scroll = 0
        elif event.key == pygame.K_END:
            self.scroll = self._max_scroll

    def handle_mouse(self, pos: tuple[int, int]) -> None:
        width = self.host.screen.get_width()
        if pos[1] < 72 and pos[0] > width - 120:
            self.close()

    def handle_mouse_wheel(self, event: pygame.event.Event) -> None:
        self.scroll = max(0, min(self._max_scroll, self.scroll - event.y * 3))

    def _display_lines(self) -> list[tuple[str, tuple[int, int, int]]]:
        lines: list[tuple[str, tuple[int, int, int]]] = []
        for raw in describe_standing(self.host.engine):
            if not raw:
                lines.append(("", MUTED))
                continue
            stripped = raw.strip()
            if raw.startswith("Standing -"):
                color = ACCENT
            elif stripped.endswith(":") or stripped.startswith("Blood on"):
                color = GOLD
            elif "blood feud" in stripped.lower():
                color = DANGER
            elif raw.startswith("  "):
                color = TEXT
            else:
                color = MUTED
            indent = "  " if raw.startswith("  ") else ""
            wrap_width = 84 if indent else 88
            for part in wrap_text(stripped, wrap_width):
                lines.append((indent + part, color))
        return lines

    def draw(self) -> None:
        host = self.host
        screen = host.screen
        screen.fill(BACKGROUND)
        width, height = screen.get_size()
        margin = 48
        host.draw_text("STANDING", margin, 34, host.tile_font, ACCENT)
        host.draw_text(
            "Esc/T closes  -  arrows, PgUp/PgDn scroll",
            margin,
            66,
            host.small_font,
            MUTED,
        )
        close = pygame.Rect(width - 104, 34, 58, 28)
        pygame.draw.rect(screen, PANEL_EDGE, close, width=1, border_radius=4)
        close_label = host.small_font.render("Close", True, MUTED)
        screen.blit(
            close_label,
            (
                close.centerx - close_label.get_width() // 2,
                close.centery - close_label.get_height() // 2,
            ),
        )
        pygame.draw.line(screen, PANEL_EDGE, (margin, 104), (width - margin, 104), 1)

        lines = self._display_lines()
        line_h = host.small_font.get_linesize() + 4
        body_top = 124
        body_h = height - body_top - 44
        visible = max(1, body_h // line_h)
        self._max_scroll = max(0, len(lines) - visible)
        self.scroll = max(0, min(self.scroll, self._max_scroll))
        y = body_top
        for text, color in lines[self.scroll : self.scroll + visible]:
            host.draw_text(text, margin, y, host.small_font, color)
            y += line_h

        if self._max_scroll > 0:
            track = pygame.Rect(width - margin - 10, body_top, 8, body_h)
            pygame.draw.rect(screen, (20, 22, 27), track, border_radius=4)
            thumb_h = max(28, int(body_h * (visible / len(lines))))
            usable = max(1, body_h - thumb_h)
            thumb_y = body_top + int(usable * (self.scroll / self._max_scroll))
            pygame.draw.rect(
                screen,
                ACCENT,
                pygame.Rect(track.x, thumb_y, track.width, thumb_h),
                border_radius=4,
            )
