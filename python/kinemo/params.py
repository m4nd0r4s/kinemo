"""Scene parameters: fixed values in video, controls in interactive output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence, cast

from .diagnostics import KinemoError

if TYPE_CHECKING:
    from .scene.scene import Scene


@dataclass(frozen=True)
class Param:
    default: Any
    kind: str

    def validate(self, v: object) -> object:
        """Check a value given on the command line (`--param`)."""
        return v


@dataclass(frozen=True)
class Int(Param):
    lo: int = 0
    hi: int = 100

    def __init__(self, lo: int, hi: int, default: int | None = None) -> None:
        object.__setattr__(self, "lo", int(lo))
        object.__setattr__(self, "hi", int(hi))
        object.__setattr__(self, "default", int(lo if default is None else default))
        object.__setattr__(self, "kind", "float")

    def validate(self, v: object) -> object:
        """Check a value given on the command line (`--param`) against the range."""
        v = int(cast("float", v))
        if not self.lo <= v <= self.hi:
            raise KinemoError.make("K0105", f"parameter outside the range [{self.lo}, {self.hi}]: {v}")
        return v


@dataclass(frozen=True)
class Float(Param):
    lo: float = 0.0
    hi: float = 1.0

    def __init__(self, lo: float, hi: float, default: float | None = None) -> None:
        object.__setattr__(self, "lo", float(lo))
        object.__setattr__(self, "hi", float(hi))
        object.__setattr__(self, "default", float(lo if default is None else default))
        object.__setattr__(self, "kind", "float")

    def validate(self, v: object) -> object:
        """Check a value given on the command line (`--param`) against the range."""
        v = float(cast("float", v))
        if not self.lo <= v <= self.hi:
            raise KinemoError.make("K0105", f"parameter outside the range [{self.lo}, {self.hi}]: {v}")
        return v


class Bool(Param):
    def __init__(self, default: bool = False) -> None:
        super().__init__(bool(default), "bool")

    def validate(self, v: object) -> object:
        """Accept booleans and `true/false/yes/no/on/off/1/0` from the command line."""
        if isinstance(v, bool):
            return v
        text = str(v).strip().lower()
        if text in ("true", "yes", "on", "1"):
            return True
        if text in ("false", "no", "off", "0"):
            return False
        raise KinemoError.make("K0105", f"not a boolean: {v!r}", fixes=[("use true or false", "--param flag=true")])


class Choice(Param):
    if TYPE_CHECKING:
        options: list[Any]

    def __init__(self, options: Sequence[Any], default: Any = None) -> None:
        opts = list(options)
        super().__init__(opts[0] if default is None else default, "")
        object.__setattr__(self, "options", opts)

    def validate(self, v: object) -> object:
        """Check that a value given on the command line is one of the options."""
        if v in self.options:
            return v
        # From the command line options arrive as text: match their name, hex or str().
        from .values.color import PALETTE, Color

        text = str(v)
        for option in self.options:
            names = {str(option)}
            if isinstance(option, Color):
                names |= {option.to_hex().lower(), *(n.lower() for n, c in PALETTE.items() if c == option)}
            if text in names or text.lower() in names:
                return option
        raise KinemoError.make(
            "K0105",
            f"invalid option {v!r}",
            fixes=[(f"use one of {', '.join(map(str, self.options))}", None)],
        )


class TextParam(Param):
    def __init__(self, default: str = "") -> None:
        super().__init__(str(default), "str")


def _param_signal_class() -> type:
    from ._runtime.spans import user_span
    from .reactive.signal import Signal

    class ParamSignal(Signal):
        """A scene parameter. Reading it with `.now` freezes it at build time (W1301)."""

        __slots__ = ("_param_name",)

        @property
        def now(self) -> Any:
            self._scene.lints.warn(
                "W1301",
                f"parameter '{self._param_name}' was read with .now: it is fixed at build time and does not become an interactive control",
                spans=[user_span()],
                fixes=[("use the parameter as a signal (expressions, lambdas, props)", None)],
            )
            return Signal.now.fget(self)  # type: ignore[attr-defined]

    return ParamSignal


def param_signals(s: "Scene", specs: dict[str, Param], values: dict[str, Any]) -> dict[str, Any]:
    from .reactive.signal import signal

    param_class = _param_signal_class()
    out: dict[str, Any] = {}
    for name, spec in specs.items():
        value = spec.validate(values[name]) if name in values else spec.default
        base = signal(value, lerp=None if spec.kind != "float" else "linear")
        param = param_class(s, base._id, base.kind, base.lerp)
        object.__setattr__(param, "_param_name", name)
        s._param_signals[param._id] = name
        out[name] = param
    unknown = set(values) - set(specs)
    if unknown:
        raise KinemoError.make("K0105", f"unknown parameters: {', '.join(sorted(unknown))}")
    return out
