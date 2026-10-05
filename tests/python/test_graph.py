"""`k.Graph`: layouts, parts, structure changes, paths and relayouts."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build
from kinemo.objects.graphs import layout


def test_tree_layout_puts_parents_over_their_children() -> None:
    positions = layout.tree(["a", "b", "c"], [("a", "b"), ("a", "c")], None, False)
    assert positions["a"] == (0.5, 0.0)
    assert positions["b"] == (0.0, -1.0) and positions["c"] == (1.0, -1.0)


def test_layered_layout_follows_longest_paths() -> None:
    positions = layout.layered(["x", "h", "y"], [("x", "h"), ("h", "y"), ("x", "y")])
    assert [positions[name][0] for name in ("x", "h", "y")] == [0.0, 1.0, 2.0]


def test_force_layout_is_deterministic_and_fits_the_box() -> None:
    nodes, edges = list("abcde"), [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")]
    first = layout.fit(layout.force(nodes, edges), 6, 4)
    assert first == layout.fit(layout.force(nodes, edges), 6, 4)
    assert all(abs(x) <= 3 + 1e-9 and abs(y) <= 2 + 1e-9 for x, y in first.values())


def test_edges_follow_nodes_and_structure_changes() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        g = k.Graph(["a", "b", "c"], [("a", "b", 3)], layout={"a": (-2, 0), "b": (2, 0), "c": (0, 2)})
        s.play(k.draw(g))
        edge = g.edge_between("b", "a")
        seen["mid"] = (edge.x.now, edge.y.now)
        seen["weight"] = edge.label.text.now if edge.label else None
        s.play(g.add_node("d", edges=[("c", "d")], at=(0, -2)))
        s.play(g.add_edge("a", "c"))
        s.play(g.remove("b"))
        seen["nodes"] = [node.name for node in g.nodes]
        seen["edges"] = [edge.ends for edge in g.edges]
        s.play(g.node("a").to(x=-3))
        s.play(g.path(["a", "c", "d"]))

    assert seen["mid"] == pytest.approx((0.0, 0.0))
    assert seen["weight"] == "3"
    assert seen["nodes"] == ["a", "c", "d"]
    assert seen["edges"] == [("c", "d"), ("a", "c")]


def test_add_node_relayouts_and_relayout_moves_nodes() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        g = k.Graph(["a", "b"], [("a", "b")], layout="tree")
        s.play(k.draw(g))
        before = g.node("b").x.now
        s.play(g.add_node("c", edges=[("a", "c")]))
        seen["moved"] = g.node("b").x.now != before
        s.play(g.relayout("circle"))
        seen["top"] = g.node("a").y.now > g.node("b").y.now

    assert seen["moved"] is True and seen["top"] is True


def test_unknown_names_are_errors() -> None:
    with pytest.raises(k.KinemoError):

        @build
        def edge_to_nowhere(s: k.Scene) -> None:
            k.Graph(["a"], [("a", "z")])

    with pytest.raises(k.KinemoError):

        @build
        def missing_path(s: k.Scene) -> None:
            g = k.Graph(["a", "b"], [])
            s.add(g)
            s.play(g.path(["a", "b"]))
