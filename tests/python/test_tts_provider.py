"""A `[tts] provider` that is not installed is reported as such (W1402), not as a missing
configuration (W1401)."""

from __future__ import annotations

from pathlib import Path

from kinemo.cli.loader import build, find_scenes, load_module

SCENE = '''import kinemo as k


@k.scene
def narrated(s: k.Scene):
    with s.voice("Hello there"):
        s.play(k.write(k.Text("hi")))
'''


def lint_codes(folder: Path) -> list[str]:
    scene = folder / "scene.py"
    scene.write_text(SCENE, encoding="utf-8")
    result = build(find_scenes(load_module(str(scene)))[0], {})
    return [d.code for d in result.diagnostics]


def test_a_missing_provider_names_itself(tmp_path: Path) -> None:
    (tmp_path / "kinemo.toml").write_text('[tts]\nprovider = "pipr"\n', encoding="utf-8")
    codes = lint_codes(tmp_path)
    assert "W1402" in codes and "W1401" not in codes


def test_no_provider_is_still_w1401(tmp_path: Path) -> None:
    codes = lint_codes(tmp_path)
    assert "W1401" in codes and "W1402" not in codes
