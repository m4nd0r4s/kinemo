# Implementation status relative to the specification

Updated for 0.9.0, the first public release, which completes the milestones the spec calls
v0.1 to v1.0 (the 1.0 version number waits for feedback from real use). The spec is
[specs.md](specs.md); this document records what was delivered, where the implementation
decided a detail the spec left open, and what is left for later (as the spec anticipates).

## Milestones

| Milestone | Spec criterion | Status |
| --- | --- | --- |
| v0.1 Core | `hello` and `bubble_sort` identical to the snapshot; `check` < 300 ms | ✓ (`tests/golden/`, `test_performance.py`) |
| v0.2 DX | rebuild < 500 ms; every implemented code has a fix test | ✓ |
| v0.3 Expressiveness | `pythagoras` passes; math corpus ≥ 98% | ✓ (corpus 182/182) |
| v0.4 Advanced time | `solar_day` and `bounce` pass; fixed-point and `K0501` tests | ✓ |
| v0.5 Scale | performance targets; AI eval ≥ 90% | ✓ (eval 50/50; see GPU below) |
| v1.0 | 35 contracts pass; API frozen; `llms.txt`; semver | ✓ |

## Decisions made during implementation

- **Python ↔ Rust bridge.** The IR lives in Rust (`Builder` in `kinemo-py`); Python sends
  operations as JSON per call. `.now` queries the core at the cursor.
- **Constraints.** Solved by memoized directional recursion (each object depends on its
  target), with cycle detection (K0402), instead of a generic solver (cassowary). Containers
  are implemented directly (no taffy). A `place()` pins both axes.
- **Text.** rustybuzz + ttf-parser with embedded DejaVu fonts (determinism, no system
  fonts). Text, code and formulas are groups of glyph *runs*: each addressed part
  (`txt["world"]`) becomes a run with its own props.
- **Math.** typst 0.15 + mitex, no TeX; subexpressions tracked by per-node color markers,
  verified not to alter the layout (maximum deviation 0). `engine="tex"` is not yet
  available in this installation (the error says so).
- **Progressive tempo** (`s.tempo(1, to=8)`): the block is recorded in local time and
  remapped on exit.
- **Clips** learn their duration by running; when a `duration=` needs the natural duration
  beforehand, the clip runs in speculative mode and the scene is rolled back (IR snapshot +
  Python state).
- **Resolve** iterates handlers → tables → firings until the set of firings stops changing.
- **`k.reparent`** preserves Python identity by swapping the IR node from the instant of the
  swap (the IR has one fixed parent per node).
- **Renderer.** tiny-skia is the default and the reference. The Vello backend (`--features gpu`)
  exists and passes the tolerance tests, but does **not** meet the switch criterion (≥ 3× at
  1080p): typical scenes are even slower on the GPU (fixed cost of ~2 ms per frame). Per the
  spec's rule, it stays optional.
- **Video output.** ffmpeg over a pipe, with bitexact flags (identical bytes across runs).
- **Editing from the preview** (after 1.0). Spans record the exact range of the user's call
  (`co_positions`), so the preview finds a call's arguments with `ast` and rewrites only a
  literal's characters (`kinemo.editing`). Edits go page → Rust server queue → the `dev`
  loop; dragging rebuilds from the edited text in memory and writes the file on release.
  The code stays the only source of truth.

## Not in this release (planned by the spec for v1.x)

- 3D (`@k.scene(camera="3d")`, `s.camera`, `s.hud`, `k.Surface`, ...).
- Interactive web (`--format web`, core in WASM).
- polars expressions translated to the IR; Pyodide on the web.
