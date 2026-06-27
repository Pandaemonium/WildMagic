from __future__ import annotations

from wildmagic.rendering.fonts import GameFonts


def test_game_fonts_create_uses_expected_faces(monkeypatch) -> None:
    calls: list[tuple[str, int, bool, bool]] = []

    def sys_font(name: str, size: int, bold: bool = False, italic: bool = False):
        calls.append((name, size, bold, italic))
        return object()

    monkeypatch.setattr("pygame.font.SysFont", sys_font)

    fonts = GameFonts.create()

    assert fonts.tile is not None
    assert calls == [
        ("consolas", 20, True, False),
        ("consolas", 17, False, False),
        ("consolas", 14, False, False),
        ("georgia,palatino linotype,times new roman", 22, True, False),
        ("georgia,palatino linotype,times new roman", 16, False, False),
        ("georgia,palatino linotype,times new roman", 13, False, True),
    ]
