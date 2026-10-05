"""Metadata the `kinemo dev` page receives with each scene: timeline bars, marks, the
object tree, diagnostics and the editable call sites."""

from __future__ import annotations

import functools
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


def audio_tracks(result: BuildResult, ir: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Clips of the Narration, Sounds and Music tracks. `index` is the clip's place in the
    scene's audio (the page plays `/audio/<version>/<index>`); narration still estimated has
    no audio, so no index. A narration clip carries its text, beat, words and sources."""
    s = result.scene
    if s is None:
        return []
    lines = list(s.__dict__.get("_narration", []))
    unmatched = list(lines)
    tracks: list[dict[str, Any]] = []
    for index, clip in enumerate(ir.get("audio", [])):
        role, start, path = clip.get("role", "sound"), float(clip["t"]), clip["path"]
        line = next((n for n in unmatched if role == "voice" and n.audio is not None and _same_file(n.audio, path) and abs(n.start - start) < 1e-6), None)
        if line is not None:
            unmatched.remove(line)
            tracks.append(_narration_clip(line, index, clip))
            continue
        length = _length(path)
        end = s.duration if role == "music" else start + length
        if role == "music" and length > 0:
            end = min(s.duration, start + length)
        tracks.append(
            {
                "index": index,
                "role": role,
                "start": start,
                "end": max(start, end),
                "label": os.path.basename(path),
                "file": path,
                "gain": clip.get("gain", 1.0),
                "duck": clip.get("duck", 0.0),
                "fade": clip.get("fade", 0.0),
                "span": _audio_verb_span(s, role, path, start),
                "narration": None,
            }
        )
    tracks.extend(_narration_clip(line, None, None) for line in unmatched)
    return sorted(tracks, key=lambda c: (c["start"], c["role"]))


def _narration_clip(line: Any, index: int | None, clip: Mapping[str, Any] | None) -> dict[str, Any]:
    span = line.span
    return {
        "index": index,
        "role": "voice",
        "start": line.start,
        "end": line.end,
        "label": f"{line.beat} · {line.text}" if line.beat else line.text,
        "file": line.audio,
        "gain": clip.get("gain", 1.0) if clip else 1.0,
        "duck": 0.0,
        "fade": 0.0,
        "span": {"file": os.path.abspath(span.file), "line": span.line} if span is not None else None,
        "narration": {
            "text": line.text,
            "beat": line.beat,
            "voice": line.voice,
            "timing": line.timing,
            "words": [list(w) for w in line.words],
            "script": {"file": os.path.abspath(line.script[0]), "line": line.script[1]} if line.script else None,
        },
    }


def _same_file(a: str, b: str) -> bool:
    return os.path.abspath(a) == os.path.abspath(b)


def _length(path: str) -> float:
    """Seconds of an audio file (0 when it cannot be read)."""
    try:
        return _cached_length(path, os.stat(path).st_mtime)
    except (OSError, ValueError, RuntimeError):
        return 0.0


@functools.lru_cache(maxsize=256)
def _cached_length(path: str, mtime: float) -> float:
    from ..audio.voice import audio_duration

    try:
        return audio_duration(path)
    except Exception:  # noqa: BLE001 - an unreadable file shows as a tick, never a failed build
        return 0.0


def _audio_verb_span(s: Any, role: str, path: str, start: float) -> dict[str, Any] | None:
    """The `k.sound`/`k.music` call that scheduled a clip, from the timeline log."""
    wanted = f"{'music' if role == 'music' else 'sound'}({os.path.basename(path)})"
    for entry in s._log:  # pyright: ignore[reportPrivateUsage]
        if abs(entry.start - start) < 1e-6 and wanted in entry.label:
            return {"file": os.path.abspath(entry.span.file), "line": entry.span.line}
    return None


def scene_statements(result: BuildResult) -> list[dict[str, Any]]:
    """Every statement that schedules time or acts at the cursor, by file and line, with its runs
    (a statement in a loop runs once per iteration): what the code view lights up and seeks to."""
    s = result.scene
    if s is None:
        return []
    by_line: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for st in s._statements:  # pyright: ignore[reportPrivateUsage]
        key = (os.path.abspath(st.span.file), st.span.line)
        by_line.setdefault(key, []).append({"kind": st.kind, "start": st.start, "end": st.end, "label": st.label})
    return [
        {"file": file, "line": line, "runs": sorted(runs, key=lambda r: (r["start"], r["end"]))}
        for (file, line), runs in sorted(by_line.items())
    ]


#: Largest source file sent to the code view (characters).
CODE_FILE_LIMIT = 400_000


def code_files(statements: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The highlighted source of every file with statements (the scene and the local modules it
    ran), as lines of `[text, kind]` segments; only files the scene itself executed are sent."""
    from .._core import code_tokens

    out: dict[str, dict[str, Any]] = {}
    for file in dict.fromkeys(entry["file"] for entry in statements):
        try:
            with open(file, encoding="utf-8") as fh:
                source = fh.read(CODE_FILE_LIMIT + 1)
        except (OSError, UnicodeDecodeError):
            continue
        if len(source) > CODE_FILE_LIMIT:
            continue
        out[file] = {"name": os.path.basename(file), "lines": _highlighted_lines(source, code_tokens(source, "python"))}
    return out


def _highlighted_lines(source: str, tokens: list[tuple[str, str, int, int]]) -> list[list[list[str]]]:
    """Each line as `[text, kind]` segments that cover it, whitespace included (as `plain`)."""
    kinds = ["plain"] * len(source)
    for _, kind, start, end in tokens:
        for i in range(start, min(end, len(source))):
            kinds[i] = kind
    lines: list[list[list[str]]] = [[]]
    for char, kind in zip(source, kinds):
        if char == "\n":
            lines.append([])
            continue
        line = lines[-1]
        if line and line[-1][1] == kind:
            line[-1][0] += char
        else:
            line.append([char, kind])
    if source.endswith("\n"):
        lines.pop()
    return lines


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
        "tracks": audio_tracks(result, ir),
        "statements": (statements := scene_statements(result)),
        "code": code_files(statements),
        "diagnostics": diagnostics_json(result.diagnostics),
        "objects": object_tree(result, ir),
        "sources": editable,
        "built_at": time.time(),
        "debug": [],
        "live": False,
    }

