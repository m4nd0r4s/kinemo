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
kinemo render scene.py --scene intro --out docs/intro.gif   # one file: the format comes from its extension
kinemo render scene.py --format png --at 2.5    # one frame
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--scene NAME` | every scene | Which `@k.scene` function to render |
| `--format` | `mp4` (or the `--out` file's extension) | `mp4`, `webm`, `mov`, `gif`, `png`, `svg`, `slides` |
| `--quality` | `final` | `draft` or `final` (see [Quality](#quality-and-size)) |
| `--out PATH` | `out` | Output folder, created if needed; files are named after the scene. A path with an output extension (`intro.mp4`, `still.png`) is one file instead, for one scene. |
| `--at T` | `end` | For `png`/`svg`: seconds, a mark name, or `end` |
| `--frames` | off | For `png`: the whole sequence, `out/<scene>/00000.png`, ... |
| `--transparent` | off | Transparent background where the format supports it |
| `--progress` | `bar` | On stderr: a progress bar, `json` (one object per line: `{"event": "progress", "scene", "done", "total"}`, then `{"event": "done", "scene", "path"}`) for tools, or `none` |
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

```python signature
with s.voice(narration, *, text=None, voice=None, gain=1.0) as v:
    ...
```

A narrated block. `narration` is either text, spoken by the TTS provider configured for the
project, or the path of an audio file (`.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.aac`), with
`text=` saying what the file says (its words then get times and marks). The
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

### Syncing with the line: `k.Voice`

`with s.voice(...) as v` gives the line as a `k.Voice`, so animations follow what is being
said instead of hand-tuned waits:

| Member | Meaning |
| --- | --- |
| `v.at(0.5)` | Wait until halfway through the line (the cursor moves; already past it, it stays) |
| `v.at("the slope")` | Wait until the phrase starts (`occurrence=2` for its second appearance) |
| `v.time(...)` | The same instant without waiting, for `s.start(..., at=...)` |
| `v.start`, `v.end`, `v.duration` | When the line starts and ends, in scene seconds |
| `v.words` | `(word, start, end)` of every word |

```python
import kinemo as k


@k.scene
def slope(s: k.Scene):
    curve = k.Arc(r=2, angle=120).place(at="center")
    with s.voice("A curve has a slope at every point, and the slope can change") as v:  # kinemo: allow W1401
        s.play(k.draw(curve), duration=1.5)
        v.at("the slope")
        s.play(k.indicate(curve), duration=0.6)
    s.wait(0.5)
```

A phrase that the line does not contain is an error that suggests the closest words. When
the animations of a block last longer than its narration, `W1403` warns: the next line would
start late, with a silence.

### Narration from a script: `k.Script`

A narrated video is easier to write and review when the narration lives in its own file,
beat by beat. `k.Script("script.md")` reads a Markdown file with one heading per beat (the
first word is its id) and the beat's narration on `> ` lines; other lines are notes:

```markdown
### B01 · The claim (~4 s)

> Every right triangle hides a relation between its sides.

### B02 · The relation

> The square on the long side equals the two other squares.
```

JSON works too: `{"B01": "...", "B02": "..."}`. In the scene, `s.voice(script["B01"])`
narrates a beat:

- When `audio/B01.wav` (or `.mp3`, ...) exists next to the script, it is used, with the
  beat's text giving its words. Otherwise the beat is spoken by the TTS provider, or estimated.
- The beat adds the marks `B01` (its start) and `B01.end` (the end of its narration), for
  `kinemo snap --at B01+50%` and `s.start(..., at=s.marks["B01.end"])`.
- `audio/manifest.json` records the text each audio was made from; when the script changes
  afterwards, `W1404` reports the stale beat.

An unknown id is an error that suggests the closest one.

### Word times of recorded audio

Marks, `v.at("phrase")` and subtitles need to know when each word is said. TTS providers
can give it; for a recording, or a provider that gives none, kinemo finds it:

- With the optional extra, `pip install "kinemo[align]"` (faster-whisper, CPU), the audio is
  transcribed with word timestamps and matched to the known text, so a misheard word only
  blurs itself. The model (`[align] model`, `base.en` by default) downloads on first use;
  results are cached by audio and text.
- Without it, the times are estimated from each word's syllables and the pauses its
  punctuation implies.

`kinemo check --json` tells which was used for each line (`timing`: `provider`, `aligned`,
`syllables`, or `estimated` when there is no audio yet).

### Making the audio: `kinemo voice`

`kinemo voice scene.py` builds the scenes without synthesizing, lists their narration lines,
and makes only those that have no audio yet or whose text changed since their audio was made,
with the provider configured in `kinemo.toml`:

```bash
kinemo voice scene.py --check        # list missing and stale lines; exit 1 if any
kinemo voice scene.py                # make them
kinemo voice scene.py --force B03    # make a beat again (or --force all)
```

A script beat is written next to the script: `audio/B03.wav`, its word times in
`audio/B03.wav.json` (from the provider, or aligned to the audio), and its text hash in
`audio/manifest.json`. A line written in the scene goes to the cache, where builds find it.
`--progress json` reports progress as JSON lines, and `kinemo check --json` lists each scene's
`narration`: start, end, text, beat, audio and where its word times come from (`timing`).

### Subtitles

`kinemo render scene.py --subtitles` also writes `scene.srt` and `scene.vtt` next to the video,
from the narration: cues of at most two lines of 42 characters, timed by the words (so they
follow the audio when its word times were aligned), and a sentence end closes a cue. A scene
without narration writes none.

### Without a TTS provider

When no provider is configured, the voice becomes **silence with an estimated duration**
(150 words per minute), marks are spread over the estimate, and lint `W1401` warns. The
scene can be timed, previewed and checked without a network or a model. The
`# kinemo: allow W1401` comment on the `with` line keeps `check --strict` passing while you
write; remove it once a provider is set.

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

### A voice from another program: `provider = "command"`

A voice that lives outside kinemo's environment (another Python, a large model) is run as a
command, with no package to install:

```toml
[tts]
provider = "command"
command = [".venv-voice/bin/python", "tools/voice.py", "{text_file}", "{out}", "{voice}"]
wpm = 170
```

For each line, kinemo writes the text to a UTF-8 file and runs the command from the project
root, replacing `{text_file}`, `{out}` (the WAV to write) and `{voice}` (`voice=`, or empty).
If the program also writes `{out}.json` with `{"word_times": [...]}` (each word's start, in
seconds), the marks are exact; otherwise the words are aligned to the audio (see below). The audio is cached
like any provider's; changing the command makes new audio. A command that fails is `K1401`,
with the end of its error output.

A model that takes long to load should make **every line in one run**: with `{lines_file}`
in the command, kinemo writes one UTF-8 JSON file listing the lines and runs the command once,
and `kinemo voice` makes all its missing lines that way:

```toml
[tts]
provider = "command"
command = [".venv-voice/bin/python", "tools/voice.py", "{lines_file}"]
```

```python
# tools/voice.py: load the model once, then write every line.
import json
import sys

lines = json.load(open(sys.argv[1], encoding="utf-8"))  # [{"text", "out", "voice"}, ...]
model = load_model()
for line in lines:
    model.speak(line["text"], voice=line["voice"]).save(line["out"])  # optionally out + ".json"
```

A line whose file is missing when the program exits is `K1401`, naming it. A build that needs
one line runs the same command with a list of one.

`wpm` (words per minute, 150 by default) is the speaking rate of the silent estimate used
when there is no audio yet: set it to your voice's rate so drafts are timed like the final.

### Recorded narration

An audio file is used as is: the block lasts as long as the file. Pass what it says as
`text=` to give its words times (aligned to the file), `[word]{name}` marks and phrases for
`v.at(...)`: `s.voice("audio/B03.wav", text="...")`.

A string that ends with an audio extension (`.wav`, `.mp3`, ...) is a file; any other
string is text to speak. A relative path starts from the scene file's folder, like
`k.Image`, and a missing file is `K0105` in `check`. The snippet below assumes a
`narration.wav` next to the scene file:

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

### Music and the final mix

`k.music(path, gain=0.3, duck=0.25, fade=1.0)` plays background music from the scheduled
instant to the end of the scene. While a voice speaks, the music drops to `duck` of its level
(`1` keeps it as is), and it fades in over `fade` seconds and out at the end of the scene.

The audio track is mixed in groups (voices, sounds, music) and limited so overlapping clips
never clip. Two project settings finish it:

```toml
[audio]
loudness = -16        # LUFS: normalize the track (web platforms use -14 to -16)
trim_silence = true   # cut the silence TTS models and recordings leave around each line
```

`trim_silence` works when a line is measured, so the line's length, its marks and the next
line's start all follow the trimmed audio.

### A narrated video, end to end

The pieces above make one workflow. The narration lives in `script.md`, next to the scene:

```markdown
### B01 · The claim

> Every right [triangle]{tri} hides a relation between its sides.

### B02 · The relation

> The square on the long side equals the two other squares.
```

The scene narrates beat by beat and follows the words:

```python
import kinemo as k

script = k.Script("script.md")


@k.scene
def pythagoras(s: k.Scene):
    tri = k.Triangle.right(3, 4, scale=0.6).place(at="center")
    with s.voice(script["B01"]):  # kinemo: allow W1401
        s.play(k.draw(tri))
    s.start(k.indicate(tri), at=s.marks["tri"])
    with s.voice(script["B02"]) as v:  # kinemo: allow W1401
        v.at("the two other squares")
        s.play(k.indicate(tri), duration=0.6)
    s.wait(0.5)
```

While drafting there is no audio: every line is estimated, so the timing is already close.
Then:

```bash
kinemo voice scene.py --check                      # which beats have no audio, or a stale one
kinemo voice scene.py                              # make them (or record audio/B01.wav, ...)
kinemo snap scene.py --at marks --sheet            # one contact sheet, a frame per mark
kinemo render scene.py --quality final --subtitles # the video, scene.srt and scene.vtt
```

Editing a line of `script.md` marks its beat stale (`W1404`); `kinemo voice` makes only that
one again, and the marks, the waits on `v.at(...)` and the subtitles follow the new audio.

## Common mistakes

> | Diagnostic | What happened | Fix |
> | --- | --- | --- |
> | `W1401` | `s.voice("...")` with no TTS provider: silence with an estimated duration. | Configure `[tts] provider` in `kinemo.toml`, or add `# kinemo: allow W1401` while drafting. |
> | `W1402` | `[tts] provider` names a provider that is not installed (a typo, or the package is missing): silence with an estimated duration. | Fix the name (the message lists the installed providers) or install `kinemo-tts-<name>`. |
> | `K1401` | The `command` TTS provider failed: no command, it could not start, it exited with an error or wrote no audio. | Run the command by hand with a short text; check `[tts] command`. |
> | `W1403` | The animations of a voice block run past its narration: the next line starts late, after a silence. | Shorten or speed up the animations, sync them with `v.at(...)`, or lengthen the line. |
> | `W1404` | A script beat's audio was made from a different text: the script changed after the audio was made. | Make the audio again for that beat. |
> | `W1301` | A parameter read with `.now`, so its value is frozen at build time. | Pass the signal itself to props and lambdas. |
> | `K0105` | `--param` value out of range, not one of the `k.Choice` options, or an unknown parameter name. | Check the name and the range in `params=`. |
> | `W0110` | `s.play(..., at=s.marks["x"])` does not move the cursor. | Write `s.start(..., at=...)`. |
> | `W1001` | Objects outside the safe area after switching to `size="vertical"` or `"square"`. | The frame is 9 units wide there: use containers, `.fit(s.frame.safe)`, or smaller sizes. |
> | `K0105` | `s.voice("narration.wav")` or `k.sound("click.wav")` where the file does not exist. | Fix the path: relative paths start from the scene file's folder. |
> | none (no alpha) | `--transparent` with `mp4` or `gif`. | Use `webm`, `mov` or `png`. |

See also: [Output reference](../reference/output.md), [Parameters](../reference/parameters.md),
[`s.voice`](../reference/scene.md#scene-voice), [`s.mark`](../reference/scene.md#scene-mark),
[Command line](../reference/cli.md#render), [Configuration](../reference/configuration.md).
