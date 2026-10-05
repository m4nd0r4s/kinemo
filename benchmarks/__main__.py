"""`python -m benchmarks [names...] [--quick] [--json out.json] [--markdown out.md]`

Times every stage of the example scenes and the benchmark scenes (heavy content and a long
episode-like scene). `--quick` skips the long scene and the video renders; names filter the
scenes (`python -m benchmarks bubble_sort points`)."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from pathlib import Path
from typing import Any, Iterator

import kinemo as k

from .report import markdown_table, text_table
from .stages import SceneTimings, measure

ROOT = Path(__file__).resolve().parents[1]
LONG_SCENES = {"long_episode"}


def scene_defs() -> Iterator[tuple[str, Any]]:
    """Every `@k.scene` of the examples and of `benchmarks/scenes`, as (label, definition)."""
    paths = sorted((ROOT / "examples").glob("*.py")) + sorted((ROOT / "benchmarks" / "scenes").glob("[!_]*.py"))
    for path in paths:
        spec = importlib.util.spec_from_file_location(f"benchmark_{path.stem}", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name, value in vars(module).items():
            if isinstance(value, k.SceneDef):
                yield f"{path.stem}:{name}", value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m benchmarks", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("names", nargs="*", help="only scenes whose label contains one of these")
    parser.add_argument("--quick", action="store_true", help="skip the long scene and the video renders")
    parser.add_argument("--json", type=Path, help="write the timings as JSON")
    parser.add_argument("--markdown", type=Path, help="write the table as Markdown (CI job summary)")
    args = parser.parse_args(argv)

    results: list[SceneTimings] = []
    for label, scene_def in scene_defs():
        if args.names and not any(name in label for name in args.names):
            continue
        if args.quick and label.split(":")[1] in LONG_SCENES:
            continue
        print(f"… {label}", file=sys.stderr, flush=True)
        results.append(measure(label, scene_def, video=not args.quick))

    print(text_table(results))
    if args.json:
        machine = {"python": platform.python_version(), "machine": platform.machine(), "system": platform.system(), "kinemo": k.__version__}
        args.json.write_text(json.dumps({"machine": machine, "scenes": [r.as_dict() for r in results]}, indent=1))
    if args.markdown:
        args.markdown.write_text(markdown_table(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
