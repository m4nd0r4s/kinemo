"""Golden snapshots: the spec scenes must render byte-identical frames (CPU renderer).

Regenerate with `KINEMO_UPDATE_GOLDEN=1 pytest tests/python/test_golden.py`."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "golden"
UPDATE = os.environ.get("KINEMO_UPDATE_GOLDEN") == "1"

CASES = {
    "hello": [0.5, 1.5, 3.0],
    "bubble_sort": [0.4, 2.0, 6.0, 11.0],
}


def _scene(name: str):
    spec = importlib.util.spec_from_file_location(f"golden_{name}", ROOT / "examples" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, name).build()


@pytest.mark.parametrize("name", sorted(CASES))
def test_check_summary_is_stable(name: str) -> None:
    s = _scene(name)
    summary = {"duration": round(s.duration, 6), "timeline": [(round(e.start, 6), round(e.end, 6), e.label) for e in s._log]}
    path = GOLDEN / f"{name}.timeline.json"
    if UPDATE or not path.exists():
        path.write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8")) == json.loads(json.dumps(summary))


@pytest.mark.parametrize("name,t", [(n, t) for n, ts in sorted(CASES.items()) for t in ts])
def test_frames_match_golden(name: str, t: float) -> None:
    png = _scene(name).builder.frame_png(t, "draft")
    path = GOLDEN / f"{name}_{t:.2f}.png"
    if UPDATE or not path.exists():
        path.write_bytes(png)
    assert png == path.read_bytes(), f"{path.name} differs from the golden snapshot"
