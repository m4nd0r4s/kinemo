"""PNG frame sequences: `builder.render_frames` writes numbered files in parallel, identical to
`frame_png` at the same instants."""

from __future__ import annotations

from pathlib import Path

import kinemo as k
from conftest import build


def test_frames_match_single_frame_renders(tmp_path: Path) -> None:
    @build
    def scene(s: k.Scene) -> None:
        dot = k.Dot(r=0.3)
        s.add(dot)
        s.play(dot.to(x=3), duration=0.5)

    builder = scene.builder
    progress: list[int] = []
    builder.render_frames(tmp_path, 12, 24.0, "draft", False, lambda done, total: progress.append(done))
    files = sorted(tmp_path.glob("*.png"))
    assert [f.name for f in files] == [f"{i:05d}.png" for i in range(12)]
    for i in (0, 5, 11):
        assert files[i].read_bytes() == builder.frame_png(i / 24.0, "draft", False)
    assert sorted(progress) == list(range(1, 13))
