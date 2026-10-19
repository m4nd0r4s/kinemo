"""What a lesson ships besides its IR: the formula layouts and code tokens its frames use,
computed natively because the WASM player has neither typst nor tree-sitter."""

from __future__ import annotations

import json

import kinemo as k
from conftest import build


def test_baked_layouts_cover_every_formula_and_code_block_on_screen() -> None:
    @build
    def scene(s: k.Scene) -> None:
        formula = k.Math(r"\frac{a}{b}")
        code = k.Code("x = 1\n", lang="python", y=-2)
        s.add(formula, code)
        s.wait(0.5)
        s.play(k.morph(formula, k.Math(r"a b^{-1}")))
        s.add(k.Text("The slope is $2x$."))

    baked = json.loads(scene.builder.baked_layouts(30.0))
    texs = {entry["tex"] for entry in baked["math"]}
    assert {r"\frac{a}{b}", r"a b^{-1}", "2x"} <= texs
    first = next(e for e in baked["math"] if e["tex"] == r"\frac{a}{b}")
    assert first["glyphs"] and first["rules"] and first["parts"][0]["parent"] is None
    assert [(e["source"], e["language"]) for e in baked["code"]] == [("x = 1", "python")]
    assert [t[:2] for t in baked["code"][0]["tokens"]] == [["x", "variable"], ["=", "operator"], ["1", "number"]]
