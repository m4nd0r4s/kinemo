"""Scene and timeline: `@k.scene`, `s.play`, `s.start`, `s.wait`, blocks, `k.time`."""

from __future__ import annotations

from ..entry import DocEntry

ENTRIES = (
    DocEntry(
        "k.scene",
        "Scene",
        "Turns a function `def name(s: k.Scene)` into a scene. The body runs exactly once, "
        "in the build phase, and produces a timeline; the frame at time t is a pure function of t. "
        "The decorator arguments (size, fps, background, seed, tail, theme, parameters) take "
        "precedence over `kinemo.toml`.",
        '''
import kinemo as k

@k.scene(size="1080p", fps=60, tail=0.5)
def hello(s: k.Scene):
    title = k.Text("Hello, kinemo").place(at="center")
    s.play(k.write(title))
    s.play(title.to(color=k.BLUE, scale=1.5))
    s.wait(1)
''',
        related=("Scene.play", "k.Text", "k.Int"),
        signature='@k.scene(size="1080p", fps=60, background=None, seed=0, tail=0.5, theme=None, camera="2d", params=None, name=None)',
    ),
    DocEntry(
        "Scene.play",
        "Scene",
        "Schedules animations at the cursor and advances the cursor to their end. Multiple "
        "arguments run in parallel (`s.play(a, b)` is by definition `s.play(k.par(a, b))`). "
        "`duration=` sets the total duration of the group, rescaling its contents.",
        '''
import kinemo as k

@k.scene
def steps(s: k.Scene):
    a = k.Circle(r=0.8).place(at="center")
    b = k.Square(1.4).place(right_of=a, gap=0.6)
    s.play(k.draw(a), k.draw(b), duration=2)
    s.play(a.to(color=k.RED))
''',
        related=("Scene.start", "k.par", "Scene.wait"),
    ),
    DocEntry(
        "Scene.start",
        "Scene",
        "Schedules animations at the cursor without moving it: this is how to run something in the "
        "background (clocks, simulations, continuous motion) while the script continues. Returns a "
        "`TimeSpan`; `h.done` is an event at the end of the animation.",
        '''
import kinemo as k

@k.scene
def background(s: k.Scene):
    dot = k.Dot(r=0.2, x=-4)
    title = k.Text("In parallel").place(at="top", margin=0.8)
    s.add(dot)
    s.start(dot.to(x=4), duration=3)
    s.play(k.write(title))
    s.wait(2)
''',
        related=("Scene.play", "Scene.wait_for", "k.simulate"),
    ),
    DocEntry(
        "Scene.wait",
        "Scene",
        "Advances the cursor by `d` seconds (default 1). It is the script's pause: nothing is "
        "scheduled, but whatever was started with `s.start` keeps running.",
        '''
import kinemo as k

@k.scene
def pause(s: k.Scene):
    title = k.Text("Think for a moment").place(at="center")
    s.play(k.write(title))
    s.wait(1.5)
    s.play(k.fade_out(title))
''',
        related=("Scene.play", "Scene.mark"),
    ),
    DocEntry(
        "Scene.wait_for",
        "Scene",
        "Moves the main cursor to the time of an event (the `count`-th firing after the "
        "cursor) and returns the `EventInfo`. It only sees what has already been scheduled, so the "
        "usual pattern is `s.start(...)` followed by `s.wait_for(...)`. `timeout=` is required "
        "when the source has no guaranteed end.",
        '''
import kinemo as k

@k.scene
def wait_for_it(s: k.Scene):
    dot = k.Dot(r=0.2, x=-5)
    title = k.Text("Moving...").place(at="top", margin=0.8)
    s.add(dot)
    h = s.start(dot.to(x=5), duration=3)
    s.play(k.write(title))
    s.wait_for(h.done)
    s.play(k.fade_out(dot, title))
''',
        related=("k.when", "EventSource.on", "Scene.start"),
    ),
    DocEntry(
        "Scene.add",
        "Scene",
        "Puts objects in the scene instantly, at the cursor. Creating an object does not put it in "
        "the scene: it enters with `s.add` or with an entrance verb (`k.draw`, `k.write`, "
        "`k.fade_in`, `k.grow`).",
        '''
import kinemo as k

@k.scene
def instant(s: k.Scene):
    box = k.Rect(w=3, h=1.5).place(at="center")
    label = k.Text("Ready").place(inside=box)
    s.add(box, label)
    s.wait(1)
    s.play(box.to(color=k.GREEN))
''',
        related=("Scene.remove", "k.draw", "k.fade_in"),
    ),
    DocEntry(
        "Scene.remove",
        "Scene",
        "Takes objects out of the scene instantly, at the cursor. After that the object does not "
        "accept `.to()` (error K0102) until it enters again with an entrance verb.",
        '''
import kinemo as k

@k.scene
def cut(s: k.Scene):
    a = k.Text("Before").place(at="center")
    b = k.Text("After").place(at="center")
    s.add(a)
    s.wait(1)
    s.remove(a)
    s.add(b)
    s.wait(1)
''',
        related=("Scene.add", "k.fade_out", "k.shrink"),
    ),
    DocEntry(
        "Scene.mark",
        "Scene",
        "Creates a time anchor at the cursor without moving it and returns the time. Named marks "
        "are stored in `s.marks[name]` (useful with `at=`); `slide=True` defines a slide break "
        "for `kinemo render --format slides`.",
        '''
import kinemo as k

@k.scene
def presentation(s: k.Scene):
    title = k.Text("Part 1").place(at="center")
    s.play(k.write(title))
    s.mark("part2", slide=True)
    s.play(title.to(text="Part 2"))
    s.wait(1)
''',
        related=("Scene.start", "Scene.voice"),
    ),
    DocEntry(
        "Scene.during",
        "Scene",
        "`with` block that applies state changes on entry and reverts them, animated, on exit. "
        "The revert uses the same duration and easing; `revert=\"instant\"`, `revert=0.3` or "
        "`revert=k.ease.out` change that. Only accepts reversible animations (`.to`, `k.indicate`).",
        '''
import kinemo as k

@k.scene
def highlight(s: k.Scene):
    a = k.Circle(r=0.6)
    b = k.Circle(r=0.6)
    row = k.Row(a, b, gap=1).place(at="center")
    s.play(k.draw(row))
    with s.during(a.to(color=k.YELLOW), b.to(color=k.YELLOW), duration=0.3):
        s.play(row.swap(0, 1))
    s.wait(0.5)
''',
        related=("Node.to", "k.indicate", "Group.swap"),
    ),
    DocEntry(
        "Scene.tempo",
        "Scene",
        "`with` block that multiplies the speed of everything inside: `s.tempo(4)` divides "
        "durations and waits by 4. `s.tempo(1, to=8)` speeds up progressively over the block. "
        "Nested tempos multiply; `k.time` is not affected.",
        '''
import kinemo as k

@k.scene
def speed_up(s: k.Scene):
    dots = [k.Dot(r=0.2) for _ in range(6)]
    row = k.Row(*dots, gap=0.6).place(at="center")
    s.add(row)
    with s.tempo(1, to=4):
        for d in dots:
            s.play(k.indicate(d), duration=0.5)
''',
        related=("Scene.during", "k.stagger"),
    ),
    DocEntry(
        "Scene.voice",
        "Scene",
        "Narrated `with` block: takes text (TTS from the provider in `kinemo.toml`) or an audio "
        "file (`text=` says what it says), and lasts at least as long as the audio. It gives a "
        "`k.Voice`: `v.at(0.5)` / `v.at(\"phrase\")` wait until that point of the line, "
        "`v.time(...)` gives the instant, `v.words` lists `(word, start, end)`. Words marked "
        "`[word]{name}` become `s.marks[name]`. Without a TTS provider, the voice becomes silence "
        "with an estimated duration and lint W1401 warns; content longer than the line is W1403.",
        '''
import kinemo as k

@k.scene
def narrated(s: k.Scene):
    tri = k.Triangle.right(3, 4, scale=0.6).place(at="center")
    with s.voice("Every right triangle hides a relation.") as v:  # kinemo: allow W1401
        s.play(k.draw(tri))
        v.at("relation")
        s.play(k.indicate(tri), duration=0.4)
''',
        related=("Scene.mark", "k.sound"),
    ),
    DocEntry(
        "k.Script",
        "Scene",
        "Narration kept outside the code, by beat: a Markdown file with a heading per beat "
        "(`### B03 · Title`, the first word is the id) and its narration on `> ` lines, or JSON "
        "(`{\"B03\": \"...\"}`). `s.voice(script[\"B03\"])` uses `audio/B03.wav` next to the script "
        "when it exists (else TTS or the estimate) and adds the marks `B03` and `B03.end`. Audio "
        "made from an older text is W1404.",
        '''
import kinemo as k

script = k.Script("script.md")

@k.scene
def triangle(s: k.Scene):
    tri = k.Triangle.right(3, 4, scale=0.6).place(at="center")
    with s.voice(script["B01"]) as v:  # kinemo: allow W1401
        s.play(k.draw(tri))
        v.at("relation")
        s.play(k.indicate(tri), duration=0.5)
''',
        related=("Scene.voice",),
        assets=("script.md",),
    ),
    DocEntry(
        "k.time",
        "Scene",
        "Global scene time in seconds, as a read-only signal. It is the right way to express "
        "clocks and continuous motion, because it advances linearly and is never eased. "
        "Works at module level, in contexts and in components.",
        '''
import kinemo as k

@k.scene
def clock(s: k.Scene):
    hand = k.Line(start=(0, 0), end=(0, 2), rotate=-k.time * 90)
    label = k.Text(lambda: f"{k.time():.1f} s").place(at="top", margin=0.8)
    s.add(hand, label)
    s.wait(4)
''',
        related=("k.signal", "Expr.map", "k.integrate"),
    ),
)
