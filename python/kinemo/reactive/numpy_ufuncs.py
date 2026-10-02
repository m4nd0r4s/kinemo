"""numpy ufuncs applied to expressions: traced to the same native operations as `k.*`."""

from __future__ import annotations

from typing import Any

from ..diagnostics import KinemoError

_UNARY = {
    "sin": "sin", "cos": "cos", "tan": "tan", "exp": "exp", "log": "ln", "sqrt": "sqrt",
    "floor": "floor", "ceil": "ceil", "absolute": "abs", "negative": "neg", "rint": "round",
}
_BINARY = {
    "add": "add", "subtract": "sub", "multiply": "mul", "divide": "div", "true_divide": "div",
    "power": "pow", "minimum": "min", "maximum": "max", "fmin": "min", "fmax": "max",
    "arctan2": "atan2", "remainder": "mod", "less": "lt", "less_equal": "le", "greater": "gt",
    "greater_equal": "ge",
}


def apply_ufunc(ufunc: Any, method: str, inputs: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    from .expr import Op, lift

    name = getattr(ufunc, "__name__", "")
    if method == "__call__" and not kwargs:
        if name in _UNARY and len(inputs) == 1:
            return Op("un", {"f": _UNARY[name], "a": lift(inputs[0])})
        if name in _BINARY and len(inputs) == 2:
            kind = "bool" if _BINARY[name] in ("lt", "le", "gt", "ge") else "float"
            return Op("bin", {"f": _BINARY[name], "a": lift(inputs[0]), "b": lift(inputs[1])}, kind=kind)
    raise KinemoError.make(
        "K0310",
        f"numpy.{name} has no native equivalent on signals",
        fixes=[("use the k.* blocks", "k.sin, k.where, k.interp, ..."), ("or accept the cost explicitly", "x.map(k.python(fn))")],
    )
