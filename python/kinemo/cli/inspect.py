"""`kinemo inspect`: the scene graph at instant t, with where each value came from."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from ..values.color import Color
from .loader import BuildResult, LoadError, build, find_scenes, load_module, select
from .output import emit_json
from .instants import parse_time


def _fmt(v: Any) -> str:
    if isinstance(v, dict) and len(v) == 1:
        (tag, x), = v.items()
        if tag == "Float":
            return f"{x:.4g}"
        if tag == "Vec2":
            return f"({x[0]:.2f}, {x[1]:.2f})"
        if tag == "Color":
            return Color(*x).to_hex()
        if tag == "Str":
            return repr(x)
        return str(x)
    return str(v)


def _source(obj: dict[str, Any], names: dict[int, str]) -> str:
    src = obj["position_source"]
    if src["kind"] == "container":
        return f"← container {names.get(src['container'], src['container'])}"
    if src["kind"] == "place":
        p = src["placement"]
        if p.get("side"):
            return f"← place({p['side']}={names.get(p['target'], p['target'])})"
        if p.get("at"):
            return f"← place(at={p['at']!r})"
        return "← place(at=point)"
    return "← x, y"


def text_report(objects: list[dict[str, Any]], names: dict[int, str], t: float) -> str:
    out: list[str] = []
    for o in objects:
        if not o["present"]:
            continue
        label = names.get(o["id"], f"{o['kind']}#{o['id']}")
        loc = f"{os.path.basename(o['span']['file'])}:{o['span']['line']}"
        out.append(f"{label}: {o['kind']:<10} {loc}")
        x, y = o["position"]
        out.append(f"  position = ({x:.2f}, {y:.2f})   {_source(o, names)}")
        b = o["bbox"]
        out.append(f"  bbox     = [{b[0]:.2f}, {b[1]:.2f} → {b[2]:.2f}, {b[3]:.2f}]")
        for k in ("text", "fill", "stroke", "opacity", "scale", "value"):
            if k in o["props"]:
                out.append(f"  {k:<8} = {_fmt(o['props'][k])}")
    return "\n".join(out) or f"(nothing in the scene at t = {t:.2f} s)"


def object_labels(result: BuildResult) -> dict[int, str]:
    """Object id → the label users know it by (variable name, `row[2]`, `kind#id`)."""
    assert result.scene is not None
    return {n._id: n._label() for n in result.scene._nodes}


def inspect_payload(result: BuildResult, at: str, include_absent: bool = False) -> dict[str, Any]:
    """The `kinemo inspect --json` payload of a built scene at instant `at` (seconds, mark or 'end')."""
    assert result.scene is not None
    t = parse_time(at, result.scene.duration, result.scene.marks)
    objects = json.loads(result.scene.builder.inspect(t))
    names = object_labels(result)
    for o in objects:
        o["label"] = names.get(o["id"])
    return {
        "scene": result.definition.name,
        "t": t,
        "objects": [o for o in objects if o["present"] or include_absent],
    }


def run(args: argparse.Namespace) -> int:
    try:
        module = load_module(args.file)
    except LoadError as e:
        print(e.diagnostic.render())
        return 1
    for defn in select(find_scenes(module), args.scene):
        result = build(defn, args.params)
        if result.scene is None:
            print("\n".join(d.render() for d in result.diagnostics))
            return 1
        payload = inspect_payload(result, str(args.at), include_absent=True)
        if args.json:
            if not args.all:
                payload["objects"] = [o for o in payload["objects"] if o["present"]]
            emit_json(payload)
        else:
            print(text_report(payload["objects"], object_labels(result), payload["t"]))
    return 0
