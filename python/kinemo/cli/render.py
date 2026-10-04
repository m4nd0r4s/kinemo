"""`kinemo render`: final output (video, GIF, frames)."""

from __future__ import annotations

import argparse
import os

from .loader import LoadError, build, find_scenes, load_module, select
from .output_path import ensure_folder_of, single_file
from .progress import finished, reporter

VIDEO = ("mp4", "webm", "mov", "gif")


def run(args: argparse.Namespace) -> int:
    try:
        module = load_module(args.file)
    except LoadError as e:
        print(e.diagnostic.render())
        return 1
    status = 0
    from ..movie import Movie

    single = single_file(args.out, (*VIDEO, "png", "svg"))
    if single is not None and args.format is not None and args.format != single[1]:
        print(f"kinemo: --out {args.out} is a .{single[1]} file but --format is {args.format}")
        return 2
    args.format = args.format or (single[1] if single else "mp4")
    if single is not None and args.frames:
        print("kinemo: --frames writes a folder of PNGs; pass a folder to --out")
        return 2
    movies = [m for m in vars(module).values() if isinstance(m, Movie)]
    outputs = len(movies) if movies and args.scene is None else len(select(find_scenes(module), args.scene))
    if single is not None and outputs != 1:
        print(f"kinemo: --out {args.out} names one file, but {outputs} scenes would render; pass --scene NAME")
        return 2
    if single is not None:
        ensure_folder_of(single[0])
    else:
        os.makedirs(args.out, exist_ok=True)
    if movies and args.scene is None and args.format not in VIDEO:
        print(f"kinemo: a movie renders to video ({', '.join(VIDEO)}); pass --scene NAME for --format {args.format}")
        return 2
    if movies and args.scene is None:
        for m in movies:
            path = single[0] if single else os.path.join(args.out, f"{m.name}.{args.format if args.format in VIDEO else 'mp4'}")
            m.render(path, args.format if args.format in VIDEO else "mp4", args.quality, reporter(args.progress, m.name))
            finished(args.progress, m.name, path)
            print(f"kinemo: {path}")
        return 0
    for defn in select(find_scenes(module), args.scene):
        result = build(defn, args.params)
        if result.scene is None:
            print("\n".join(d.render() for d in result.diagnostics))
            status = 1
            continue
        b = result.scene.builder
        base = os.path.splitext(single[0])[0] if single else os.path.join(args.out, defn.name)
        if args.format in VIDEO:
            path = f"{base}.{args.format}"
            b.render_video(path, args.format, args.quality, args.transparent, reporter(args.progress, defn.name))
            finished(args.progress, defn.name, path)
            print(f"kinemo: {path}")
        elif args.format == "png":
            if args.frames:
                os.makedirs(base, exist_ok=True)
                fps = result.scene.config.fps if args.quality == "final" else min(30.0, result.scene.config.fps)
                n = int(result.scene.duration * fps) + 1
                for i in range(n):
                    with open(os.path.join(base, f"{i:05d}.png"), "wb") as fh:
                        fh.write(b.frame_png(i / fps, args.quality, args.transparent))
                print(f"kinemo: {n} frames in {base}/")
            else:
                t = parse_time(args.at or "end", result.scene.duration, result.scene.marks)
                path = f"{base}.png"
                with open(path, "wb") as fh:
                    fh.write(b.frame_png(t, args.quality, args.transparent))
                print(f"kinemo: {path}")
        elif args.format == "svg":
            t = parse_time(args.at or "end", result.scene.duration, result.scene.marks)
            path = f"{base}.svg"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(b.frame_svg(t, args.transparent))
            print(f"kinemo: {path}")
        elif args.format == "slides":
            from ..export.slides import export

            print(f"kinemo: {export(result.scene, args.out, args.quality)}")
        else:
            print(f"kinemo: format '{args.format}' is not supported yet")
            status = 2
    return status


def parse_time(text: str, duration: float, marks: dict[str, float]) -> float:
    text = text.strip()
    if text == "end":
        return max(0.0, duration - 1e-6)
    if text in marks:
        return marks[text]
    return min(max(0.0, float(text)), duration)
