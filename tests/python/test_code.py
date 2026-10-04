"""`k.Code`: line highlight and the language check."""

from __future__ import annotations

import kinemo as k
from conftest import build, diagnostic_of

SOURCE = """
def area(r):
    return 3.14 * r * r
"""


def test_highlight_of_an_existing_line_builds() -> None:
    @build
    def scene(s: k.Scene) -> None:
        code = k.Code(SOURCE)
        s.add(code)
        s.play(code.highlight(lines=[1, 2]))

    assert scene.duration > 1


def test_highlight_of_a_missing_line_is_k0105() -> None:
    def body(s: k.Scene) -> None:
        code = k.Code(SOURCE)  # the surrounding newlines are dropped: two lines
        s.add(code)
        s.play(code.highlight(lines=[3]))

    d = diagnostic_of(body, "K0105")
    assert "line 3 does not exist" in d.message and "2 line(s)" in d.message


def test_an_unknown_language_is_k0802_with_the_supported_ones() -> None:
    def body(s: k.Scene) -> None:
        s.add(k.Code("public class A {}", lang="java"))

    d = diagnostic_of(body, "K0802")
    assert "'java'" in d.message and "python" in d.message and "cpp" in d.message
    assert any(fix.code == 'lang="text"' for fix in d.fixes)


def test_a_misspelled_language_suggests_the_closest() -> None:
    def body(s: k.Scene) -> None:
        s.add(k.Code("x = 1", lang="pyhton"))

    d = diagnostic_of(body, "K0802")
    assert d.fixes[0].code == 'lang="python"'


def test_aliases_and_case_are_accepted() -> None:
    @build
    def scene(s: k.Scene) -> None:
        s.add(k.Code("x = 1", lang="Py"), k.Code("int x;", lang="c++"), k.Code("anything", lang="text"))

    assert scene.duration >= 0


def test_a_language_set_later_that_is_unknown_shows_plain_text() -> None:
    widths: list[float] = []

    @build
    def scene(s: k.Scene) -> None:
        code = k.Code("x = 1", lang="python")
        s.add(code)
        code.set(lang="cobol")
        widths.append(code.width.now)

    assert widths[0] > 0
