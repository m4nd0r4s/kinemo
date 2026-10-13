"""`$...$` inside `k.Text`: formulas typeset inline, on the text's baseline, addressable by
their TeX; dollar signs that are not math (`$5 and $10`) stay text."""

from __future__ import annotations

import pytest

import kinemo as k
from kinemo.diagnostics import KinemoError
from conftest import build


def glyph_count(text: k.Text) -> int:
    _, glyphs = text._glyphs()  # pyright: ignore[reportPrivateUsage]
    return len(glyphs)


def test_math_spans_are_typeset_and_addressable_by_tex() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        line = k.Text("The slope is $f'(x) = 2x$, at $x = 3$.")
        literal = k.Text(r"The slope is \$f'(x) = 2x\$, at \$x = 3\$.")
        s.add(line, literal)
        part = line["f'(x) = 2x"]
        seen["part"] = len(part.indices.now)
        seen["glyphs"] = (glyph_count(line), glyph_count(literal))
        seen["text"] = line._char_text()  # pyright: ignore[reportPrivateUsage]
        s.wait(0.1)

    assert seen["part"] >= 7
    inline, literal = seen["glyphs"]  # type: ignore[misc]
    assert inline != literal
    assert seen["text"] == "The slope is f'(x) = 2x, at x = 3."


def test_prices_stay_text() -> None:
    seen: dict[str, str] = {}

    @build
    def scene(s: k.Scene) -> None:
        price = k.Text("costs $5 and $10 today")
        s.add(price)
        seen["text"] = price._char_text()  # pyright: ignore[reportPrivateUsage]
        s.wait(0.1)

    assert seen["text"] == "costs $5 and $10 today"


def test_inline_math_sits_on_the_line_and_widens_it() -> None:
    seen: dict[str, float] = {}

    @build
    def scene(s: k.Scene) -> None:
        plain = k.Text("area pi r2 here")
        math = k.Text(r"area $\frac{\pi r^2}{2}$ here")
        s.add(plain, math)
        seen["plain_h"], seen["math_h"] = float(plain.height.now), float(math.height.now)
        s.wait(0.1)

    # One line each: the formula is part of the line, not a block below it.
    assert seen["math_h"] == pytest.approx(seen["plain_h"])


def test_unsupported_latex_in_a_span_is_k0801() -> None:
    def scene(s: k.Scene) -> None:
        s.add(k.Text(r"bad $\begin{tabular}{c} x \end{tabular}$ here"))

    with pytest.raises(KinemoError) as info:
        build(scene)
    assert info.value.diagnostic.code == "K0801"
    assert "escape the dollar signs" in info.value.diagnostic.fixes[0].description


def test_changing_the_text_checks_the_new_math() -> None:
    def scene(s: k.Scene) -> None:
        line = k.Text("$x$")
        s.add(line)
        s.play(line.to(text=r"$\begin{tabular}{c}x\end{tabular}$"))

    with pytest.raises(KinemoError):
        build(scene)
