"""`python -m benchmarks`: every stage is timed and both tables render."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.__main__ import scene_defs  # noqa: E402
from benchmarks.report import markdown_table, text_table  # noqa: E402
from benchmarks.stages import measure  # noqa: E402


def test_scenes_include_examples_and_benchmark_scenes() -> None:
    labels = [label for label, _ in scene_defs()]
    assert "hello:hello" in labels and "heavy:points_cloud" in labels and "long_episode:long_episode" in labels


def test_measure_times_every_stage() -> None:
    hello = dict(scene_defs())["hello:hello"]
    result = measure("hello:hello", hello, video=False, runs=1)
    assert result.frames > 0 and result.build > 0 and result.frame_final_ms > 0 and result.render_only_fps > 0
    assert result.video_fps is None
    assert "hello:hello" in text_table([result])
    assert markdown_table([result]).startswith("### Benchmarks")
