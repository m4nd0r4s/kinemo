# Changelog

All notable changes to kinemo are listed here. The project follows
[semantic versioning](https://semver.org/); until 1.0, a minor version may change the API, and
`kinemo upgrade` rewrites the forms it replaces.

## 0.13.0

Components for explanatory videos: terminals, annotation marks, angles, cards, gauges, callouts,
arrays, graphs and a number plane that bends, plus axes that keep their ticks right while they
zoom.

**Added**

- **`k.Terminal`:** a terminal or REPL window. `term.type(cmd)` types a command as `k.Code`
  after the prompt with a caret, `term.output(text)` prints rows (staggered or at once), and
  the window scrolls when full; `term.clear()`.
- **Annotation marks:** `k.underline`, `k.box`, `k.encircle`, `k.strike` and `k.cross` draw
  around any object and follow it.
- **`k.Angle` and `k.RightAngle`:** the arc of the smaller angle between two rays, with a
  label or its measure (`unit="deg"` or `"rad"`), following reactive points.
- **`k.Card`:** a panel around content with a title, caption and accent bar.
- **`k.Gauge`:** a dial with ticks, colored zones, a needle and a readout; `gauge.to(value=)`.
- **`k.Callout`:** a label pointing at an object as a bubble, a box or a leader line.
- **`k.Array`:** cells with indices for algorithm videos: `swap`, `compare`, `set` and
  `pointer`.
- **`k.Graph`:** nodes and edges with `force`, `tree`, `layered` and `circle` layouts (or
  positions), weighted and directed edges, `add_node`, `add_edge`, `remove`, `path` highlights
  and `relayout` transitions.
- **`k.NumberPlane`:** a grid with basis vectors; `plane.apply([[a, b], [c, d]])` or
  `plane.apply(fn)` deforms it, carrying `plane.vector`, `plane.dot`, `plane.polygon` and
  `plane.add(obj, at=)`; `plane.reset()`.
- **Axes:** `ax.add(obj)` puts objects in the axes' coordinates (they follow zooms),
  `ax.origin()` and `ax.in_view(x=, y=)`; `x_ticks=`/`y_ticks=` set tick values and
  `tick_format=` writes their labels.
- The style keyword dicts are public for reusable styles: `k.StyleKeywords`,
  `k.PaintKeywords`, `k.TextKeywords` and the others.

**Changed**

- `ax.zoom_to(...)` regenerates the ticks for the new ranges with a nice step: new ones grow
  in and ones that no longer fit fade out. y tick labels are right-aligned to the axis.
- W1003 (contrast) measures text against the shapes drawn behind it, not only the background.

**Fixed**

- `group.to(children=...)` enters the new children and exits the removed ones.

## 0.12.0

A debugging view in `kinemo dev`: the scene's code follows the playhead, with breakpoints,
stepping, call stacks and watched values. Nothing is edited from it.

**Added**

- **Code tab** beside the inspector: the scene's code (and the local modules it ran), with the
  same colors as `k.Code`; the statements running at the playhead are lit, the latest one
  marked, and **follow** keeps it in view. Selecting a bar or an audio clip shows its line.
- **Run times in the gutter:** when each statement runs (`1.20s`, `×3` for a loop, `◆ mark`);
  click to go there, hover for every run.
- **Breakpoints:** click a line number; playback pauses exactly where a run of that statement
  starts and selects it. A loop can stop on one run, a clip's line on one call site.
  Breakpoints are remembered per browser and follow their line when the file changes.
- **Stepping:** next / previous statement (F10 / Shift+F10) and run to line (F8).
- **Call stacks:** a statement inside a `@k.clip`, a component method or a helper knows the
  lines that called it; the code lights them and the inspector lists them (*Called from*).
- **Watch:** ☆ pins a prop from the inspector; its value at the playhead, flashing when it
  changes, and a sparkline over the scene for numbers.
- **Code and canvas:** names of objects in the code are links (hover draws the object's box,
  click selects it); selecting an object marks the lines that make and animate it.
- **Script tab:** a scene narrated from a `k.Script` shows the script, the beat being narrated
  lit, each beat's time and whether its audio is recorded, stale or estimated.
- The dev page opens on more states from its URL: `pane=code` and `bp=17,20`.

**Changed**

- `kinemo dev` metadata carries the statements of the scene (`play`, `start`, `wait`,
  `wait_for`, `v.at`, voice blocks, `add`/`remove`, marks) with every run, and the highlighted
  source of the files the scene ran.
- The website shows the code view; its editor screenshots are checked before they are published
  (a shot taken before the scene arrived is retaken).

## 0.11.1

Faster narration with heavy voice models, audio in the dev editor, more code languages and
versioned docs, from a first production client's feedback.

**Added**

- **Batch voices:** a `[tts] command` with `{lines_file}` makes every line in one run (a JSON
  list of `{text, out, voice}`), so a model loads once; `kinemo voice` and `kinemo render`
  send all missing lines in one call.
- **The dev editor shows the audio:** Narration, Sounds and Music tracks under the timeline.
  Clicking a line shows its full text (each word moves the playhead), its beat and script
  line, the audio file, where the word times come from, the warnings on its line, and plays
  just that line. Music is mixed as in the video (fades, duck under the voice).
- **`k.Code` languages:** Java, Kotlin, Go, C#, Swift, Ruby, Haskell, Bash, SQL, HTML, CSS,
  YAML and TOML (with their common aliases); JSON keys get their own color.
- **`kinemo inspect --at 0,B03,end`** inspects several instants from one build (and `marks`);
  so does the MCP `inspect` tool.
- **Subtitles for movies:** `kinemo render --subtitles` on a `k.movie` covers the whole movie.
- **Versioned docs** on the website: `latest`, each release (`0.11`, `0.10`, ...) and `dev`,
  with a version switcher.

**Changed**

- `kinemo check` never calls the voice model: lines without audio are estimated and hint
  `W1405` names them (`--strict` does not fail on it). `[tts] on_build` chooses for other
  builds (`estimate` by default for the command provider); `kinemo render` makes missing lines
  before rendering.
- Source links in the dev editor open the editor of `[editor] command` (`cursor`, `zed`,
  `idea`, `pycharm`, `sublime`, ... by URL, or any command with `{file}` and `{line}`).
- Timeline: marks at one instant share a label (`B01.end · B02`) and never overlap; zero-length
  entries are ticks in their own row; the timeline can be resized.
- Objects made in a list are named after it (`squares[0]`); `k.Square.on` names its result.

**Fixed**

- `k.Code` with an unsupported `lang=` drew nothing and reported nothing: it is `K0802`, listing
  the languages and suggesting the closest.
- `k.sound` and `k.music` were labelled `instant` on the timeline.
- A movie scene's music kept playing over the next scenes.
- The site's editor screenshots are taken on every deploy.

## 0.11.0

Narration and tooling: a narrated video made from a script, timed by its words, mixed and
subtitled, and a CLI that agents and editors can drive.

**Added**

- **`k.Voice`:** `with s.voice(...) as v` gives the line: `v.at(0.5)` and `v.at("the slope")`
  wait for a point of the line, `v.time(...)` gives the instant, and `v.start`, `v.end`,
  `v.words` say when it is spoken. `W1403` warns when a block's animations outlast its
  narration.
- **`k.Script`:** narration in its own Markdown (or JSON) file, beat by beat. A beat uses
  `audio/<id>.wav` next to the script when it exists, adds the marks `<id>` and `<id>.end`,
  and `W1404` reports a beat whose audio was made from another text.
- **`kinemo voice`:** makes only the narration that has no audio yet or a stale one
  (`--check`, `--force B03`), with the configured provider.
- **`[tts] provider = "command"`** runs any program for each line (`{text_file}`, `{out}`,
  `{voice}`), so a voice can live in another environment; `[tts] wpm` sets the speaking rate
  of the silent estimate. Failures are `K1401`.
- **Word times for recorded audio:** with `pip install "kinemo[align]"`, words are aligned to
  the audio by speech recognition (`[align] model`); without it, they are estimated from
  syllables. `kinemo check --json` lists each line's `narration`, with its `timing`.
- **Audio mix:** `k.music(path, gain, duck, fade)` is lowered while a voice speaks; voices,
  sounds and music are mixed in groups and limited. `[audio] loudness` normalizes the track
  (LUFS) and `[audio] trim_silence` cuts the silence around each line.
- **Subtitles:** `kinemo render --subtitles` writes `.srt` and `.vtt` next to the video,
  timed by the words.
- **The dev preview plays the audio** (narration, sounds, music), with a mute button.
- **`kinemo snap`:** `--at` takes marks shifted by seconds or by a share of the beat
  (`B01+1.5`, `B01+50%`) and `marks` (every mark); `--sheet` writes one labelled contact sheet.
  `kinemo check --json` lists each scene's `marks`.
- **`--progress json`** on `render` and `voice`: one JSON object per line on stderr.
- **`bleed=True`** declares an object cropped by the frame on purpose; it and objects entirely
  offstage are left out of `W1001`.

**Changed**

- Timeline entries are labelled with the calls as written in the scene.
- A curve's label (`ax.plot(..., label=...)`) fades in as a growing curve reaches its end.
- Contrast and size checks skip objects in the middle of a fade, and `W1005` reports only
  objects that are never seen again.

**Fixed**

- The CLI reference showed argparse's `%%` escape.

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
