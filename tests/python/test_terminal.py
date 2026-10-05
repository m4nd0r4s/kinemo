"""`k.Terminal`: typed commands as `k.Code` after a prompt, output rows, scrolling when full,
`clear()`, and the rows as addressable parts."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build, diagnostic_of


def test_type_and_output_add_rows_in_order() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        term = k.Terminal(rows=6)
        s.add(term)
        s.play(term.type("ls"))
        s.play(term.output("a.txt\nb.txt"))
        seen["kinds"] = [type(row).__name__ for row in term.lines]
        seen["code"] = term.lines[0].code.code.now  # type: ignore[attr-defined]
        seen["lang"] = term.lines[0].code.lang.now  # type: ignore[attr-defined]
        seen["ys"] = [row.y.now for row in term.lines]

    assert seen["kinds"] == ["Group", "Text", "Text"]
    assert seen["code"] == "ls" and seen["lang"] == "bash"
    ys = seen["ys"]
    assert isinstance(ys, list) and ys == sorted(ys, reverse=True)


def test_typing_lasts_the_command_at_the_typing_speed() -> None:
    @build
    def scene(s: k.Scene) -> None:
        term = k.Terminal()
        s.add(term)
        s.play(term.type("x" * 44, cps=22))

    assert scene.duration == pytest.approx(2.0 + scene.config.tail)


def test_a_full_terminal_scrolls_the_oldest_rows_away() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        term = k.Terminal(rows=3)
        s.add(term)
        s.play(term.output("one\ntwo\nthree\nfour\nfive"))
        seen["texts"] = [row.text.now for row in term.lines]  # type: ignore[attr-defined]
        seen["labels"] = [row._label() for row in term.lines]

    assert seen["texts"] == ["three", "four", "five"]
    assert seen["labels"] == ["term.lines[0]", "term.lines[1]", "term.lines[2]"]


def test_staggered_output_longer_than_the_window_scrolls_line_by_line() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        term = k.Terminal(rows=2)
        s.add(term)
        s.play(term.output("1\n2\n3\n4", stagger=0.2))
        seen["texts"] = [row.text.now for row in term.lines]  # type: ignore[attr-defined]

    assert seen["texts"] == ["3", "4"]


def test_clear_empties_the_terminal() -> None:
    seen: dict[str, int] = {}

    @build
    def scene(s: k.Scene) -> None:
        term = k.Terminal()
        s.add(term)
        s.play(term.output("old"))
        s.play(term.clear())
        seen["after_clear"] = len(term.lines)
        s.play(term.type("new"))
        seen["after_type"] = len(term.lines)

    assert seen == {"after_clear": 0, "after_type": 1}


def test_rows_must_be_positive() -> None:
    def body(s: k.Scene) -> None:
        s.add(k.Terminal(rows=0))

    assert "at least one row" in diagnostic_of(body, "K0105").message


def test_a_terminal_scene_passes_strict_check() -> None:
    @build
    def scene(s: k.Scene) -> None:
        term = k.Terminal(title="python", prompt=">>>", lang="python", rows=4).place(at="center")
        s.play(k.fade_in(term))
        s.play(term.type("sum(range(10))"))
        s.play(term.output("45"))

    assert not [d for d in scene.lints.items if d.level in ("error", "warning")]
