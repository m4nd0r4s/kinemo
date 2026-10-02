"""Real output for the landing page, produced while the site builds: `kinemo check` runs,
its JSON, an edit made by the preview's engine, and timings against the budgets the test
suite asserts. Nothing here is written by hand."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .media import load_scene
from .paths import EXAMPLES, ROOT, WEBSITE

SNIPPETS = WEBSITE / "snippets"


def check_output(file: Path, *extra: str) -> str:
    """`kinemo check FILE` as a terminal shows it, run next to the file (short paths)."""
    env = {**os.environ, "NO_COLOR": "1", "COLUMNS": "100"}
    run = subprocess.run(
        [sys.executable, "-m", "kinemo.cli", "check", file.name, *extra],
        cwd=file.parent, env=env, capture_output=True, text=True, check=False,
        encoding="utf-8",
    )
    return (run.stdout + run.stderr).rstrip().replace(str(ROOT) + os.sep, "")


def check_json(file: Path) -> str:
    """`kinemo check --json`, trimmed to its first scene, with paths relative to the repo."""
    data = json.loads(check_output(file, "--json"))
    for scene in data["scenes"]:
        for bar in scene.get("timeline", []):
            bar["file"] = os.path.relpath(bar["file"], ROOT) if os.path.isabs(bar["file"]) else bar["file"]
    return json.dumps(data, indent=2)


@dataclass
class Edit:
    before: str
    after: str
    line: int


def preview_edit() -> Edit:
    """The line the preview writes when the dot's radius in `examples/derivative.py` is
    dragged to 0.18: done by the same engine `kinemo dev` uses, on a copy of the text."""
    from kinemo.editing.call_sites import SourceFile
    from kinemo.editing.scene_index import index_scene, span_key
    from kinemo.editing.source_edit import Change, apply_changes

    path = EXAMPLES / "derivative.py"
    text = path.read_text(encoding="utf-8")
    scene = load_scene("derivative").build()
    index = index_scene(scene, json.loads(scene.builder.to_json()), {str(path): SourceFile(str(path), text)})
    dot = next(n for n in scene._nodes if n._name == "dot")  # pyright: ignore[reportPrivateUsage]
    entry = index.sites[span_key(dot._span)]  # pyright: ignore[reportPrivateUsage]
    edited = apply_changes(entry.source, [Change(entry.site, "r", "0.18", entry.params)])
    line = entry.site.start.line
    return Edit(text.split("\n")[line - 1], edited.split("\n")[line - 1], line)


@dataclass
class Timing:
    what: str
    budget: str
    measured: str
    ok: bool


def _best(runs: int, fn: Callable[[], Any]) -> float:
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def timings() -> list[Timing]:
    """The budgets of `tests/python/test_performance.py`, measured again on this machine."""
    from kinemo.cli.loader import build

    out: list[Timing] = []
    code = "import time; t = time.perf_counter(); import kinemo; print(time.perf_counter() - t)"
    imports = min(float(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, encoding="utf-8").stdout) for _ in range(3))
    out.append(Timing("import kinemo", "150 ms", f"{imports * 1000:.0f} ms", imports < 0.150))
    bubble = load_scene("bubble_sort")
    check = _best(3, lambda: build(bubble))
    out.append(Timing("kinemo check, bubble sort (build, resolve, lints)", "300 ms", f"{check * 1000:.0f} ms", check < 0.300))
    solar = load_scene("solar_day")
    rebuild = _best(3, solar.build)
    out.append(Timing("rebuild after a save, a day of solar power with events", "500 ms", f"{rebuild * 1000:.0f} ms", rebuild < 0.500))
    builder = bubble.build().builder
    frame = _best(5, lambda: builder.frame_rgba(5.0, "draft"))
    out.append(Timing("one preview frame at draft quality", "30 ms", f"{frame * 1000:.1f} ms", frame < 0.030))
    scene = bubble.build()
    with tempfile.TemporaryDirectory() as folder:
        render = _best(1, lambda: scene.builder.render_video(str(Path(folder) / "out.mp4"), "mp4", "final"))
    speed = scene.duration / render
    out.append(Timing(f"final 1080p render of {scene.duration:.1f} s of video", "real time (1×)", f"{speed:.1f}× real time", speed >= 1))
    return out


def snippet(name: str) -> Path:
    return SNIPPETS / name
