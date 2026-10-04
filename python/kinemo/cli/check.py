"""`kinemo check`: build + resolve without rendering — errors, lints, timeline summary."""

from __future__ import annotations

import argparse
import os
from typing import Any

from ..audio.voice import collecting_lines
from ..diagnostics import Diagnostic
from .fix import apply_fixes
from .loader import BuildResult, LoadError, build, find_scenes, load_module, select
from ..scene.written_labels import written_labels
from .output import emit_json, exit_code, summary_word


def timeline_entries(result: BuildResult) -> list[dict[str, Any]]:
    """Every scheduled play/wait of the scene in time order, with the line that scheduled it."""
    s = result.scene
    if s is None:
        return []
    log = sorted(s._log, key=lambda e: (e.start, e.end))
    return [
        {"start": e.start, "end": e.end, "label": label, "file": e.span.file, "line": e.span.line}
        for e, label in zip(log, written_labels(log))
    ]


def scene_report(result: BuildResult, strict: bool = False) -> dict[str, Any]:
    """One scene's entry in `kinemo check --json` (also used by `kinemo.testing` and `kinemo mcp`).
    With `strict`, warnings make `ok` false too."""
    failing = ("error", "warning") if strict else ("error",)
    return {
        "name": result.definition.name,
        "ok": result.scene is not None and not any(d.level in failing for d in result.diagnostics),
        "duration": result.scene.duration if result.scene else None,
        "timeline": timeline_entries(result),
        "marks": dict(sorted(result.scene.marks.items(), key=lambda m: m[1])) if result.scene else {},
        "narration": [line.json() for line in result.scene.__dict__.get("_narration", [])] if result.scene else [],
        "diagnostics": [d.json() for d in result.diagnostics],
    }


def load_error_report(file: str, d: Diagnostic) -> dict[str, Any]:
    """The `kinemo check --json` payload when the file itself fails to load."""
    return {"file": file, "scenes": [], "diagnostics": [d.json()]}


def _grouped(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse repeated entries from the same line (e.g. a handler firing many times).

    An entry joins an earlier group with the same label and line when that group's span
    still overlaps or touches it; interleaved entries from other lines don't break runs."""
    groups: list[dict[str, Any]] = []
    open_by_key: dict[tuple[str, str, int], dict[str, Any]] = {}
    for e in timeline:
        key = (e["label"], e["file"], e["line"])
        g = open_by_key.get(key)
        if g is not None and e["start"] <= g["end"] + 1.0:
            g["end"] = max(g["end"], e["end"])
            g["count"] += 1
            continue
        g = {**e, "count": 1}
        groups.append(g)
        open_by_key[key] = g
    return groups


def _text(path: str, result: BuildResult) -> str:
    name = os.path.basename(path)
    dur = f"{result.scene.duration:.1f} s" if result.scene else "—"
    out = [f"{name} — scene '{result.definition.name}' — {dur} — {summary_word(result.diagnostics)}"]
    timeline = _grouped(timeline_entries(result))
    if timeline:
        out.append("timeline")
        last_file = None
        for e in timeline:
            loc = f"{os.path.basename(e['file'])}:{e['line']}" if e["file"] != last_file else f":{e['line']}"
            last_file = e["file"]
            label = e["label"] if e["count"] == 1 else f"{e['label']} ×{e['count']}"
            out.append(f"  {e['start']:5.2f}–{e['end']:5.2f}  {label[:40]:<40} {loc}")
    errors = [d for d in result.diagnostics if d.level == "error"]
    lints = [d for d in result.diagnostics if d.level != "error"]
    if errors:
        out.append("errors")
        out += ["  " + line for d in errors for line in d.render().splitlines()]
    if lints:
        out.append("lints")
        for d in lints:
            when = f"{d.time:.2f} s " if d.time is not None else ""
            loc = f":{d.spans[0].line}" if d.spans else ""
            out.append(f"  {d.code} {when} {d.message}   {loc}")
            for f in d.fixes:
                out.append(f"        fix: {f.code or f.description}")
    return "\n".join(out)


def run(args: argparse.Namespace) -> int:
    try:
        module = load_module(args.file)
    except LoadError as e:
        return _report_load_error(args, e.diagnostic)
    # A check never calls the voice model: lines without audio are estimated (W1405).
    with collecting_lines():
        results = [build(d, args.params) for d in select(find_scenes(module), args.scene)]
    if not results:
        print(f"kinemo: no scenes (@k.scene) in {args.file}")
        return 1
    diags = [d for r in results for d in r.diagnostics]
    if args.fix:
        applied = apply_fixes(diags)
        if applied:
            print(f"kinemo: applied {applied} fix(es); running check again")
            return run(argparse.Namespace(**{**vars(args), "fix": False}))
    if args.json:
        emit_json({"file": args.file, "scenes": [scene_report(r, args.strict) for r in results]})
    else:
        print("\n\n".join(_text(args.file, r) for r in results))
    return exit_code(diags, args.strict)


def _report_load_error(args: argparse.Namespace, d: Diagnostic) -> int:
    if args.json:
        emit_json(load_error_report(args.file, d))
    else:
        print(d.render())
    return 1
