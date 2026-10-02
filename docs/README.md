# kinemo documentation

kinemo is a Python library for explanatory animations (math, algorithms, engineering,
data) with a native Rust core, live preview and an API designed to be written by people
and by AI without mistakes.

## Guides

Read them in order the first time; each one builds on the previous.

| # | Guide | What you learn |
| --- | --- | --- |
| 1 | [Getting started](guide/01-getting-started.md) | Install, first scene, the check → dev → render loop |
| 2 | [Mental model](guide/02-mental-model.md) | Build → resolve → render, the cursor, `.now` vs `x()`, the seven rules |
| 3 | [Timeline](guide/03-timeline.md) | `play`/`start`/`wait`, composition, `during`, `tempo`, marks, clips |
| 4 | [Objects and layout](guide/04-objects-and-layout.md) | Lifecycle, props, constraints, containers, groups, copies |
| 5 | [Animations](guide/05-animations.md) | Verbs, easing, morphs, emphasis, motion along paths |
| 6 | [Reactive values](guide/06-reactive.md) | Signals, expressions, tracing, `k.python`, time |
| 7 | [Components](guide/07-components.md) | `k.Component` with props, outs and events; context |
| 8 | [Events and simulation](guide/08-events-and-simulation.md) | `k.when`, handlers, `wait_for`, integrals, simulations, trails |
| 9 | [Text, math and code](guide/09-text-math-code.md) | Markup and parts, LaTeX without TeX, code highlighting and morphs |
| 10 | [Charts and data](guide/10-charts-and-data.md) | Axes, plots, zoom, polar axes, bar/line charts, tables, Arrow data |
| 11 | [Mass objects](guide/11-mass-objects.md) | Points, vector fields and stream lines drawn in batches |
| 12 | [Media](guide/12-media.md) | Images, SVG with addressable parts, braces, boolean shapes |
| 13 | [Output](guide/13-output.md) | Video/GIF/PNG/SVG/slides, quality, parameters, movies, voice |
| 14 | [Tooling](guide/14-tooling.md) | `check`, `inspect`, `snap`, `dev`, `--fix`, testing with pytest |
| 15 | [AI agents](guide/15-ai-agents.md) | The agent loop, `llms.txt`, JSON outputs, the MCP server |

## Reference

- [API reference](reference/README.md) — every public symbol, with signatures, props,
  parameters and canonical examples (generated from the code).
- [Diagnostics](reference/diagnostics.md) — every error and lint code with its fix.
- [CLI](reference/cli.md) — every `kinemo` command and option.
- [Configuration](reference/configuration.md) — `kinemo.toml`, `@k.scene` options,
  sizes and quality presets.
- [llms.txt](llms.txt) — the compact reference for language models.

## More

- [Examples](examples/README.md) — complete scenes with rendered frames.
- [Caveats](caveats.md) — behaviors that surprise people, known limitations, workarounds.
- [Specification](specs.md) — the design document kinemo implements.
- [Implementation status](status.md) — what this release delivers and the decisions it made.

## Keeping the docs current

The API reference, `llms.txt` and the example gallery are generated; tests fail when the
committed files drift from the code:

```bash
python -m kinemo.docs.markdown docs/reference   # API reference
python -m kinemo.docs.llms > docs/llms.txt      # reference for language models
python scripts/build_gallery.py                 # example pages and frames
```
