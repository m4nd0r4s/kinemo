"""`k.Math`: LaTeX syntax laid out natively (no TeX installation), with addressable parts.

`\\id{name}{...}` names a subexpression (`eq["name"]`); any TeX subexpression can be
looked up by syntax tree (`eq["c^2"]` ≡ `eq["c^{2}"]`)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Unpack, overload

from .._runtime.spans import user_span
from ..diagnostics import KinemoError
from .props import PropSpec
from .node import Node
from .text import TEXT_STYLE, TextLike, TextPart

if TYPE_CHECKING:
    from .keywords import StyleKeywords
    from .props import PropAccessor


class Math(TextLike):
    kind = "math"
    PROPS = {
        **TEXT_STYLE,
        "tex": PropSpec("str", "", "step_end"),
        "size": PropSpec("float", 0.6),
        "display": PropSpec("bool", True, "step_end"),
    }

    if TYPE_CHECKING:
        tex: PropAccessor[str]
        display: PropAccessor[bool]

    def __init__(self, tex: str, *, size: float = 0.6, display: bool = True, engine: str = "builtin", **props: Unpack[StyleKeywords]) -> None:
        from .._runtime.context import current_scene

        if engine != "builtin":
            raise KinemoError.make(
                "K0105",
                f"engine={engine!r} is not available in this installation yet",
                fixes=[("use the built-in engine", 'k.Math(r"...")')],
            )
        error = current_scene()._b.math_error(tex, float(size), bool(display))
        if error is not None:
            code, message, command = error
            raise KinemoError.make(
                code,
                f"LaTeX not supported by the built-in engine: {message}",
                spans=[user_span()],
                fixes=[("rewrite it with mathematical commands the built-in engine supports (engine=\"tex\" for full LaTeX is planned, not available in 1.0)", None)]
                if command
                else [("check the LaTeX syntax", None)],
            )
        super().__init__(tex=tex, size=size, display=display, **props)

    def _info(self) -> dict[str, Any]:
        s = self._scene
        return json.loads(s._b.math_info(self.tex.now, self.size.now, self.display.now))

    @overload
    def __getitem__(self, key: str) -> TextPart: ...
    @overload
    def __getitem__(self, key: int) -> Node: ...
    def __getitem__(self, key: str | int) -> Node:
        if not isinstance(key, str):
            return super().__getitem__(key)
        matches = self._scene._b.math_find(self.tex.now, key, self.size.now, self.display.now)
        if not matches:
            raise KinemoError.make(
                "K0105",
                f"{key!r} is neither an \\id nor a subexpression of {self._label()}",
                fixes=[("name the subexpression", rf"\id{{name}}{{{key}}}")],
            )
        return self._run_for(("tex", key, 0), list(matches[0]))

    def find_all(self, needle: str) -> list[TextPart]:
        matches = self._scene._b.math_find(self.tex.now, needle, self.size.now, self.display.now)
        return [self._run_for(("tex", needle, i), list(m)) for i, m in enumerate(matches)]

    def _char_text(self) -> str:
        return ""
