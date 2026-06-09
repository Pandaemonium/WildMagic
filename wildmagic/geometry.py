from __future__ import annotations


def sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def bresenham_line(x1: int, y1: int, x2: int, y2: int) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    dx = abs(x2 - x1)
    dy = -abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    error = dx + dy
    x = x1
    y = y1
    while True:
        points.append((x, y))
        if x == x2 and y == y2:
            return points
        twice_error = 2 * error
        if twice_error >= dy:
            error += dy
            x += sx
        if twice_error <= dx:
            error += dx
            y += sy


def unique_points(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    seen: set[tuple[int, int]] = set()
    result: list[tuple[int, int]] = []
    for point in points:
        if point in seen:
            continue
        seen.add(point)
        result.append(point)
    return result


def _on_bresenham(a: tuple[int, int], b: tuple[int, int], p: tuple[int, int]) -> bool:
    """True if point p lies on the Bresenham line from a to b (inclusive)."""
    x0, y0 = a
    x1, y1 = b
    px, py = p
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x1 > x0 else -1
    sy = 1 if y1 > y0 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        if (x, y) == (px, py):
            return True
        if (x, y) == (x1, y1):
            return False
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
