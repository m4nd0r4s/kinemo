# Tooling: check, inspect, snap, dev and tests

The `kinemo` command closes the write → view → fix loop. Most of the time you do not need
to render a video to know whether a scene is right:

| Command | Answers |
| --- | --- |
| `kinemo check` | Does it build? Which errors and lints, with which fixes? What is on the timeline? |
| `kinemo inspect` | Where is each object at instant t, and why is it there? |
| `kinemo snap` | What does the frame look like at these instants? |
| `kinemo dev` | Live preview with hot reload and a draggable timeline |
| `kinemo explain` / `kinemo docs` | What does this code mean? How is this symbol used? |
| `kinemo upgrade` | Rewrite deprecated forms after a version change |
| `kinemo.testing` | The same checks inside pytest, plus golden-frame snapshots |

The full option list is in the [command line reference](../reference/cli.md). This guide
shows how to use the commands together, then covers determinism and performance.

## Starting a project

```bash
kinemo new demo        # demo/kinemo.toml, demo/scene.py, demo/pyrightconfig.json, .gitignore
cd demo && kinemo check scene.py && kinemo render scene.py
```

`kinemo.toml` holds the project defaults (size, fps, theme, lints, TTS provider). It is
looked up from the **working directory** upwards, so run `kinemo` from inside the project.
See [Configuration](../reference/configuration.md).

## `kinemo check`

`check` builds and resolves the scene without rendering, then runs the lints. It is fast
(about 0.2 to 0.3 s for a typical scene), so run it after every edit.

```bash
kinemo check scene.py                 # every scene in the file
kinemo check scene.py --scene intro   # one scene
kinemo check scene.py --strict        # warnings count as errors (use this in CI)
kinemo check scene.py --fix           # apply safe fixes, then check again
kinemo check scene.py --json          # machine-readable (see the AI agents guide)
```

The text report has a header, the timeline (each scheduled animation as it is written, with
its source line; a call that runs in a loop shows each run's objects, and repeated firings
are grouped as `×n`), then errors and lints:

```
edge.py — scene 'edge' — 1.5 s — ok with 1 warning
timeline
   0.00– 1.00  k.write(title)                           edge.py:7
lints
  W1001 1.00 s  title leaves the safe area (top, 0.4 u)   :6
        fix: title = k.Text("A long title near the top", size=0.6).place(at="top", margin=0.1, clamp=True)
```

Errors carry the full anatomy: code, message, the offending line (and the related line, such
as where a constraint was declared), the instant, and numbered fixes:

```
K0401 error: 'ax' cannot animate x: the axis is held by a constraint
  --> scene.py:10          s.play(ax.to(x=1))
  --> scene.py:6           ax = k.Axes(x=(-3, 3, 1), y=(0, 2, 1)).place(at="center")   ← constraint here
   t = 1.00 s
  fix 1: change the constraint with an animation
         s.play(ax.to_place(right_of=...))
  fix 2: release it and animate freely
         s.play(ax.to(x=..., unpin=True))
  more: kinemo explain K0401
```

Levels and exit codes:

- **error** stops the build. Exit code 1.
- **warning** (a lint) does not stop the build. Exit code 0, or 1 with `--strict`.
- **hint** is a style suggestion and never fails.

`--fix` applies the fix of every diagnostic that has exactly one safe, mechanical edit (a
whole-line replacement), then runs the check again. Fixes that need a decision (two
options, or a description without code) are left for you.

### Silencing a lint

Lints are turned off explicitly, never globally by accident:

```python
title = k.Text("Overlaps on purpose").place(at="center")  # kinemo: allow W1002
```

or for the whole project, in `kinemo.toml`:

```toml
[lints]
allow = ["W1007"]
```

The comment goes on the line the lint points to (the `:line` in the report).

## `kinemo inspect`

`inspect` prints the scene graph at an instant: every object present, its position and
bounding box, and where the position comes from (a constraint, a container, or plain
`x`/`y`).

```bash
kinemo inspect scene.py --at 2.5        # seconds
kinemo inspect scene.py --at part2      # a mark name
kinemo inspect scene.py --at end        # the last frame
kinemo inspect scene.py --at 2.5 --json # every prop and its source (see the AI agents guide)
kinemo inspect scene.py --at 2.5 --all  # also objects not in the scene at that instant
kinemo inspect scene.py --at "0,B03+50%,end"  # several instants, one build
```

```
ball: circle     moon.py:24
  position = (0.00, -1.08)   ← place(above=floor)
  bbox     = [-0.30, -1.38 → 0.30, -0.78]
  fill     = #4C9BE8
```

Objects are labeled by their variable name (`ball`), by their place in a parent
(`row[2]`, `txt["never"]`), or by kind and id (`text#3`). Pass `name="..."` to objects
created without an assignment to get a readable label.

The most useful instants are the end of each `s.play`, which you can read from the
timeline that `check` prints.

## `kinemo snap`

`snap` writes PNG frames of the requested instants (draft quality by default):

```bash
kinemo snap scene.py --at 0,2.5,end              # out/<scene>_0.png, out/<scene>_2.5.png, out/<scene>_end.png
kinemo snap scene.py --at 3 --quality final --out shots
kinemo snap scene.py --scene intro --at 3 --out shots/intro.png   # one scene, one instant: one file
kinemo snap scene.py --at "B03,B03+65%,B03.end-0.5"   # marks, shifted marks, a fraction of B03 → B03.end
kinemo snap scene.py --at marks --sheet               # every mark, as one labelled contact sheet
```

`--at` takes seconds, `end`, a mark name, a mark shifted by seconds (`intro+1.5`), or a
percentage of the stretch between a mark and the mark of the same name with `.end`
(`B03+65%`); `marks` stands for every mark in time order. `--sheet` writes one contact sheet
per scene (`<scene>_sheet.png`, `--columns 3` by default) with each frame labelled, drawn by
kinemo itself.

## `kinemo dev`

```bash
kinemo dev scene.py                    # opens http://127.0.0.1:7878/
kinemo dev scene.py --scene intro --port 8000 --no-open
kinemo dev scene.py --debug layout,safe
```

The page has three panes: the **outliner** (every object as a tree), the **frame**, and the
**inspector**, with the transport and the timeline below.

- The timeline shows each `play`/`start` as a bar (verb and line; hovering shows the code)
  and the marks, named in a row under the ruler (marks at one instant share a label,
  `B01.end · B02`). Zero-length entries (`s.add`, `k.sound`, `k.music`) are ticks in a thin
  row of their own. Dragging it requests frames from the native server, so Python is not
  involved. Bars from one statement in a loop are grouped into one (`group repeats`;
  double-click a group to expand it). Ctrl/⌘ + wheel, or the `−` `fit` `+` buttons, zoom
  in on a stretch of time. The speed menu plays at 0.25× to 2×.
- Narration (`s.voice`) and sounds (`k.sound`) play with the scene, in sync with the
  playhead, at the playback speed. The speaker button (or `M`) mutes them; the choice is
  remembered. Lines without audio yet (the silent estimate) are silent. Music is mixed as in
  the video: it fades in and out and drops to its `duck` level while a voice speaks.
- Under the animations, the **Narration**, **Sounds** and **Music** tracks show each clip
  over the time it sounds; a line without audio yet is dashed. Clicking a narration line
  shows its full text (click a word to move the playhead to it), its beat with a link to the
  script, the audio file, where the word times come from, the warnings on its line
  (`W1403`, `W1404`, ...) and a button that plays just that line.
- Saving the file (or a local module it imports) rebuilds the scene, and the preview stays
  at the same instant.
- Clicking an object, on the frame or in the outliner, shows its props and where each one
  came from: a link to the line that wrote it, or *default* for a prop the scene never set.
  The selection box and the props follow the object while the scene plays.
- Clicking a timeline bar selects the objects it animates and shows the arguments of its
  call (`box.to(rotate=30)`) and of the `play` that scheduled it (`duration=`, `ease=`).
- Source links (and Ctrl/⌘ + click on a bar) open the line in the editor of `[editor] command`
  in kinemo.toml: `vscode` (the default), `cursor`, `zed`, `idea`, `pycharm`, `sublime` and
  others open by URL; any other value is a command `kinemo dev` runs, with `{file}` and
  `{line}` replaced (`command = "emacsclient -n +{line} {file}"`).
- If the build fails, the preview keeps the last good version and shows the error as an
  overlay.
- `--debug layout` draws object boxes and constraint relations; `--debug safe` draws the
  safe area.
- After every build, `dev` builds the scene a second time and warns if the two results
  differ (see [Determinism](#determinism)).

### Editing from the preview

Values the code wrote as **literals** (numbers, strings, booleans, `(x, y)` tuples, colors)
are editable in the inspector, underlined. The edit is written to the source file, changing
only those characters, and the scene rebuilds:

- **Drag a number** sideways to change it (Shift: 10× faster, Alt: 10× finer). While you
  drag, the scene rebuilds from the edited text without touching the file; the file is
  written once, on release. Esc cancels the drag.
- **Click** a number or a string to type a new value (Enter saves, Esc cancels).
- Each value gets an editor for its type, read from the API's annotations:
  - enumerations (`align=`, `at="top"`, a brace's `direction=`) are a select; `at=` also
    offers *point (x, y)*, which writes the current position as a tuple;
  - points (`at=(1, 2)`, `anchor=`, `position=`) are two numbers, each dragged or typed on
    its own;
  - colors open a popover with kinemo's palette (written as `k.RED`), the theme's colors
    (`k.theme.accent`) and a color picker or hex field (written as `"#rrggbb"`);
  - easings are a select of the `k.ease` curves (written as `k.ease.out_back`);
  - fractions (`opacity=`) stay between 0 and 1 while dragged.
- A prop marked *default* can be set too: the preview adds the keyword to the constructor
  (`k.Text("hi", size=0.5)` → `k.Text("hi", size=0.5, rotate=8)`). In a timeline bar's
  panel, the optional parameters a call leaves out (`duration=`, `ease=`, `delay=`) are
  listed with their default and added when edited.
- **Drag the selected object** on the frame, or edit its *position* (two numbers), to move it.
  This rewrites `place(at=(x, y))`, or the `x`/`y` literals that position it; dragging
  snaps to 0.01 units.

Only what the code already wrote is edited; the preview never invents statements. A value the
code computes (a variable, an expression, a lambda) is shown, not editable. A line that runs
several times, as in a loop, carries a `×N` mark, and editing it changes every run. If the
file was changed elsewhere since the last build (unsaved edits in your editor, for example),
the preview refuses the edit and reloads.

`dev` previews at draft quality. A wheel built with `maturin develop --features gpu`
rasterizes the preview on the GPU when an adapter is available. The final render always uses
the CPU renderer, which is the reference.

## `kinemo explain` and `kinemo docs`

```bash
kinemo explain K0401        # what a diagnostic means (some codes add an example and the fix)
kinemo docs k.morph         # signature, summary and the canonical example
kinemo docs ax.plot         # methods work too (also s.play, Scene.play, draw)
kinemo docs k.morph --json  # the same, as JSON
kinemo docs                 # the list of documented symbols
```

An unknown symbol suggests the closest names (`kinemo docs k.morp` → `k.morph`, ...).
Every canonical example passes `kinemo check --strict`, and `kinemo docs --check` builds them
all, which is a quick way to validate an installation.

## `kinemo upgrade`

Between versions, deprecated forms are rewritten by exact codemods:

```bash
kinemo upgrade --check scenes/*.py   # show the diff, write nothing (exit 1 if anything would change)
kinemo upgrade scenes/*.py           # rewrite in place
```

Each codemod changes only the deprecated call and keeps the rest of the file byte for byte.
In 1.0 there are two: `k.Line(width=)` → `k.Line(length=)`, and a `k.Text(...)` used as a
scene parameter → `k.Str(...)`.

## Testing scenes with pytest

`kinemo.testing` runs the same build, inspection and snapshot logic as the CLI, without
rendering video.

| Function | Does |
| --- | --- |
| `build(scene, params=None, *, strict=False)` | Builds the scene. Raises `SceneBuildError` (an `AssertionError`) with the rendered diagnostics on errors, or on warnings with `strict=True`. Returns a `BuiltScene`. |
| `inspect(scene_or_built, t)` | The `kinemo inspect --json` payload at `t` (seconds, a mark or `"end"`), with `.object(label)` and `report["label"]` lookups. |
| `assert_snapshot(scene_or_built, t, name=None)` | Compares the frame at `t` with a golden PNG in `__snapshots__/` next to the test. |

`BuiltScene` has `.duration`, `.marks`, `.timeline` (the entries of `check --json`),
`.diagnostics`, `.lint_codes` and `.report()`. `build` also accepts a plain
`def body(s: k.Scene)` function, which is handy for small cases inside a test.

A scene module:

```python
import kinemo as k


@k.scene
def hello(s: k.Scene):
    title = k.Text("Hello, kinemo").place(at="center")
    s.play(k.write(title))
    s.play(title.to(color=k.BLUE, scale=1.5))
    s.wait(1)


@k.scene(params={"n": k.Int(3, 12, default=5)})
def polygon(s: k.Scene, n: k.Signal[int]):
    shape = k.Polygon.regular(n, r=2, name="shape").place(at="center")
    s.play(k.draw(shape))
```

And its tests:

```python
import pytest

import kinemo as k
from kinemo.testing import SceneBuildError, assert_snapshot, build, inspect

from scenes import hello, polygon


def test_hello_builds_cleanly():
    built = build(hello, strict=True)
    assert built.duration == pytest.approx(3.5)
    assert [e["label"] for e in built.timeline] == ["write(title)", "title.to(fill, scale)"]
    assert built.lint_codes == []


def test_title_ends_centered():
    title = inspect(hello, "end").object("title")
    assert title["position"] == pytest.approx([0.0, 0.0])


def test_polygon_with_a_parameter():
    built = build(polygon, params={"n": 8})
    assert inspect(built, "end")["shape"]["present"]


def test_hello_frame():
    assert_snapshot(hello, 2.0)


def test_animating_before_entering_is_k0101():
    def body(s: k.Scene) -> None:
        c = k.Circle()
        s.play(c.to(x=1))

    with pytest.raises(SceneBuildError) as info:
        build(body)
    assert info.value.diagnostics[0].code == "K0101"
```

How snapshots work:

- The first run writes the golden file (`__snapshots__/test_hello_frame-hello-2.0.png`)
  and passes. Commit it.
- Later runs compare byte for byte. On a mismatch, the new frame is saved beside the golden
  one as `.actual.png`, and the assertion message gives both paths.
- After an intended change, rerun with `KINEMO_UPDATE_SNAPSHOTS=1` to rewrite the golden
  files.

`.timeline` lists the scheduled animations; plain `s.wait` pauses are not entries.

## Determinism

The same source, the same assets and the same kinemo version produce the same bytes. Caching,
parallel rendering and byte-for-byte snapshots depend on it:

- `random` and `numpy.random` are seeded for each scene before the build
  (`@k.scene(seed=0)` by default). Unseeded randomness gives the same result every time.
- Simulations use a fixed step, and integrals and event detection use the same sampling
  grid on every machine.
- Text uses bundled fonts, never system fonts.
- The CPU renderer (tiny-skia) is the reference for snapshots. Video is encoded with
  bit-exact settings.

What kinemo cannot guarantee is that **your** code is pure. Handlers, `.map` functions and
`k.python` functions must not read the clock, global counters or files that change. `kinemo
dev` warns when two consecutive builds differ:

```
kinemo dev: warning — two consecutive builds of the same source gave different results; ...
```

## Performance tips

- **Prefer `k` functions to `k.python`.** Expressions built with `k.sin`, `k.where`,
  `k.interp` are traced and evaluated natively, in parallel. `k.python(fn)` is called once
  per frame during resolve. Use it only for code that cannot be expressed natively, and
  prefer `vectorized=True`, which receives the whole timeline as one numpy array.
- **Use mass objects for many points.** One `k.Points` with 10,000 points is far cheaper than
  10,000 `k.Dot` (lint `W0901`). See [Mass objects](11-mass-objects.md).
- **Keep reactive text coarse.** Text layout is redone only when the string changes; a
  label formatted with `:.0f` changes less often than one with `:.4f`.
- **Iterate with `check` and `snap`**, not `render`. When you do render, `--quality draft`
  is much faster than `final`.
- **Keep handlers short.** Every handler may run on several resolve passes. Logic that does
  not depend on the event belongs in the build.
- **Size simulations sensibly.** `dt=1/240` (the default) is plenty for most motion; a
  smaller step multiplies the Python work of `k.simulate`.

## Common mistakes

> | Diagnostic | What happened | Fix |
> | --- | --- | --- |
> | exit code 1 in CI | `check --strict` turns every warning into a failure. | Fix the lint, or allow it explicitly on its line (`# kinemo: allow W1002`). |
> | lint still reported | `[lints] allow` in `kinemo.toml` ignored, because `kinemo` ran outside the project folder. | Run from the project folder (the file is found from the working directory upwards). |
> | `K0001` | A plain Python exception (including a syntax error) while loading or building. | Read the message. For syntax errors, the reported location may point inside Python's import machinery rather than your file. |
> | `SceneBuildError` | `kinemo.testing.build` failed; the message is the same text `check` prints. | Fix the diagnostics, or pass `strict=False` to tolerate warnings. |
> | `SnapshotMismatch` | The frame changed. | Open the `.actual.png`; if the change is intended, rerun with `KINEMO_UPDATE_SNAPSHOTS=1`. |
> | `KeyError` in `inspect(...).object("x")` | No object with that label at that instant. The message lists the available labels. | Check the instant, or name the object with `name="x"`. |
> | `dev` warning | Two builds differ: a handler or traced function is not pure. | Remove clock, global state and unseeded randomness from handlers and `k.python` functions. |

See also: [Command line reference](../reference/cli.md),
[Diagnostics](../reference/diagnostics.md), [AI agents](15-ai-agents.md).
