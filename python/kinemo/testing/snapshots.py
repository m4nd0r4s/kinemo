"""`assert_snapshot(scene, t)`: compare a frame with a golden PNG kept next to the test."""

from __future__ import annotations

import inspect as python_inspect
import os
import re
from typing import Union

from ..cli.snap import snap_png
from .building import BuiltScene, SceneLike, build

Instant = Union[float, int, str]

#: Environment variable that, when set to `1`, rewrites golden files instead of comparing.
UPDATE_ENVIRONMENT_VARIABLE = "KINEMO_UPDATE_SNAPSHOTS"
SNAPSHOT_DIRECTORY = "__snapshots__"


class SnapshotMismatch(AssertionError):
    """The rendered frame differs from the golden file; the actual frame was saved beside it."""

    def __init__(self, golden_path: str, actual_path: str, scene_name: str, t: float) -> None:
        self.golden_path = golden_path
        self.actual_path = actual_path
        super().__init__(
            f"snapshot mismatch for scene '{scene_name}' at t = {t:.2f} s\n"
            f"  expected: {golden_path}\n"
            f"  actual:   {actual_path}\n"
            f"  if the change is intended, rerun with {UPDATE_ENVIRONMENT_VARIABLE}=1"
        )


def assert_snapshot(
    scene_def_or_built: SceneLike,
    t: Instant,
    name: str | None = None,
    quality: str = "draft",
) -> str:
    """Assert that the frame at `t` matches `__snapshots__/<name>.png` next to the calling test.

    - First run (no golden file): the frame is written and the assertion passes.
    - `KINEMO_UPDATE_SNAPSHOTS=1`: the golden file is rewritten.
    - Mismatch: the frame is saved as `<name>.actual.png` and `SnapshotMismatch` (an
      `AssertionError`) is raised with both paths. A stale `.actual.png` is removed on a match.

    `name` defaults to `<test function>-<scene>-<t>`. Comparison is byte for byte: the CPU
    renderer is deterministic. Returns the golden file's path."""
    built: BuiltScene = build(scene_def_or_built)
    resolved_t, png = snap_png(built.result, str(t), quality)
    caller_file, caller_function = _calling_test()
    directory = os.path.join(os.path.dirname(os.path.abspath(caller_file)), SNAPSHOT_DIRECTORY)
    base = _safe_file_name(name or f"{caller_function}-{built.name}-{t}")
    golden_path = os.path.join(directory, f"{base}.png")
    actual_path = os.path.join(directory, f"{base}.actual.png")

    if os.environ.get(UPDATE_ENVIRONMENT_VARIABLE) == "1" or not os.path.exists(golden_path):
        _write(golden_path, png)
        _remove(actual_path)
        return golden_path
    with open(golden_path, "rb") as fh:
        expected = fh.read()
    if expected == png:
        _remove(actual_path)
        return golden_path
    _write(actual_path, png)
    raise SnapshotMismatch(golden_path, actual_path, built.name, resolved_t)


def _calling_test() -> tuple[str, str]:
    """File and function of the first frame outside `kinemo.testing` (the test calling us)."""
    package_directory = os.path.dirname(os.path.abspath(__file__))
    frame = python_inspect.currentframe()
    try:
        while frame is not None:
            filename = os.path.abspath(frame.f_code.co_filename)
            if os.path.dirname(filename) != package_directory:
                return filename, frame.f_code.co_name
            frame = frame.f_back
    finally:
        del frame
    return os.path.abspath("snapshot"), "snapshot"


def _safe_file_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "snapshot"


def _write(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
