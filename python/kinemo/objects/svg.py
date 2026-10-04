"""`k.SVG`: an SVG illustration imported as kinemo paths and groups, with its parts
addressable by SVG id (`svg["#motor"]`)."""

from __future__ import annotations

import difflib
import json
import os
from typing import TYPE_CHECKING, Any, ClassVar, Unpack

from .._runtime.context import current_scene
from .._runtime.spans import user_span
from ..diagnostics import KinemoError
from .groups import Group
from .media_paths import media_error, resolve_media_path
from .node import Node
from .props import PropSpec
from .shapes import Path

if TYPE_CHECKING:
    from .keywords import TransformKeywords
    from .props import PropAccessor


class SVGPath(Path):
    """A path imported from an SVG file: a `k.Path` that also keeps the SVG fill rule and
    the ends and corners of its stroke (`line_cap`, `line_join`)."""

    PROPS: ClassVar[dict[str, PropSpec]] = {
        "fill_rule": PropSpec("str", "nonzero", "step_end", ("nonzero", "evenodd")),
        "line_cap": PropSpec("str", "round", "step_end", ("butt", "round", "square")),
        "line_join": PropSpec("str", "round", "step_end", ("miter", "round", "bevel")),
    }

    if TYPE_CHECKING:
        fill_rule: PropAccessor[str]
        line_cap: PropAccessor[str]
        line_join: PropAccessor[str]


def _read_source(source: Any) -> tuple[bytes, str]:
    """SVG bytes and a short name for messages. Markup can be passed inline."""
    if isinstance(source, str) and source.lstrip().startswith("<"):
        return source.encode("utf-8"), "<svg inline>"
    path = resolve_media_path(source, "k.SVG")
    with open(path, "rb") as fh:
        return fh.read(), path


def _path_props(node: dict[str, Any]) -> dict[str, Any]:
    fill, stroke = node["fill"], node["stroke"]
    props: dict[str, Any] = {"closed": fill is not None, "fill_rule": "evenodd" if node["even_odd"] else "nonzero"}
    if fill is not None:
        props["fill"] = (fill[0], fill[1], fill[2], 1.0)
        props["fill_opacity"] = fill[3]
    else:
        props["fill_opacity"] = 0.0
    if stroke is not None:
        props["stroke"] = tuple(stroke)
        props["stroke_width"] = node["stroke_width"]
        props["line_cap"] = node["line_cap"]
        props["line_join"] = node["line_join"]
    else:
        props["stroke_width"] = 0.0
    return props


class SVG(Group):
    """`k.SVG("motor.svg", height=3)`: each SVG shape becomes a `k.Path` with its fill,
    stroke and stroke width; `<g>` elements stay groups. The drawing is scaled so its
    height is `height` units and centered on the object's position. Elements with an
    `id` are addressable: `svg["#motor"]` (or `svg["motor"]`); `svg.ids` lists them."""

    if TYPE_CHECKING:
        _svg_tree: dict[str, Any]
        _by_id: dict[str, Node | None]

    def __init__(self, source: str | os.PathLike[str], height: float = 3.0, **props: Unpack[TransformKeywords]) -> None:
        data, origin = _read_source(source)
        try:
            tree = json.loads(current_scene()._b.svg_import(data, float(height)))
        except ValueError as e:
            raise media_error("k.SVG", origin, str(e)) from None
        object.__setattr__(self, "_svg_tree", tree)
        object.__setattr__(self, "_by_id", {})
        super().__init__(**props)

    def _parts(self) -> list[Node]:
        return [self._build(node, i) for i, node in enumerate(self._svg_tree["children"])]

    def _build(self, node: dict[str, Any], index: int) -> Node:
        built: Node
        element_id = node.get("id")
        if element_id and element_id not in self._by_id:
            self._by_id[element_id] = None  # reserves document order (parents first)
        if node["type"] == "group":
            kids = [self._build(child, i) for i, child in enumerate(node["children"])]
            built = Group(*kids, opacity=node["opacity"])
        else:
            built = SVGPath(node["d"], **_path_props(node))
        if element_id and self._by_id[element_id] is None:
            self._by_id[element_id] = built
        # Parts are labeled like `logo["#motor"]` / `logo[2]` and are not user leaves.
        object.__setattr__(built, "_part", f'["#{element_id}"]' if element_id else f"[{index}]")
        return built

    @property
    def ids(self) -> list[str]:
        """Ids of the addressable elements, in document order."""
        return list(self._by_id)

    def __getitem__(self, key: str | int) -> Node:
        """`svg["#motor"]`: the element with that SVG id; `svg[i]`: the i-th child."""
        if not isinstance(key, str):
            return super().__getitem__(key)
        name = key[1:] if key.startswith("#") else key
        found = self._by_id.get(name)
        if found is None:
            near = difflib.get_close_matches(name, self.ids, n=1)
            fixes = [(f'did you mean "#{near[0]}"?', None)] if near else [(f"ids in this SVG: {', '.join(self.ids) or '(none)'}", None)]
            raise KinemoError.make("K0105", f"the SVG has no element with id {name!r}", spans=[user_span()], fixes=fixes)
        return found
