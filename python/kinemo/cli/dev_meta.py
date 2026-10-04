"""Metadata the `kinemo dev` page receives with each scene: timeline bars, marks, the
object tree, diagnostics and the editable call sites."""

from __future__ import annotations

import os
import time
from typing import Any, Mapping

from ..diagnostics import Diagnostic
from ..editing.call_sites import SourceFile
from ..editing.scene_index import span_key
from ..scene.written_labels import written_labels
from .loader import BuildResult

#: Longest code excerpt shown when hovering a timeline bar.
CODE_EXCERPT_CHARS = 400


def timeline_bars(result: BuildResult, ir: Mapping[str, Any], sources: Mapping[str, SourceFile]) -> list[dict[str, Any]]:
    """One bar per `play`/`start`, with the objects it touches, the call that scheduled it
    (`group`: repeated runs of one statement share it) and a code excerpt."""
    s = result.scene
    if s is None:
        return []
    entries = _timed_entries(ir)
    bars: list[dict[str, Any]] = []
    log = sorted(s._log, key=lambda e: (e.start, e.end))  # pyright: ignore[reportPrivateUsage]
    for e, label in zip(log, written_labels(log)):
        call = e.call or e.span
        bars.append(
            {
                "label": label,
                "start": e.start,
                "end": e.end,
                "file": os.path.abspath(e.span.file),
                "line": e.span.line,
                "site": span_key(e.span),
                "call": span_key(call),
                "group": span_key(call),
                "code": _excerpt(sources, call),
                "objects": sorted(_objects_of(entries, e.start, e.end, call, span_key(e.span))),
            }
        )
    return bars


def _timed_entries(ir: Mapping[str, Any]) -> list[tuple[int, float, float, str, str, int]]:
    """(owner, t0, t1, span key, file, line) of every timed IR item that has an owner."""
    out: list[tuple[int, float, float, str, str, int]] = []
    for signal in ir.get("signals", []):
        owner = signal.get("owner")
        if not owner:
            continue
        for item in signal.get("timeline", []):
            span = item.get("span")
            if not span:
                continue
            t0 = item.get("t0", item.get("t", 0.0))
            t1 = item.get("t1", t0)
            out.append((owner[0], t0, t1, span_key(span), span["file"], span["line"]))
    for obj in ir.get("objects", []):
        for place in obj.get("place", []):
            span = place.get("span")
            if span:
                out.append((obj["id"], place["t"], place["t"] + place.get("dur", 0.0), span_key(span), span["file"], span["line"]))
    return out


def _objects_of(entries: list[tuple[int, float, float, str, str, int]], start: float, end: float, call: Any, site: str) -> set[int]:
    """Objects changed by a bar: items written by its animation's call, or by any call
    inside its `play(...)` statement, within its time."""
    tolerance = 1e-9
    out: set[int] = set()
    for owner, t0, t1, key, file, line in entries:
        inside = start - tolerance <= t0 and t1 <= end + tolerance
        if not inside:
            continue
        in_statement = file == call.file and call.line <= line <= (call.end_line or call.line)
        if key == site or in_statement:
            out.add(owner)
    return out


def _excerpt(sources: Mapping[str, SourceFile], span: Any) -> str:
    source = sources.get(span.file)
    if source is None or not span.end_line:
        return span.source_line()
    site = source.call_at(span)
    text = source.segment(site.start, site.end) if site is not None else span.source_line()
    return text if len(text) <= CODE_EXCERPT_CHARS else text[: CODE_EXCERPT_CHARS - 1] + "…"


def scene_marks(result: BuildResult) -> list[dict[str, Any]]:
    s = result.scene
    if s is None:
        return []
    return [{"name": name, "t": t, "slide": slide} for name, t, slide, _ in s._marks]  # pyright: ignore[reportPrivateUsage]


def object_tree(result: BuildResult, ir: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Label, kind, parent and presence toggles of every object (the outliner)."""
    s = result.scene
    if s is None:
        return {}
    labels: dict[int, str] = {}
    for node in s._nodes:  # pyright: ignore[reportPrivateUsage]
        try:
            labels[node._id] = node._label()  # pyright: ignore[reportPrivateUsage]
        except Exception:  # noqa: BLE001 - a label is a nicety, never a build failure
            continue
    out: dict[str, dict[str, Any]] = {}
    for obj in ir.get("objects", []):
        out[str(obj["id"])] = {
            "label": labels.get(obj["id"], f"{obj['kind']}#{obj['id']}"),
            "kind": obj["kind"],
            "parent": obj.get("parent"),
            "presence": obj.get("presence", []),
        }
    return out


def diagnostics_json(diagnostics: list[Diagnostic]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in diagnostics:
        entry = d.json()
        entry["rendered"] = d.render()
        for span in entry["spans"]:  # type: ignore[union-attr]
            span["file"] = os.path.abspath(span["file"])
        out.append(entry)
    return out


def preview_meta(
    path: str,
    result: BuildResult,
    available_scenes: list[str],
    ir: Mapping[str, Any],
    sources: Mapping[str, SourceFile],
    editable: Mapping[str, Any],
) -> dict[str, Any]:
    s = result.scene
    assert s is not None
    return {
        "file": os.path.abspath(path),
        "scene": result.definition.name,
        "scenes": available_scenes,
        "duration": s.duration,
        "scene_fps": s.config.fps,
        "timeline": timeline_bars(result, ir, sources),
        "marks": scene_marks(result),
        "diagnostics": diagnostics_json(result.diagnostics),
        "objects": object_tree(result, ir),
        "sources": editable,
        "built_at": time.time(),
        "debug": [],
        "live": False,
    }

