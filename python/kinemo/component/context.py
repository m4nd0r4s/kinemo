"""Context: values many components need (theme, clock, units), provided lexically at build."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Iterator, TypeVar, overload

if TYPE_CHECKING:
    from ..reactive.expr import Val

T = TypeVar("T")

_values: ContextVar[dict[str, Any]] = ContextVar("kinemo_context", default={})


@dataclass(frozen=True)
class Context(Generic[T]):
    """`Clock = k.context("clock", default=k.time)`, declared at module level."""

    name: str
    default: T

    def get(self) -> T:
        """Value provided for this context in the enclosing `k.provide` block, or the default."""
        return _values.get().get(self.name, self.default)


@overload
def context(name: str, default: T) -> Context[T]: ...
@overload
def context(name: str) -> Context[Any]: ...
def context(name: str, default: Any = None) -> Context[Any]:
    return Context(name, default)


@contextmanager
def provide(ctx: Context[T], value: Val[T]) -> Iterator[None]:
    """Components constructed inside the block receive `value` for `ctx`."""
    token = _values.set({**_values.get(), ctx.name: value})
    try:
        yield
    finally:
        _values.reset(token)


@dataclass(frozen=True)
class FromContext:
    """Default marker: `clock: k.Prop[float] = k.from_context(Clock)`."""

    ctx: Context[Any]


def from_context(ctx: Context[Any]) -> Any:
    """Default of a prop or field read from `ctx` at construction. Typed `Any` on purpose:
    the same marker is a valid default for `k.Prop[T]` and for static fields."""
    return FromContext(ctx)
