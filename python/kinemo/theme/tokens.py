"""Theme definition, built-in themes and the lazy `k.theme.*` tokens."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ..values.color import Color


@dataclass(frozen=True)
class Theme:
    name: str
    bg: Color
    fg: Color
    accent: Color
    muted: Color
    secondary: Color
    font_size: float = 0.5
    stroke_width: float = 4.0
    extra: dict[str, Any] = field(default_factory=dict)

    def with_(self, **changes: object) -> "Theme":
        """A copy of the theme with some tokens changed."""
        return replace(self, **changes)


class _Themes:
    dark = Theme(
        "dark",
        bg=Color.hex("#14151A"),
        fg=Color.hex("#ECEEF2"),
        accent=Color.hex("#4C9BE8"),
        muted=Color.hex("#6B7280"),
        secondary=Color.hex("#F5C542"),
    )
    light = Theme(
        "light",
        bg=Color.hex("#FAFAF7"),
        fg=Color.hex("#1B1D22"),
        accent=Color.hex("#2F6FD0"),
        muted=Color.hex("#9AA0AA"),
        secondary=Color.hex("#D98E04"),
    )
    blueprint = Theme(
        "blueprint",
        bg=Color.hex("#0F2A4A"),
        fg=Color.hex("#E6F0FA"),
        accent=Color.hex("#7FD1FF"),
        muted=Color.hex("#5C7FA3"),
        secondary=Color.hex("#FFD166"),
    )


themes = _Themes()
DEFAULT = themes.dark


@dataclass(frozen=True)
class ThemeToken:
    """A reference to a theme value, resolved when the scene is built."""

    name: str

    def resolve(self, t: Theme | None = None) -> Any:
        from .._runtime.context import maybe_scene

        if t is None:
            s = maybe_scene()
            t = s.theme if s is not None else DEFAULT
        if hasattr(t, self.name):
            return getattr(t, self.name)
        return t.extra[self.name]


class _ThemeProxy:
    """`k.theme.accent` → a token, so themes can change without touching scene code."""

    def __getattr__(self, name: str) -> ThemeToken:
        if name.startswith("_"):
            raise AttributeError(name)
        return ThemeToken(name)


theme = _ThemeProxy()
