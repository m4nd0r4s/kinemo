"""Every raised KinemoError carries a diagnostic: code, spans in user code, fixes, rendering."""

from __future__ import annotations

import json
import math
from typing import Callable

import pytest

import kinemo as k
from conftest import build, diagnostic_of, line_of
from kinemo.diagnostics import CATALOG, explain


def k0101(s: k.Scene) -> None:
    c = k.Circle()
    s.play(c.to(x=1))  # diag-K0101


def k0102(s: k.Scene) -> None:
    c = k.Circle()
    s.add(c)
    s.remove(c)
    s.play(c.to(x=1))  # diag-K0102


def k0103(s: k.Scene) -> None:
    c = k.Circle()
    k.Group(c)
    k.Group(c)  # diag-K0103


def k0201(s: k.Scene) -> None:
    c = k.Circle()
    s.add(c)
    s.start(c.to(x=1))
    s.play(c.to(x=2))  # diag-K0201


def k0203(s: k.Scene) -> None:
    s.play()  # diag-K0203


def k0204(s: k.Scene) -> None:
    c = k.Circle()
    with s.during(k.fade_in(c)):  # diag-K0204
        pass


def k0205(s: k.Scene) -> None:
    xs = k.signal([1.0, 2.0])
    s.play(xs.to([3.0, 4.0]))  # diag-K0205


def k0301(s: k.Scene) -> None:
    x = k.signal(1.0)
    x()  # diag-K0301


def k0302(s: k.Scene) -> None:
    x = k.signal(1.0)
    k.Text(lambda: str(x.now))  # diag-K0302


def k0303(s: k.Scene) -> None:
    x = k.signal(1.0)
    s.play((x * 2).to(4))  # diag-K0303


def k0304(s: k.Scene) -> None:
    x = k.signal(1.0)
    if x > 0:  # diag-K0304
        pass


def k0305(s: k.Scene) -> None:
    math.sin(k.signal(1.0))  # diag-K0305


def k0310(s: k.Scene) -> None:
    k.signal(1.0).map(lambda h: math.sin(h))  # diag-K0310


def k0401(s: k.Scene) -> None:
    a = k.Square()
    b = k.Circle().place(above=a)
    s.add(a, b)
    s.play(b.to(y=3))  # diag-K0401


def k0403(s: k.Scene) -> None:
    a = k.Square()
    k.Circle().place(above=a, below=a)  # diag-K0403


def k0404(s: k.Scene) -> None:
    k.Circle().place(at="nowhere")  # diag-K0404


def k0106(s: k.Scene) -> None:
    k.Circle(radius=2)  # diag-K0106


def k1101(s: k.Scene) -> None:
    k.Write  # diag-K1101


def k1102(s: k.Scene) -> None:
    k.Circle().animate  # diag-K1102


CASES: dict[str, Callable[[k.Scene], None]] = {
    "K0101": k0101,
    "K0102": k0102,
    "K0103": k0103,
    "K0201": k0201,
    "K0203": k0203,
    "K0204": k0204,
    "K0205": k0205,
    "K0301": k0301,
    "K0302": k0302,
    "K0303": k0303,
    "K0304": k0304,
    "K0305": k0305,
    "K0310": k0310,
    "K0401": k0401,
    "K0403": k0403,
    "K0404": k0404,
    "K0106": k0106,
    "K1101": k1101,
    "K1102": k1102,
}


@pytest.mark.parametrize("code", sorted(CASES))
def test_error_has_code_span_and_fix(code: str) -> None:
    d = diagnostic_of(CASES[code], code)
    assert d.level == "error"
    assert d.spans, "a diagnostic always points somewhere"
    assert d.spans[0].file == __file__
    assert d.spans[0].line == line_of(f"# diag-{code}")
    assert d.fixes, f"{code} must suggest at least one fix"
    assert all(f.description for f in d.fixes)


@pytest.mark.parametrize("code", sorted(CASES))
def test_render_shows_code_source_and_explain(code: str) -> None:
    d = diagnostic_of(CASES[code], code)
    text = d.render()
    assert text.startswith(f"{code} error: ")
    assert f"kinemo explain {code}" in text
    assert f"test_diagnostics.py:{d.spans[0].line}" in text
    assert f"# diag-{code}" in text  # the offending source line is quoted
    assert "fix" in text


@pytest.mark.parametrize("code", sorted(CASES))
def test_json_has_the_documented_fields(code: str) -> None:
    payload = diagnostic_of(CASES[code], code).json()
    json.dumps(payload)
    assert set(payload) == {"code", "level", "message", "spans", "time", "objects", "fixes"}
    assert payload["spans"][0]["file"] == __file__
    assert {"description", "code", "edits"} <= set(payload["fixes"][0])


@pytest.mark.parametrize("code", sorted(CASES))
def test_every_raised_code_is_in_the_catalog(code: str) -> None:
    assert code in CATALOG
    text = explain(code)
    assert text.startswith(code)
    assert CATALOG[code].explanation in text


def test_exception_message_is_the_rendered_diagnostic() -> None:
    with pytest.raises(k.KinemoError) as info:
        build(k0101)
    assert str(info.value) == info.value.diagnostic.render()


def test_rendered_k0401_shows_time_and_both_spans() -> None:
    text = diagnostic_of(k0401, "K0401").render()
    assert "t = 0.00 s" in text
    assert "← constraint here" in text
    assert "fix 1:" in text and "fix 2:" in text


def test_explain_unknown_code() -> None:
    assert "unknown code" in explain("K9999")


def test_lints_do_not_interrupt_the_build_and_carry_a_span() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.play(c.to(x=1), at=1)  # lint-W0110

    scene = build(body)
    (lint,) = scene.lints.items
    assert lint.code == "W0110"
    assert lint.level == "warning"
    assert lint.spans[0].line == line_of("# lint-W0110")
    assert lint.render().startswith("W0110 warning: ")


def test_inline_allow_silences_a_lint() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.play(c.to(x=1), at=1)  # kinemo: allow W0110

    assert build(body).lints.items == []
