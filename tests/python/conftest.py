"""Shared helpers for the kinemo test suite.

Scenes are built with `build(fn)`; everything after the build is read from the IR
(`scene.builder.to_json()`) or from the core's `inspect(t)` snapshot, because `.now`
only works while a scene is being built.
"""

from __future__ import annotations

import inspect as python_inspect
import json
from contextlib import contextmanager
from typing import Any, Callable, Iterator

import pytest

import kinemo as k
from kinemo.diagnostics import Diagnostic, KinemoError
from kinemo.scene.scene import Scene

SceneBody = Callable[[k.Scene], None]


@pytest.fixture(autouse=True)
def _no_speech_recognition(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Word times come from the syllable estimate in tests, so results do not depend on
    whether `kinemo[align]` is installed and no model is downloaded. Tests marked `align`
    use it, and run only with KINEMO_TEST_ALIGN=1."""
    if request.node.get_closest_marker("align") is None:
        monkeypatch.setattr("kinemo.audio.align.aligner_available", lambda: False)


def build(fn: SceneBody | None = None, **config: Any) -> Any:
    """Wrap `fn` with `@k.scene(**config)` and build it. Usable as `build(fn)` or `@build`."""

    def build_now(body: SceneBody) -> Scene:
        return k.scene(name=getattr(body, "__name__", "test_scene"), **config)(body).build()

    if fn is not None:
        return build_now(fn)
    return build_now


def ir(scene: Scene) -> dict[str, Any]:
    """The scene's IR mirrored as JSON."""
    return json.loads(scene.builder.to_json())


def inspect(scene: Scene, t: float) -> list[dict[str, Any]]:
    """The core's snapshot of every object at `t`."""
    return json.loads(scene.builder.inspect(t))


def snapshot_of(scene: Scene, t: float, name: str) -> dict[str, Any]:
    """`inspect(t)` entry of the object whose inferred variable name is `name`."""
    matches = [o for o in inspect(scene, t) if o["name"] == name]
    assert len(matches) == 1, f"expected one object named {name!r}, found {len(matches)}"
    return matches[0]


def plain(value: Any) -> Any:
    """Unwrap an encoded IR value (`{"Float": 1.0}` → 1.0)."""
    if isinstance(value, dict) and len(value) == 1:
        (inner,) = value.values()
        if isinstance(inner, list):
            return [plain(v) for v in inner]
        return inner
    return value


def prop_at(scene: Scene, t: float, name: str, prop: str) -> Any:
    return plain(snapshot_of(scene, t, name)["props"][prop])


def position_at(scene: Scene, t: float, name: str) -> tuple[float, float]:
    """Resolved position (after layout) of a named object at `t`."""
    x, y = snapshot_of(scene, t, name)["position"]
    return x, y


def object_ir(scene: Scene, name: str) -> dict[str, Any]:
    matches = [o for o in ir(scene)["objects"] if o["name"] == name]
    assert len(matches) == 1, f"expected one object named {name!r}, found {len(matches)}"
    return matches[0]


def prop_timeline(scene: Scene, name: str, prop: str) -> list[dict[str, Any]]:
    """Timeline entries (sets and animations) of one prop of a named object."""
    signal_id = object_ir(scene, name)["props"][prop]
    return ir(scene)["signals"][signal_id]["timeline"]


def animations(scene: Scene, name: str, prop: str) -> list[tuple[float, float]]:
    """(t0, t1) of every animation of `name.prop`, in schedule order."""
    return [(e["t0"], e["t1"]) for e in prop_timeline(scene, name, prop) if e["k"] == "anim"]


def presence(scene: Scene, name: str) -> list[tuple[float, bool]]:
    return [(t, present) for t, present in object_ir(scene, name)["presence"]]


def line_of(marker: str, depth: int = 1) -> int:
    """1-based line in the caller's file that contains `marker` (a trailing comment)."""
    frame = python_inspect.stack()[depth]
    with open(frame.filename, encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            if marker in line and "line_of(" not in line:
                return number
    raise AssertionError(f"marker {marker!r} not found in {frame.filename}")


@contextmanager
def raises_code(code: str) -> Iterator[pytest.ExceptionInfo[KinemoError]]:
    """Expect a `KinemoError` carrying the diagnostic `code`."""
    with pytest.raises(KinemoError) as info:
        yield info
    assert info.value.diagnostic.code == code, info.value.diagnostic.render()


def diagnostic_of(fn: SceneBody, code: str, **config: Any) -> Diagnostic:
    """Build `fn`, expect it to fail with `code`, and return the diagnostic."""
    with raises_code(code) as info:
        build(fn, **config)
    return info.value.diagnostic


def lint_codes(scene: Scene) -> list[str]:
    return [d.code for d in scene.lints.items]
