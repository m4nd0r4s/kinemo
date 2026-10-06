"""`k.Icon("check")`: a built-in icon, stroked like any shape."""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING, Any, Unpack

from ...diagnostics import KinemoError
from ..groups import Group
from ..node import Node
from ..props import PropSpec, fg
from ..shapes import Path
from .shapes import ICONS

if TYPE_CHECKING:
    from ...values.aliases import ColorLike
    from ...values.color import Color
    from ..keywords import TransformKeywords
    from ..props import PropAccessor

__all__ = ["ICON_NAMES", "Icon"]

#: Names of the built-in icons.
ICON_NAMES: tuple[str, ...] = tuple(sorted(ICONS))


class Icon(Group):
    """`k.Icon("lightbulb", size=1, color=k.YELLOW)`: a built-in icon (`k.ICON_NAMES`) drawn
    with strokes on a square of side `size`. `stroke` and `stroke_width` are the icon's own
    props: `icon.to(stroke=k.RED)` recolors every stroke."""

    PROPS = {"stroke": PropSpec("color", fg), "stroke_width": PropSpec("float", 3.0)}

    if TYPE_CHECKING:
        stroke: PropAccessor[Color]
        stroke_width: PropAccessor[float]
        #: Which icon (a name of `k.ICON_NAMES`).
        icon: str
        _icon_size: float

    def __init__(self, icon: str, *, size: float = 1.0, color: ColorLike | None = None, stroke_width: float = 3.0, **props: Unpack[TransformKeywords]) -> None:
        if icon not in ICONS:
            close = difflib.get_close_matches(icon, ICON_NAMES, n=3)
            raise KinemoError.make(
                "K0105",
                f"unknown icon {icon!r}",
                fixes=[(f"did you mean {', '.join(repr(c) for c in close)}?", None)] if close else [(f"icons: {', '.join(ICON_NAMES)}", None)],
            )
        object.__setattr__(self, "icon", icon)
        object.__setattr__(self, "_icon_size", float(size))
        options: dict[str, Any] = {"stroke_width": stroke_width}
        if color is not None:
            options["stroke"] = color
        super().__init__(**options, **props)

    def _parts(self) -> list[Node]:
        scale = self._icon_size / 24.0
        parts: list[Node] = []
        for points, is_closed in ICONS[self.icon]:
            local = [((x - 12.0) * scale, (12.0 - y) * scale) for x, y in points]
            # Every stroke follows the icon's own stroke props.
            parts.append(Path(local, closed=is_closed, stroke=self.stroke, stroke_width=self.stroke_width, fill_opacity=0.0))
        return parts
