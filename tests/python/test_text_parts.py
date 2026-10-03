"""Parts of a text (`txt["world"]`, `txt.words[1]`, `txt.lines[0]`): every glyph is drawn
exactly once, whatever parts were addressed; a part inside another nests in it (style,
opacity and transforms compose); a text change gives the text its glyphs back."""

from __future__ import annotations

from collections import Counter
from typing import Any

import kinemo as k
from conftest import build, inspect, plain

NODES: dict[str, k.Node] = {}


def keep(**nodes: k.Node) -> None:
    NODES.clear()
    NODES.update(nodes)


def drawn(scene: Any, t: float) -> Counter[int]:
    """How many times each glyph index is drawn at `t` (by the present glyph leaves)."""
    count: Counter[int] = Counter()
    for entry in inspect(scene, t):
        if entry["present"] and "drawn_glyphs" in entry:
            count.update(entry["drawn_glyphs"])
    return count


def entry_of(scene: Any, t: float, name: str) -> dict[str, Any]:
    return next(o for o in inspect(scene, t) if o["id"] == NODES[name]._id)


def fill_of(scene: Any, t: float, name: str) -> list[float]:
    return plain(entry_of(scene, t, name)["props"]["fill"])


def assert_each_glyph_once(scene: Any, t: float, glyphs: int) -> None:
    count = drawn(scene, t)
    assert sorted(count) == list(range(glyphs)), count
    assert set(count.values()) == {1}, count


def test_overlapping_parts_draw_each_glyph_once() -> None:
    @build
    def scene(s: k.Scene) -> None:
        txt = k.Text("Energy is never created", size=0.5)
        s.add(txt)
        s.play(txt["never"].to(color=k.YELLOW))
        s.play(txt.words[0].to(color=k.TEAL))
        s.play(txt.chars[0:6].to(scale=1.2))
        s.play(txt.lines[0].to(opacity=0.5))
        s.play(txt.chars[2:12].to(color=k.RED))

    for t in (0.5, 1.5, 2.5, 3.5, 4.5, 5.0):
        assert_each_glyph_once(scene, t, len("Energyisnevercreated"))


def test_a_part_inside_another_starts_with_its_style() -> None:
    @build
    def scene(s: k.Scene) -> None:
        txt = k.Text("Energy is never created", size=0.5)
        s.add(txt)
        word = txt.words[0]
        s.play(word.to(color=k.TEAL))
        start = txt.chars[0:2]
        keep(txt=txt, word=word, start=start)
        s.play(start.to(scale=1.3))

    assert entry_of(scene, 1.5, "start")["parent"] == NODES["word"]._id
    assert fill_of(scene, 1.5, "start") == fill_of(scene, 1.5, "word")
    assert fill_of(scene, 1.5, "start") != fill_of(scene, 1.5, "txt")


def test_a_part_around_others_takes_them_in() -> None:
    @build
    def scene(s: k.Scene) -> None:
        txt = k.Text("Energy is never created, only converted", size=0.5, width=8)
        s.add(txt)
        never = txt["never"]
        s.play(never.to(color=k.YELLOW))
        on = txt.find_all("on")[0]
        s.play(k.indicate(on))
        line = txt.lines[0]
        keep(txt=txt, never=never, on=on, line=line)
        s.play(line.to(color=k.RED, opacity=0.5))

    after = 3.5
    assert entry_of(scene, after, "never")["parent"] == NODES["line"]._id
    assert entry_of(scene, after, "on")["parent"] == NODES["line"]._id
    # A part that set its own color keeps it; one that only followed its owner follows the line.
    assert fill_of(scene, after, "never") != fill_of(scene, after, "line")
    assert fill_of(scene, after, "on") == fill_of(scene, after, "line")
    assert_each_glyph_once(scene, after, len("Energyisnevercreated,onlyconverted"))


def test_partly_overlapping_parts_give_shared_glyphs_to_the_later_one() -> None:
    @build
    def scene(s: k.Scene) -> None:
        txt = k.Text("abcdef")
        s.add(txt)
        first = txt.chars[0:4]
        s.play(first.to(color=k.RED))
        second = txt.chars[2:6]
        keep(first=first, second=second)
        s.play(second.to(color=k.BLUE))

    assert_each_glyph_once(scene, 2.0, 6)
    leaves = {o["parent"]: o["drawn_glyphs"] for o in inspect(scene, 2.0) if o["present"] and "drawn_glyphs" in o}
    assert leaves[NODES["first"]._id] == [0, 1]
    assert leaves[NODES["second"]._id] == [2, 3, 4, 5]


def test_a_text_change_gives_the_text_its_glyphs_back() -> None:
    @build
    def scene(s: k.Scene) -> None:
        txt = k.Text("Hello world, hello kinemo", size=0.6)
        keep(txt=txt)
        s.play(k.write(txt))
        s.play(txt["world"].to(color=k.YELLOW))
        s.play(*[p.to(color=k.TEAL) for p in txt.find_all("o")])
        s.play(txt.to(text="Goodbye world"))
        s.play(txt["bye"].to(color=k.RED))

    # At 4.0 the change is over and `txt["bye"]` (glyphs 4-6) is a new part of the new string.
    end = 4.0
    rest = next(o for o in inspect(scene, end) if o["parent"] == NODES["txt"]._id and plain(o["props"].get("rest", False)))
    assert rest["drawn_glyphs"] == [i for i in range(len("Goodbyeworld")) if i not in (4, 5, 6)]
    assert_each_glyph_once(scene, end, len("Goodbyeworld"))
    assert_each_glyph_once(scene, 5.0, len("Goodbyeworld"))


def test_math_and_code_parts_nest_too() -> None:
    @build
    def scene(s: k.Scene) -> None:
        eq = k.Math(r"\id{lhs}{a^2 + b^2} = c^2", size=0.9)
        code = k.Code("total = price * count", lang="python")
        s.add(eq, k.Column(code))
        s.play(eq["lhs"].to(color=k.YELLOW))
        for term in eq.find_all("2"):
            s.play(k.indicate(term), duration=0.4)
        s.play(code.lines[0].to(color=k.RED))
        s.play(code["price"].to(scale=1.2))
        keep(eq=eq, lhs=eq["lhs"], first_two=eq.find_all("2")[0], price=code["price"], line=code.lines[0])

    end = 4.5
    assert entry_of(scene, end, "first_two")["parent"] == NODES["lhs"]._id
    assert fill_of(scene, end, "first_two") == fill_of(scene, end, "lhs")
    price = entry_of(scene, end, "price")
    assert price["parent"] == NODES["line"]._id
    assert plain(price["props"]["recolor"]) == 1.0
