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
        "k.underline",
        "Text",
        "Annotation marks on any object or part of a text or formula (`eq[\"dx\"]`): "
        "`k.underline(target)`, `k.box(target)`, `k.encircle(target)`, `k.strike(target)` (crossed "
        "out) and `k.cross(target)` (an X). Each is an ordinary object bound to the target's box in "
        "world coordinates, so it follows the target; it enters with `k.draw` and leaves with "
        "`k.fade_out`. `pad=` (or `overhang=` for `strike`), `color=` and `stroke_width=`.",
        '''
import kinemo as k

@k.scene
def marks(s: k.Scene):
    eq = k.Math(r"a^2 + b^2 = c^2", size=0.8).place(at="center")
    s.add(eq)
    s.play(k.draw(k.box(eq["c^2"])))
    s.play(k.draw(k.underline(eq["a^2"])), k.draw(k.encircle(eq["b^2"])))
    wrong = k.Text("a + b = c", size=0.5).place(below=eq, gap=1)
    s.play(k.write(wrong))
    s.play(k.draw(k.cross(wrong)))
    s.wait(0.5)
''',
        related=("k.Math", "k.draw", "k.fade_out"),
    ),
    DocEntry(
        "k.Terminal",
        "Text",
        "A terminal or REPL window: `title=`, `prompt=` (`\"$ \"`, `\">>>\"`), `lang=` of the commands "
        "(`\"bash\"`, `\"python\"`...), `width=` and `rows=` on screen, `size=`, `theme=\"auto\"`. "
        "`term.type(cmd)` types a command after the prompt as `k.Code`, `term.output(text)` prints "
        "monospace lines; the window grows row by row and scrolls up when full. `term.lines` are the "
        "rows on screen (an input row has `.prompt` and `.code`), `term.frame`, `term.title` and "
        "`term.caret` are the window's parts.",
        '''
import kinemo as k

@k.scene
def terminal(s: k.Scene):
    term = k.Terminal(title="zsh", width=9, rows=5).place(at="center")
    s.play(k.fade_in(term), duration=0.4)
    s.play(term.type("pip install kinemo"))
    s.play(term.output("Successfully installed kinemo"))
    s.play(term.type("kinemo check scene.py"))
    s.play(term.output("scene.py — scene 'hello' — ok"))
    s.wait(0.5)
''',
        related=("Terminal.type", "Terminal.output", "k.Code"),
    ),
    DocEntry(
        "Terminal.type",
        "Text",
        "Named transition: types a command after the prompt, character by character, as `k.Code` in "
        "the terminal's language, with the caret following; `cps=` characters per second (22 by "
        "default) or `duration=`.",
        '''
import kinemo as k

@k.scene
def repl(s: k.Scene):
    term = k.Terminal(title="python", prompt=">>>", lang="python", rows=4).place(at="center")
    s.add(term)
    s.play(term.type("sum(range(10))", cps=12))
    s.play(term.output("45"))
    s.wait(0.5)
''',
        related=("k.Terminal", "Terminal.output"),
    ),
    DocEntry(
        "Terminal.output",
        "Text",
        "Named transition: prints `text` below the last row, one row per line, all at once or "
        "`stagger=` seconds apart; lines that do not fit scroll the older ones up. "
        "`term.clear()` fades every row out and starts again at the top.",
        '''
import kinemo as k

@k.scene
def build_log(s: k.Scene):
    term = k.Terminal(title="cargo", rows=4).place(at="center")
    s.add(term)
    s.play(term.type("cargo build"))
    s.play(term.output("Compiling kinemo\\nCompiling kinemo-py\\nFinished release", stagger=0.4))
    s.play(term.clear())
    s.wait(0.5)
''',
        related=("k.Terminal", "Terminal.type"),
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
