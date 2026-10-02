"""`k.Code`: line highlight."""

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
