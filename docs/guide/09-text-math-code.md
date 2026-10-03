# Text, math and code

kinemo has three kinds of text: `k.Text` for prose and labels, `k.Math` for formulas in
LaTeX syntax, and `k.Code` for syntax-highlighted source. They share one model:

- each one is a group of glyphs that enters with `k.write` (character by character);
- **any part is addressable** (a word, a subexpression, a token) and the part is an object
  with its own props, so `s.play(eq["c^2"].to(color=k.GREEN))` works;
- `k.morph(a, b)` between two versions moves matching glyphs to their new places, and the
  rest fades out and in.

Everything is typeset by the built-in engine, with bundled fonts and no TeX installation,
so the output is identical on every machine.

## `k.Text`

```python
k.Text(text="", *, size=None, width=None, align="left", **props)
```

- **Markup is minimal**: `**bold**`, `*italic*` and `` `code` `` (monospace). There is
  nothing beyond that. In particular, `$...$` is kept literally: put formulas in `k.Math`
  (see [Mixing text and formulas](#mixing-text-and-formulas)).
- **`size=`** is the font size in units (the default comes from the theme).
- **`width=`** wraps lines at that width. Without it the text is a single line. `align=`
  (`"left"`, `"center"`, `"right"`) aligns the wrapped lines.
- **Style**: `fill=`/`color=` (the glyph color), `opacity=`, and the transform props.

### Parts

| Lookup | Returns |
| --- | --- |
| `txt["never"]` | The first occurrence of `"never"` in the text without markup |
| `txt.find_all("on")` | Every occurrence, as a list of parts |
| `txt.chars[0:6]` | Characters 0 to 5 |
| `txt.words[1]` | The second word |
| `txt.lines[0]` | The first line (after wrapping) |

Each part animates like any object: color, scale, opacity, `k.indicate`.

Parts can overlap, and every glyph is still drawn once:

- A part inside another one (`txt.chars[0:6]` inside `txt.words[0]`) nests in it. It starts
  with that part's color, and follows its opacity, scale and position.
- A part around others (`txt.lines[0]` around `txt["never"]`) takes them in. Its opacity
  and transforms apply to them. A part that set its own color keeps it; the others take
  the new part's color.
- Two parts that share only some glyphs stay side by side, and the later one draws the
  shared glyphs.

After `txt.to(text=...)`, the old parts select nothing: look up parts again in the new
string.

```python
import kinemo as k


@k.scene
def parts(s: k.Scene):
    txt = k.Text("Energy is **never** created, only *converted*", size=0.5, width=8).place(at="center")
    s.play(k.write(txt))
    s.play(txt["never"].to(color=k.YELLOW))
    s.play(txt.words[0].to(color=k.TEAL))
    for part in txt.find_all("on"):
        s.play(k.indicate(part), duration=0.4)
    s.play(txt.chars[0:6].to(scale=1.1))
    s.play(txt.lines[0].to(opacity=0.5))
    s.wait(0.5)
```

### Reactive text

Pass a lambda and the text follows its signals. The lambda is traced to native code: read
signals with `x()` and use format specs. Digits use tabular widths, so a counter does not
jitter, and the layout is recomputed only when the string actually changes.

```python
import kinemo as k


@k.scene
def meter(s: k.Scene):
    kwh = k.signal(0.0)
    title = k.Text("**Solar** energy", size=0.7).place(at="top", margin=0.8)
    value = k.Text(lambda: f"{kwh():.1f} kWh", size=0.9).place(at="center")
    s.play(k.write(title), k.fade_in(value))
    s.play(kwh.to(12.5), duration=2)
    s.wait(0.5)
```

### Changing the string: `txt.to(text=...)`

`txt.to(text="...")` morphs the glyphs to a new string: equal characters travel to their
new places and the rest fade. You can change other props in the **same** call:

```python
import kinemo as k


@k.scene
def steps(s: k.Scene):
    label = k.Text("Step 1: measure", size=0.6).place(at="center")
    s.play(k.write(label))
    s.play(label.to(text="Step 2: compare"))
    s.play(label.to(text="Step 3: decide", color=k.GREEN))
    s.wait(0.5)
```

During the morph, the text is temporarily replaced by the morph itself. Do not run a second
`label.to(...)` in parallel (`s.play(label.to(text=...), label.to(color=...))` is `K0102`,
"already left the scene"). Put both changes in one `.to()`, as above.

### Mixing text and formulas

`k.Text` does not typeset math. Put a `k.Math` next to it with a container:

```python
import kinemo as k


@k.scene
def mixed(s: k.Scene):
    line = k.Row(
        k.Text("The area is", size=0.5),
        k.Math(r"A = \pi r^2", size=0.6),
        gap=0.25,
    ).place(at="center")
    s.play(k.write(line))
    s.wait(0.5)
```

## `k.Math`

```python
k.Math(tex, *, size=0.6, display=True, engine="builtin", **props)
```

`k.Math` takes LaTeX syntax: fractions, roots, sums, integrals, matrices, `\left…\right`,
accents, Greek letters, `\mathbb`. It is converted and typeset natively, in milliseconds.
`display=False` uses inline (text-style) layout.

### Naming and finding subexpressions

- **`\id{name}{...}`** names a subexpression. `eq["name"]` returns it. `\id` does not change
  the layout.
- **Any subexpression** can also be found by its TeX: `eq["c^2"]`. The lookup matches the
  *syntax tree*, not the string, so `eq["c^2"]` and `eq["c^{2}"]` are the same part.
- **A lookup must be a node of the tree.** In `x + x = 2x`, `eq["x"]` is the first `x`
  and `eq.find_all("x")` is every one, but `eq["2x"]` is not a node (it is two atoms side
  by side), so it is an error. Wrap it: `\id{twox}{2x}`.

```python
import kinemo as k


@k.scene
def pythagoras(s: k.Scene):
    eq = k.Math(r"\id{lhs}{a^2 + b^2} = c^2", size=0.9).place(at="center")
    s.play(k.write(eq))
    s.play(eq["lhs"].to(color=k.YELLOW))
    s.play(eq["c^{2}"].to(color=k.GREEN))
    for term in eq.find_all("2"):
        s.play(k.indicate(term), duration=0.4)
    s.wait(0.5)
```

### Morphing equations

`k.morph(eq1, eq2)` takes `eq1` out of the scene, puts `eq2` in, and moves matching parts
between them. Parts are matched in this order:

1. explicit `match=` from you;
2. `\id{...}` names present in both formulas;
3. identical TeX subtrees, largest first;
4. identical glyphs, by relative position (this breaks ties between repeated terms);
5. whatever remains fades out of `eq1` and into `eq2`.

Naming the part that should travel is the most reliable way to get the motion you want:

```python
import kinemo as k


@k.scene
def solve_for_c(s: k.Scene):
    eq1 = k.Math(r"\id{lhs}{a^2 + b^2} = c^2", size=0.9).place(at="center")
    eq2 = k.Math(r"c = \sqrt{\id{lhs}{a^2 + b^2}}", size=0.9).place(at="center")
    s.play(k.write(eq1))
    s.play(k.morph(eq1, eq2), duration=1.5)
    s.wait(0.5)
```

`match=` maps glyphs of `a` to glyphs of `b` **by their key**, which is the character (or,
in code, the token). Use it to pair glyphs that differ, such as a renamed variable:

```python
import kinemo as k


@k.scene
def rename(s: k.Scene):
    a = k.Math(r"f(x) = x^2", size=0.9).place(at="center")
    b = k.Math(r"f(t) = t^2", size=0.9).place(at="center")
    s.play(k.write(a))
    s.play(k.morph(a, b, match={"x": "t"}))
    s.wait(0.5)
```

When two objects have nothing in common, the morph does a warp plus crossfade and lint
`W0801` warns. Shapes without glyphs (a circle into a square) pair by order and morph
outline to outline without a warning.

### What the built-in engine does not cover

Commands outside mathematical LaTeX, such as `\usepackage` or a TikZ environment, are
`K0801`. The diagnostic suggests `engine="tex"`, but that option is not available yet
(`K0105`, "not available in this installation yet"). Rewrite the formula with
mathematical commands, or draw the figure with kinemo shapes.

## `k.Code`

```python
k.Code(src, lang="python", *, theme="auto", line_numbers=False, size=0.32, **props)
```

- Highlighting uses tree-sitter. `lang=` selects the grammar.
- `theme="auto"` picks a light or dark palette from the scene background; `"light"` and
  `"dark"` force one.
- Leading and trailing blank lines of `src` are stripped, so a triple-quoted string that
  starts with a newline works as expected.
- Parts work as in `k.Text`: `code["s += x"]`, `code.find_all("xs")`, `code.lines[2]`.
  Recoloring a part overrides its syntax colors.

### Highlighting lines

`code.highlight(lines=[3, 4])` dims every line except the given ones (numbered from 1, like
`line_numbers=True` shows them). `code.highlight(None)` removes the highlight. It is a named
transition, equivalent to `code.to(highlight=lines, highlight_amount=1)`. Changing from one
highlight to another fades out and back in within the same duration.

### Code morphs

`k.morph(before, after)` between two `k.Code` objects animates the diff: a line diff
followed by a token diff. Unchanged lines slide to their new place, inserted tokens enter,
removed tokens leave.

```python
import kinemo as k

V1 = """
def total(xs):
    s = 0
    for x in xs:
        s += x
    return s
"""

V2 = """
def total(xs):
    return sum(xs)
"""


@k.scene
def refactor(s: k.Scene):
    before = k.Code(V1, lang="python", line_numbers=True, size=0.4).place(at="center")
    after = k.Code(V2, lang="python", line_numbers=True, size=0.4).place(at="center")
    s.play(k.write(before), duration=2)
    s.play(before.highlight(lines=[3, 4, 5]))
    s.play(before["s += x"].to(color=k.YELLOW))
    s.play(before.highlight(None))
    s.play(k.morph(before, after), duration=1.5)
    s.wait(0.5)
```

## Common mistakes

> | Diagnostic | What happened | Fix |
> | --- | --- | --- |
> | none (renders literally) | `k.Text("area $x^2$")`: `$...$` is not markup. | Put the formula in a `k.Math` beside the text, in a `k.Row`. |
> | `K0105` | `txt["word"]` or `eq["..."]` does not appear (or is not a node of the formula). | Check the spelling. In math, name the part with `\id{name}{...}` and look up `eq["name"]`. |
> | `K0801` | A command the built-in engine does not support (`\usepackage`, TikZ). | Use mathematical LaTeX only. `engine="tex"` is not available yet (`K0105`). |
> | `K0102` | `s.play(t.to(text=...), t.to(color=...))`: the text morph takes `t` out of the scene for its duration. | One call: `t.to(text="...", color=k.RED)`. |
> | `W0801` | `k.morph(a, b)` found no common glyphs or tokens. | Add `match={"x": "y"}`, name parts with `\id`, or use `k.fade_out(a)` + `k.write(b)`. |
> | `W1002` | Two texts overlap, often two versions of a formula both in the scene. | Morph between them (only one is present at a time), or place one `below=` the other. |
> | `W1004` | Text smaller than 18 px at the final resolution. | Increase `size=` (about 0.15 units is the limit at 1080p). |

See also: [Text reference](../reference/text.md), [`k.morph`](../reference/verbs.md#k-morph),
[`k.write`](../reference/verbs.md#k-write), [Diagnostics](../reference/diagnostics.md#range-08).
