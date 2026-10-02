"""Symbolic expressions: the Python face of the IR expression graph.

Operators on signals build expressions instead of computing numbers. Expressions are
evaluated natively by the core, at any time, which keeps the render phase pure.

Typing model: `Expr[T]` is a value of type `T` that changes over time. Reading it gives a
`T` (`x.now` at the build cursor, `x()` inside reactive functions, where the symbolic value
stands in for the number while tracing). Functions given to `.map`, `k.computed` and object
props are therefore annotated with plain values (`def f(x: float) -> float`).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar, Union, cast, overload

from .._runtime.context import current_scene, tracing
from ..diagnostics import KinemoError
from ..theme.tokens import ThemeToken
from ..values.color import Color
from ..values.encode import decode, encode, infer_kind
from ..values.vec import Vec

IR = dict[str, Any]

T = TypeVar("T")
U = TypeVar("U")
T_co = TypeVar("T_co", covariant=True)

#: Operands accepted where a vector is combined with an expression.
VecOperand = Union[Vec, tuple[float, float], "Expr[Vec]"]
#: Operands accepted where a number is combined with an expression.
FloatOperand = Union[float, "Expr[float]"]
#: Operands of `&` and `|`.
BoolOperand = Union[bool, "Expr[bool]"]


class Expr(Generic[T_co]):
    """A value that may change over time. Read it with `.now` (build) or `x()` (reactive)."""

    __slots__ = ()

    #: Value kind used to encode constants combined with this expression.
    kind: str = "float"

    def _ir(self) -> IR:
        raise NotImplementedError

    # ---- reads -------------------------------------------------------------------
    @property
    def now(self) -> T_co:
        """Value at the build cursor (scene body, component `build()`, event handlers)."""
        if tracing():
            raise KinemoError.make(
                "K0302",
                "'.now' inside a reactive function would freeze the value",
                fixes=[("read it in a tracked way with x()", None)],
            )
        s = current_scene()
        s._refresh_tables()
        return decode(json.loads(s._b.eval_expr(json.dumps(self._ir()), s.cursor)))

    def __call__(self) -> T_co:
        """Tracked read inside reactive functions. While tracing, the symbolic expression
        stands in for the value (that is how the function compiles to native code)."""
        from ..events.stateful import sim_time

        t = sim_time.get()
        if t is not None and not tracing():
            # Inside a simulation step: the value at the simulated instant.
            s = current_scene()
            return decode(json.loads(s._b.eval_expr(json.dumps(self._ir()), t)))
        if not tracing():
            raise KinemoError.make(
                "K0301",
                "x() is a tracked read and only works inside lambdas, k.computed or .map",
                fixes=[("in the scene body, read the value at the cursor", "x.now")],
            )
        return cast(T_co, self)

    @overload
    def map(self, fn: Callable[[T_co], Expr[U]]) -> Expr[U]: ...
    @overload
    def map(self, fn: Callable[[T_co], U]) -> Expr[U]: ...
    def map(self, fn: Callable[[T_co], Any]) -> Expr[Any]:
        """Apply `fn` to this value. `fn` is traced to native code (K0310 if it cannot be)."""
        from .tracer import trace_call

        return trace_call(fn, self)

    # ---- guards against classic mistakes ---------------------------------------
    # The guards below exist only at runtime, so the type checker reports these mistakes
    # statically: a derived value has no `.set`/`.to`, and a signal is neither a number
    # nor iterable.
    if not TYPE_CHECKING:

        def set(self, value: Any) -> None:
            """Not allowed: derived values are read-only (K0303)."""
            raise _read_only_derived()

        def to(self, value: Any, **kwargs: Any) -> Any:
            """Not allowed: derived values are read-only (K0303); animate the source instead."""
            raise _read_only_derived()

        def __float__(self) -> float:
            raise KinemoError.make(
                "K0305",
                "a signal cannot become a number: use native k functions",
                fixes=[("native", "k.sin(x)"), ("apply a Python function (opaque, precomputed)", "x.map(k.python(math.sin))")],
            )

        __int__ = __float__
        __index__ = __float__

        def __iter__(self):
            raise TypeError("signals are not iterable; read the value with .now")

    def __bool__(self) -> bool:
        raise KinemoError.make(
            "K0304",
            "a signal has no single boolean value: it changes over time",
            fixes=[
                ("decide at the cursor", "if x.now > 2:"),
                ("react during playback", "k.when(x > 2, ...)"),
            ],
        )

    def __format__(self, spec: str) -> str:
        from .tracer import format_placeholder

        if tracing():
            return format_placeholder(self, spec)
        raise KinemoError.make(
            "K0301",
            "formatting a signal in the scene body requires picking an instant",
            fixes=[("value at the cursor", "f\"{x.now:.2f}\""), ("reactive text", "k.Text(lambda: f\"{x():.2f}\")")],
        )

    def __hash__(self) -> int:
        return id(self)

    # ---- arithmetic ----------------------------------------------------------
    def _bin(self, f: str, other: object, swap: bool = False) -> Op:
        a, b = self, lift(other, self.kind)
        if swap:
            a, b = b, a
        return Op("bin", {"f": f, "a": a, "b": b}, kind=_result_kind(f, a.kind, b.kind))

    @overload
    def __add__(self: Expr[float], o: FloatOperand) -> Expr[float]: ...
    @overload
    def __add__(self: Expr[Vec], o: VecOperand) -> Expr[Vec]: ...
    @overload
    def __add__(self: Expr[str], o: str | Expr[str]) -> Expr[str]: ...
    def __add__(self, o: object) -> Expr[Any]:
        return self._bin("add", o)

    @overload
    def __radd__(self: Expr[float], o: float) -> Expr[float]: ...
    @overload
    def __radd__(self: Expr[Vec], o: Vec | tuple[float, float]) -> Expr[Vec]: ...
    @overload
    def __radd__(self: Expr[str], o: str) -> Expr[str]: ...
    def __radd__(self, o: object) -> Expr[Any]:
        return self._bin("add", o, swap=True)

    @overload
    def __sub__(self: Expr[float], o: FloatOperand) -> Expr[float]: ...
    @overload
    def __sub__(self: Expr[Vec], o: VecOperand) -> Expr[Vec]: ...
    def __sub__(self, o: object) -> Expr[Any]:
        return self._bin("sub", o)

    @overload
    def __rsub__(self: Expr[float], o: float) -> Expr[float]: ...
    @overload
    def __rsub__(self: Expr[Vec], o: Vec | tuple[float, float]) -> Expr[Vec]: ...
    def __rsub__(self, o: object) -> Expr[Any]:
        return self._bin("sub", o, swap=True)

    @overload
    def __mul__(self: Expr[float], o: FloatOperand) -> Expr[float]: ...
    @overload
    def __mul__(self: Expr[Vec], o: FloatOperand) -> Expr[Vec]: ...
    def __mul__(self, o: object) -> Expr[Any]:
        return self._bin("mul", o)

    @overload
    def __rmul__(self: Expr[float], o: float) -> Expr[float]: ...
    @overload
    def __rmul__(self: Expr[Vec], o: float) -> Expr[Vec]: ...
    def __rmul__(self, o: object) -> Expr[Any]:
        return self._bin("mul", o, swap=True)

    @overload
    def __truediv__(self: Expr[float], o: FloatOperand) -> Expr[float]: ...
    @overload
    def __truediv__(self: Expr[Vec], o: FloatOperand) -> Expr[Vec]: ...
    def __truediv__(self, o: object) -> Expr[Any]:
        return self._bin("div", o)

    def __rtruediv__(self: Expr[float], o: float) -> Expr[float]:
        return self._bin("div", o, swap=True)

    def __mod__(self: Expr[float], o: FloatOperand) -> Expr[float]:
        return self._bin("mod", o)

    def __pow__(self: Expr[float], o: FloatOperand) -> Expr[float]:
        return self._bin("pow", o)

    def __rpow__(self: Expr[float], o: float) -> Expr[float]:
        return self._bin("pow", o, swap=True)

    def __lt__(self, o: FloatOperand) -> Expr[bool]:
        return self._bin("lt", o)

    def __le__(self, o: FloatOperand) -> Expr[bool]:
        return self._bin("le", o)

    def __gt__(self, o: FloatOperand) -> Expr[bool]:
        return self._bin("gt", o)

    def __ge__(self, o: FloatOperand) -> Expr[bool]:
        return self._bin("ge", o)

    def __and__(self, o: BoolOperand) -> Expr[bool]:
        return self._bin("and", o)

    def __rand__(self, o: bool) -> Expr[bool]:
        return self._bin("and", o, swap=True)

    def __or__(self, o: BoolOperand) -> Expr[bool]:
        return self._bin("or", o)

    def __ror__(self, o: bool) -> Expr[bool]:
        return self._bin("or", o, swap=True)

    def __invert__(self) -> Expr[bool]:
        return Op("un", {"f": "not", "a": self}, kind="bool")

    def __neg__(self) -> Expr[T_co]:
        return Op("un", {"f": "neg", "a": self}, kind=self.kind)

    def __pos__(self) -> Expr[T_co]:
        return self

    def __abs__(self) -> Expr[T_co]:
        return Op("un", {"f": "abs", "a": self}, kind=self.kind)

    if not TYPE_CHECKING:

        def __array_ufunc__(self, ufunc: Any, method: str, *inputs: Any, **kwargs: Any) -> Any:
            """numpy functions on signals trace to native expressions (`np.sin(x())`)."""
            from .numpy_ufuncs import apply_ufunc

            return apply_ufunc(ufunc, method, inputs, kwargs)

    def __round__(self, ndigits: int | None = None) -> Expr[float]:
        if ndigits:
            k = 10.0**ndigits
            return Op("un", {"f": "round", "a": self._bin("mul", k)})._bin("div", k)
        return Op("un", {"f": "round", "a": self})

    # ---- vectors ---------------------------------------------------------------
    @property
    def x(self) -> Expr[float]:
        """x component of a vector expression."""
        return Op("un", {"f": "x", "a": self})

    @property
    def y(self) -> Expr[float]:
        """y component of a vector expression."""
        return Op("un", {"f": "y", "a": self})


#: `k.Val[T]`: what a reactive input accepts — a plain value, a signal or expression, or a
#: zero-argument function traced to native code (`lambda: f"{x():.1f}"`).
Val = Union[T, Expr[T], Callable[[], Union[T, Expr[T]]]]


def _read_only_derived() -> KinemoError:
    return KinemoError.make(
        "K0303",
        "a derived value is read-only: it is recomputed from its sources",
        fixes=[("animate the source", "s.play(x.to(3))  # instead of (x + 1).to(4)")],
    )


def _result_kind(f: str, a: str, b: str) -> str:
    if f in ("lt", "le", "gt", "ge", "eq", "ne", "and", "or"):
        return "bool"
    if "str" in (a, b) and f == "add":
        return "str"
    if "vec2" in (a, b):
        return "vec2"
    if "color" in (a, b):
        return "color"
    return "float"


class Op(Expr[Any]):
    """Generic expression node. `fields` may contain nested expressions."""

    __slots__ = ("op", "fields", "kind")

    def __init__(self, op: str, fields: dict[str, Any], kind: str = "float") -> None:
        self.op = op
        self.fields = fields
        self.kind = kind

    def _ir(self) -> IR:
        out: IR = {"op": self.op}
        for k, v in self.fields.items():
            if isinstance(v, Expr):
                out[k] = v._ir()
            elif isinstance(v, list) and v and isinstance(v[0], Expr):
                out[k] = [e._ir() for e in v]
            else:
                out[k] = v
        return out


class Const(Expr[Any]):
    __slots__ = ("value", "kind")

    def __init__(self, value: Any, kind: str | None = None) -> None:
        if isinstance(value, ThemeToken):
            value = value.resolve()
        self.value = value
        self.kind = kind or infer_kind(value)

    def _ir(self) -> IR:
        return {"op": "const", "v": encode(self.value, self.kind)}


class Time(Expr[float]):
    """`k.time`: the global scene time in seconds (read-only, never eased)."""

    __slots__ = ()

    def _ir(self) -> IR:
        return {"op": "time"}

    def __repr__(self) -> str:
        return "k.time"


def lift(value: object, kind_hint: str = "float") -> Expr[Any]:
    """`k.Val[T]` (`T | Signal[T] | Callable[[], T]`) → expression."""
    if isinstance(value, Expr):
        return value
    if callable(value) and not isinstance(value, Color | ThemeToken | type):
        from .tracer import trace

        return trace(value)
    if isinstance(value, tuple) and len(value) == 2 and any(isinstance(v, Expr) for v in value):
        return Op("vec2", {"x": lift(value[0]), "y": lift(value[1])}, kind="vec2")
    if isinstance(value, int | float) and not isinstance(value, bool):
        return Const(float(value), "float")
    return Const(value)


def is_reactive(value: object) -> bool:
    return isinstance(value, Expr) or (callable(value) and not isinstance(value, Color | ThemeToken | type))
