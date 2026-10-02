"""`k.Component`: one form for reusable objects, written with the public API."""

from __future__ import annotations

import sys
import typing
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from typing import Self

from ..diagnostics import KinemoError
from ..events.event import Event, EventSource
from ..objects.groups import Group
from ..objects.node import Node
from ..objects.props import PropSpec
from ..reactive.expr import Expr, is_reactive
from ..values.color import Color
from ..values.vec import Vec
from .context import FromContext
from .declarations import FieldSpec, Out, Prop

_KINDS: dict[Any, str] = {float: "float", int: "float", bool: "bool", str: "str", Color: "color", Vec: "vec2"}


def _kind_of(tp: Any) -> str:
    if tp in _KINDS:
        return _KINDS[tp]
    origin = typing.get_origin(tp)
    if origin is tuple:
        return "vec2"
    if origin in (list, typing.List):  # noqa: UP006
        return "list"
    return "float"


class Component(Group):
    """Subclass with `k.Prop[T]` inputs, static fields, `k.Out[T]` outputs and `k.Event`s,
    and a `build()` returning the visual. Verbs use `enter()`/`exit()`/`indicate()` if defined."""

    _component_props: ClassVar[dict[str, tuple[PropSpec, Any]]] = {}
    _component_fields: ClassVar[dict[str, Any]] = {}
    _component_outs: ClassVar[tuple[str, ...]] = ()
    _component_events: ClassVar[tuple[str, ...]] = ()

    def __init_subclass__(cls, **kw: Any) -> None:
        hints = _hints(cls)
        own = _own_annotation_names(cls)
        props: dict[str, tuple[PropSpec, Any]] = dict(getattr(cls, "_component_props", {}))
        fields: dict[str, Any] = dict(getattr(cls, "_component_fields", {}))
        outs: list[str] = list(getattr(cls, "_component_outs", ()))
        events: list[str] = list(getattr(cls, "_component_events", ()))
        for name, tp in hints.items():
            if name.startswith("_") or name not in own:
                continue
            _check_reserved(cls, name)
            origin = typing.get_origin(tp) or tp
            default = cls.__dict__.get(name)
            if origin is Prop:
                args = typing.get_args(tp)
                inner = args[0] if args else float
                spec = PropSpec(_kind_of(inner), _plain_default(default), "step_end" if _kind_of(inner) in ("str", "bool", "list") else "linear")
                props[name] = (spec, default)
            elif origin is Out:
                outs.append(name)
            elif origin is Event:
                events.append(name)
            else:
                fields[name] = default
            if name in cls.__dict__:
                delattr(cls, name)
        cls._component_props = props
        cls._component_fields = fields
        cls._component_outs = tuple(outs)
        cls._component_events = tuple(events)
        cls.PROPS = {n: spec for n, (spec, _) in props.items()}  # type: ignore[misc]
        super().__init_subclass__(**kw)

    def __init__(self, *, name: str | None = None, **kwargs: object) -> None:
        cls = type(self)
        label = cls.__name__
        for n, default in cls._component_fields.items():
            value = kwargs.pop(n, _field_default(default))
            if isinstance(value, FromContext):
                value = value.ctx.get()
            if isinstance(value, Expr) or is_reactive(value) and not isinstance(value, type):
                raise KinemoError.make(
                    "K0601",
                    f"{label}.{n} is a static field and does not accept reactive values",
                    fixes=[("declare it as a reactive prop", f"{n}: k.Prop[float] = ...")],
                )
            if isinstance(default, FieldSpec):
                default.validate(label, n, value)
            object.__setattr__(self, n, value)
        reactive: dict[str, Any] = {}
        for n, (spec, default) in cls._component_props.items():
            value = kwargs.pop(n, None)
            if value is None and isinstance(default, FromContext):
                value = default.ctx.get()
            if isinstance(default, FieldSpec) and value is not None and not is_reactive(value):
                default.validate(label, n, value)
            if value is not None:
                reactive[n] = value
        for n in cls._component_outs + cls._component_events:
            if n in kwargs:
                raise KinemoError.make("K0105", f"{label}.{n} is an output, not an argument")
        object.__setattr__(self, "_building", True)
        from .._runtime.context import current_scene

        stack = current_scene()._component_stack
        stack.append(self)
        try:
            passthrough: dict[str, Any] = kwargs  # transform props, checked by `Node`
            super().__init__(name=name, **reactive, **passthrough)
        finally:
            stack.pop()
            object.__setattr__(self, "_building", False)

    def _parts(self) -> list[Node]:
        for n in type(self)._component_events:
            object.__setattr__(self, n, EventSource(self._scene, n, self))
        built = self.build()
        if not isinstance(built, Node):
            raise KinemoError.make("K0105", f"{type(self).__name__}.build() must return a k.Node, returned {type(built).__name__}")
        missing = [n for n in type(self)._component_outs if n not in self.__dict__]
        if missing:
            raise KinemoError.make(
                "K0602",
                f"{type(self).__name__}.build() did not assign {', '.join(missing)}",
                fixes=[(f"assign it in build(): self.{missing[0]} = ...", None)],
            )
        if built._part is None and built._name is None:
            object.__setattr__(built, "_part", "body")
        return [built]

    def build(self) -> Node:
        """Return the component's visual (a node built from the props); runs once, at construction."""
        raise NotImplementedError(f"{type(self).__name__} must implement build()")

    def __setattr__(self, name: str, value: Any) -> None:
        if isinstance(value, Node) and value._part is None and value._name is None:
            object.__setattr__(value, "_part", name)
        if name in type(self)._component_fields and not self.__dict__.get("_building", False):
            raise KinemoError.make("K0105", f"static fields cannot change after construction: {name}")
        super().__setattr__(name, value)

    def _color_targets(self) -> list[tuple[Node, str]]:
        return [t for c in self.children for t in c._color_targets()]

    def copy(self, frozen: bool = False) -> Self:
        """Rebuilds the component with the same arguments."""
        return super().copy(frozen)


def _check_reserved(cls: type, name: str) -> None:
    """A component field must not hide a built-in prop, a layout-derived value or a method."""
    from ..objects.props import DERIVED, STYLE, TRANSFORM

    reserved = set(TRANSFORM) | set(STYLE) | set(DERIVED) | {"color", "world", "age", "children"}
    reserved |= {n for n in dir(Group) if not n.startswith("_")}
    if name in reserved:
        raise KinemoError.make(
            "K0105",
            f"{cls.__name__}.{name} hides the built-in '{name}' of every object",
            fixes=[(f"rename the field, e.g. {name}_value", None)],
        )


def _plain_default(default: Any) -> Any:
    if isinstance(default, FieldSpec):
        return default.default
    if isinstance(default, FromContext):
        return 0.0
    return 0.0 if default is None else default


def _field_default(default: Any) -> Any:
    return default.default if isinstance(default, FieldSpec) else default


def _own_annotation_names(cls: type) -> set[str]:
    import inspect

    try:
        return set(inspect.get_annotations(cls))
    except Exception:  # noqa: BLE001
        return set(cls.__dict__.get("__annotations__", {}))


def _hints(cls: type) -> dict[str, Any]:
    """The class's own annotations, evaluated (string annotations resolved in its module)."""
    import inspect

    import kinemo

    module = sys.modules.get(cls.__module__)
    globalns = {"k": kinemo, **(dict(vars(module)) if module else {})}
    try:
        return dict(inspect.get_annotations(cls, globals=globalns, eval_str=True))
    except Exception:  # noqa: BLE001 - unresolvable annotations are treated as static fields
        return {n: Any for n in _own_annotation_names(cls)}
