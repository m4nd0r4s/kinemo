"""Write the site's data: `src/lib/generated/site-data.json` and `static/media/`."""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import kinemo

from .evidence import check_json, check_output, preview_edit, snippet, timings
from .media import Media, render_example
from .paths import DATA, EXAMPLES, LESSONS, MEDIA, ROOT
from .versions import export_versions

#: The example shown in the landing page's studio, next to its source.
HERO = "derivative"


def gallery_entries() -> dict[str, tuple[str, str, list[str], tuple[float, ...]]]:
    """Titles and descriptions of the examples, shared with `scripts/build_gallery.py`."""
    spec = importlib.util.spec_from_file_location("build_gallery", ROOT / "scripts" / "build_gallery.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.GALLERY


def export_lessons() -> list[str]:
    """`examples/lessons/*.py` as lesson pages in `static/lessons/<name>/`, when this kinemo has
    the lesson player (the site's build makes it; a plain checkout skips them)."""
    from kinemo.cli.loader import build, find_scenes, load_module
    from kinemo.export.lesson import export, player_available

    if not player_available():
        print("lessons skipped: no lesson player (python scripts/build_player.py)", flush=True)
        return []
    if LESSONS.exists():
        shutil.rmtree(LESSONS)
    names = []
    for path in sorted((EXAMPLES / "lessons").glob("*.py")):
        for definition in find_scenes(load_module(str(path))):
            scene = build(definition).scene
            assert scene is not None, f"{path.name} does not build"
            export(scene, str(LESSONS), definition.name)
            names.append(definition.name)
    return names


def export(*, videos: bool = True, measure: bool = True, data_file: Path = DATA) -> dict[str, Any]:
    """Renders the media and writes the data to `data_file` (the site reads `KINEMO_SITE_DATA`
    instead of the default when set)."""
    started = time.perf_counter()
    MEDIA.mkdir(parents=True, exist_ok=True)
    media: dict[str, Media] = {}
    examples: list[dict[str, Any]] = []
    for name, (title, about, features, _frames) in gallery_entries().items():
        media[name] = render_example(name, videos=videos)
        for file in (media[name].video, media[name].poster):
            if file.exists():
                shutil.copy2(file, MEDIA / file.name)
        examples.append({"name": name, "title": title, "about": about, "features": features, "duration": media[name].duration})
    hero = media[HERO]
    lessons = export_lessons()
    data: dict[str, Any] = {
        "version": kinemo.__version__,
        "hero": {
            "name": HERO,
            "source": (EXAMPLES / f"{HERO}.py").read_text(encoding="utf-8").rstrip("\n"),
            "duration": hero.duration,
            "bars": hero.bars,
        },
        "examples": examples,
        "lessons": lessons,
        "docs_versions": export_versions(),
        "checks": {
            "timeline": {"command": f"kinemo check {HERO}.py", "output": check_output(EXAMPLES / f"{HERO}.py")},
            "constraint": {"command": "kinemo check constraint.py", "output": check_output(snippet("constraint.py"))},
            "manim": {"command": "kinemo check manim.py", "output": check_output(snippet("manim.py"))},
            "json": {"command": "kinemo check hello.py --json", "output": check_json(EXAMPLES / "hello.py")},
        },
        "edit": dataclasses.asdict(preview_edit()),
        "timings": [dataclasses.asdict(t) for t in timings()] if measure else [],
        "machine": f"{platform.system()} {platform.machine()}, Python {sys.version_info.major}.{sys.version_info.minor}",
    }
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"exported {len(examples)} examples and the landing data in {time.perf_counter() - started:.1f} s", flush=True)
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="website/export.py", description="Export the kinemo website's data.")
    parser.add_argument("--no-videos", action="store_true", help="skip rendering videos that are not cached yet")
    parser.add_argument("--no-timings", action="store_true", help="skip measuring the performance budgets")
    args = parser.parse_args(argv)
    export(videos=not args.no_videos, measure=not args.no_timings)
    return 0
