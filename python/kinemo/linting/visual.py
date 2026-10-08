"""W10xx: visual lints computed by the core, as located diagnostics with fixes.

The core (`Builder.visual_lints`) samples the finished timeline and returns findings
with object ids and measurements; this module names the objects, points each finding at
the line that created the object (and, for W1001, at the `.place` call), writes the
Portuguese message and builds the fix. `# kinemo: allow W10xx` on any of those lines
silences the finding (handled by `Collector`).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable

from .._runtime.spans import UNKNOWN, Span
from ..diagnostics import Collector, Diagnostic, Fix
from .source_edits import line_fix, read_line, with_keyword_in_call

if TYPE_CHECKING:
    from ..scene.scene import Scene

DEFAULT_SAMPLE_STEP = 0.1

EDGE_NAMES = {"top": "top", "bottom": "bottom", "left": "left", "right": "right"}
INVISIBILITY_REASONS = {
    "transparent": "opacity 0",
    "outside_frame": "outside the frame",
    "hidden": "visible=False",
}


def _number(value: float, digits: int = 1) -> str:
    """A number with a fixed number of decimals: 4.5."""
    return f"{value:.{digits}f}"


def _owner(node: Any) -> Any:
    """The `rest` glyph run of a text stands for the text itself."""
    if getattr(node, "kind", "") == "glyphs" and getattr(node, "_part", None) == "rest" and node._parent is not None:
        return node._parent
    return node


class _Finding:
    """One core finding with its objects resolved to scene nodes."""

    def __init__(self, raw: dict[str, Any], nodes_by_id: dict[int, Any]) -> None:
        self.raw = raw
        self.code: str = raw["code"]
        self.t: float = raw["t"]
        self.details: dict[str, Any] = raw["details"]
        self.nodes = [_owner(nodes_by_id[i]) for i in raw["objects"] if i in nodes_by_id]
        self.labels = [n._label() for n in self.nodes]
        self.nodes_by_id = nodes_by_id

    @property
    def label(self) -> str:
        return self.labels[0] if self.labels else "object"

    def core_span(self) -> Span | None:
        span = self.raw.get("span")
        if not span or not span.get("file"):
            return None
        return Span(span["file"], int(span["line"]), int(span.get("col", 0)))


# ---- messages and fixes, one function per code ----------------------------------------

def _outside_safe_area(f: _Finding) -> tuple[str, list[Fix], list[Span]]:
    d = f.details
    edge = EDGE_NAMES.get(d["edge"], d["edge"])
    if d.get("moving"):
        message = f"{f.label} is cut by the frame edge while it moves ({edge}, {_number(d['overshoot'])} u)"
        if d.get("reorder"):
            fix = Fix("keep the whole path inside the frame: move the row away from the edge, or swap in a straight line", 'row.swap(i, j, path="straight")')
        else:
            fix = Fix("keep the whole path inside the frame: move it away from the edge, or ease without overshoot", f"{f.label}.to(..., ease=k.ease.smooth)")
        return message, [fix], []
    message = f"{f.label} leaves the safe area ({edge}, {_number(d['overshoot'])} u)"
    fix_info: dict[str, Any] = f.raw.get("fix") or {}
    target_id = fix_info.get("target")
    target = f.nodes_by_id.get(target_id) if isinstance(target_id, int) else None
    extra_spans: list[Span] = []
    fixes: list[Fix] = []
    if fix_info.get("kind") == "clamp_placement" and target is not None:
        place_span = _placement_span(target, f.t)
        if place_span is not None:
            extra_spans.append(place_span)
            fixes.append(_clamp_fix(place_span, target._label()))
    if not fixes:
        name = target._label() if target is not None else f.label
        fixes.append(Fix("keep the object inside the safe area with a constraint", f"{name}.place(..., clamp=True)"))
    return message, fixes, extra_spans


def _placement_span(node: Any, t: float) -> Span | None:
    """Span of the `.place` call that holds `node` at `t`."""
    active: Span | None = None
    for when, placed, span in node._place_log:
        if when <= t + 1e-9:
            active = span if placed else None
    return active


def _clamp_fix(place_span: Span, name: str) -> Fix:
    description = "clamp the constraint to the safe area"
    line = read_line(place_span.file, place_span.line)
    new_line = with_keyword_in_call(line, "place", "clamp", "True") if line is not None else None
    if new_line is None:
        return Fix(description, f"{name}.place(..., clamp=True)")
    return line_fix(description, place_span.file, place_span.line, new_line)


def _text_over_text(f: _Finding) -> tuple[str, list[Fix], list[Span]]:
    pct = f.details["overlap_fraction"] * 100
    a, b = (f.labels + ["text", "text"])[:2]
    message = f"text over text: {a} and {b} overlap ({pct:.0f}% of the smaller one)"
    return message, [Fix("separate the texts with a constraint", f"{b}.place(below={a}, gap=0.3)")], []


def _low_contrast(f: _Finding) -> tuple[str, list[Fix], list[Span]]:
    ratio = f.details["ratio"]
    message = f"low contrast: {f.label} has {_number(ratio)}:1 against the background (minimum 4.5:1)"
    fix = Fix("use a text color lighter/darker than the background, without transparency", f"{f.label}.set(color=k.WHITE)")
    return message, [fix], []


def _small_text(f: _Finding) -> tuple[str, list[Fix], list[Span]]:
    pixels = f.details["pixels"]
    factor = 18.0 / pixels if pixels > 0 else 2.0
    message = f"small text: {f.label} is {pixels:.0f} px at the final resolution (minimum 18 px)"
    return message, [Fix(f"increase the text size ({_number(factor)}× or more)", None)], []


def _invisible_object(f: _Finding) -> tuple[str, list[Fix], list[Span]]:
    d = f.details
    reason = INVISIBILITY_REASONS.get(d["reason"], d["reason"])
    message = f"{f.label} is invisible for {_number(d['duration'])} s ({reason}) and never removed"
    return message, [Fix("remove the object once it is out of view", f"s.remove({f.label})")], []


def _visual_noise(f: _Finding) -> tuple[str, list[Fix], list[Span]]:
    n = f.details["simultaneous"]
    message = f"visual noise: {n} short animations (< 0.3 s) at the same time"
    fix = Fix("spread the animations with k.stagger or lengthen them (≥ 0.3 s)", "k.stagger([...], lag=0.05)")
    return message, [fix], []


def _static_scene(f: _Finding) -> tuple[str, list[Fix], list[Span]]:
    message = f"static scene: {_number(f.details['duration'])} s without any visual change"
    return message, [Fix("shorten the wait or animate something in that stretch", None)], []


MESSAGES: dict[str, Callable[[_Finding], tuple[str, list[Fix], list[Span]]]] = {
    "W1001": _outside_safe_area,
    "W1002": _text_over_text,
    "W1003": _low_contrast,
    "W1004": _small_text,
    "W1005": _invisible_object,
    "W1006": _visual_noise,
    "W1007": _static_scene,
}


def visual_diagnostics(s: "Scene", collector: Collector | None = None, step: float = DEFAULT_SAMPLE_STEP) -> list[Diagnostic]:
    """Visual lints of the built scene `s`, as diagnostics (inline allows respected)."""
    out = collector if collector is not None else Collector()
    nodes_by_id = {n._id: n for n in s._nodes}
    for raw in json.loads(s._b.visual_lints(step)):
        f = _Finding(raw, nodes_by_id)
        render = MESSAGES.get(f.code)
        if render is None:
            continue
        message, fixes, extra_spans = render(f)
        spans = [n._span for n in f.nodes] + extra_spans
        if not spans:
            core = f.core_span()
            spans = [core] if core is not None else [s._nodes[0]._span if s._nodes else UNKNOWN]
        out.warn(f.code, message, fixes=fixes, spans=spans, time=f.t, objects=f.labels)
    return out.items
