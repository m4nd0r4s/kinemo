"""`Node`: base of every visible object. Every public prop is a signal."""

from __future__ import annotations

import difflib
import json
import re
from typing import TYPE_CHECKING, Any, ClassVar, Iterator, Mapping, Unpack, cast

from .._runtime.context import current_scene
from .._runtime.spans import Span, user_span
from ..anim.animation import Animation
from ..anim.prop import PropTo
from ..diagnostics import KinemoError
from ..diagnostics.manim import manim_attribute
from ..values.encode import encode
from .placement import PlacementMixin
from .props import DERIVED, HIDDEN, RESERVED, TRANSFORM, DerivedExpr, PropSignal, PropSpec, WorldView
from .user_arguments import explicit_props, track

if TYPE_CHECKING:
    from typing import Self

    from ..anim.ease import EaseLike
    from ..events.event import EventSource
    from ..reactive.expr import Expr
    from ..reactive.signal import Blend
    from ..values.aliases import Anchor
    from ..values.vec import Vec
    from .keywords import PlaceKeywords, PropChanges
    from .props import DerivedAccessor, PropAccessor, ReadOnly

#: IR span of a prop the caller did not write.
DEFAULT_SPAN = Span("", 0)

_ASSIGN = re.compile(r"^\s*(?:self\.)?([A-Za-z_]\w*)\s*(?::[^=]+)?=(?!=)\s*(?:\w+\.)?(\w+)(?:\.\w+)?\(")


class Node(PlacementMixin):
    """Objects are values: creating one does not put it in the scene (use `s.add` or a verb)."""

    kind: ClassVar[str] = "group"
    PROPS: ClassVar[dict[str, PropSpec]] = dict(TRANSFORM)
    _all_props: ClassVar[dict[str, PropSpec]]

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        merged: dict[str, PropSpec] = {}
        for base in reversed(cls.__mro__):
            merged.update(getattr(base, "PROPS", {}) if "PROPS" in base.__dict__ else {})
        cls._all_props = merged
        if "__init__" in cls.__dict__:
            cls.__init__ = track(cls.__dict__["__init__"])  # type: ignore[method-assign]

    if TYPE_CHECKING:
        # Per-object state, set with `object.__setattr__` in `__init__`.
        _span: Span
        _key: str | None
        _name: str | None
        _part: str | None
        _sigs: dict[str, PropSignal[Any]]
        _binding_log: dict[str, list[tuple[float, bool, Span]]]

        # Props and layout-derived values, declared for the type checker; at runtime they
        # are resolved by `__getattr__` from `PROPS` (see `ReadOnly`).
        x: PropAccessor[float]
        y: PropAccessor[float]
        rotate: PropAccessor[float]
        scale: PropAccessor[float]
        scale_x: PropAccessor[float]
        scale_y: PropAccessor[float]
        anchor: PropAccessor[Vec]
        opacity: PropAccessor[float]
        z: PropAccessor[float]
        visible: PropAccessor[bool]
        width: DerivedAccessor[float]
        height: DerivedAccessor[float]
        left: DerivedAccessor[float]
        right: DerivedAccessor[float]
        top: DerivedAccessor[float]
        bottom: DerivedAccessor[float]
        center: DerivedAccessor[Vec]
        position: DerivedAccessor[Vec]
        bbox: DerivedAccessor[list[float]]
        #: `obj.world.position`: the same derived values in world coordinates.
        world: ReadOnly[WorldView]

    def __init__(self, *, name: str | None = None, key: str | None = None, **props: object) -> None:
        s = current_scene()
        span = user_span()
        object.__setattr__(self, "_scene", s)
        object.__setattr__(self, "_span", span)
        object.__setattr__(self, "_key", key)
        object.__setattr__(self, "_name", name or _variable_name(span, type(self)))
        object.__setattr__(self, "_part", None)
        object.__setattr__(self, "_sigs", {})
        object.__setattr__(self, "_parent", None)
        object.__setattr__(self, "_place_log", [])
        object.__setattr__(self, "_binding_log", {})
        object.__setattr__(self, "_id", s._b.add_object(self.kind, json.dumps(span.ir()), self._name))
        s._b.add_root(self._id)
        s._nodes.append(self)
        self._init_props(props)

    # ---- props ---------------------------------------------------------------------
    @classmethod
    def _spec(cls, name: str) -> PropSpec | None:
        return cls._all_props.get(name) or HIDDEN.get(name)

    def _init_props(self, values: dict[str, Any]) -> None:
        color = values.pop("color", None)
        if color is not None:
            for p in self._color_props():
                values.setdefault(p, color)
        position = values.pop("position", None)
        if position is not None:
            from ..reactive.expr import Expr

            px, py = (position.x, position.y) if isinstance(position, Expr) else (position[0], position[1])
            values.setdefault("x", px)
            values.setdefault("y", py)
        unknown = [k for k in values if k not in self._all_props]
        if unknown:
            raise self._unknown_prop(unknown[0])
        explicit = explicit_props(self, values)
        for name in self._all_props:
            self._create_signal(name, values.get(name), explicit=name in explicit)

    def _create_signal(self, name: str, value: Any, explicit: bool = False) -> PropSignal[Any]:
        from ..reactive.expr import is_reactive

        spec = self._spec(name)
        assert spec is not None
        s = self._scene
        default = spec.default_value(s.theme)
        initial = default if value is None or is_reactive(value) else value
        encoded = encode(initial, spec.kind)
        # A default (not written by the caller) carries no span: tools show "default"
        # instead of pointing at the constructor line.
        is_default = value is None or (not explicit and encoded == encode(default, spec.kind))
        span = DEFAULT_SPAN if is_default else self._span
        sid = s._b.add_signal(json.dumps(encoded), spec.lerp, (self._id, name), json.dumps(span.ir()))
        s._b.set_prop(self._id, name, sid)
        sig = PropSignal(s, sid, spec.kind, spec.lerp, self, name)
        self._sigs[name] = sig
        if value is not None and is_reactive(value):
            s._push_set(sig, value, self._span)
        return sig

    def _sig(self, name: str) -> PropSignal[Any]:
        sig = self._sigs.get(name)
        if sig is None:
            if self._spec(name) is None:
                raise self._unknown_prop(name)
            sig = self._create_signal(name, None)
        return sig

    def _color_props(self) -> tuple[str, ...]:
        """Props that `color=` sets. Leaves: stroke and fill; groups: their children."""
        return tuple(p for p in ("stroke", "fill") if p in self._all_props)

    if not TYPE_CHECKING:
        # Hidden from the type checker, which sees the declarations above instead: an
        # undeclared attribute is then a static error rather than `Any`.
        def __getattr__(self, name: str) -> Any:
            if name.startswith("__"):
                raise AttributeError(name)
            cls = type(self)
            if name in cls._all_props:
                return self._sig(name)
            if name == "color" and self._color_props():
                return self._sig(self._color_props()[0])
            if name in DERIVED:
                return DerivedExpr(self, name)
            if name == "world":
                return WorldView(self)
            hint = manim_attribute(self, name)
            if hint is not None:
                raise hint
            raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        if name in type(self)._all_props or name == "color" or name in DERIVED:
            raise KinemoError.make(
                "K0105",
                f"props are not assigned with '=': use {self._label()}.set({name}=...)",
                fixes=[("instant", f"{self._label()}.set({name}=...)"), ("animated", f"s.play({self._label()}.to({name}=...))")],
            )
        object.__setattr__(self, name, value)

    def _unknown_prop(self, name: str) -> KinemoError:
        hint = manim_attribute(self, name)
        if hint is not None:
            return hint
        public = [p for p in self._all_props if not p.startswith("_")] + ["color", "position"]
        near = difflib.get_close_matches(name, public, n=1)
        listing = (f"props of {type(self).__name__}: {', '.join(sorted(public))}", None)
        fixes = [(f"did you mean '{near[0]}'?", None)] if near else [listing]
        return KinemoError.make("K0106", f"{type(self).__name__} has no prop '{name}'", fixes=fixes)

    # ---- state ---------------------------------------------------------------------
    def _expand(self, props: Mapping[str, Any], *, for_write: bool) -> list[tuple[PropSignal[Any], Any]]:
        out: list[tuple[PropSignal[Any], Any]] = []
        for name, value in props.items():
            if name in RESERVED:
                raise KinemoError.make("K0105", f"'{name}' is not a prop")
            if name in DERIVED and name != "position":
                raise KinemoError.make(
                    "K0303",
                    f"'{name}' is derived from the layout and is read-only",
                    fixes=[("animate the source (position, scale or size)", None)],
                )
            if name == "color":
                targets = self._color_targets()
                if not targets:
                    raise self._unknown_prop(name)
                out += [(t._sig(p), value) for t, p in targets]
            elif name == "position":
                out += [(self._sig("x"), value[0]), (self._sig("y"), value[1])]
            else:
                out.append((self._sig(name), value))
        return out

    def _color_targets(self) -> list[tuple["Node", str]]:
        return [(self, p) for p in self._color_props()]

    def set(self, **props: Unpack[PropChanges]) -> Self:
        """Instant change at the cursor. A signal or lambda value creates a binding."""
        span = user_span()
        for sig, value in self._expand(props, for_write=True):
            self._scene._push_set(sig, value, span)
        return self

    def to(
        self,
        *,
        duration: float | None = None,
        ease: EaseLike | None = None,
        delay: float = 0.0,
        blend: Blend = "replace",
        place: PlaceKeywords | Mapping[str, object] | None = None,
        unpin: bool = False,
        **props: Unpack[PropChanges],
    ) -> Animation:
        """Animated change of state from the cursor to the given props. `unpin=True`
        releases the placement first, so a placed object can animate `x`/`y` freely."""
        from .placement import Unpin

        span = user_span()
        extra: list[Animation] = []
        if place is not None:
            extra.append(self._place_to(place, span))
        prelude: list[Animation] = [Unpin(self, span)] if unpin else []
        targets = self._expand(props, for_write=True)
        return PropTo(targets, duration=duration, ease=ease, delay=delay, blend=blend, span=span, extra=extra, prelude=prelude)

    def unbind(self, *names: str) -> None:
        """Drop reactive bindings (all props when no name is given), keeping current values."""
        span = user_span()
        for name in names or tuple(self._sigs):
            sig = self._sig(name)
            self._scene._push_set(sig, sig.now, span)

    # ---- checks used by the scene ------------------------------------------------------
    def _check_settable(self, prop: str, span: Span) -> None:
        self._check_animatable_prop(prop, self._scene.cursor, span, animated=False)

    def _check_animatable_prop(self, prop: str, t: float, span: Span, animated: bool = True) -> None:
        if prop not in ("x", "y"):
            return
        label = self._label()
        bound = self._bound_by(prop, t) if animated else None
        if bound is not None:
            raise KinemoError.make(
                "K0401",
                f"'{label}' cannot animate {prop}: the axis is held by a reactive binding",
                spans=[span, bound],
                notes=["", "binding here"],
                time=t,
                objects=[label],
                fixes=[("remove the binding before animating", f'{label}.unbind("{prop}")')],
            )
        why = self._pinned_by(t)
        if why is None:
            return
        parent = self._parent
        if parent is not None and getattr(parent, "is_container", False):
            fixes = [
                ("reorder through the container", f"s.play({parent._label()}.swap(i, j))"),
                ("or move it out of the container first", f"s.play(k.reparent({label}, other_group))"),
            ]
        else:
            fixes = [
                ("change the constraint with an animation", f"s.play({label}.to_place(right_of=...))"),
                ("release it and animate freely", f"s.play({label}.to({prop}=..., unpin=True))"),
            ]
        raise KinemoError.make(
            "K0401",
            f"'{label}' cannot animate {prop}: the axis is held by {why[0]}",
            spans=[span, why[1]],
            notes=["", "constraint here"],
            time=t,
            objects=[label],
            fixes=fixes,
        )

    def _bound_by(self, prop: str, t: float) -> Span | None:
        """Span of the reactive binding holding `prop` at `t`, if any."""
        state: Span | None = None
        for when, bound, span in self._binding_log.get(prop, ()):
            if when <= t + 1e-9:
                state = span if bound else None
        return state

    # ---- tree ------------------------------------------------------------------------
    def _children_at(self, t: float) -> list["Node"]:
        return []

    def _descendants(self, t: float) -> Iterator["Node"]:
        for c in self._children_at(t):
            yield c
            yield from c._descendants(t)

    def _ancestors(self) -> Iterator["Node"]:
        p = self._parent
        while p is not None:
            yield p
            p = p._parent

    def _ancestors_or_self(self) -> list["Node"]:
        return [self, *self._ancestors()]

    def _leaves(self, t: float) -> list["Node"]:
        kids = self._children_at(t)
        if not kids:
            return [self]
        return [leaf for c in kids for leaf in c._leaves(t)]

    def edge(self, name: Anchor = "center") -> Expr[Vec]:
        """Point of the object's box named by an anchor ("right", "top-left", ...), in its
        parent's coordinates, reactive: `k.Arrow(start=a.edge("right"), end=b.edge("left"))`."""
        from ..reactive.native import vec
        from .placement import ANCHORS

        if name not in ANCHORS:
            raise KinemoError.make("K0404", f"unknown anchor {name!r}", fixes=[(f"use one of {', '.join(sorted(ANCHORS))}", None)])
        parts = name.split("-")
        center: DerivedExpr[Vec] = DerivedExpr(self, "center")
        x: Expr[float] = DerivedExpr(self, "left") if "left" in parts else DerivedExpr(self, "right") if "right" in parts else center.x
        y: Expr[float] = DerivedExpr(self, "top") if "top" in parts else DerivedExpr(self, "bottom") if "bottom" in parts else center.y
        return vec(x, y)

    @property
    def age(self) -> "Expr[float]":
        """Seconds since the object (or its nearest present ancestor) last entered the scene."""
        from ..reactive.expr import Op

        return Op("age", {"obj": self._id})

    @property
    def entered(self) -> EventSource[None]:
        """Event at each entry of the object into the scene."""
        return self._lifecycle_event("entered", True)

    @property
    def exited(self) -> EventSource[None]:
        """Event at each exit of the object from the scene."""
        return self._lifecycle_event("exited", False)

    def _lifecycle_event(self, name: str, present: bool) -> EventSource[None]:
        from ..events.event import EventSource

        cache: dict[str, EventSource[None]] = self.__dict__.setdefault("_lifecycle_events", {})
        if name not in cache:
            def times() -> list[tuple[float, Any]]:
                ir = json.loads(self._scene._b.object_presence(self._id))
                return [(t, None) for t, p in ir if p == present]

            source: EventSource[None] = EventSource(self._scene, name, self, computed=times)
            cache[name] = source
        return cache[name]

    def _adopt_into(self, group: Any) -> None:
        group._add_child(self)

    def _grow_parts(self) -> tuple[list["Node"], list["Node"]]:
        """For `k.grow`/`k.shrink`: parts that scale and parts that fade (components override)."""
        return [self], []

    def _label(self) -> str:
        if self._name:
            return self._name
        owner = self.__dict__.get("_parent_label")
        if owner is not None and self._part:
            # A part reachable as an attribute of another object (`curve.label`).
            return f"{owner._label()}.{self._part}"
        parent = self._parent
        if parent is not None:
            if self._part:
                joiner = "" if self._part.startswith(("[", ".")) else "."
                return f"{parent._label()}{joiner}{self._part}"
            kids = parent._children_at(parent._scene.cursor)
            if self in kids:
                return f"{parent._label()}[{kids.index(self)}]"
        return f"{type(self).__name__.lower()}#{self._id}"

    def copy(self, frozen: bool = False) -> Self:
        """A new identity with the same props: the same reactive bindings as this object
        (or, with `frozen=True`, the values at the cursor). The copy starts where this
        object is and is free (no placement)."""
        from .copying import copy_node

        return cast("Self", copy_node(self, frozen))

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self._label()}>"

    def __hash__(self) -> int:
        return id(self)

    def __bool__(self) -> bool:
        return True

    def __eq__(self, other: object) -> bool:
        return self is other


def name_from_factory(node: "Node", factory: str) -> None:
    """`hexagon = k.Polygon.regular(6)`: name an object returned by a factory function."""
    if node._name is not None:
        return
    match = re.match(rf"^\s*([A-Za-z_]\w*)\s*=\s*[\w.\[\]]*\b{factory}\(", node._span.source_line())
    if match:
        object.__setattr__(node, "_name", match.group(1))


def _variable_name(span: Span, cls: type) -> str | None:
    """`title = k.Text(...)` → "title", only when this object is the assigned value."""
    m = _ASSIGN.match(span.source_line())
    if m is None:
        return None
    constructor = m.group(2)
    if any(constructor == c.__name__ for c in cls.__mro__):
        return m.group(1)
    return None

Node._all_props = dict(TRANSFORM)
