"""`kinemo snap`: PNGs of the requested instants."""

from __future__ import annotations

import argparse
import os

from .loader import BuildResult, LoadError, build, find_scenes, load_module, select
from .render import parse_time


def snap_png(result: BuildResult, at: str, quality: str = "draft") -> tuple[float, bytes]:
    """The instant `at` resolves to (seconds, mark or 'end') and the PNG bytes of that frame."""
    assert result.scene is not None
    t = parse_time(at, result.scene.duration, result.scene.marks)
    return t, result.scene.builder.frame_png(t, quality)


def run(args: argparse.Namespace) -> int:
    try:
        module = load_module(args.file)
    except LoadError as e:
        print(e.diagnostic.render())
        return 1
    os.makedirs(args.out, exist_ok=True)
    status = 0
    for defn in select(find_scenes(module), args.scene):
        result = build(defn, args.params)
        if result.scene is None:
            print("\n".join(d.render() for d in result.diagnostics))
            status = 1
            continue
        for text in args.at.split(","):
            _, png = snap_png(result, text, args.quality)
            path = os.path.join(args.out, f"{defn.name}_{text.strip()}.png")
            with open(path, "wb") as fh:
                fh.write(png)
            print(path)
    return status
