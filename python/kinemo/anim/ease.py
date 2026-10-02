"""Easing curves. Every verb and `.to()` defaults to `k.ease.smooth` (cubic in-out)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Union


@dataclass(frozen=True)
class Ease:
    kind: str
    params: dict[str, Any] = field(default_factory=dict)

    def ir(self) -> dict[str, Any]:
        return {"kind": self.kind, **self.params}

    def __repr__(self) -> str:
        return f"k.ease.{self.kind}"


class _EaseNamespace:
    linear = Ease("linear")
    smooth = Ease("smooth")
    in_ = Ease("in")
    out = Ease("out")
    in_out = Ease("in_out")
    out_back = Ease("out_back")
    out_elastic = Ease("out_elastic")

    @staticmethod
    def spring(stiffness: float = 100.0, damping: float = 10.0) -> Ease:
        return Ease("spring", {"stiffness": float(stiffness), "damping": float(damping)})

    @staticmethod
    def steps(n: int) -> Ease:
        return Ease("steps", {"n": int(n)})

    @staticmethod
    def custom(fn: Callable[[float], float], samples: int = 256) -> Ease:
        """Any f: [0, 1] → ℝ, sampled into a table evaluated natively."""
        return Ease("table", {"ys": [float(fn(i / samples)) for i in range(samples + 1)]})

    @staticmethod
    def reverse(e: Ease) -> Ease:
        return Ease("reverse", {"inner": e.ir()})


ease = _EaseNamespace()
DEFAULT = ease.smooth

#: What `ease=` accepts: a curve from `k.ease` or any function f: [0, 1] → ℝ.
EaseLike = Union[Ease, Callable[[float], float]]


def as_ease(e: EaseLike) -> Ease:
    if isinstance(e, Ease):
        return e
    if callable(e):
        return ease.custom(e)
    raise TypeError(f"not an easing: {e!r}")
