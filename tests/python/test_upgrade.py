"""Codemods rewrite deprecated forms exactly and idempotently."""

from kinemo.upgrade import upgrade_source


def test_line_width_becomes_length() -> None:
    new, applied = upgrade_source('floor = k.Line(width=10).place(at="bottom")\n')
    assert new == 'floor = k.Line(length=10).place(at="bottom")\n'
    assert applied == ["line-length"]


def test_param_text_becomes_str() -> None:
    src = '@k.scene(params={"t": k.Text("a")})\ndef s(s): pass\n'
    new, applied = upgrade_source(src)
    assert 'k.Str("a")' in new and applied == ["param-str"]


def test_idempotent_and_untouched_elsewhere() -> None:
    src = 'x = k.Text("width")\ny = k.Line(length=2)\n'
    assert upgrade_source(src) == (src, [])
    once, _ = upgrade_source("k.Line(width=1)\n")
    assert upgrade_source(once) == (once, [])
