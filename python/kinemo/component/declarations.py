"""Declarations used in component class bodies: `k.Prop[T]`, `k.Out[T]`, `k.Event`, `k.field`.

How the declarations type-check (Pyright strict)
-------------------------------------------------

`k.Prop[T]`, `k.Out[T]` and `k.Event[P]` are read at runtime by `Component.__init_subclass__`
from the class annotations; for the type checker they are *descriptors*, declared only
under `TYPE_CHECKING` (runtime behavior is untouched):

    class Battery(k.Component):
        power: k.Prop[float] = k.prop(0.0)      # self.power: Signal[float]
        capacity: float = 10.0                  # self.capacity: float (static field)
        initial: float = k.field(0.2, range=(0, 1))
        soc: k.Out[float]                       # self.soc: Expr[float]; assigned in build()
        full: k.Event                           # self.full: EventSource[None]

- `Prop[T].__get__` gives `Signal[T]` on instances: inside the component a prop is always
  a signal, whatever the caller passed.
- `Out[T].__get__` gives `Expr[T]` (read-only for readers) and `Out[T].__set__` accepts
  an expression, so `self.soc = k.integrate(...)` in `build()` type-checks.
- A prop's default must be written `k.prop(default)` for the type checker: a plain
  `power: k.Prop[float] = 0.0` works at runtime, but no descriptor type can accept a
  bare `float` in the class body while reading as `Signal[float]` on instances, so
  Pyright reports that assignment. `k.prop` returns the declaration type itself.
- `k.field(default)` returns the default's own type (a static field is a plain value).
- `k.from_context(ctx)` is valid as the default of a prop or of a field, so it is typed
  `Any` (the one deliberately dynamic default).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Sequence, TypeVar, overload

if TYPE_CHECKING:
    from typing import Self

    from ..reactive.expr import Expr
    from ..reactive.signal import Signal

T = TypeVar("T")


class Prop(Generic[T]):
    """Reactive input. Inside the component it is always a signal, even if a constant was passed."""

    if TYPE_CHECKING:

        @overload
        def __get__(self, instance: None, owner: type[object]) -> Self: ...
        @overload
        def __get__(self, instance: object, owner: type[object]) -> Signal[T]: ...
        def __get__(self, instance: object, owner: type[object]) -> Signal[T] | Self: ...


class Out(Generic[T]):
    """Continuous output: a read-only signal assigned in `build()`."""

    if TYPE_CHECKING:

        @overload
        def __get__(self, instance: None, owner: type[object]) -> Self: ...
        @overload
        def __get__(self, instance: object, owner: type[object]) -> Expr[T]: ...
        def __get__(self, instance: object, owner: type[object]) -> Expr[T] | Self: ...
        def __set__(self, instance: object, value: Expr[T]) -> None: ...


@dataclass(frozen=True)
class FieldSpec:
    """Default plus validation for a field or prop: `k.field(0.2, range=(0, 1))`."""

    default: Any
    range: tuple[float, float] | None = None
    choices: Sequence[Any] | None = None

    def validate(self, owner: str, name: str, value: Any) -> None:
        from ..diagnostics import KinemoError

        if self.range is not None and isinstance(value, int | float):
            lo, hi = self.range
            if not lo <= value <= hi:
                raise KinemoError.make(
                    "K0105",
                    f"{owner}.{name} = {value} is outside the range [{lo}, {hi}]",
                    fixes=[(f"use a value between {lo} and {hi}", None)],
                )
        if self.choices is not None and value not in self.choices:
            raise KinemoError.make("K0105", f"{owner}.{name} = {value!r} is not one of the options {list(self.choices)}")


@overload
def field(default: T, *, range: tuple[float, float] | None = None, choices: Sequence[T] | None = None) -> T: ...  # noqa: A002
@overload
def field(*, range: tuple[float, float] | None = None, choices: Sequence[Any] | None = None) -> Any: ...  # noqa: A002
def field(default: Any = None, *, range: tuple[float, float] | None = None, choices: Sequence[Any] | None = None) -> Any:  # noqa: A002
    """Default of a static field, validated at construction: `inicial: float = k.field(0.2, range=(0, 1))`.

    Typed as the default's own type: the class body sees a plain value."""
    return FieldSpec(default, range, choices)


@overload
def prop(default: bool, *, range: tuple[float, float] | None = None) -> Prop[bool]: ...  # pyright: ignore[reportOverlappingOverload] - bool before float
@overload
def prop(default: float, *, range: tuple[float, float] | None = None) -> Prop[float]: ...
@overload
def prop(default: T, *, range: tuple[float, float] | None = None) -> Prop[T]: ...
def prop(default: Any = None, *, range: tuple[float, float] | None = None) -> Any:
    """Default of a reactive prop: `power: k.Prop[float] = k.prop(0.0, range=(-5, 5))`."""
    return FieldSpec(default, range, None)
