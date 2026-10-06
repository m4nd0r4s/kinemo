"""Scene presets: `[presets.<name>]` in kinemo.toml with `@k.scene(preset=)`, and
`k.scene_preset(...)` decorators."""

from __future__ import annotations

from pathlib import Path

import pytest

import kinemo as k
from kinemo.cli.loader import find_scenes, load_module
from kinemo.project import load

SCENE = """
import kinemo as k

@k.scene(preset="short")
def teaser(s: k.Scene):
    s.wait(1)

@k.scene(preset="short", tail=2.0)
def overridden(s: k.Scene):
    s.wait(1)
"""


def test_toml_presets_apply_under_the_decorator(tmp_path: Path) -> None:
    (tmp_path / "kinemo.toml").write_text('[scene]\nfps = 30\n\n[presets.short]\nsize = "vertical"\ntail = 1.0\n', encoding="utf-8")
    (tmp_path / "scene.py").write_text(SCENE, encoding="utf-8")
    load.cache_clear()
    teaser, overridden = find_scenes(load_module(str(tmp_path / "scene.py")))
    assert teaser.config.size == (1080, 1920) and teaser.config.tail == 1.0 and teaser.config.fps == 30.0
    assert overridden.config.tail == 2.0


def test_unknown_preset_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "kinemo.toml").write_text("[scene]\n", encoding="utf-8")
    (tmp_path / "scene.py").write_text(SCENE, encoding="utf-8")
    load.cache_clear()
    with pytest.raises(Exception, match="unknown scene preset 'short'"):
        load_module(str(tmp_path / "scene.py"))


def test_scene_preset_makes_a_decorator() -> None:
    episode = k.scene_preset(tail=1.5, fps=24)

    @episode
    def plain(s: k.Scene) -> None:
        s.wait(1)

    @episode(fps=30)
    def faster(s: k.Scene) -> None:
        s.wait(1)

    assert plain.config.tail == 1.5 and plain.config.fps == 24.0
    assert faster.config.fps == 30.0 and faster.config.tail == 1.5
