"""The built-in icons as strokes on a 24-unit grid (y down, like icon editors): each icon is a
list of polylines, `(points, closed)`. Drawn for kinemo, simple enough to read at small sizes."""

from __future__ import annotations

import math

Point = tuple[float, float]
Stroke = tuple[list[Point], bool]


def arc(cx: float, cy: float, r: float, start: float, end: float, steps: int = 24) -> list[Point]:
    """Points on a circle (degrees, clockwise on screen since y points down)."""
    return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in (start + (end - start) * i / steps for i in range(steps + 1))]


def circle(cx: float, cy: float, r: float) -> Stroke:
    return (arc(cx, cy, r, 0.0, 360.0, 48)[:-1], True)


def ellipse(cx: float, cy: float, rx: float, ry: float, start: float = 0.0, end: float = 360.0) -> list[Point]:
    return [(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a))) for a in (start + (end - start) * i / 48 for i in range(49))]


def line(*points: Point) -> Stroke:
    return (list(points), False)


def closed(*points: Point) -> Stroke:
    return (list(points), True)


def dot(cx: float, cy: float) -> Stroke:
    return circle(cx, cy, 0.6)


def _gear() -> list[Stroke]:
    teeth = [line((12 + 6.5 * math.cos(math.radians(a)), 12 + 6.5 * math.sin(math.radians(a))), (12 + 9.0 * math.cos(math.radians(a)), 12 + 9.0 * math.sin(math.radians(a)))) for a in range(0, 360, 45)]
    return [circle(12, 12, 3), circle(12, 12, 6.5), *teeth]


def _star() -> list[Stroke]:
    points = [(12 + (9.5 if i % 2 == 0 else 4.0) * math.cos(math.radians(-90 + 36 * i)), 12.8 + (9.5 if i % 2 == 0 else 4.0) * math.sin(math.radians(-90 + 36 * i))) for i in range(10)]
    return [(points, True)]


def _cpu() -> list[Stroke]:
    pins: list[Stroke] = []
    for p in (9.5, 12.0, 14.5):
        pins += [line((p, 3.5), (p, 7)), line((p, 17), (p, 20.5)), line((3.5, p), (7, p)), line((17, p), (20.5, p))]
    return [closed((7, 7), (17, 7), (17, 17), (7, 17)), closed((10, 10), (14, 10), (14, 14), (10, 14)), *pins]


ICONS: dict[str, list[Stroke]] = {
    "check": [line((5, 12.5), (10, 17.5), (19, 7))],
    "x": [line((6, 6), (18, 18)), line((18, 6), (6, 18))],
    "plus": [line((12, 5), (12, 19)), line((5, 12), (19, 12))],
    "minus": [line((5, 12), (19, 12))],
    "arrow-right": [line((5, 12), (19, 12)), line((13, 6), (19, 12), (13, 18))],
    "arrow-left": [line((19, 12), (5, 12)), line((11, 6), (5, 12), (11, 18))],
    "arrow-up": [line((12, 19), (12, 5)), line((6, 11), (12, 5), (18, 11))],
    "arrow-down": [line((12, 5), (12, 19)), line((6, 13), (12, 19), (18, 13))],
    "warning": [closed((12, 3.5), (21.5, 20), (2.5, 20)), line((12, 9.5), (12, 14)), dot(12, 17)],
    "info": [circle(12, 12, 9), line((12, 11), (12, 16.5)), dot(12, 7.8)],
    "question": [circle(12, 12, 9), (arc(12, 9.6, 2.7, 190, 400, 20) + [(12, 14)], False), dot(12, 17)],
    "lightbulb": [(arc(12, 10, 6, 130, 410, 32), False), line((9.5, 15), (9.5, 18), (14.5, 18), (14.5, 15)), line((10.5, 21), (13.5, 21))],
    "gear": _gear(),
    "user": [circle(12, 8, 4), (arc(12, 21, 7.5, 180, 360, 24), False)],
    "cpu": _cpu(),
    "star": _star(),
    "clock": [circle(12, 12, 9), line((12, 7), (12, 12), (15.5, 13.5))],
    "play": [closed((8, 5), (19, 12), (8, 19))],
    "pause": [line((9, 5), (9, 19)), line((15, 5), (15, 19))],
    "home": [line((3.5, 11), (12, 4), (20.5, 11)), line((6, 9.5), (6, 20), (18, 20), (18, 9.5)), line((10, 20), (10, 14), (14, 14), (14, 20))],
    "search": [circle(10.5, 10.5, 6), line((15, 15), (20, 20))],
    "lock": [closed((6, 11), (18, 11), (18, 20), (6, 20)), (arc(12, 11, 4, 180, 360, 16), False), dot(12, 15.5)],
    "bolt": [closed((13, 3), (5, 13.5), (11.5, 13.5), (10.5, 21), (19, 10), (12.5, 10))],
    "mail": [closed((3.5, 6), (20.5, 6), (20.5, 18), (3.5, 18)), line((3.5, 6.5), (12, 13), (20.5, 6.5))],
    "book": [closed((4, 5), (11, 6.5), (11, 20), (4, 18.5)), closed((20, 5), (13, 6.5), (13, 20), (20, 18.5))],
    "chart": [line((4, 20), (20, 20)), closed((6, 14), (9, 14), (9, 20), (6, 20)), closed((11, 9), (14, 9), (14, 20), (11, 20)), closed((16, 5), (19, 5), (19, 20), (16, 20))],
    "flag": [line((6, 21), (6, 4)), closed((6, 4), (18, 6), (13.5, 9), (18, 12), (6, 12))],
    "globe": [circle(12, 12, 9), (ellipse(12, 12, 4, 9), True), line((3, 12), (21, 12))],
    "database": [(ellipse(12, 6, 7, 2.5), True), line((5, 6), (5, 18)), line((19, 6), (19, 18)), (ellipse(12, 18, 7, 2.5, 0, 180), False), (ellipse(12, 12, 7, 2.5, 0, 180), False)],
    "cloud": [(arc(8, 14, 4, 90, 270, 16) + arc(12.5, 10, 5, 200, 340, 16) + arc(17, 13.5, 3.5, 270, 450, 16), True)],
}
