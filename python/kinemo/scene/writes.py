"""Low-level timeline writes and the checks that guard them (K0101, K0102, K0201, K0401)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .._runtime.spans import Span
from ..diagnostics import KinemoError
from ..objects.props import PropSignal
from ..reactive.signal import Signal, source_ir

if TYPE_CHECKING:
    from .._core import Builder


class WritesMixin:
    _b: "Builder"
    cursor: float
    _base: dict[int, dict[str, Any]]
    _max_end: float

    def _push_entry(self, sig: Signal[Any], entry: dict[str, Any], base_src: dict[str, Any] | None) -> None:
        self._b.push_entry(sig._id, json.dumps(entry))
        if base_src is not None:
            self._base[sig._id] = base_src
            node, prop = getattr(sig, "_node", None), getattr(sig, "_prop", None)
            if node is not None and prop in ("x", "y") and entry.get("blend", "replace") == "replace":
                when = entry.get("t1", entry.get("t", 0.0))
                span = Span(entry.get("span", {}).get("file", "<unknown>"), entry.get("span", {}).get("line", 0))
                node._binding_log.setdefault(prop, []).append((when, base_src.get("k") == "expr", span))
        end = entry.get("t1", entry.get("t", 0.0))
        self._max_end = max(self._max_end, end)

    def _push_set(self, sig: Signal[Any], value: Any, span: Span, t: float | None = None) -> None:
        from .._runtime.context import tracing

        if tracing():
            raise KinemoError.make(
                "K0306",
                "a derived value cannot write to a signal: traced functions must be pure",
                spans=[span],
                fixes=[("compute the value instead of setting it, or schedule the change in the scene body", None)],
            )
        if isinstance(sig, PropSignal):
            sig._node._check_settable(sig._prop, span)
        src = source_ir(value, sig.kind)
        when = self.cursor if t is None else t
        self._push_entry(sig, {"k": "set", "t": when, "src": src, "span": span.ir()}, src)

    def _base_source(self, sig: Signal[Any]) -> dict[str, Any]:
        """Source the signal follows at the cursor (constant or binding), for reverts."""
        src = self._base.get(sig._id)
        if src is not None and src.get("k") == "expr":
            return src
        return {"k": "val", "v": json.loads(self._b.eval_signal(sig._id, self.cursor))}

    def _check_animatable(self, sig: Signal[Any], t: float, span: Span) -> None:
        if not isinstance(sig, PropSignal):
            return
        self._check_alive(sig._node, t, span)
        sig._node._check_animatable_prop(sig._prop, t, span)

    def _check_alive(self, node: Any, t: float, span: Span) -> None:
        """K0101 / K0102: animations need the object in the scene at their start."""
        if not self._b.present(node._id, t + 1e-9) and not self._b.present(node._id, t):
            exit_t = self._b.last_exit(node._id, t)
            if exit_t is not None:
                exit_span = self._exit_span(node, exit_t)
                raise KinemoError.make(
                    "K0102",
                    f"'{node._label()}' already left the scene at t = {exit_t:.2f} s",
                    spans=[span, exit_span] if exit_span else [span],
                    notes=["", "exit here"],
                    time=t,
                    objects=[node._label()],
                    fixes=[("bring it back before animating", f"s.play(k.fade_in({node._label()}))")],
                )
            raise KinemoError.make(
                "K0101",
                f"'{node._label()}' is not in the scene yet",
                spans=[span],
                time=t,
                objects=[node._label()],
                fixes=[
                    ("bring it in with a verb", f"s.play(k.draw({node._label()}))"),
                    ("or add it instantly", f"s.add({node._label()})"),
                ],
            )

    def _exit_span(self, node: Any, t: float) -> Span | None:
        for when, span in reversed(getattr(self, "_exits", {}).get(node._id, [])):
            if abs(when - t) < 1e-9:
                return span
        return None

    def _check_conflict(self, sig: Signal[Any], t0: float, t1: float, span: Span) -> None:
        found = self._b.overlapping_anim(sig._id, t0, t1)
        if found is None:
            return
        other, a0, a1 = json.loads(found)
        other_span = Span(other.get("file", "<unknown>"), other.get("line", 0))
        from ..anim.prop import describe

        raise KinemoError.make(
            "K0201",
            f"two animations write {describe(sig)} at the same time ({a0:.2f}–{a1:.2f} s and {t0:.2f}–{t1:.2f} s)",
            spans=[span, other_span],
            notes=["", "the other animation"],
            time=t0,
            fixes=[
                ("chain the two", "s.play(k.seq(a, b))"),
                ("or add them, if intended", 'obj.to(..., blend="add")'),
            ],
        )
