"""`kinemo snap`: PNGs of the requested instants."""

from __future__ import annotations

import argparse
import os

from .loader import BuildResult, LoadError, build, find_scenes, load_module, select
from .output_path import ensure_folder_of, single_file
from .instants import InstantError, parse_time


def snap_png(result: BuildResult, at: str, quality: str = "draft") -> tuple[float, bytes]:
    """The instant `at` resolves to (seconds, mark or 'end') and the PNG bytes of that frame."""
    assert result.scene is not None
    t = parse_time(at, result.scene.duration, result.scene.marks)
    return t, result.scene.builder.frame_png(t, quality)


def instants_of(at: str, marks: dict[str, float]) -> list[str]:
    """The `--at` list, with `marks` standing for every mark of the scene in time order."""
    out: list[str] = []
    for text in (t.strip() for t in at.split(",")):
        out += sorted(marks, key=lambda name: marks[name]) if text == "marks" else [text]
    return out


def run(args: argparse.Namespace) -> int:
    try:
        module = load_module(args.file)
    except LoadError as e:
        print(e.diagnostic.render())
        return 1
    status = 0
    scenes = select(find_scenes(module), args.scene)
    single = single_file(args.out, ("png",))
    if single is not None:
        expected = len(scenes) if args.sheet else len(scenes) * len(args.at.split(","))
        if expected != 1 or (not args.sheet and "marks" in args.at.split(",")):
            what = "sheets" if args.sheet else "frames"
            print(f"kinemo: --out {args.out} names one file, but several {what} would be written; pass one --scene" + ("" if args.sheet else " and one --at"))
            return 2
        ensure_folder_of(single[0])
    else:
        os.makedirs(args.out, exist_ok=True)
    for defn in scenes:
        result = build(defn, args.params)
        if result.scene is None:
            print("\n".join(d.render() for d in result.diagnostics))
            status = 1
            continue
        scene = result.scene
        try:
            instants = instants_of(args.at, scene.marks)
            times = [parse_time(text, scene.duration, scene.marks) for text in instants]
        except InstantError as error:
            print(f"kinemo: {error}")
            return 2
        if args.sheet:
            labels = [f"{text}  {t:.2f} s" if text != f"{t:g}" else f"{t:.2f} s" for text, t in zip(instants, times)]
            path = single[0] if single else os.path.join(args.out, f"{defn.name}_sheet.png")
            with open(path, "wb") as fh:
                fh.write(scene.builder.contact_sheet_png(times, labels, args.columns))
            print(path)
            continue
        for text, t in zip(instants, times):
            path = single[0] if single else os.path.join(args.out, f"{defn.name}_{text}.png")
            with open(path, "wb") as fh:
                fh.write(scene.builder.frame_png(t, args.quality))
            print(path)
    return status
