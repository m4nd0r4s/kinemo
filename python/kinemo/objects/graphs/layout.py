"""Graph layouts: positions for the nodes of a `k.Graph`, fitted to a box centered on the origin.
Deterministic, so a scene builds the same picture every time."""

from __future__ import annotations

import math
import random
from typing import Hashable, Literal, Mapping, Sequence

NodeName = Hashable
Edge = tuple[NodeName, NodeName]
Position = tuple[float, float]

#: `k.Graph(layout=...)`: a named layout or the positions of every node.
LayoutName = Literal["force", "tree", "layered", "circle"]


def circle(nodes: Sequence[NodeName]) -> dict[NodeName, Position]:
    """On a circle, the first node on top, clockwise."""
    n = max(len(nodes), 1)
    return {name: (math.sin(2 * math.pi * i / n), math.cos(2 * math.pi * i / n)) for i, name in enumerate(nodes)}


def _children(nodes: Sequence[NodeName], edges: Sequence[Edge], directed: bool) -> dict[NodeName, list[NodeName]]:
    out: dict[NodeName, list[NodeName]] = {name: [] for name in nodes}
    for u, v in edges:
        out[u].append(v)
        if not directed:
            out[v].append(u)
    return out


def tree(nodes: Sequence[NodeName], edges: Sequence[Edge], root: NodeName | None, directed: bool) -> dict[NodeName, Position]:
    """Top-down tree from `root` (default: the first node): leaves take consecutive slots and
    each parent sits centered over its children. Nodes it cannot reach start new trees beside."""
    adjacency = _children(nodes, edges, directed)
    positions: dict[NodeName, Position] = {}
    next_slot = [0.0]

    def place(name: NodeName, depth: int) -> float:
        positions[name] = (0.0, 0.0)
        xs = [place(kid, depth + 1) for kid in adjacency[name] if kid not in positions]
        if xs:
            x = (xs[0] + xs[-1]) / 2
        else:
            x = next_slot[0]
            next_slot[0] += 1.0
        positions[name] = (x, -float(depth))
        return x

    order = ([root] if root is not None else []) + [name for name in nodes if name != root]
    for name in order:
        if name not in positions:
            place(name, 0)
    return positions


def layered(nodes: Sequence[NodeName], edges: Sequence[Edge]) -> dict[NodeName, Position]:
    """Left-to-right layers by longest path from the sources (neural networks, DAGs); nodes of
    a layer are stacked vertically, centered, in the order given."""
    depth = {name: 0 for name in nodes}
    for _ in range(len(nodes)):
        changed = False
        for u, v in edges:
            if depth[v] < depth[u] + 1 and depth[u] + 1 < len(nodes):
                depth[v] = depth[u] + 1
                changed = True
        if not changed:
            break
    layers: dict[int, list[NodeName]] = {}
    for name in nodes:
        layers.setdefault(depth[name], []).append(name)
    positions: dict[NodeName, Position] = {}
    for d, members in layers.items():
        for i, name in enumerate(members):
            positions[name] = (float(d), (len(members) - 1) / 2 - i)
    return positions


def force(nodes: Sequence[NodeName], edges: Sequence[Edge], start: Mapping[NodeName, Position] | None = None, iterations: int = 300) -> dict[NodeName, Position]:
    """Fruchterman-Reingold spring layout with a fixed seed; `start` keeps known nodes near
    where they were (so adding a node barely moves the rest)."""
    rng = random.Random(7)
    pos = {name: (start[name] if start and name in start else (rng.uniform(-1, 1), rng.uniform(-1, 1))) for name in nodes}
    if len(nodes) < 2:
        return {name: (0.0, 0.0) for name in nodes}
    k = math.sqrt(4.0 / len(nodes))
    temperature = 0.2
    for _ in range(iterations):
        moves = {name: [0.0, 0.0] for name in nodes}
        for i, a in enumerate(nodes):
            for b in nodes[i + 1 :]:
                dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
                dist = max(math.hypot(dx, dy), 1e-3)
                push = k * k / dist
                moves[a][0] += dx / dist * push
                moves[a][1] += dy / dist * push
                moves[b][0] -= dx / dist * push
                moves[b][1] -= dy / dist * push
        for u, v in edges:
            dx, dy = pos[u][0] - pos[v][0], pos[u][1] - pos[v][1]
            dist = max(math.hypot(dx, dy), 1e-3)
            pull = dist * dist / k
            moves[u][0] -= dx / dist * pull
            moves[u][1] -= dy / dist * pull
            moves[v][0] += dx / dist * pull
            moves[v][1] += dy / dist * pull
        for name in nodes:
            mx, my = moves[name]
            length = max(math.hypot(mx, my), 1e-9)
            step = min(length, temperature)
            pos[name] = (pos[name][0] + mx / length * step, pos[name][1] + my / length * step)
        temperature = max(temperature * 0.985, 0.005)
    return pos


def fit(positions: Mapping[NodeName, Position], width: float, height: float, *, keep_aspect: bool = True) -> dict[NodeName, Position]:
    """Scale and center positions into a `width` × `height` box: uniformly with `keep_aspect`,
    else each axis on its own (trees and layers fill the box)."""
    if not positions:
        return {}
    xs, ys = [p[0] for p in positions.values()], [p[1] for p in positions.values()]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
    scales = [s for s in (width / span_x if span_x > 1e-9 else None, height / span_y if span_y > 1e-9 else None) if s is not None]
    scale = min(scales) if scales else 1.0
    if keep_aspect:
        return {name: ((x - cx) * scale, (y - cy) * scale) for name, (x, y) in positions.items()}
    scale_x = width / span_x if span_x > 1e-9 else scale
    scale_y = height / span_y if span_y > 1e-9 else scale
    return {name: ((x - cx) * scale_x, (y - cy) * scale_y) for name, (x, y) in positions.items()}
