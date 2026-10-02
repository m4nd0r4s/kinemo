"""Code and morphs between versions: `k.Code`, `code.highlight`, `k.morph`."""

from __future__ import annotations

from ..entry import DocEntry

ENTRIES = (
    DocEntry(
        "k.Math",
        "Text",
        "Formula in LaTeX syntax, typeset by the built-in engine (no TeX installation needed). "
        "`\\id{name}{...}` names a subexpression (`eq[\"name\"]`); any subexpression is "
        "found through the syntax tree (`eq[\"c^2\"]` ≡ `eq[\"c^{2}\"]`). `k.morph` between "
        "equations matches names first, then identical TeX subtrees. Unsupported command: K0801.",
        '''
import kinemo as k

@k.scene
def formula(s: k.Scene):
    eq = k.Math(r"\\id{lhs}{a^2 + b^2} = c^2").place(at="center")
    s.play(k.write(eq))
    s.play(eq["lhs"].to(color=k.YELLOW))
    s.play(eq["c^2"].to(color=k.GREEN))
''',
        related=("k.morph", "k.Text", "k.write"),
    ),
    DocEntry(
        "k.Code",
        "Text",
        "Code with syntax highlighting (tree-sitter) and stable tokens: `lang=`, "
        "`line_numbers=True`, `size=`, `theme=\"auto\"` (follows the scene background). `code.highlight` "
        "highlights lines and `k.morph` between two versions animates the diff: unchanged lines slide, "
        "inserted lines enter, removed lines leave.",
        '''
import kinemo as k

SRC = """
def add(a, b):
    return a + b
"""

@k.scene
def code_block(s: k.Scene):
    code = k.Code(SRC, lang="python", line_numbers=True).place(at="center")
    s.play(k.write(code))
    s.wait(0.5)
''',
        related=("Code.highlight", "k.morph", "k.Text"),
    ),
    DocEntry(
        "Code.highlight",
        "Text",
        "Named transition: dims every line except `lines` (numbered from 1); "
        "`code.highlight(None)` removes the highlight. Equivalent to "
        "`code.to(highlight=lines, highlight_amount=1)`.",
        '''
import kinemo as k

SRC = """
x = 1
y = 2
print(x + y)
"""

@k.scene
def code_highlight(s: k.Scene):
    code = k.Code(SRC, lang="python").place(at="center")
    s.add(code)
    s.play(code.highlight(lines=[3]))
    s.play(code.highlight(None))
''',
        related=("k.Code",),
    ),
    DocEntry(
        "k.morph",
        "Verbs",
        "Swap: `a` leaves, `b` enters and the matching parts travel between them (identical "
        "characters and tokens slide; the rest fades out and in). `match={part_a: part_b}` "
        "forces matches. With nothing in common, it does a warp + crossfade and emits W0801.",
        '''
import kinemo as k

@k.scene
def swap(s: k.Scene):
    a = k.Text("a + b = c", size=0.8).place(at="center")
    b = k.Text("c = a + b", size=0.8).place(at="center")
    s.play(k.write(a))
    s.play(k.morph(a, b))
    s.wait(0.5)
''',
        related=("k.Code", "k.write", "k.fade_out"),
    ),
)
