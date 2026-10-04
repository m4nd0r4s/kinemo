# Changelog

All notable changes to kinemo are listed here. The project follows
[semantic versioning](https://semver.org/); until 1.0, a minor version may change the API, and
`kinemo upgrade` rewrites the forms it replaces.

## 0.10.1

Fixes, plus what a first production client (narrated series) ran into.

**Fixed**

- `k.reparent` and `group.copy()` placed the children of the moved or copied group at their
  world position used as a local one.
- `txt.to(text=...)` between strings with no characters in common reported `W0801` (morph
  without matches); a crossfade is the expected result of a text change.
- Synthesized narration is reused from the cache instead of being synthesized again on every
  build, as the guide describes.
- A `[tts] provider` that is not installed is reported as `W1402` with the installed
  providers, instead of `W1401` (no provider).
- Empty children (an empty group, an emptied text part) no longer stretch a group's box.
- Paths imported with `k.SVG` keep their stroke caps and joins (`line_cap`, `line_join`);
  SVG's defaults are butt and miter.
- Objects made by factories (`k.Polygon.regular`, `ax.plot`, `ax.vline`, ...) carry their
  variable name into the scene, so `kinemo inspect` and diagnostics see it.

**Docs and CI**

- The guide's API signatures are fenced `python signature`; every `python` block of the guide
  is checked to be valid Python.
- CI tests the wheel built from the branch (it could pick the PyPI release of the same
  version) and runs once per pull request.

## 0.10.0

A round of fixes from rendering every example of the guide and checking the frames.

**Added**

- **Charts:** objects an axes creates (`plot`, `parametric`, `area`, `vline`, `hline`,
  `scatter`, `bars`, `curve.tangent_at`, polar `plot`) take `enter_with_axes=False` to stay
  hidden until their own verb brings them in.
- **Output:** `--out` of `kinemo render` and `kinemo snap` can name one file
  (`--out intro.gif`); the format comes from its extension.
- **Tooling:** `kinemo inspect` lists the glyphs each text run draws (`drawn_glyphs`).
- **Tests:** every complete example of the guide passes `kinemo check --strict` in CI.

**Changed**

- **Text parts nest.** A part addressed inside another (`txt.chars[0:6]` inside
  `txt.words[0]`) nests in it and starts with its style; a part around others
  (`txt.lines[0]`) takes them in, so its opacity and transforms apply to them. Every glyph is
  drawn once, and after `txt.to(text=...)` the old parts select nothing. Styling or scaling a
  part no longer moves the text.
- **Draw order:** with equal `z`, an object that enters the scene later is drawn on top
  (`s.add(trail, dot)` puts the dot above the trail).
- **Containers:** children that swap places pass on opposite arcs; `insert` grows the new
  child in while its neighbours make room, `pop` shrinks the leaving one in its slot, and a
  placed container slides instead of jumping. A table makes room for new rows gradually.
- **Charts:** new bars grow from no width in their slot and removed ones narrow away;
  `k.indicate(chart.bar(key))` pulses the bar from its baseline.
- **Drawing:** an arrow's shaft is traced first and its head last.
- **Text:** the sign of a number is drawn as a true minus (−), as wide as `+`, so a readout
  does not shift when the sign flips. `k.Bar` labels round to two decimals.

**Fixed**

- Overlapping text parts drew their glyphs twice and lost the colors set earlier.
- `row.pop` removed the child at once and snapped the others into place.
- A formula morph could make a thin bar (a square root's) vanish halfway.
- The preview's inspector bound the arguments of objects made by a method (`ax.vline(4)`)
  to the constructor of the object, offering a vector editor for a number.
- The preview now follows changes of the URL hash on an open page.
- Guide: examples and text aligned with how kinemo behaves (copies, `k.reparent`, recorded
  narration paths, default verb durations, `fit`, and several examples).

## 0.9.0 — first public release

The complete design of [docs/specs.md](docs/specs.md), up to its v1.0 milestone. The version
number waits for feedback from real use before promising API stability.

- **Scenes and time:** `@k.scene`, `s.play`/`s.start`/`s.wait`, composition with `k.seq`,
  `k.par`, `k.stagger`, `s.during`, `s.tempo`, marks, slides and clips (`@k.clip`).
- **Objects:** shapes, text with addressable parts, LaTeX math through typst (no TeX),
  highlighted code with morphs, images, SVG with addressable parts, braces, boolean shapes.
- **Layout:** constraints (`.place`, `.to_place`), containers (`k.Row`, `k.Column`, `k.Grid`,
  `k.Stack`), groups and copies.
- **Reactive values:** signals, expressions and lambdas traced to native code, `k.python` as
  the explicit escape hatch, time as a signal.
- **Events and systems:** `k.when`, handlers, `s.wait_for`, integrals, fixed-step simulations
  and trails, resolved to a fixed point before rendering.
- **Charts and data:** axes, plots, parametric and polar plots, zoom, bar and line charts,
  tables; data from polars, pandas, pyarrow, duckdb, numpy or plain Python.
- **Mass objects:** points, vector fields and stream lines drawn in batches.
- **Components:** `k.Component` with typed props, outputs, events and context.
- **Output:** MP4, WebM, MOV, GIF, PNG, SVG and slides; final and draft quality; parameters;
  movies of several scenes; narration with optional TTS providers.
- **Tooling:** `kinemo check` (diagnostics with stable codes and fixes, `--fix`, `--json`),
  `inspect`, `snap`, `explain`, `docs`, `upgrade`, and the MCP server for agents.
- **Preview:** `kinemo dev` with hot reload, a scrubbable timeline, an outliner and an
  inspector that edits the code: literals, colors, points, easings and object positions are
  rewritten in the source file.
- **Docs:** fifteen guides, the generated API reference, examples, caveats and `llms.txt`.
