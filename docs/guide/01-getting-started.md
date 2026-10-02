# Getting started

This guide takes you from a fresh clone to a rendered video. You will build kinemo from
source, write a first scene, and learn the three commands you will use all the time:
`kinemo check` (is the scene correct?), `kinemo dev` (what does it look like?) and
`kinemo render` (make the final file).

## Install

```bash
pip install kinemo
```

Wheels are published for Linux, macOS and Windows, for Python 3.11 or newer. Video output
(mp4, webm, mov, gif) also needs `ffmpeg` on your `PATH`. The extras `kinemo[numpy]` and
`kinemo[polars]` install the data libraries that charts can read.

### From source

kinemo is a Python package with a Rust core, compiled into a single extension module with
[maturin](https://www.maturin.rs/) and PyO3.

Requirements:

- stable Rust (`rustup`);
- Python 3.11 or newer;
- [uv](https://github.com/astral-sh/uv) (or any other way to create a virtual environment);
- `ffmpeg` on your `PATH` (only needed for video output: mp4, webm, mov, gif).

From the root of the repository:

```bash
uv venv .venv
uv pip install --python .venv/bin/python maturin pytest numpy polars
source .venv/bin/activate
maturin develop            # builds the Rust core and installs kinemo into .venv
```

`maturin develop` compiles a debug build by default. For realistic performance (rendering
long videos), use `maturin develop --release`. The optional GPU preview backend is enabled
with `maturin develop --features gpu`; the final render always uses the CPU renderer, which
is the reference.

Check the installation:

```bash
kinemo --help
python -c "import kinemo as k; print(k.Circle)"
```

`numpy` and `polars` are optional. kinemo never imports them itself; they are only needed
if your scenes use them (see the extras `kinemo[numpy]` and `kinemo[polars]`).

## Create a project

`kinemo new` creates a folder with a `kinemo.toml`, an example scene and a Pyright
configuration:

```bash
kinemo new demo
cd demo
```

```
demo/
├─ kinemo.toml          # fps, size, theme, output folder, allowed lints
├─ pyrightconfig.json   # type checking for your scenes
├─ scene.py             # example scene
└─ .gitignore
```

Settings in `kinemo.toml` are project defaults; arguments of `@k.scene(...)` override them,
and CLI flags override both. See [configuration](../reference/configuration.md).

## Your first scene

A scene is a function decorated with `@k.scene` that receives `s: k.Scene`. Save this as
`hello.py`:

```python
import kinemo as k


@k.scene
def hello(s: k.Scene):
    title = k.Text("Hello, kinemo").place(at="center")
    s.play(k.write(title))
    s.play(title.to(color=k.BLUE, scale=1.5))
    s.wait(1)
```

Line by line:

- `k.Text(...)` creates an object. Creating it does **not** put it on screen yet.
- `.place(at="center")` declares where it sits. Position comes from constraints, not
  coordinates.
- `s.play(k.write(title))` schedules an animation that writes the text and moves the time
  cursor to its end (1 s by default).
- `title.to(color=..., scale=...)` is an animated state change; `s.play` runs it.
- `s.wait(1)` holds the last frame for a second.

The scene lasts 3.5 s: 1 s of writing, 1 s of color change, 1 s of waiting, plus a default
`tail` of 0.5 s.

## The workflow: check, dev, render

### `kinemo check`: build without rendering

```bash
kinemo check hello.py
```

```
hello.py — scene 'hello' — 3.5 s — ok
timeline
   0.00– 1.00  write(title)                             hello.py:7
   1.00– 2.00  title.to(fill, scale)                    :8
```

`check` runs the scene code, resolves the timeline and runs every lint, but draws nothing,
so it takes a fraction of a second. Use it after every edit. Useful flags:

| Flag | Effect |
| --- | --- |
| `--strict` | Warnings (lints) become errors. This is what CI and the MCP server use. |
| `--json` | The same report as stable JSON, for tools and agents. |
| `--fix` | Applies the fix of each diagnostic that has exactly one safe fix. |
| `--scene NAME` | Only that scene, when the file has several. |
| `--param n=7` | Value for a scene parameter. |

When something is wrong, the report tells you the code, the line, the instant and the fix:

```
e1.py — scene 'e1' — — — 1 error
errors
  K0101 error: 'c' is not in the scene yet
    --> e1.py:6            s.play(c.to(x=2))
     t = 0.00 s
    fix 1: bring it in with a verb
           s.play(k.draw(c))
    fix 2: or add it instantly
           s.add(c)
    more: kinemo explain K0101
```

`kinemo explain K0101` prints the long explanation of any code.

### `kinemo dev`: live preview

```bash
kinemo dev hello.py
```

This opens a browser preview (port 7878 by default; `--no-open` to skip opening the
browser) with:

- the current frame, and a timeline where every animation is a bar labeled with its verb
  and source line;
- a draggable playhead: the frame at any instant is computed on demand, so you can scrub
  backwards and forwards freely;
- hot reload: when you save the file, the scene is rebuilt and the preview returns to the
  same instant;
- clicking an object shows its props and where each value came from;
- if the build fails, the last good version stays on screen with the error as an overlay.

Debug overlays: `kinemo dev hello.py --debug layout,safe` draws layout boxes and the safe
area.

### `kinemo inspect` and `kinemo snap`: look without a browser

```bash
kinemo inspect hello.py --at 1.5        # scene graph at t = 1.5 s
kinemo snap hello.py --at 0.5,end       # PNGs in out/
```

`inspect` prints every object with its position, bounding box, colors, and the origin of
each value (`← place(at='center')`, `← arg`, `← theme`). Add `--json` for machine-readable
output. `snap` writes PNG frames (draft quality by default) at the requested instants; `end`
means the last frame.

### `kinemo render`: final output

```bash
kinemo render hello.py                       # out/hello.mp4, final quality
kinemo render hello.py --quality draft       # 540p, 30 fps: quick look
kinemo render hello.py --format gif
kinemo render hello.py --format png --at 2   # a single frame
kinemo render hello.py --format slides       # HTML slides, one section per s.mark(slide=True)
```

Formats: `mp4` (default), `webm` (with `--transparent`), `mov` (ProRes 4444 with alpha),
`gif`, `png` (`--at` or `--frames`), `svg` (`--at`) and `slides`. See
[output](../reference/output.md) and [CLI](../reference/cli.md).

## A slightly bigger scene

Here is a scene that uses a few more ideas. Every snippet in these guides passes
`kinemo check --strict`, so you can paste it into a file and run it.

```python
import kinemo as k


@k.scene
def intro_shapes(s: k.Scene):
    title = k.Text("Three shapes", size=0.7).place(at="top", margin=0.8)
    circle = k.Circle(r=0.8, fill=k.BLUE, fill_opacity=0.4)
    square = k.Square(1.6, fill=k.GREEN, fill_opacity=0.4)
    tri = k.Triangle(fill=k.ORANGE, fill_opacity=0.4)
    row = k.Row(circle, square, tri, gap=0.8).place(at="center")

    s.play(k.write(title))
    s.play(k.stagger([k.draw(o) for o in row], lag=0.2))
    s.play(row.swap(0, 2))
    s.play(k.indicate(square))
    s.wait(0.5)
```

- `k.Row` lays its children out horizontally and keeps them there.
- `k.stagger` starts each animation 0.2 s after the previous one.
- `row.swap(0, 2)` reorders the row; the reflow animates by itself.
- `k.indicate` is a temporary highlight that returns to the original state.

## Where to go next

- [Mental model](02-mental-model.md): build → resolve → render, the cursor, `.now` vs `x()`.
- [Timeline](03-timeline.md): `play`, `start`, composition, `during`, `tempo`, clips.
- [Objects and layout](04-objects-and-layout.md): lifecycle, props, constraints, containers.
- [Animations](05-animations.md): verbs, easing, morphs, emphasis.
- [Reactive values](06-reactive.md): signals, lambdas, tracing.
- [Components](07-components.md): reusable objects with props, outputs and events.
- More topics: [events and simulation](08-events-and-simulation.md), [text, math and code](09-text-math-code.md),
  [charts and data](10-charts-and-data.md), [mass objects](11-mass-objects.md).

> **Common mistakes**
>
> | You see | Why | Fix |
> | --- | --- | --- |
> | `K0101 'c' is not in the scene yet` | You animated an object that was created but never entered. | `s.play(k.draw(c))` or `s.add(c)` first. |
> | `K0104 outside scene construction` | You created objects or signals at module level, outside a `@k.scene` function. | Move them into the scene function (or into a clip, a handler or a component's `build()`). |
> | `K1103 'self.play'` and other `K11xx` | Manim habits (`self.play`, `Create`, `.animate`). | Use the translation in the message: `s.play(...)`, `k.draw(...)`, `s.play(x.to(...))`. |
> | `W1001 ... leaves the safe area` | Part of an object is too close to the frame edge. | Use `margin=` with `at=`, a smaller size, or `clamp=True` in `.place(...)`. |
> | `check` passes but `render` fails | `ffmpeg` is missing from `PATH`. | Install ffmpeg, or render `--format png`. |
> | `check` exits with status 1 on a warning | You used `--strict`, which turns lints into errors. | Fix the lint, or allow it explicitly: `# kinemo: allow W1001` on that line. |
