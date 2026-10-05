"""Timings of each stage of a scene: build, lints, one frame, parallel rendering and the
end-to-end video render. Every measurement is the best of a few runs, so a busy machine
shows less noise."""

from __future__ import annotations

import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from kinemo import lints
from kinemo.linting import code_diagnostics, visual_diagnostics
from kinemo.linting.component_ranges import range_diagnostics
from kinemo.linting.mass_objects import mass_object_diagnostics


@dataclass
class SceneTimings:
    """Seconds for each stage (fps for the throughput ones) of one scene."""

    scene: str
    duration: float
    frames: int
    build: float
    lint_layout: float
    lint_visual: float
    lint_other: float
    frame_draft_ms: float
    frame_final_ms: float
    render_only_fps: float
    video_fps: float | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def best_of(runs: int, action: Callable[[], object]) -> float:
    """The shortest of `runs` timings of `action`, in seconds."""
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        action()
        best = min(best, time.perf_counter() - start)
    return best


def measure(label: str, scene_def: Any, *, video: bool = True, runs: int = 3) -> SceneTimings:
    scene = scene_def.build()
    builder = scene.builder
    fps = scene.config.fps
    frames = max(1, int(scene.duration * fps))
    build = best_of(runs, scene_def.build)

    def collector() -> Any:
        return lints._collector_like(scene)  # pyright: ignore[reportPrivateUsage]

    lint_layout = best_of(1, lambda: lints.layout_diagnostics(scene))
    lint_visual = best_of(1, lambda: visual_diagnostics(scene, collector(), lints.VISUAL_SAMPLE_STEP))
    lint_other = best_of(
        1,
        lambda: (code_diagnostics(scene, scene_def, collector()), mass_object_diagnostics(scene, collector()), range_diagnostics(scene)),
    )
    middle = scene.duration / 2
    frame_draft = best_of(5, lambda: builder.frame_rgba(middle, "draft"))
    frame_final = best_of(5, lambda: builder.frame_rgba(middle, "final"))

    # Final-quality frames over the whole scene on every core (the renderer releases the GIL).
    times = [index / fps for index in range(frames)]
    start = time.perf_counter()
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        for _ in pool.map(lambda t: builder.frame_rgba(t, "final"), times):
            pass
    render_only_fps = frames / (time.perf_counter() - start)

    video_fps = None
    if video:
        with tempfile.TemporaryDirectory() as folder:
            start = time.perf_counter()
            builder.render_video(Path(folder) / "out.mp4", "mp4", "final")
            video_fps = frames / (time.perf_counter() - start)

    return SceneTimings(
        scene=label,
        duration=scene.duration,
        frames=frames,
        build=build,
        lint_layout=lint_layout,
        lint_visual=lint_visual,
        lint_other=lint_other,
        frame_draft_ms=frame_draft * 1000,
        frame_final_ms=frame_final * 1000,
        render_only_fps=render_only_fps,
        video_fps=video_fps,
    )
