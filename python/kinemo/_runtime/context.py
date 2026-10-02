"""The active build context: which scene is being built and in which mode."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..scene.scene import Scene

_current_scene: ContextVar["Scene | None"] = ContextVar("kinemo_scene", default=None)
_tracing: ContextVar[int] = ContextVar("kinemo_tracing", default=0)


def current_scene() -> "Scene":
    s = _current_scene.get()
    if s is None:
        from ..diagnostics import KinemoError

        raise KinemoError.make(
            "K0104",
            "objects and animations can only be created while a scene is being built",
            fixes=[("create it inside a function decorated with @k.scene", None)],
        )
    return s


def maybe_scene() -> "Scene | None":
    return _current_scene.get()


def push_scene(s: "Scene"):
    return _current_scene.set(s)


def pop_scene(token) -> None:
    _current_scene.reset(token)


def tracing() -> bool:
    return _tracing.get() > 0


class trace_mode:
    """Inside, signal calls `x()` return symbolic expressions."""

    def __enter__(self) -> None:
        self._tok = _tracing.set(_tracing.get() + 1)

    def __exit__(self, *exc: object) -> None:
        _tracing.reset(self._tok)
