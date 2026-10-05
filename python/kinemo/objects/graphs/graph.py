"""`k.Graph`: nodes and edges laid out as a force, tree, layered or circle graph, with animated
structure changes (`add_node`, `add_edge`, `remove`), path highlights and relayouts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Sequence, Unpack

from ...anim.animation import Animation, par, stagger
from ...diagnostics import KinemoError
from ...reactive.native import max as native_max
from ...reactive.native import sqrt, vec
from ..groups import Group, ReorderTiming
from ..node import Node
from ..shapes import Arrow, Circle, Line
from ..text import Text
from . import layout as layouts
from .layout import LayoutName, NodeName, Position

if TYPE_CHECKING:
    from ...values.aliases import ColorLike
    from ..keywords import TransformKeywords

#: An edge: `("a", "b")`, or `("a", "b", 4)` with a weight shown as its label.
EdgeSpec = tuple[NodeName, NodeName] | tuple[NodeName, NodeName, object]

#: `layout=`: a named layout or the position of every node.
GraphLayout = LayoutName | Mapping[NodeName, Position]


class GraphNode(Group):
    """A node of a `k.Graph`: its `circle` and `label`, and the `name` it was given."""

    if TYPE_CHECKING:
        circle: Circle
        label: Text
        name: NodeName

    def __init__(self, name: NodeName, circle: Circle, label: Text, position: Position) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "circle", circle)
        object.__setattr__(self, "label", label)
        object.__setattr__(circle, "_part", "circle")
        object.__setattr__(label, "_part", "label")
        super().__init__(circle, label, x=position[0], y=position[1])


class GraphEdge(Group):
    """An edge of a `k.Graph`: its `line` (an arrow when the graph is directed), the optional
    weight `label`, and the `ends` it joins. It sits at its midpoint and follows its nodes."""

    if TYPE_CHECKING:
        line: Line | Arrow
        label: Text | None
        ends: tuple[NodeName, NodeName]


class Graph(Group):
    """`k.Graph(["a", "b", "c"], [("a", "b"), ("b", "c", 4)], layout="tree")`: circles with
    labels joined by lines (arrows with `directed=True`; a third item is a weight label).
    `layout=` is `"force"`, `"tree"` (from `root=`), `"layered"` (left to right, for networks),
    `"circle"` or a dict of positions. `g.node("a")` and `g.edge_between("a", "b")` give the parts."""

    if TYPE_CHECKING:
        _graph_opts: tuple[float, float, float, float, bool, NodeName | None]
        _layout: GraphLayout
        _nodes: dict[NodeName, GraphNode]
        _edges: dict[tuple[NodeName, NodeName], GraphEdge]

    def __init__(
        self,
        nodes: Sequence[NodeName],
        edges: Sequence[EdgeSpec] = (),
        *,
        layout: GraphLayout = "force",
        root: NodeName | None = None,
        directed: bool = False,
        width: float = 10.0,
        height: float = 5.5,
        radius: float = 0.35,
        size: float = 0.3,
        **props: Unpack[TransformKeywords],
    ) -> None:
        object.__setattr__(self, "_graph_opts", (float(width), float(height), float(radius), float(size), directed, root))
        object.__setattr__(self, "_layout", layout)
        object.__setattr__(self, "_nodes", {})
        object.__setattr__(self, "_edges", {})
        names = list(nodes)
        if len(set(names)) != len(names):
            raise KinemoError.make("K0105", "k.Graph node names must be unique")
        specs = [self._check_edge(spec, names) for spec in edges]
        positions = self._positions(names, [(u, v) for u, v, _ in specs])
        for name in names:
            self._nodes[name] = self._make_node(name, positions[name])
        for u, v, weight in specs:
            self._edges[(u, v)] = self._make_edge(u, v, weight)
        # Edges under the nodes.
        super().__init__(*self._edges.values(), *self._nodes.values(), **props)

    # ---- parts ---------------------------------------------------------------------------
    def node(self, name: NodeName) -> GraphNode:
        """The node called `name` (`.circle`, `.label`)."""
        if name not in self._nodes:
            raise KinemoError.make("K0105", f"the graph has no node {name!r}")
        return self._nodes[name]

    def edge_between(self, u: NodeName, v: NodeName) -> GraphEdge:
        """The edge between `u` and `v` (`.line`, `.label`); either order for undirected graphs."""
        found = self._find_edge(u, v)
        if found is None:
            raise KinemoError.make("K0105", f"the graph has no edge {u!r} - {v!r}")
        return self._edges[found]

    @property
    def nodes(self) -> list[GraphNode]:
        """The nodes, in the order they were added."""
        return list(self._nodes.values())

    @property
    def edges(self) -> list[GraphEdge]:
        """The edges, in the order they were added."""
        return list(self._edges.values())

    # ---- structure changes ---------------------------------------------------------------
    def add_node(self, name: NodeName, *, edges: Sequence[EdgeSpec] = (), at: Position | None = None, **kw: Unpack[ReorderTiming]) -> Animation:
        """A new node (and its `edges=`) grows in. Without `at=`, the graph is laid out again
        with it and the other nodes move to make room."""
        if name in self._nodes:
            raise KinemoError.make("K0105", f"the graph already has a node {name!r}")
        names = [*self._nodes, name]
        specs = [self._check_edge(spec, names) for spec in edges]
        pairs = [*self._edges, *((u, v) for u, v, _ in specs)]
        positions = self._positions(names, pairs) if at is None else {**self._current_positions(), name: (float(at[0]), float(at[1]))}
        moves = [node.to(x=positions[other][0], y=positions[other][1], duration=kw.get("duration"), ease=kw.get("ease")) for other, node in self._nodes.items() if positions[other] != self._current_positions()[other]]
        new_node = self._make_node(name, positions[name])
        self._nodes[name] = new_node
        new_edges = [self._add_edge_part(u, v, weight) for u, v, weight in specs]
        grow = self._reorder(self._ordered_children(), entering=[new_node, *new_edges], **kw)
        return par(grow, *moves) if moves else grow

    def add_edge(self, u: NodeName, v: NodeName, weight: object = None, **kw: Unpack[ReorderTiming]) -> Animation:
        """A new edge grows in between two existing nodes."""
        _, _, w = self._check_edge((u, v, weight), list(self._nodes))
        edge = self._add_edge_part(u, v, w)
        return self._reorder(self._ordered_children(), entering=[edge], **kw)

    def remove(self, *targets: NodeName | tuple[NodeName, NodeName], **kw: Unpack[ReorderTiming]) -> Animation:
        """Remove nodes (with their edges) or edges given as `(u, v)`: they shrink away."""
        leaving: list[Node] = []
        for target in targets:
            if isinstance(target, tuple) and len(target) == 2 and target not in self._nodes:  # pyright: ignore[reportUnknownArgumentType]
                key = self._find_edge(target[0], target[1])
                if key is None:
                    raise KinemoError.make("K0105", f"the graph has no edge {target[0]!r} - {target[1]!r}")
                leaving.append(self._edges.pop(key))
                continue
            node = self.node(target)
            del self._nodes[target]
            leaving.append(node)
            for key in [key for key in self._edges if target in key]:
                leaving.append(self._edges.pop(key))
        return self._reorder(self._ordered_children(), leaving=leaving, **kw)

    def relayout(self, layout: GraphLayout | None = None, **kw: Unpack[ReorderTiming]) -> Animation:
        """Move the nodes to a new layout (the current one again by default, or another
        named layout or positions); edges follow their nodes."""
        if layout is not None:
            object.__setattr__(self, "_layout", layout)
        positions = self._positions(list(self._nodes), list(self._edges), start=self._current_positions())
        return par(*(node.to(x=positions[name][0], y=positions[name][1], duration=kw.get("duration"), ease=kw.get("ease")) for name, node in self._nodes.items()))

    def path(self, names: Sequence[NodeName], *, color: ColorLike | None = None, lag: float = 0.15, duration: float | None = None) -> Animation:
        """Highlight a path: its nodes and the edges between them take `color` one after the
        other (the accent color by default)."""
        tint: Any = color if color is not None else self._scene.theme.accent
        steps: list[Animation] = []
        for i, name in enumerate(names):
            if i > 0:
                edge = self.edge_between(names[i - 1], name)
                line_props: dict[str, Any] = {"stroke": tint, "stroke_width": 5.0}
                if isinstance(edge.line, Arrow):
                    line_props["fill"] = tint
                steps.append(edge.line.to(duration=duration, **line_props))
            steps.append(self.node(name).circle.to(stroke=tint, stroke_width=5.0, duration=duration))
        return stagger(steps, lag=lag)

    # ---- building ------------------------------------------------------------------------
    def _check_edge(self, spec: EdgeSpec | tuple[NodeName, NodeName, object], names: Sequence[NodeName]) -> tuple[NodeName, NodeName, object]:
        if len(spec) not in (2, 3):
            raise KinemoError.make("K0105", f"a graph edge is (u, v) or (u, v, weight), got {spec!r}")
        u, v = spec[0], spec[1]
        weight = spec[2] if len(spec) == 3 else None
        for end in (u, v):
            if end not in names:
                raise KinemoError.make("K0105", f"edge {u!r} - {v!r} names a node the graph does not have: {end!r}")
        return u, v, weight

    def _find_edge(self, u: NodeName, v: NodeName) -> tuple[NodeName, NodeName] | None:
        if (u, v) in self._edges:
            return (u, v)
        if not self._graph_opts[4] and (v, u) in self._edges:
            return (v, u)
        return None

    def _positions(self, names: list[NodeName], pairs: list[tuple[NodeName, NodeName]], start: Mapping[NodeName, Position] | None = None) -> dict[NodeName, Position]:
        width, height, radius, _, directed, root = self._graph_opts
        chosen = self._layout
        if not isinstance(chosen, str):
            missing = [name for name in names if name not in chosen]
            if missing:
                raise KinemoError.make("K0105", f"layout positions are missing for {missing!r}")
            return {name: (float(chosen[name][0]), float(chosen[name][1])) for name in names}
        if chosen == "circle":
            raw = layouts.circle(names)
        elif chosen == "tree":
            raw = layouts.tree(names, pairs, root, directed)
        elif chosen == "layered":
            raw = layouts.layered(names, pairs)
        elif chosen == "force":
            raw = layouts.force(names, pairs, start=self._unfit(start) if start else None)
        else:
            raise KinemoError.make("K0105", f"unknown graph layout {chosen!r}: use force, tree, layered, circle or positions")
        return layouts.fit(raw, width - 2 * radius, height - 2 * radius, keep_aspect=chosen in ("circle", "force"))

    def _unfit(self, positions: Mapping[NodeName, Position]) -> dict[NodeName, Position]:
        """Scene positions back to the force layout's own scale, to start from them."""
        width = self._graph_opts[0]
        return {name: (x / (width / 2), y / (width / 2)) for name, (x, y) in positions.items()}

    def _current_positions(self) -> dict[NodeName, Position]:
        return {name: (float(node.x.now), float(node.y.now)) for name, node in self._nodes.items()}

    def _make_node(self, name: NodeName, position: Position) -> GraphNode:
        _, _, radius, size, _, _ = self._graph_opts
        node = GraphNode(name, Circle(r=radius, stroke_width=3.0), Text(str(name), size=size), position)
        object.__setattr__(node, "_part", f"node({name!r})")
        return node

    def _make_edge(self, u: NodeName, v: NodeName, weight: object) -> GraphEdge:
        _, _, radius, size, directed, _ = self._graph_opts
        a, b = self._nodes[u], self._nodes[v]
        dx, dy = b.x - a.x, b.y - a.y
        length = native_max(sqrt(dx * dx + dy * dy), 1e-6)
        ux, uy = dx / length, dy / length
        # The edge sits at its midpoint (so it grows from there) and spans circle to circle.
        half = length / 2 - radius
        tip_gap = 0.04 if directed else 0.0
        line: Line | Arrow
        if directed:
            line = Arrow(start=vec(-ux * half, -uy * half), end=vec(ux * (half - tip_gap), uy * (half - tip_gap)), stroke_width=3.0, tip=0.2)
        else:
            line = Line(start=vec(-ux * half, -uy * half), end=vec(ux * half, uy * half), stroke_width=3.0)
        object.__setattr__(line, "_part", "line")
        parts: list[Node] = [line]
        label: Text | None = None
        if weight is not None:
            label = Text(str(weight), size=size * 0.8, x=-uy * size * 1.1, y=ux * size * 1.1)
            object.__setattr__(label, "_part", "label")
            parts.append(label)
        edge = GraphEdge(*parts, x=(a.x + b.x) / 2, y=(a.y + b.y) / 2)
        object.__setattr__(edge, "line", line)
        object.__setattr__(edge, "label", label)
        object.__setattr__(edge, "ends", (u, v))
        object.__setattr__(edge, "_part", f"edge({u!r}, {v!r})")
        return edge

    def _add_edge_part(self, u: NodeName, v: NodeName, weight: object) -> GraphEdge:
        if self._find_edge(u, v) is not None:
            raise KinemoError.make("K0105", f"the graph already has an edge {u!r} - {v!r}")
        edge = self._make_edge(u, v, weight)
        self._edges[(u, v)] = edge
        return edge

    def _ordered_children(self) -> list[Node]:
        return [*self._edges.values(), *self._nodes.values()]
