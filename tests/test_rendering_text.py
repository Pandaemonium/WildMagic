from __future__ import annotations

from wildmagic.rendering.text import draw_text


class FakeSurface:
    def __init__(self, height: int) -> None:
        self._height = height

    def get_height(self) -> int:
        return self._height


class FakeFont:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool, tuple[int, int, int]]] = []

    def render(
        self, text: str, antialias: bool, color: tuple[int, int, int]
    ) -> FakeSurface:
        self.calls.append((text, antialias, color))
        return FakeSurface(12)


class FakeScreen:
    def __init__(self) -> None:
        self.blits: list[tuple[object, tuple[int, int]]] = []

    def blit(self, surface: object, pos: tuple[int, int]) -> None:
        self.blits.append((surface, pos))


def test_draw_text_renders_blits_and_returns_next_y() -> None:
    screen = FakeScreen()
    font = FakeFont()

    next_y = draw_text(screen, "hello", 4, 8, font, (1, 2, 3))

    assert font.calls == [("hello", True, (1, 2, 3))]
    assert len(screen.blits) == 1
    surface, pos = screen.blits[0]
    assert isinstance(surface, FakeSurface)
    assert pos == (4, 8)
    assert next_y == 22
