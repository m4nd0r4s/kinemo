"""`k.Scene`: the object a scene function receives. Holds the build cursor."""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any

from .._core import Builder
from ..diagnostics import Collector, KinemoError
from ..events.registry import EventRegistry
from ..theme.tokens import Theme
from .config import SceneConfig
from .frame import Frame, frame_of
from ..audio.voice import VoiceMixin
from .events import EventsMixin
from .lifecycle import LifecycleMixin
from .probe import ProbeMixin
from .timeline import TimelineMixin
from .writes import WritesMixin

if TYPE_CHECKING:
    from ..reactive.expr import Expr
    from ..reactive.native import PythonFn


def _referenced_params(ir: Any, params: dict[int, str], builder: Builder, seen: set[int] | None = None) -> list[str]:
    """Parameters an expression depends on, following bindings of the signals it reads."""
    seen = seen if seen is not None else set()
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("op") == "sig":
                sid = node["id"]
                if sid in params and params[sid] not in found:
                    found.append(params[sid])
                if sid not in seen:
                    seen.add(sid)
                    for src in json.loads(builder.signal_sources(sid)):
                        walk(src)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(ir)
    return found


class Scene(TimelineMixin, LifecycleMixin, WritesMixin, ProbeMixin, EventsMixin, VoiceMixin):
    """Timeline of one scene. Code runs once; every call records something at the cursor."""

    def __init_subclass__(cls, **kw: Any) -> None:
        from ..diagnostics import KinemoError as _Error

        raise _Error.make(
            "K1103",
            f"'class {cls.__name__}(k.Scene)' is the Manim style; a kinemo scene is a decorated function",
            fixes=[("write the scene as a function that receives `s`", f"@k.scene\ndef {cls.__name__.lower()}(s: k.Scene):\n    s.play(...)")],
        )

    def __init__(self, config: SceneConfig) -> None:
        self.config = config
        self.theme: Theme = config.theme
        self._b = Builder(json.dumps(config.ir()))
        #: Build cursor in seconds.
        self.cursor = 0.0
        #: Duration multiplier from enclosing constant `s.tempo` blocks.
        self._speed = 1.0
        self._max_end = 0.0
        self._base: dict[int, dict[str, Any]] = {}
        self._marks: list[tuple[str | None, float, bool, int]] = []
        self._tables: list[tuple[int, "PythonFn", "Expr"]] = []
        self._nodes: list[Any] = []
        self._log: list[Any] = []
        self._statements: list[Any] = []
        self.lints = Collector()
        from ..project import project_config

        self.lints.allow(project_config().lints_allow)
        self._events = EventRegistry()
        self._statefuls: list[Any] = []
        self._tables_dirty = False
        self._component_stack: list[Any] = []
        self._handler_nodes: list[Any] = []
        #: Signal id → name of every scene parameter.
        self._param_signals: dict[int, str] = {}
        fw, fh = config.frame_units
        self.frame: Frame = frame_of(fw, fh)

    @property
    def builder(self) -> Builder:
        """The native IR builder of this scene (outputs: frames, video, inspect)."""
        return self._b

    # ---- resolve-phase precomputation -------------------------------------------------
    def _precompute(self, fn: "PythonFn", arg: "Expr") -> "Expr":
        from ..reactive.expr import Op

        params = _referenced_params(arg._ir(), self._param_signals, self._b)
        if params:
            from .._runtime.spans import user_span

            self.lints.warn(
                "W1302",
                f"k.python depends on the parameter {', '.join(params)}: it cannot be precomputed for the interactive web player",
                spans=[user_span()],
                fixes=[("rewrite the function with native k building blocks (k.sin, k.where, k.interp, ...)", None)],
            )
        table = self._b.add_table()
        self._tables.append((table, fn, arg))
        return Op("table", {"table": table})

    def _fill_tables(self) -> None:
        fps = self.config.fps
        n = int(math.ceil(self._b.duration * fps)) + 1
        dt = 1.0 / fps
        for table, fn, arg in self._tables:
            xs = self._b.eval_expr_grid(json.dumps(arg._ir()), 0.0, dt, n)
            if fn.vectorized:
                import numpy as np

                raw = list(fn.fn(np.asarray(xs, dtype=float)))
            else:
                raw = [fn.fn(x) for x in xs]
            try:
                ys = [float(v) for v in raw]
            except (TypeError, ValueError):
                bad = next(v for v in raw if not isinstance(v, int | float))
                raise KinemoError.make(
                    "K0105",
                    f"k.python({fn.__name__}) must return numbers; it returned {type(bad).__name__} {bad!r}",
                    spans=[fn.span],
                    fixes=[("for text, pick between strings natively", 'k.where(cond, "a", "b")')],
                ) from None
            self._b.set_table(table, 0.0, dt, ys)

    # ---- end of build -----------------------------------------------------------------
    def _finish(self) -> None:
        from ..events.resolve import compute_tables, resolve

        resolve(self)
        end = max(self.cursor, self._max_end)
        self._b.set_duration(end + self.config.tail)
        if self._statefuls:
            compute_tables(self, end + self.config.tail)
        self._fill_tables()
        self._lint_handler_objects()

    def _lint_handler_objects(self) -> None:
        end = self._b.duration
        for node in self._handler_nodes:
            if node._parent is None and self._b.present(node._id, end - 1e-6) and self._b.last_exit(node._id, end) is None:
                self.lints.warn(
                    "W0701",
                    f"'{node._label()}' was created in a handler and never leaves the scene",
                    spans=[node._span],
                    fixes=[("remove it in the handler itself", f"s.play(k.fade_out({node._label()}))")],
                )

    @property
    def duration(self) -> float:
        """Total length in seconds (known after the build)."""
        return self._b.duration

    def __repr__(self) -> str:
        return f"<Scene {self.config.name!r} t={self.cursor:.2f}>"
