from __future__ import annotations

from dataclasses import dataclass

import pygame


@dataclass(frozen=True)
class GameFonts:
    tile: pygame.font.Font
    ui: pygame.font.Font
    small: pygame.font.Font
    book_title: pygame.font.Font
    book_body: pygame.font.Font
    book_small: pygame.font.Font

    @classmethod
    def create(cls) -> "GameFonts":
        return cls(
            tile=pygame.font.SysFont("consolas", 20, bold=True),
            ui=pygame.font.SysFont("consolas", 17),
            small=pygame.font.SysFont("consolas", 14),
            # Book popup: a serif face for printed matter (falls back if absent).
            book_title=pygame.font.SysFont(
                "georgia,palatino linotype,times new roman", 22, bold=True
            ),
            book_body=pygame.font.SysFont(
                "georgia,palatino linotype,times new roman", 16
            ),
            book_small=pygame.font.SysFont(
                "georgia,palatino linotype,times new roman", 13, italic=True
            ),
        )
