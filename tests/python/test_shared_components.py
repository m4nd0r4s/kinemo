"""Components shared across scene files: `[python] paths` in kinemo.toml, a file's own scenes
(not the preview scenes of what it imports), and `kinemo dev` reloading shared modules."""

from __future__ import annotations

import sys
from pathlib import Path

from kinemo.cli.dev import Session
from kinemo.cli.loader import find_scenes, load_module
from kinemo.project import load
from test_dev_editing import FakeServer

COMPONENT = '''import kinemo as k


def badge(text: str) -> k.Text:
    return k.Text(text, size=0.4)


@k.scene
def preview(s: k.Scene):
    s.add(badge("preview"))
    s.wait(0.5)
'''

EPISODE = '''import kinemo as k
from badges import badge


@k.scene
def episode(s: k.Scene):
    s.add(badge("{label}"))
    s.wait(0.5)
'''


def project(tmp_path: Path, label: str = "v1") -> Path:
    (tmp_path / "kinemo.toml").write_text('[python]\npaths = ["lib"]\n', encoding="utf-8")
    (tmp_path / "lib").mkdir(exist_ok=True)
    (tmp_path / "lib" / "badges.py").write_text(COMPONENT, encoding="utf-8")
    (tmp_path / "episodes").mkdir(exist_ok=True)
    scene = tmp_path / "episodes" / "e01.py"
    scene.write_text(EPISODE.replace("{label}", label), encoding="utf-8")
    load.cache_clear()
    sys.modules.pop("badges", None)  # each test has its own project
    return scene


def test_scene_files_import_from_project_paths_and_keep_only_their_scenes(tmp_path: Path) -> None:
    scene = project(tmp_path)
    scenes = find_scenes(load_module(str(scene)))
    assert [s.name for s in scenes] == ["episode"]
    component = find_scenes(load_module(str(tmp_path / "lib" / "badges.py")))
    assert [s.name for s in component] == ["preview"]


def test_dev_reloads_a_shared_component_outside_the_scene_folder(tmp_path: Path) -> None:
    scene = project(tmp_path)
    session = Session(str(scene), None, {}, FakeServer())  # type: ignore[arg-type]
    assert session.rebuild()
    assert str(tmp_path / "lib" / "badges.py") in session.watched
    (tmp_path / "lib" / "badges.py").write_text(COMPONENT.replace("size=0.4", "size=0.5"), encoding="utf-8")
    assert session.rebuild()
    import badges  # type: ignore[import-not-found]  # the fresh module, imported by the rebuild

    assert "size=0.5" in Path(badges.__file__).read_text(encoding="utf-8")  # type: ignore[attr-defined]
