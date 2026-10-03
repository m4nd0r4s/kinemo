"""`kinemo snap`: PNGs of the requested instants."""

from __future__ import annotations

import argparse
import os

from .loader import BuildResult, LoadError, build, find_scenes, load_module, select
from .output_path import ensure_folder_of, single_file
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
    status = 0
    scenes = select(find_scenes(module), args.scene)
    instants = args.at.split(",")
    single = single_file(args.out, ("png",))
    if single is not None and len(scenes) * len(instants) != 1:
        print(f"kinemo: --out {args.out} names one file, but {len(scenes) * len(instants)} frames would be written; pass one --scene and one --at")
        return 2
    if single is not None:
        ensure_folder_of(single[0])
    else:
        os.makedirs(args.out, exist_ok=True)
    for defn in scenes:
        result = build(defn, args.params)
        if result.scene is None:
            print("\n".join(d.render() for d in result.diagnostics))
            status = 1
            continue
        for text in instants:
            _, png = snap_png(result, text, args.quality)
            path = single[0] if single else os.path.join(args.out, f"{defn.name}_{text.strip()}.png")
            with open(path, "wb") as fh:
                fh.write(png)
            print(path)
    return status
