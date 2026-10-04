"""Objects made as the elements of a list assigned to a variable are named after it:
`squares[0]`, `dots[1]`, in labels, diagnostics and the dev editor."""

from __future__ import annotations

from pathlib import Path

from kinemo.cli.loader import build, find_scenes, load_module

SCENE = '''import kinemo as k


@k.scene
def lists(s: k.Scene):
    tri = k.Triangle.right(3, 4, scale=0.6)
    squares = [k.Square.on(side, outward=True) for side in tri.sides]
    dots = [k.Dot(x=-1), k.Dot(x=1)]
    single = k.Square.on(tri.sides[0])
    loose = [k.Group(k.Dot(), k.Circle(r=0.2))]
    s.add(tri, *squares, *dots, single, *loose)
'''


def labels(tmp_path: Path) -> set[str]:
    scene = tmp_path / "scene.py"
    scene.write_text(SCENE, encoding="utf-8")
    result = build(find_scenes(load_module(str(scene)))[0], {})
    assert result.scene is not None, [d.render() for d in result.diagnostics]
    return {node._label() for node in result.scene._nodes}


def test_comprehension_elements_are_numbered(tmp_path: Path) -> None:
    assert {"squares[0]", "squares[1]", "squares[2]"} <= labels(tmp_path)


def test_list_literal_elements_take_their_index(tmp_path: Path) -> None:
    assert {"dots[0]", "dots[1]"} <= labels(tmp_path)


def test_a_factory_assigned_to_a_name_is_named(tmp_path: Path) -> None:
    assert "single" in labels(tmp_path)


def test_objects_made_inside_an_element_are_not_named_after_the_list(tmp_path: Path) -> None:
    # The group is `loose[0]`; the dot and circle made in its arguments are its children.
    found = labels(tmp_path)
    assert {"loose[0]", "loose[0][0]", "loose[0][1]"} <= found
