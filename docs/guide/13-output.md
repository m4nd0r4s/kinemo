# Output: formats, quality, parameters, movies and voice

One scene file produces every output: a video for publishing, a GIF for a README, a single
PNG or SVG frame for a document, or an HTML slide deck for a talk. This guide covers:

- `kinemo render` and its formats;
- quality presets, sizes and transparent backgrounds;
- scene parameters and `--param`;
- movies (several scenes with transitions);
- narration with `s.voice` and TTS providers, and sound effects with `k.sound`.

Before rendering, run `kinemo check --strict` (see [Tooling](14-tooling.md)). Rendering builds
the scene the same way and fails on the same errors, so checking first is faster.

## `kinemo render`

```bash
kinemo render scene.py                          # every scene in the file → out/<scene>.mp4
kinemo render scene.py --scene intro            # one scene
kinemo render scene.py --format gif --out docs/img
kinemo render scene.py --format png --at 2.5    # one frame
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--scene NAME` | every scene | Which `@k.scene` function to render |
| `--format` | `mp4` | `mp4`, `webm`, `mov`, `gif`, `png`, `svg`, `slides` |
| `--quality` | `final` | `draft` or `final` (see [Quality](#quality-and-size)) |
| `--out DIR` | `out` | Output folder, created if needed. Files are named after the scene. |
| `--at T` | `end` | For `png`/`svg`: seconds, a mark name, or `end` |
| `--frames` | off | For `png`: the whole sequence, `out/<scene>/00000.png`, ... |
| `--transparent` | off | Transparent background where the format supports it |
| `--param NAME=VALUE` | parameter defaults | Scene parameters (repeatable) |

### Formats

| Format | Output | Notes |
| --- | --- | --- |
| `mp4` | `out/<scene>.mp4` | H.264, the default. Audio (voice, sounds) is muxed as AAC. |
| `webm` | `out/<scene>.webm` | VP9. With `--transparent`, the video keeps an alpha channel. |
| `mov` | `out/<scene>.mov` | ProRes 4444, for video editors. Supports `--transparent`. |
| `gif` | `out/<scene>.gif` | Palette optimized per scene. Keep scenes short. |
| `png` | `out/<scene>.png` | One frame at `--at` (default: the last frame), or every frame with `--frames`. Supports `--transparent`. |
| `svg` | `out/<scene>.svg` | One vector frame at `--at`, for documents. Images are embedded. |
| `slides` | `out/<scene>_slides/index.html` | One video per section and an HTML player (see [Slides](#slides)). |

`mp4` and `gif` have no alpha channel, so `--transparent` has no effect on them.

Output is deterministic: the same source, assets and kinemo version give the same bytes,
so rendered files can be committed and diffed.

## Quality and size

| Preset | Resolution and frame rate | Used by default in |
| --- | --- | --- |
| `draft` | 540p (960 × 540 for 16:9), at most 30 fps, no extra antialiasing | `kinemo snap`, `kinemo dev` |
| `final` | The scene's `size` and `fps` | `kinemo render` |

Use `--quality draft` while iterating on a long render; it is faster.

The size and frame rate come from the scene decorator (or `kinemo.toml`, see
[Configuration](../reference/configuration.md)):

```python
@k.scene(size="vertical", fps=30)
def short(s: k.Scene): ...
```

| `size=` | Pixels | Frame in units |
| --- | --- | --- |
| `"720p"` | 1280 × 720 | 16 × 9 |
| `"1080p"` (default) | 1920 × 1080 | 16 × 9 |
| `"4k"` | 3840 × 2160 | 16 × 9 |
| `"square"` | 1080 × 1080 | 9 × 9 |
| `"vertical"` | 1080 × 1920 | 9 × 16 |
| `(w, h)` | custom | 9 units on the shorter side |

The frame always measures 9 units on its shorter side, so a scene written for 1080p keeps
its layout at 4k. Square and vertical frames are narrower, so check them with
`kinemo check` (lint `W1001` flags objects outside the safe area).

## Slides

`s.mark(name=None, slide=True)` defines a slide break at the cursor. `--format slides`
renders one MP4 per section and writes an `index.html` that plays each section and waits:

```python
import kinemo as k


@k.scene(size="720p", fps=30)
def talk(s: k.Scene):
    title = k.Text("Part 1", size=0.8).place(at="center")
    s.play(k.write(title))
    s.mark("part2", slide=True)
    s.play(title.to(text="Part 2"))
    s.mark("part3", slide=True)
    s.play(title.to(color=k.BLUE, scale=1.4))
    s.wait(0.5)
```

```bash
kinemo render talk.py --format slides     # out/talk_slides/index.html + section_01.mp4, ...
kinemo render talk.py --format png --at part2
```

In the player, Right, Space, Page Down, Enter or a click go to the next section (a first
press skips to the end of a section that is still playing). Left and Page Up go back, and
`f` toggles full screen. The mark name, when given, is shown in the corner and can be used
as `--at` for `png`/`svg`.

## Parameters

Scene parameters are values you can change without editing the code. They are declared in
`params=` and reach the scene function as signals:

| Type | Example |
| --- | --- |
| `k.Int(lo, hi, default=None)` | `k.Int(3, 12, default=5)` |
| `k.Float(lo, hi, default=None)` | `k.Float(0.5, 3, default=1.5)` |
| `k.Bool(default=False)` | `k.Bool(default=True)` |
| `k.Choice(options, default=None)` | `k.Choice(["fast", "slow"])` (default: the first option) |
| `k.Str(default="")` | `k.Str(default="Polygon")` |

```python
import kinemo as k


@k.scene(params={"n": k.Int(3, 12, default=5), "heading": k.Str(default="Polygon")})
def polygon(s: k.Scene, n: k.Signal[int], heading: k.Signal[str]):
    title = k.Text(heading, size=0.6).place(at="top", margin=0.8)
    shape = k.Polygon.regular(n, r=2, fill=k.BLUE, fill_opacity=0.5, name="shape").place(at="center")
    label = k.Text(lambda: f"n = {n():.0f}", size=0.4).place(below=shape, gap=0.3)
    s.play(k.write(title), k.draw(shape), k.fade_in(label))
    s.wait(0.5)
```

```bash
kinemo render polygon.py --param n=8 --param heading=Octagon
kinemo check polygon.py --param n=12      # check, inspect, snap and dev accept --param too
```

- In video, a parameter takes its `default`, or the value from `--param`. Values are parsed
  as an integer, then a float, then text. Out-of-range values, unknown names and options
  that are not in a `k.Choice` are `K0105`.
- For `k.Bool`, pass `0` or `1` (`--param grid=0`).
- A `k.Choice` of colors can only be chosen in code (`default=`). From the command line,
  use choices of numbers or strings.
- **Use parameters as signals**: in props, lambdas and expressions. Reading one with `.now`
  freezes it at build time. Lint `W1301` warns, because that breaks the interactive export
  planned for a later version.

## Movies

`k.movie(scenes, transitions=(), *, name="movie")` composes several scenes into one output,
with one transition per join:

```python
import kinemo as k


@k.scene(size="720p")
def intro(s: k.Scene):
    title = k.Text("Chapter 1", size=0.8).place(at="center")
    sun = k.Circle(r=0.8, key="sun", fill=k.YELLOW, fill_opacity=1).place(at="left", margin=2)
    s.play(k.write(title), k.grow(sun))
    s.wait(0.5)


@k.scene(size="720p")
def body(s: k.Scene):
    sun = k.Circle(r=1.2, key="sun", fill=k.YELLOW, fill_opacity=1).place(at="right", margin=2)
    s.add(sun)
    s.play(sun.to(scale=1.3))
    s.wait(0.5)


@k.scene(size="720p")
def outro(s: k.Scene):
    s.play(k.write(k.Text("Thanks", size=0.8).place(at="center")))
    s.wait(0.5)


movie = k.movie([intro, body, outro], transitions=[k.morph_cut(0.6), k.crossfade(0.5)], name="chapter1")
```

| Transition | Effect |
| --- | --- |
| `k.cut` | Hard cut (the default for joins without a transition) |
| `k.crossfade(duration=0.5)` | The end of one scene dissolves into the start of the next |
| `k.morph_cut(duration=0.5)` | Meant for objects with the same `key=` in neighboring scenes. In 1.0 it renders as a crossfade. |

- `kinemo render movie.py` renders every `k.movie` in the file as one video,
  `out/<name>.mp4` (`--format webm`, `mov` or `gif` for the others). With `--scene`, it
  renders that single scene instead.
- Movies are video only. `png`, `svg` and `slides` apply to single scenes.
- `kinemo check movie.py` checks every scene of the file.
- Give the scenes of a movie the same `size` and `fps`.

## Narration: `s.voice`

```python
with s.voice(narration, *, voice=None, gain=1.0):
    ...
```

A narrated block. `narration` is either text, spoken by the TTS provider configured for the
project, or the path of an audio file (`.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.aac`). The
block lasts **at least as long as the audio**: if the animations inside are shorter, the
cursor waits for the narration to finish.

Words marked `[word]{name}` become time marks at the instant they are spoken, so animations
can be synchronized with the voice:

```python
import kinemo as k


@k.scene
def narrated(s: k.Scene):
    tri = k.Triangle.right(3, 4, scale=0.6).place(at="center")
    with s.voice("Every right [triangle]{tri} hides a relation between its sides."):  # kinemo: allow W1401
        s.play(k.draw(tri))
    s.start(k.indicate(tri), at=s.marks["tri"])
    s.wait(0.5)
```

### Without a TTS provider

When no provider is configured, the voice becomes **silence with an estimated duration**
(150 words per minute), marks are spread over the estimate, and lint `W1401` warns. The
scene can be timed, previewed and checked without a network or a model. The
`# kinemo: allow W1401` comment above keeps `check --strict` passing while you write; remove
it once a provider is set.

### Configuring a provider

Providers are separate packages named `kinemo-tts-<name>`. Install one and select it in
`kinemo.toml`:

```toml
[tts]
provider = "piper"

[cache]
dir = ".kinemo-cache"
```

Generated audio is cached in the cache directory, keyed by provider, voice and text, so
re-rendering does not synthesize again. `voice=` selects a voice of the provider and
`gain=` scales the volume.

A provider is a class with a `name` and a `synthesize(text, voice, out_path)` method that
writes the audio and returns a `kinemo.audio.tts.Speech(path, duration, word_times)`.
`word_times` (the start of each word, in seconds) makes the `[word]{name}` marks exact. The
package exposes a factory in the `kinemo.tts` entry-point group:

```toml
# pyproject.toml of kinemo-tts-mytts
[project.entry-points."kinemo.tts"]
mytts = "kinemo_tts_mytts:Provider"
```

### Recorded narration

An audio file is used as is: the block lasts as long as the file. Marked words are not
available (there is no text to align), so use `s.mark` for sync points.

The path is checked relative to the working directory, and a string is treated as a file
only when it ends with an audio extension **and** the file exists. Otherwise it is read as
text to speak, so a typo in the file name shows up as `W1401` (no TTS provider) or as the
file name being spoken. Run `kinemo` from the folder that holds the audio, or pass an
absolute path. The snippet below assumes a `narration.wav` in the working directory:

```python
import kinemo as k


@k.scene
def narrated_file(s: k.Scene):
    title = k.Text("Recorded narration", size=0.6).place(at="center")
    with s.voice("narration.wav"):
        s.play(k.write(title))
    s.wait(0.5)
```

### Sound effects

`k.sound(path, gain=1.0)` plays a file at the instant it is scheduled. It takes no time in
the script, so it composes with other animations: `s.play(k.sound("click.wav"), k.indicate(button))`.

## Common mistakes

> | Diagnostic | What happened | Fix |
> | --- | --- | --- |
> | `W1401` | `s.voice("...")` with no TTS provider: silence with an estimated duration. | Configure `[tts] provider` in `kinemo.toml`, or add `# kinemo: allow W1401` while drafting. |
> | `W1301` | A parameter read with `.now`, so its value is frozen at build time. | Pass the signal itself to props and lambdas. |
> | `K0105` | `--param` value out of range, not one of the `k.Choice` options, or an unknown parameter name. | Check the name and the range in `params=`. |
> | `W0110` | `s.play(..., at=s.marks["x"])` does not move the cursor. | Write `s.start(..., at=...)`. |
> | `W1001` | Objects outside the safe area after switching to `size="vertical"` or `"square"`. | The frame is 9 units wide there: use containers, `.fit(s.frame.safe)`, or smaller sizes. |
> | `W1401` | `s.voice("narration.wav")` where the file does not exist (or the working directory is different): the string is read as text to speak. | Fix the path, run from the folder that holds the file, or pass an absolute path. |
> | none (render error) | `k.sound("click.wav")` with a missing file passes `check`, but `render` stops with "audio file not found". | Check the path. Unlike `k.Image`, it is resolved from the working directory, not from the scene file's folder. |
> | none (no alpha) | `--transparent` with `mp4` or `gif`. | Use `webm`, `mov` or `png`. |

See also: [Output reference](../reference/output.md), [Parameters](../reference/parameters.md),
[`s.voice`](../reference/scene.md#scene-voice), [`s.mark`](../reference/scene.md#scene-mark),
[Command line](../reference/cli.md#render), [Configuration](../reference/configuration.md).
