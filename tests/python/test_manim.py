"""K11xx: Manim names are recognized and answered with the kinemo form."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

import kinemo as k
from conftest import diagnostic_of, line_of


def create(s: k.Scene) -> None:
    k.Create  # manim-K1101


def animate(s: k.Scene) -> None:
    c = k.Circle()
    c.animate  # manim-K1102


def value_tracker(s: k.Scene) -> None:
    k.ValueTracker(0)  # manim-K1104


def add_updater(s: k.Scene) -> None:
    c = k.Circle()
    c.add_updater(lambda m: m)  # manim-K1105


def up(s: k.Scene) -> None:
    k.UP  # manim-K1106


CASES: list[tuple[str, Callable[[k.Scene], None], str]] = [
    ("K1101", create, "k.draw"),
    ("K1102", animate, "obj.to("),
    ("K1104", value_tracker, "k.signal("),
    ("K1105", add_updater, "obj.set(x=other.x)"),
    ("K1106", up, "place(above="),
]


@pytest.mark.parametrize(("code", "body", "suggestion"), CASES, ids=[c[0] for c in CASES])
def test_manim_name_is_translated(code: str, body: Callable[[k.Scene], None], suggestion: str) -> None:
    d = diagnostic_of(body, code)
    assert d.spans[0].file == __file__
    assert d.spans[0].line == line_of(f"# manim-{code}")
    assert any(suggestion in (f.code or "") for f in d.fixes), [f.code for f in d.fixes]


@pytest.mark.parametrize(
    ("name", "form"),
    [("FadeIn", "k.fade_in"), ("Write", "k.write"), ("Succession", "k.seq"), ("LaggedStart", "k.stagger"), ("VGroup", "k.Group")],
)
def test_manim_verbs_and_classes_map_to_kinemo(name: str, form: str) -> None:
    with pytest.raises(k.KinemoError) as info:
        getattr(k, name)
    assert info.value.diagnostic.code == "K1101"
    assert form in str(info.value)


@pytest.mark.parametrize("method", ["shift", "move_to", "set_color"])
def test_manim_methods_on_objects_are_k1102(method: str) -> None:
    def body(s: k.Scene) -> None:
        getattr(k.Circle(), method)

    diagnostic_of(body, "K1102")


@pytest.mark.parametrize("method", ["next_to", "to_edge", "arrange", "get_center"])
def test_manim_positioning_methods_are_k1106(method: str) -> None:
    def body(s: k.Scene) -> None:
        getattr(k.Circle(), method)

    diagnostic_of(body, "K1106")


def test_manim_direction_constants_are_k1106() -> None:
    for name in ("DOWN", "LEFT", "RIGHT", "ORIGIN", "UL"):
        with pytest.raises(k.KinemoError) as info:
            getattr(k, name)
        assert info.value.diagnostic.code == "K1106"


def test_manim_animation_value_passed_to_play_is_translated() -> None:
    class Create:  # what a model trained on Manim would hand to s.play
        pass

    def body(s: k.Scene) -> None:
        s.play(Create())  # type: ignore[arg-type]

    diagnostic_of(body, "K1101")


def test_unknown_module_attribute_is_a_plain_attribute_error() -> None:
    with pytest.raises(AttributeError):
        getattr(k, "definitely_not_a_kinemo_name")


def test_a_bare_manim_name_from_a_star_import_habit_is_k1101(tmp_path: Path) -> None:
    from kinemo.cli.loader import build, find_scenes, load_module

    path = tmp_path / "scene.py"
    path.write_text("import kinemo as k\n\n@k.scene\ndef habit(s: k.Scene):\n    s.play(Create(k.Circle()))\n", encoding="utf-8")
    result = build(find_scenes(load_module(str(path)))[0])
    (d,) = result.diagnostics
    assert d.code == "K1101" and "k.draw(obj)" in d.message
    assert d.spans[0].line == 5
