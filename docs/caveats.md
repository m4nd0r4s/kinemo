# Caveats

Things that behave differently from what you might expect, known limitations of this release, and
the workaround for each. Most of them are also caught by `kinemo check`; the diagnostic
code is given where one exists.

## Build phase vs. playback

- **The scene function runs once.** Python `if`/`for` decide the script at build time from
  values *at the cursor* (`x.now`). They never re-run during playback. To react while the
  video plays, use `k.when`, `@event.on` or expressions.
- **`x.now` is a snapshot; `x()` is a tracked read.** `x()` in the scene body is K0301;
  `x.now` inside a lambda is K0302 (it would freeze the value).
- **`.now` only sees what is already scheduled.** Animations started later in the script,
  and handlers (which run during resolve), are not visible to an earlier `.now` or
  `s.wait_for`.
- **Handlers and traced functions must be pure.** The resolve phase may run a handler
  several times until the event times stop changing; `kinemo dev` warns when two builds
  of the same source differ. Global counters, the clock or unseeded randomness break this.
- **Event loops stop after 8 passes** (K0501). A handler that always schedules the next
  firing of its own event at a new instant never converges; use `once=True` or `rearm=`.

## Tracing

- **Functions passed to `.map`, `k.computed` and lambdas in props are traced**, not
  called per frame: they run once with symbolic values. `if`, `and`/`or`, `math.*`,
  `int()`, built-in `min()`/`max()` on signals fail with K0310. Use `k.where`, `&`/`|`,
  `k.sin`, `k.floor`, `k.min`, `k.max`.
- **`k.python(fn)` is the explicit escape hatch.** It is precomputed once per frame at
  resolve time (the cost is shown by `check`) and cannot be exported to interactive web if
  it depends on a parameter (W1302).
- **`k.simulate` step functions and `.on` handlers are plain Python**: `if`, `min`,
  `math` are fine there.
- **f-strings work in lambdas only with signals read as `x()`**; formatting a signal in the
  scene body without `.now` is K0301.

## Layout

- **`place()` holds both axes.** `place(left_of=a)` also aligns vertically (use
  `align=`). Animating `x`/`y` of a placed object is K0401: animate the constraint with
  `.to_place(...)`, or release it with `.to(..., unpin=True)`.
- **Children of containers are positioned by the container** (`Row`, `Column`, `Grid`,
  `Stack`). Reorder with `swap`/`insert`/`pop`/`to(children=...)`; to nudge a child on
  top of the layout use `blend="add"`.
- **Constraints use the unrotated bounding box** unless `place(..., by="rotated")`.
- **Scale and rotation pivot on the bounding-box center** of the object (prop `anchor`).
  A group's pivot therefore moves when its children change.
- **One parent per object** (K0103). Use `obj.copy()` for a second instance, or
  `k.reparent(obj, group)` to move it (instant; the world position is kept).
- **Hidden children (`visible=False`) do not count** in their group's bounding box;
  transparent ones (`opacity=0`) do.
- **`tri.sides` and `Square.on(side)` are evaluated at the cursor**: the squares do not
  follow the triangle if it moves later.

## Animations

- **Two animations on the same prop at the same time are an error** (K0201), including
  hidden overlaps such as a `during` revert meeting a later `.to()`. Sequence them or use
  `blend="add"` for intentional sums.
- **`s.play(..., at=)` does not move the cursor** (W0110); write `s.start(..., at=)`.
- **`duration=` rescales the whole composition**, keeping the relative timing of its parts.
- **`s.during` only accepts reversible animations** (`.to()`, `k.indicate`); entry and
  exit verbs are K0204.
- **Progressive tempo (`s.tempo(1, to=8)`) is applied when the block ends**; inside the
  block, `.now` on animations started *before* the block reads slightly different times.
- **Clips with `duration=` run twice** (once to measure, then for real). Side effects
  outside kinemo inside a clip happen twice.
- **Lists only interpolate when declared** (`k.signal([...], lerp=k.lerp.pointwise)`),
  otherwise K0205.

## Text, math and code

- **Markup is minimal**: `**bold**`, `*italic*`, `` `code` ``. Bold italic renders as bold.
  `$...$` inside `k.Text` is kept literally — use `k.Math` for formulas.
- **Text layout is left-to-right only** (no bidirectional text) and uses the bundled
  DejaVu fonts; system fonts are never used, so output is identical on every machine.
- **`txt["word"]` addresses the first occurrence** in the text without markup; use
  `txt.find_all("word")` for all of them.
- **`k.Math` covers mathematical LaTeX**, not text-mode or TikZ commands (K0801).
  `\textcolor`/`\color` are ignored (style parts with `eq["..."].to(color=...)` instead),
  `\tag`/`\label` render nothing, `\hspace` is always 0.5 em, `array` column specs use the
  first column's alignment. `engine="tex"` is not available yet.
- **Subexpression lookup matches whole syntax-tree nodes**: in `a^2 + b^2 = c^2`, `a^2`
  and `c^2` are nodes but `a^2 + b^2` is not unless wrapped in `{}` or `\id{...}{...}`.
- **Code highlighting has no language injections** (SQL inside strings stays a string);
  repeated identical lines may pair unexpectedly in a code morph.

## Charts and data

- **`ax.plot` samples the function at build time** with floats; the curve then follows
  `until=`/`from_=` signals and zooms natively. Curves are cut at the visible x and y
  ranges — choose `y=` to cover the values you want to see.
- **Ticks are generated for the initial ranges**; after a zoom, ticks outside the new
  range hide, but new tick values are not created.
- **`LineChart.to(data=)` keeps the `y=` column names**; rename series by keeping column
  names stable across datasets.
- **Data must be Arrow-compatible** (polars, pandas ≥ 2.2, pyarrow, duckdb), numpy, or plain
  Python lists/dicts; anything else is K1201.

## Rendering and output

- **The CPU renderer (tiny-skia) is the reference.** The optional GPU backend
  (`maturin develop --features gpu`) is only used by the `dev` preview and is usually *not*
  faster for typical scenes.
- **MP4 drops transparency**; use `--format webm --transparent` or `--format mov`.
- **Odd output sizes are padded by one pixel** in MP4 (yuv420p needs even dimensions).
- **Slides split audio at section boundaries**: a narration starting before a slide break
  is not carried into the next section.
- **`--format web` (interactive) and 3D (`camera="3d"`, `s.camera`, `s.hud`) are not in
  this release**; the spec plans them for later versions.
- **Voice without a TTS provider is silence** with a duration estimated at 150 words/min
  (W1401). Install a provider package and set it in `kinemo.toml`.

## Editing from the preview

- **Computed values are edited through their numbers.** Literals are edited whole; in an
  expression or a lambda only the numbers written inside it are editable, and a name is
  edited where it is assigned only when it is assigned once to a literal (in the scene
  function or at module level). Parameters, loop variables, names assigned more than once
  and anything without a number in it stay read-only; edit them in the code. The preview
  edits arguments that already exist (or adds a keyword for a default prop); it never adds
  statements.
- **A number that a drag crosses to negative keeps its operator**: dragging the `1.2` of
  `title.x + 1.2` below zero writes `title.x + -0.3`.
- **Editing a line inside a loop changes every run of it** (the `×N` mark). A clip's body is
  one line for all its uses.
- **Dragging an object adds the pointer distance to its literal position**, or to the number
  its computed position adds (`title.x + 1.2`). Inside a scaled or rotated group the object
  moves by a different amount on screen than the pointer. Objects positioned by a relation
  (`place(above=...)`), a container or an expression without such a number can't be
  dragged, and neither can an object whose `x`/`y` is animating at the playhead.
- **An edit is refused when the file changed since the preview last built it** (for example
  unsaved changes in the editor that were then saved); the preview reloads and the edit can
  be repeated.

## Not yet implemented

These are described in the specification but are not implemented yet:

- `k.morph_cut` renders as a crossfade; objects with the same `key=` do not travel across
  the cut yet.
- `kinemo dev --debug` draws `layout` and `safe`; the `morph` and `trace` overlays, and the
  events track on the timeline, are not there yet.
- `s.start(..., loop=True)` (looping animations that keep running on a paused slide).
- `$...$` inline math inside `k.Text`; use a separate `k.Math`.
- `kinemo check` does not yet print the measured cost of each `k.python` function.
- `k.PolarAxes.plot` is sampled at build time: it does not follow later changes of
  `r_max`/`radius`.

## Typing

- **Component prop defaults must use `k.prop(...)`** to type-check in strict mode:
  `power: k.Prop[float] = k.prop(0.0)`. A bare `= 0.0` works at runtime but Pyright
  rejects it.
- **Simulation fields (`sim.y`) are typed `Any`**: Pyright cannot map a `k.State`'s fields
  onto the simulation object.
- **User component constructors accept `**kwargs: object`**, not per-prop types.

## Performance

- **Avoid thousands of individual objects** (W0901): use `k.Points`, `k.VectorField` or
  `k.StreamLines`, which are drawn in batches.
- **`k.python` functions run once per frame of the scene** during resolve; vectorize them
  (`k.python(fn, vectorized=True)`) for long scenes.
- **The build uses about 10 GB of `target/` in a full development checkout** (typst, wgpu
  and tree-sitter grammars). `cargo build` excludes the GPU crate by default.
