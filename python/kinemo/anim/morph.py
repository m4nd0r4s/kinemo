"""`k.morph(a, b)`: `a` leaves, `b` enters, corresponding parts travel.

Parts are paired in priority order: explicit `match=`, equal keys aligned as sequences
(characters, tokens, TeX), equal keys by nearest position (repeated terms), then by
order for keyless shapes; the rest fades out of `a` and into `b`."""

from __future__ import annotations

import difflib
import json
import math
from typing import TYPE_CHECKING, Mapping

from .._runtime.spans import Span, user_span
from ..diagnostics import KinemoError
from .animation import Animation
from .ease import Ease, EaseLike
from .verbs import _nodes, _ramp

if TYPE_CHECKING:
    from ..objects.node import Node
    from ..scene.scene import Scene

Part = tuple[str | None, tuple[float, float]]

#: `match={"a^2": "a^2"}`: parts of `a` (by key) to the parts of `b` they become.
MorphMatch = Mapping[str, str]


def _parts(s: "Scene", node: "Node", t: float) -> list[Part]:
    return [(p["key"], (p["center"][0], p["center"][1])) for p in json.loads(s._b.morph_parts(node._id, t))]


def _explicit(match: MorphMatch, a: list[Part], b: list[Part]) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for ka, kb in match.items():
        ia = [i for i, (k, _) in enumerate(a) if k == str(ka)]
        ib = [j for j, (k, _) in enumerate(b) if k == str(kb)]
        pairs += list(zip(ia, ib))
    return pairs


def _math_pairs(s: "Scene", a: "Node", b: "Node", t: float, match: MorphMatch | None = None) -> list[tuple[int, int]]:
    """Structural pairs between two formulas, as flat part indices: explicit `match=`
    entries (TeX subexpressions or `\\id` names), then same `\\id` names, then identical
    TeX subtrees, largest first."""
    from ..objects.math import Math

    if not (isinstance(a, Math) and isinstance(b, Math)):
        return []
    flat_a = {p["index"]: i for i, p in enumerate(json.loads(s._b.morph_parts(a._id, t)))}
    flat_b = {p["index"]: i for i, p in enumerate(json.loads(s._b.morph_parts(b._id, t)))}
    ia, ib = a._info(), b._info()
    used_a: set[int] = set()
    used_b: set[int] = set()
    pairs: list[tuple[int, int]] = []

    def take(ga: list[int], gb: list[int]) -> None:
        if any(g in used_a for g in ga) or any(g in used_b for g in gb):
            return
        for x, y in zip(ga, gb):
            if x in flat_a and y in flat_b:
                pairs.append((flat_a[x], flat_b[y]))
        used_a.update(ga)
        used_b.update(gb)

    for key_a, key_b in (match or {}).items():
        found_a = s._b.math_find(a.tex.now, str(key_a), a.size.now, a.display.now)  # type: ignore[attr-defined]
        found_b = s._b.math_find(b.tex.now, str(key_b), b.size.now, b.display.now)  # type: ignore[attr-defined]
        for ga, gb in zip(found_a, found_b):
            take(list(ga), list(gb))
    names_b = {p["name"]: n for n, p in enumerate(ib["parts"]) if p["name"]}
    for n, part in enumerate(ia["parts"]):
        if part["name"] and part["name"] in names_b:
            take(ia["subtrees"][n], ib["subtrees"][names_b[part["name"]]])
    order = sorted(range(1, len(ib["parts"])), key=lambda n: -len(ib["subtrees"][n]))
    for nb in order:
        tex = ib["parts"][nb]["tex"]
        for na, part in enumerate(ia["parts"][1:], 1):
            if part["tex"] == tex and len(ia["subtrees"][na]) == len(ib["subtrees"][nb]):
                take(ia["subtrees"][na], ib["subtrees"][nb])
    return pairs


def pair_parts(a: list[Part], b: list[Part], match: MorphMatch | None = None, structural: list[tuple[int, int]] | None = None) -> list[tuple[int, int]]:
    pairs = _explicit(match, a, b) if match else []
    taken_a = {i for i, _ in pairs}
    taken_b = {j for _, j in pairs}
    pairs += [(i, j) for i, j in structural or [] if i not in taken_a and j not in taken_b]
    used_a = {i for i, _ in pairs}
    used_b = {j for _, j in pairs}
    keys_a = [k if i not in used_a else None for i, (k, _) in enumerate(a)]
    keys_b = [k if j not in used_b else None for j, (k, _) in enumerate(b)]
    # Equal keys in the same order (unchanged runs of text slide into place).
    matcher = difflib.SequenceMatcher(a=keys_a, b=keys_b, autojunk=False)
    for block in matcher.get_matching_blocks():
        for d in range(block.size):
            i, j = block.a + d, block.b + d
            if keys_a[i] is not None:
                pairs.append((i, j))
                used_a.add(i)
                used_b.add(j)
    # Equal keys elsewhere: nearest position wins (repeated terms that moved).
    for i, (key, ca) in enumerate(a):
        if i in used_a or key is None:
            continue
        candidates = [j for j, (kb, _) in enumerate(b) if j not in used_b and kb == key]
        if candidates:
            j = min(candidates, key=lambda j: math.dist(ca, b[j][1]))
            pairs.append((i, j))
            used_a.add(i)
            used_b.add(j)
    # Keyless shapes pair by order.
    free_a = [i for i, (k, _) in enumerate(a) if i not in used_a and k is None]
    free_b = [j for j, (k, _) in enumerate(b) if j not in used_b and k is None]
    pairs += list(zip(free_a, free_b))
    return sorted(pairs)


class Morph(Animation):
    def __init__(self, a: "Node", b: "Node", match: MorphMatch | None, duration: float | None, ease: EaseLike | None, delay: float, span: Span) -> None:
        super().__init__(duration, ease, delay, span)
        self.a, self.b = _nodes([a, b], "morph")
        if self.a is self.b:
            raise KinemoError.make("K0105", "k.morph needs two different objects", spans=[span])
        self.match = match

    def describe(self) -> str:
        return f"morph({self.a._label()}, {self.b._label()})"

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        from ..objects.morphing import MorphNode

        s._check_alive(self.a, start, self.span)
        pa, pb = _parts(s, self.a, start), _parts(s, self.b, start)
        structural = _math_pairs(s, self.a, self.b, start, self.match)
        pairs = pair_parts(pa, pb, None if structural else self.match, structural)
        if not pairs:
            s.lints.warn(
                "W0801",
                f"morph found no matches between {self.a._label()} and {self.b._label()}: falling back to a crossfade",
                spans=[self.span],
                fixes=[("specify the matches", "k.morph(a, b, match={...})")],
            )
        cursor = s.cursor
        s.cursor = start
        try:
            node = MorphNode(self.a, self.b, pairs)
        finally:
            s.cursor = cursor
        s._exit(self.a, start)
        s._enter(node, start)
        _ramp(s, node, "progress", start, duration, ease, 0.0, 1.0, self.span)
        s._exit(node, start + duration)
        s._enter(self.b, start + duration)


def morph(a: "Node", b: "Node", *, match: MorphMatch | None = None, duration: float | None = None, ease: EaseLike | None = None, delay: float = 0.0) -> Animation:
    """Exchange: `a` leaves, `b` enters, corresponding parts travel between them."""
    return Morph(a, b, match, duration, ease, delay, user_span())
