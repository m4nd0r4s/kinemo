"""State changes: `obj.to(...)` / `x.to(...)` interpolate from the value at the cursor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from .._runtime.spans import Span
from ..diagnostics import KinemoError
from ..reactive.signal import Signal, source_ir
from .animation import Animation
from .ease import Ease

if TYPE_CHECKING:
    from ..scene.scene import Scene


class RawSource:
    """An already-encoded timeline source (used to revert to a previous state)."""

    def __init__(self, src: dict[str, Any]) -> None:
        self.src = src


Target = tuple[Signal, Any]


class PropTo(Animation):
    def __init__(
        self,
        targets: Sequence[Target],
        *,
        duration: float | None = None,
        ease: Any = None,
        delay: float = 0.0,
        blend: str = "replace",
        span: Span | None = None,
        extra: Sequence[Animation] = (),
        prelude: Sequence[Animation] = (),
    ) -> None:
        super().__init__(duration, ease, delay, span)
        if blend not in ("replace", "add"):
            raise KinemoError.make("K0105", f"invalid blend: {blend!r}", fixes=[("use 'replace' or 'add'", None)])
        self.targets = list(targets)
        self.blend = blend
        #: Extra animations that run with this one (placement changes, container reflow).
        self.extra = list(extra)
        #: Animations applied at the start, before the targets are checked (`unpin=True`).
        self.prelude = list(prelude)

    def describe(self) -> str:
        owners: dict[str, list[str]] = {}
        for sig, _ in self.targets:
            node = getattr(sig, "_node", None)
            owner = node._label() if node is not None else repr(sig)
            prop = getattr(sig, "_prop", "value")
            owners.setdefault(owner, []).append(prop)
        def props_text(ps: list[str]) -> str:
            names = list(dict.fromkeys(ps))
            if "fill" in names and "stroke" in names:
                names = ["color" if n == "fill" else n for n in names if n != "stroke"]
            return ", ".join(names)

        parts = [f"{o}.to({props_text(ps)})" for o, ps in owners.items()]
        parts = [p.describe() for p in self.prelude] + parts + [e.describe() for e in self.extra]
        return ", ".join(parts) or "to()"

    def split_for_during(self, s: "Scene") -> tuple[Animation, Animation]:
        if self.blend != "replace":
            return super().split_for_during(s)
        targets = [(sig, RawSource(s._base_source(sig))) for sig, _ in self.targets]
        extra = [e.split_for_during(s)[1] for e in self.extra]
        return self, PropTo(targets, duration=self.duration, ease=self.ease, span=self.span, extra=extra)

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        for p in self.prelude:
            p._emit(s, start, 0.0, ease)
        for sig, value in self.targets:
            s._check_animatable(sig, start, self.span)
            src = value.src if isinstance(value, RawSource) else source_ir(value, sig.kind)
            if duration <= 0:
                s._push_entry(sig, {"k": "set", "t": start, "src": src, "span": self.span.ir()}, src)
                continue
            if sig.kind in ("list", "points") and sig.lerp == "linear":
                raise KinemoError.make(
                    "K0205",
                    "this list does not know how to interpolate",
                    spans=[self.span],
                    fixes=[
                        ("declare the interpolation on the signal", "k.signal([...], lerp=k.lerp.pointwise)"),
                        ("or switch in a single step", "k.signal([...], lerp=None)"),
                    ],
                )
            if self.blend == "replace":
                s._check_conflict(sig, start, start + duration, self.span)
            s._push_entry(
                sig,
                {
                    "k": "anim",
                    "t0": start,
                    "t1": start + duration,
                    "to": src,
                    "ease": ease.ir(),
                    "blend": self.blend,
                    "span": self.span.ir(),
                },
                src if self.blend == "replace" else None,
            )
        for e in self.extra:
            e._emit(s, start, duration, ease)


def describe(sig: Signal) -> str:
    owner = getattr(sig, "_node", None)
    prop = getattr(sig, "_prop", None)
    if owner is not None and prop is not None:
        return f"{owner._label()}.{prop}"
    return repr(sig)
