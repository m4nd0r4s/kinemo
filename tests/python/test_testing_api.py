"""`kinemo.testing`: build, inspect and assert_snapshot for users' pytest suites."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import kinemo as k
from kinemo.testing import (
    BuiltScene,
    InspectReport,
    SceneBuildError,
    SnapshotMismatch,
    assert_snapshot,
    build,
    inspect,
)

ROOT = Path(__file__).resolve().parents[2]


def load_example(name: str):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(f"_example_{name}", ROOT / "examples" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, name)


hello = load_example("hello")
bubble_sort = load_example("bubble_sort")


@k.scene
def broken(s: k.Scene):
    title = k.Text("oi").place(at="center")
    s.add(title)
    s.play(title.to(x=3))


@k.scene
def out_of_safe_area(s: k.Scene):
    far = k.Text("longe")
    far.set(x=7.8, y=0)   # cut by the right edge
    s.play(k.write(far))


# --- build -------------------------------------------------------------------------------


def test_build_returns_duration_timeline_and_diagnostics() -> None:
    built = build(hello)
    assert isinstance(built, BuiltScene)
    assert built.duration == pytest.approx(3.5)
    assert [e["label"] for e in built.timeline] == ["write(title)", "title.to(fill, scale)"]
    assert built.diagnostics == []
    assert built.scene.duration == built.duration
    assert built.report()["name"] == "hello"


def test_build_bubble_sort() -> None:
    built = build(bubble_sort)
    assert built.duration > 10 and len(built.timeline) > 10


def test_build_raises_with_the_rendered_diagnostic() -> None:
    with pytest.raises(SceneBuildError) as info:
        build(broken)
    assert "K0401" in str(info.value) and "fix" in str(info.value)
    assert [d.code for d in info.value.diagnostics] == ["K0401"]
    assert isinstance(info.value, AssertionError)


def test_warnings_pass_by_default_and_fail_with_strict() -> None:
    assert build(out_of_safe_area).lint_codes == ["W1001"]
    with pytest.raises(SceneBuildError, match="W1001"):
        build(out_of_safe_area, strict=True)


def test_build_accepts_a_plain_function_and_a_built_scene() -> None:
    def body(s: k.Scene) -> None:
        s.play(k.write(k.Text("x")))

    built = build(body)
    assert built.name == "body"
    assert build(built) is built


def test_build_passes_params() -> None:
    @k.scene(params={"n": k.Int(1, 10, default=3)})
    def counted(s: k.Scene, n) -> None:  # type: ignore[no-untyped-def]
        s.wait(n.now)

    assert build(counted, {"n": 5}).duration > build(counted).duration


# --- inspect ------------------------------------------------------------------------------


def test_inspect_matches_cli_json() -> None:
    report = inspect(hello, "end")
    assert isinstance(report, InspectReport)
    cli = subprocess.run(
        [sys.executable, "-m", "kinemo.cli", "inspect", str(ROOT / "examples" / "hello.py"), "--at", "end", "--json"],
        capture_output=True, text=True, check=True,
        encoding="utf-8",
    )
    assert json.loads(json.dumps(report)) == json.loads(cli.stdout)


def test_inspect_addresses_objects_by_label() -> None:
    built = build(hello)
    start, end = inspect(built, 0), inspect(built, "end")
    assert end.object("title")["position"] == [0.0, 0.0]
    assert end["title"] is end.object("title")
    assert "title" in end and "title" in end.labels
    assert end.object("title")["bbox"][2] > start.object("title")["bbox"][2]  # scaled 1.5×
    with pytest.raises(KeyError, match="available: title"):
        end.object("nope")


def test_inspect_bubble_sort_children_are_labelled() -> None:
    labels = inspect(bubble_sort, 2.0).labels
    assert "row" in labels and any(label.startswith("row[") for label in labels)


# --- assert_snapshot ----------------------------------------------------------------------


@pytest.fixture
def snapshot_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run a generated test file in `tmp_path` so its `__snapshots__` lands there."""
    monkeypatch.delenv("KINEMO_UPDATE_SNAPSHOTS", raising=False)
    return tmp_path


def run_snapshot_test(directory: Path, body: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    test_file = directory / "test_generated.py"
    test_file.write_text(
        "import kinemo as k\nfrom kinemo.testing import assert_snapshot\n\n"
        "@k.scene\ndef hello(s):\n"
        f"    s.play(k.write(k.Text({body!r}).place(at='center')))\n\n"
        "def test_frame():\n    assert_snapshot(hello, 'end')\n",
        encoding="utf-8",
    )
    # No bytecode cache: the file is rewritten within the same second with the same size
    # ("one" → "two"), which a cached .pyc (validated by mtime and size) would not notice.
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(test_file)],
        capture_output=True, text=True, cwd=directory, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", **(env or {})},
        encoding="utf-8",
    )


def test_snapshot_lifecycle_create_match_mismatch_update(snapshot_directory: Path) -> None:
    golden = snapshot_directory / "__snapshots__" / "test_frame-hello-end.png"
    actual = golden.with_name("test_frame-hello-end.actual.png")

    first = run_snapshot_test(snapshot_directory, "one")
    assert first.returncode == 0, first.stdout
    assert golden.read_bytes().startswith(b"\x89PNG")

    assert run_snapshot_test(snapshot_directory, "one").returncode == 0

    mismatch = run_snapshot_test(snapshot_directory, "two")
    assert mismatch.returncode == 1
    assert "snapshot mismatch" in mismatch.stdout and "KINEMO_UPDATE_SNAPSHOTS=1" in mismatch.stdout
    assert actual.exists() and actual.read_bytes() != golden.read_bytes()

    updated = run_snapshot_test(snapshot_directory, "two", {"KINEMO_UPDATE_SNAPSHOTS": "1"})
    assert updated.returncode == 0 and not actual.exists()
    assert run_snapshot_test(snapshot_directory, "two").returncode == 0


def test_assert_snapshot_in_process_uses_the_callers_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KINEMO_UPDATE_SNAPSHOTS", raising=False)
    built = build(hello)
    path = assert_snapshot(built, 2.0, name="hello_middle")
    try:
        assert path == str(Path(__file__).parent / "__snapshots__" / "hello_middle.png")
        assert assert_snapshot(built, 2.0, name="hello_middle") == path  # same bytes: deterministic
        with pytest.raises(SnapshotMismatch):
            assert_snapshot(built, 0, name="hello_middle")
        assert Path(path).with_name("hello_middle.actual.png").exists()
    finally:
        for leftover in ("hello_middle.png", "hello_middle.actual.png"):
            Path(path).with_name(leftover).unlink(missing_ok=True)
        try:
            Path(path).parent.rmdir()
        except OSError:
            pass
