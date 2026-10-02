"""Which constructor arguments the caller wrote, so tools can tell an explicit prop from a
default one (the `dev` inspector labels the latter "default" instead of pointing at a line).

Subclass constructors pass their own defaults up (`Dot(r=0.08)` calls `Shape(r=r)`), so the
props reaching `Node.__init__` cannot tell. The outermost constructor call records the
names the caller actually bound; inner `super().__init__` calls leave the record alone.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

#: Instance attribute holding the recorded names.
ATTRIBUTE = "_user_arguments"

#: Shorthand arguments that set several props.
_EXPANSIONS = {"color": ("fill", "stroke"), "position": ("x", "y")}


def track(init: Callable[..., None]) -> Callable[..., None]:
    """Wraps a constructor so its outermost call records the argument names it received."""
    signature: inspect.Signature | None = None

    @functools.wraps(init)
    def wrapper(self: object, *args: Any, **kwargs: Any) -> None:
        nonlocal signature
        if ATTRIBUTE not in vars(self):
            if signature is None:
                signature = inspect.signature(init)
            object.__setattr__(self, ATTRIBUTE, _bound_names(signature, self, args, kwargs))
        init(self, *args, **kwargs)

    return wrapper


def _bound_names(signature: inspect.Signature, self: object, args: tuple[Any, ...], kwargs: dict[str, Any]) -> frozenset[str]:
    try:
        bound = signature.bind(self, *args, **kwargs)
    except TypeError:  # the constructor itself reports the bad call
        return frozenset(kwargs)
    names: set[str] = set()
    for index, (name, value) in enumerate(bound.arguments.items()):
        if index == 0:
            continue  # self
        kind = signature.parameters[name].kind
        if kind is inspect.Parameter.VAR_KEYWORD:
            names.update(value)
        elif kind is not inspect.Parameter.VAR_POSITIONAL:
            names.add(name)
    for shorthand, props in _EXPANSIONS.items():
        if shorthand in names:
            names.update(props)
    return frozenset(names)


def explicit_props(node: object, props: dict[str, Any]) -> frozenset[str]:
    """Props the caller wrote: the recorded names, or `props` itself for a bare `Node`."""
    recorded = vars(node).get(ATTRIBUTE)
    if recorded is None:
        names = set(props)
        for shorthand, expanded in _EXPANSIONS.items():
            if shorthand in names:
                names.update(expanded)
        return frozenset(names)
    return recorded
