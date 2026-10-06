# kinemo

[![CI](https://github.com/m4nd0r4s/kinemo/actions/workflows/ci.yml/badge.svg)](https://github.com/m4nd0r4s/kinemo/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/kinemo)](https://pypi.org/project/kinemo/)
[![License: MIT OR Apache-2.0](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue)](#license)

**[Website and documentation](https://m4nd0r4s.github.io/kinemo/)**

Explanatory animations (math, algorithms, engineering, data) written in Python, with a live
preview and a native core in Rust. The API was designed to be written by people and by AI
without errors: one form per concept, full typing, and errors that already carry the fix.

![A tangent sliding along a curve, with the code that makes it](docs/media/hero.gif)

<sub>Made with kinemo: [docs/media/hero.py](docs/media/hero.py).</sub>

```python
import kinemo as k

@k.scene
def hello(s: k.Scene):
    title = k.Text("Hello, kinemo").place(at="center")
    s.play(k.write(title))
    s.play(title.to(color=k.BLUE, scale=1.5))
    s.wait(1)
```

```bash
pip install kinemo
kinemo new my-video        # a project with a first scene (then cd my-video)
kinemo dev scene.py        # browser preview with hot reload and a draggable timeline
kinemo check scene.py      # errors, lints and timeline summary, without rendering
kinemo render scene.py     # MP4 (also webm, mov, gif, png, slides)
```

## Why kinemo

- **See it while you write it.** `kinemo dev` re-renders on save and lets you scrub to any
  instant; the frame at `t` is a pure function of `t`, so jumping around is instant.
- **Mistakes are caught before you render.** Lints find text that leaves the frame, overlaps,
  is too small or has too little contrast, at the instant it happens, with the fix;
  `kinemo check --fix` applies the safe ones.
- **Fast.** The timeline, layout, text, math and rendering are Rust, and frames render in
  parallel on every core.
- **Nothing else to install.** Math is typeset without LaTeX, code is highlighted with
  tree-sitter, fonts are embedded. Video needs ffmpeg, and that is all.
- **Built for agents.** Typed, one way to do each thing, machine-readable checks and an MCP
  server: a model can write a scene, check it and fix it without looking at frames.

### Compared with Manim

[Manim](https://www.manim.community/) is the reference for this kind of video, and it
inspired kinemo. Choose by what you need:

| | Manim | kinemo |
|---|---|---|
| Maturity | Years of use, a large community, many tutorials and plugins | Young (pre-1.0), a small community |
| 3D | Yes | Not yet (2D only) |
| LaTeX | Needs a TeX installation | Built in (typst), no TeX |
| Preview | Render, then watch | Live preview with a scrubbable timeline |
| Time model | Animations run as the script runs | The script builds a timeline first: scrub, parallel render, caching |
| Errors | Python tracebacks | Coded diagnostics with line, instant and fix; visual lints |
| Narration | Plugins | Built in: TTS or recorded audio, word timing, subtitles |

Coming from Manim: `Create`, `.animate` and other Manim names are recognized and the error
names the kinemo form; the [mental model](docs/guide/02-mental-model.md) explains the
differences.

## What kinemo does

- **The script runs once and produces a timeline.** The frame at `t` is a pure function of `t`:
  you can scrub the timeline, render in parallel and keep everything cached.
- **Explicit time.** `s.play` blocks the cursor, `s.start` does not; `k.seq`, `k.par`,
  `k.stagger`, `s.during`, `s.tempo` and clips (`@k.clip`) compose animations as values.
- **Constraint layout.** `.place(above=tri)`, `k.Row`, `k.Grid`: the relations keep holding
  while the objects move.
- **Reactive signals.** `x.to(3)`, `k.Text(lambda: f"{x():.1f}")`, `ball.set(x=other.x)`.
  Lambdas and `.map` are traced to native code; opaque Python only with `k.python(fn)`.
- **Events and stateful systems.** `k.when`, `@event.on`, `s.wait_for`, `k.integrate`,
  `k.simulate` — resolved before rendering, up to a fixed point.
- **Text, code and math** with addressable parts (`txt["world"]`, `code.highlight`)
  and `k.morph` between versions.
- **Charts and data.** `k.Axes`, plots that grow with a signal, animated zoom; data via
  Arrow (polars, pandas, pyarrow, duckdb) without copying.
- **Narration.** `s.voice` speaks with a TTS provider, any voice program or recorded audio,
  beat by beat from a script (`k.Script`); animations follow the words (`v.at("the slope")`),
  music ducks under the voice, and `kinemo render --subtitles` writes SRT and WebVTT.
- **Stable diagnostics.** Every error has a code (`K0401`), line, instant and fix;
  `kinemo check --fix` applies the safe ones. Manim names (`Create`, `.animate`) are
  recognized and translated.
- **Built for agents.** `kinemo check --json`, `kinemo inspect --json`, `kinemo snap` and the
  `kinemo mcp` server close the write → verify → fix loop without needing vision.

## Installation

```bash
pip install kinemo
```

Wheels for Linux, macOS and Windows, Python ≥ 3.11. Video output needs
[ffmpeg](https://ffmpeg.org/):

| System | Command |
|---|---|
| macOS | `brew install ffmpeg` |
| Windows | `winget install Gyan.FFmpeg` (or `choco install ffmpeg`) |
| Ubuntu, Debian | `sudo apt install ffmpeg` |
| Fedora | `sudo dnf install ffmpeg` |
| Arch | `sudo pacman -S ffmpeg` |

`kinemo doctor` shows what kinemo finds (Python, ffmpeg, extras); PNG and SVG frames and
`kinemo dev` work without ffmpeg. `pip install "kinemo[align]"` adds word timing for recorded
narration (speech recognition).

### Status

kinemo is before 1.0: the API can still change between minor versions. When it does,
`kinemo upgrade scene.py` rewrites the old forms, and the [changelog](CHANGELOG.md) says what
changed. kinemo collects no telemetry and makes no network requests of its own (a TTS
provider you configure for narration is the only exception).

### Questions and bugs

Questions, ideas and things you made go in
[Discussions](https://github.com/m4nd0r4s/kinemo/discussions); bugs go in
[issues](https://github.com/m4nd0r4s/kinemo/issues) (paste the output of `kinemo doctor`).

### From source

Requirements: stable Rust, Python ≥ 3.11, [uv](https://github.com/astral-sh/uv) and `ffmpeg`.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the tests and conventions.

```bash
uv venv .venv
uv pip install --python .venv/bin/python maturin pytest numpy polars
source .venv/bin/activate
maturin develop
```

GPU preview (optional): `maturin develop --features gpu` compiles the Vello (wgpu) backend
and the `kinemo dev` server then rasterizes on the GPU when an adapter is available,
falling back to the CPU (tiny-skia) otherwise. The default build does not include wgpu. The
final render stays on the CPU, which is the reference.

## Tests

```bash
cargo test --workspace          # Rust core
python -m pytest -q             # API, diagnostics, contracts and golden snapshots
```

Golden snapshots live in `tests/golden/` (CPU renderer, byte-identical). To regenerate
them after an intentional change: `KINEMO_UPDATE_GOLDEN=1 pytest tests/python/test_golden.py`.

## Architecture

The author only sees Python; everything below the IR is Rust.

```
python/kinemo/        public API (k.*), build phase, handlers, CLI
crates/kinemo-ir      IR types (serializable scene)
crates/kinemo-eval    timelines, expressions, easing, colors (OKLab)
crates/kinemo-layout  geometry, containers, constraints, glyphs
crates/kinemo-text    text (rustybuzz), embedded fonts
crates/kinemo-code    code highlighting (tree-sitter) and diff
crates/kinemo-math    LaTeX → typst, no TeX installation
crates/kinemo-resolve sampling-based visual lints
crates/kinemo-render  display list, tiny-skia, morph, movies, segments
crates/kinemo-render-gpu  optional Vello (wgpu) backend, tolerance tests vs tiny-skia
crates/kinemo-encode  ffmpeg (mp4, webm, mov, gif)
crates/kinemo-server  preview (axum + WebSocket)
crates/kinemo-py      PyO3 bindings (the only crate that knows about Python)
```

## Documentation

Start with the [documentation index](docs/README.md): numbered guides from
[getting started](docs/guide/01-getting-started.md) onwards, the complete
[API reference](docs/reference/README.md), [examples](docs/examples/README.md) with
rendered frames, and [caveats](docs/caveats.md). The design document is
[docs/specs.md](docs/specs.md).

The same docs, with a landing page and the examples as videos, build into a static SvelteKit
website: see [website/README.md](website/README.md).

## License

Licensed under either of [Apache License 2.0](LICENSE-APACHE) or [MIT](LICENSE-MIT), at your
option. Unless you state otherwise, any contribution you submit for inclusion in kinemo is
dual-licensed as above, without any additional terms.

The embedded DejaVu fonts follow [their license](assets/fonts/LICENSE_DEJAVU). The licenses of
the Rust crates compiled into the wheels are in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)
(`scripts/third_party_licenses.py` regenerates it).
