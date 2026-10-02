"""Objects an axes creates (plots, tangents, lines, areas, markers) enter with the axes by
default; `enter_with_axes=False` keeps them hidden until their own verb brings them in."""

from __future__ import annotations

from typing import Any

import kinemo as k
from conftest import build, ir

NODES: dict[str, k.Node] = {}


def f(x: float) -> float:
    return 0.15 * x**3 - 0.9 * x + 1.5


def keep(**nodes: k.Node) -> None:
    """Remember nodes by name to read their presence after the build."""
    NODES.clear()
    NODES.update(nodes)


def presence(scene: Any, name: str) -> list[tuple[float, bool]]:
    entry = next(o for o in ir(scene)["objects"] if o["id"] == NODES[name]._id)
    return [(t, present) for t, present in entry["presence"]]


def test_axes_children_enter_with_the_axes_by_default() -> None:
    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(-3, 3, 1), y=(-1, 5, 1))
        x = k.signal(-2.0)
        curve = ax.plot(f)
        tan = curve.tangent_at(x)
        keep(curve=curve, tan=tan)
        s.play(k.draw(ax))

    assert presence(scene, "curve") == [(0.0, True)]
    assert presence(scene, "tan") == [(0.0, True)]


def test_a_tangent_kept_out_enters_only_with_its_own_verb() -> None:
    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(-3, 3, 1), y=(-1, 5, 1))
        x = k.signal(-2.0)
        curve = ax.plot(f)
        tan = curve.tangent_at(x, enter_with_axes=False)
        keep(curve=curve, tan=tan)
        s.play(k.draw(ax))
        s.play(k.fade_in(tan))

    assert presence(scene, "curve") == [(0.0, True)]
    assert presence(scene, "tan") == [(1.0, True)]


def test_a_tangent_made_after_the_axes_entered_waits_too() -> None:
    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(-3, 3, 1), y=(-1, 5, 1))
        curve = ax.plot(f)
        s.play(k.draw(ax))
        tan = curve.tangent_at(0.0, enter_with_axes=False)
        keep(tan=tan)
        s.wait(1)
        s.add(tan)

    assert presence(scene, "tan") == [(2.0, True)]


def test_every_axes_helper_accepts_the_flag() -> None:
    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(-3, 3, 1), y=(-1, 5, 1))
        curve = ax.plot(f, label="f", enter_with_axes=False)
        area = ax.area(curve, domain=(0, 1), enter_with_axes=False)
        vertical = ax.vline(1, enter_with_axes=False)
        horizontal = ax.hline(2, enter_with_axes=False)
        points = ax.scatter([0, 1], [1, 2], enter_with_axes=False)
        loop = ax.parametric(lambda t: t, lambda t: t, t=(0, 1), enter_with_axes=False)
        columns = ax.bars([1, 2], [1, 2], enter_with_axes=False)
        keep(curve=curve, area=area, vertical=vertical, horizontal=horizontal, points=points, loop=loop, columns=columns)
        s.play(k.draw(ax))
        s.play(k.draw(curve, area, vertical, horizontal, points, loop, columns))

    for name in ("curve", "area", "vertical", "horizontal", "points", "loop", "columns"):
        assert presence(scene, name) == [(1.0, True)], name


def test_a_kept_out_plot_brings_its_label_along() -> None:
    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(-3, 3, 1), y=(-1, 5, 1))
        curve = ax.plot(f, label="f", enter_with_axes=False)
        label = curve.label
        keep(label=label)
        s.play(k.draw(ax))
        s.play(k.draw(curve))

    assert presence(scene, "label") == [(1.0, True)]


def test_a_polar_plot_kept_out_waits_for_its_verb() -> None:
    @build
    def scene(s: k.Scene) -> None:
        polar = k.PolarAxes()
        rose = polar.plot(lambda theta: 1.0, enter_with_axes=False)
        keep(rose=rose)
        s.play(k.draw(polar))
        s.play(k.draw(rose))

    assert presence(scene, "rose") == [(1.0, True)]
