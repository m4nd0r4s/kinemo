"""Performance targets from the spec (typical scene, recent laptop). Each test measures the
best of a few runs so a busy machine does not make it flaky; set KINEMO_SKIP_PERF=1 to skip."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("KINEMO_SKIP_PERF") == "1", reason="performance tests disabled")

ROOT = Path(__file__).resolve().parents[2]


def best_of(runs: int, fn: Callable[[], Any]) -> float:
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def scene_def(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(f"perf_{name}", ROOT / "examples" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, name)


def test_check_under_300ms() -> None:
    from kinemo.cli.loader import build

    defn = scene_def("bubble_sort")
    assert best_of(3, lambda: build(defn)) < 0.300


def test_rebuild_under_500ms() -> None:
    defn = scene_def("solar_day")
    assert best_of(3, defn.build) < 0.500


def test_draft_preview_frame_under_30ms() -> None:
    s = scene_def("bubble_sort").build()
    b = s.builder
    assert best_of(5, lambda: b.frame_rgba(5.0, "draft")) < 0.030


def test_final_render_at_least_real_time(tmp_path: Path) -> None:
    from kinemo._core import ffmpeg_available

    if not ffmpeg_available():
        pytest.skip("ffmpeg not installed")
    s = scene_def("bubble_sort").build()
    elapsed = best_of(1, lambda: s.builder.render_video(str(tmp_path / "out.mp4"), "mp4", "final"))
    assert elapsed <= s.duration


def test_import_under_150ms() -> None:
    code = "import time; t = time.perf_counter(); import kinemo; print(time.perf_counter() - t)"
    times = [float(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout) for _ in range(3)]
    assert min(times) < 0.150
