"""Colors (sRGB, straight alpha) and the fixed palette."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Color:
    r: float
    g: float
    b: float
    a: float = 1.0

    @staticmethod
    def hex(code: str) -> "Color":
        h = code.lstrip("#")
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8):
            raise ValueError(f"invalid hex color {code!r}")
        vals = [int(h[i : i + 2], 16) / 255 for i in range(0, len(h), 2)]
        return Color(*vals)

    def with_alpha(self, a: float) -> "Color":
        """The same color with another alpha."""
        return Color(self.r, self.g, self.b, a)

    def to_hex(self) -> str:
        """`#RRGGBB` (or `#RRGGBBAA` when translucent)."""
        parts = [self.r, self.g, self.b] + ([self.a] if self.a < 1 else [])
        return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02X}" for c in parts)

    def components(self) -> list[float]:
        """`[r, g, b, a]` in 0..1."""
        return [self.r, self.g, self.b, self.a]

    def __repr__(self) -> str:
        return f"Color({self.to_hex()!r})"


def rgb(r: float, g: float, b: float, a: float = 1.0) -> Color:
    """Color from 0..1 components."""
    return Color(r, g, b, a)


def parse(value: object) -> Color:
    if isinstance(value, Color):
        return value
    if isinstance(value, str):
        return Color.hex(value)
    if isinstance(value, tuple | list) and len(value) in (3, 4):
        return Color(*(float(c) for c in value))  # type: ignore[arg-type]
    raise TypeError(f"not a color: {value!r}")


BLUE = Color.hex("#4C9BE8")
RED = Color.hex("#E8645A")
GREEN = Color.hex("#5CC489")
YELLOW = Color.hex("#F5C542")
ORANGE = Color.hex("#F29A4A")
PURPLE = Color.hex("#A57BE0")
PINK = Color.hex("#E879B9")
TEAL = Color.hex("#45C1C0")
WHITE = Color.hex("#F2F2F2")
BLACK = Color.hex("#111216")
GRAY = Color.hex("#8A8F98")
TRANSPARENT = Color(0, 0, 0, 0)

PALETTE = {
    "BLUE": BLUE,
    "RED": RED,
    "GREEN": GREEN,
    "YELLOW": YELLOW,
    "ORANGE": ORANGE,
    "PURPLE": PURPLE,
    "PINK": PINK,
    "TEAL": TEAL,
    "WHITE": WHITE,
    "BLACK": BLACK,
    "GRAY": GRAY,
}
