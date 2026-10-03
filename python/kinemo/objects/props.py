"""Prop declarations and the signal wrappers objects expose (`obj.x`, `obj.left`)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar, overload

from ..reactive.expr import IR, Expr
from ..reactive.signal import Signal
from ..theme.tokens import Theme, ThemeToken
from ..values.encode import decode
from ..values.vec import Vec

if TYPE_CHECKING:
    from typing import Self

    from ..scene.scene import Scene
    from .node import Node

T = TypeVar("T")
V = TypeVar("V")


@dataclass(frozen=True)
class PropSpec:
    kind: str
    default: Any
    lerp: str = "linear"
    #: The accepted values of a `str` prop that is an enumeration (`align`), for tools.
    choices: tuple[str, ...] | None = None

    def default_value(self, theme: Theme) -> Any:
        d = self.default
        if isinstance(d, ThemeToken):
            return d.resolve(theme)
        if callable(d):
            return d(theme)
        return d


def fg(t: Theme) -> Any:
    return t.fg


def accent(t: Theme) -> Any:
    return t.accent


def stroke_width(t: Theme) -> Any:
    return t.stroke_width


TRANSFORM: dict[str, PropSpec] = {
    "x": PropSpec("float", 0.0),
    "y": PropSpec("float", 0.0),
    "rotate": PropSpec("float", 0.0),
    "scale": PropSpec("float", 1.0),
    "scale_x": PropSpec("float", 1.0),
    "scale_y": PropSpec("float", 1.0),
    "anchor": PropSpec("vec2", (0.0, 0.0)),
    "opacity": PropSpec("float", 1.0),
    "z": PropSpec("float", 0.0),
    "visible": PropSpec("bool", True, "step_end"),
}

STYLE: dict[str, PropSpec] = {
    "fill": PropSpec("color", fg),
    "fill_opacity": PropSpec("float", 0.0),
    "stroke": PropSpec("color", fg),
    "stroke_width": PropSpec("float", stroke_width),
    "dash": PropSpec("floats", (), "step_end"),
}

#: Render-only props driven by verbs; created on first use.
HIDDEN: dict[str, PropSpec] = {
    "_draw": PropSpec("float", 1.0),
    "_write": PropSpec("float", 1.0),
    "_fade": PropSpec("float", 1.0),
    "_grow": PropSpec("float", 1.0),
    "_grow_from": PropSpec("vec2", (0.0, 0.0), "step_end"),
    "_shift": PropSpec("vec2", (0.0, 0.0)),
    "_tint": PropSpec("color", fg, "step_end"),
    "_tint_amount": PropSpec("float", 0.0),
    "_pulse": PropSpec("float", 1.0),
    "_pulse_from": PropSpec("vec2", (0.0, 0.0), "step_end"),
    "_squash": PropSpec("float", 0.0),
}

#: Read-only values computed by the layout engine.
DERIVED = ("width", "height", "left", "right", "top", "bottom", "center", "bbox", "position")

#: Names that are never props.
RESERVED = ("duration", "ease", "delay", "place", "blend")


class PropSignal(Signal[T]):
    """A prop of an object: a signal whose writes go through the object's checks."""

    __slots__ = ("_node", "_prop")

    def __init__(self, scene: "Scene", sid: int, kind: str, lerp_mode: str, node: "Node", prop: str) -> None:
        super().__init__(scene, sid, kind, lerp_mode)
        self._node = node
        self._prop = prop

    def _ir(self) -> IR:
        if self._prop in ("x", "y"):
            return {"op": "derived", "obj": self._node._id, "prop": self._prop, "world": False}
        return super()._ir()

    @property
    def now(self) -> T:
        if self._prop in ("x", "y"):
            return _expression_now(self)
        return super().now

    def __repr__(self) -> str:
        return f"{self._node._label()}.{self._prop}"


def _expression_now(expr: Expr[T]) -> T:
    """`Expr.now` itself (evaluating the IR), skipping a subclass's override."""
    now = Expr.now.fget
    assert now is not None
    return now(expr)


class DerivedExpr(Expr[T]):
    """`obj.left`, `obj.width`, ...: computed by layout, read-only (K0303 on writes)."""

    __slots__ = ("_node", "_prop", "_world", "kind")

    def __init__(self, node: "Node", prop: str, world: bool = False) -> None:
        self._node = node
        self._prop = prop
        self._world = world
        self.kind = "vec2" if prop in ("center", "position") else ("list" if prop == "bbox" else "float")

    def _ir(self) -> IR:
        return {"op": "derived", "obj": self._node._id, "prop": self._prop, "world": self._world}

    @property
    def now(self) -> T:
        from .._runtime.context import tracing

        if tracing():
            return _expression_now(self)
        s = self._node._scene
        return decode(json.loads(s._b.derived(self._node._id, self._prop, s.cursor, self._world)))

    def __repr__(self) -> str:
        return f"{self._node._label()}.{self._prop}"


class WorldView:
    """`obj.world.position`: global (world) coordinates of layout-derived values."""

    def __init__(self, node: "Node") -> None:
        self._node = node

    if TYPE_CHECKING:
        x: ReadOnly[DerivedExpr[float]]
        y: ReadOnly[DerivedExpr[float]]
        width: ReadOnly[DerivedExpr[float]]
        height: ReadOnly[DerivedExpr[float]]
        left: ReadOnly[DerivedExpr[float]]
        right: ReadOnly[DerivedExpr[float]]
        top: ReadOnly[DerivedExpr[float]]
        bottom: ReadOnly[DerivedExpr[float]]
        center: ReadOnly[DerivedExpr[Vec]]
        position: ReadOnly[DerivedExpr[Vec]]
        bbox: ReadOnly[DerivedExpr[list[float]]]
    else:

        def __getattr__(self, name: str) -> DerivedExpr[Any]:
            if name in DERIVED or name in ("x", "y"):
                return DerivedExpr(self._node, name, world=True)
            raise AttributeError(name)


class ReadOnly(Generic[V]):
    """Static declaration of an attribute resolved dynamically (`Node.__getattr__`).

    Objects declare their props for the type checker only, in `if TYPE_CHECKING:` blocks
    (`r: PropAccessor[float]`), so runtime lookup is unchanged. As a descriptor without
    `__set__`, it also makes `obj.r = 3` a static error (props change with `.set`/`.to`)."""

    if TYPE_CHECKING:

        @overload
        def __get__(self, instance: None, owner: type[object]) -> Self: ...
        @overload
        def __get__(self, instance: object, owner: type[object]) -> V: ...
        def __get__(self, instance: object, owner: type[object]) -> V | Self: ...


#: `r: PropAccessor[float]` declares the prop `obj.r` as a `PropSignal[float]`.
PropAccessor = ReadOnly[PropSignal[T]]
#: `left: DerivedAccessor[float]` declares a layout-derived, read-only value.
DerivedAccessor = ReadOnly[DerivedExpr[T]]

Factory = Callable[..., Any]
