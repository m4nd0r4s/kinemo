"""Videos and posters of the repository's examples, rendered by kinemo itself, and the
timeline of a scene as the preview shows it. Renders are cached by the example's source."""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import CACHE, EXAMPLES

#: Bump to re-render every cached video (a change in how the site renders them).
RENDER_VERSION = "1"
#: Where the poster frame is taken, as a fraction of the scene's duration.
POSTER_AT = 0.6


@dataclass
class Media:
    name: str
    video: Path
    poster: Path
    duration: float
    #: The timeline as `kinemo dev` shows it: `{start, end, label, line}` per play/start.
    bars: list[dict[str, Any]]


def load_scene(name: str) -> Any:
    """The `@k.scene` definition of `examples/<name>.py`."""
    spec = importlib.util.spec_from_file_location(f"site_example_{name}", EXAMPLES / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, name)


def _cache_key(name: str) -> str:
    import kinemo

    digest = hashlib.sha256()
    for part in (RENDER_VERSION, kinemo.__version__, (EXAMPLES / f"{name}.py").read_text(encoding="utf-8")):
        digest.update(part.encode())
    return digest.hexdigest()[:16]


def render_example(name: str, *, videos: bool = True) -> Media:
    """Builds the example, and renders its MP4 and poster unless they are cached."""
    scene = load_scene(name).build()
    bars = [
        {"start": round(e.start, 4), "end": round(e.end, 4), "label": e.label, "line": e.span.line}
        for e in sorted(scene._log, key=lambda e: (e.start, e.end))  # pyright: ignore[reportPrivateUsage]
    ]
    key = _cache_key(name)
    folder = CACHE / name / key
    video, poster = folder / f"{name}.mp4", folder / f"{name}.png"
    if videos and not (video.exists() and poster.exists()):
        if folder.parent.exists():
            shutil.rmtree(folder.parent)
        folder.mkdir(parents=True)
        scene.builder.render_video(str(video), "mp4", "final")
        poster.write_bytes(scene.builder.frame_png(min(scene.duration - 1e-3, POSTER_AT * scene.duration), "final"))
    return Media(name, video, poster, scene.duration, bars)
