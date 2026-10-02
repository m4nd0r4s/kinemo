# Changelog

All notable changes to kinemo are listed here. The project follows
[semantic versioning](https://semver.org/); until 1.0, a minor version may change the API, and
`kinemo upgrade` rewrites the forms it replaces.

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
