"""Catalog of diagnostic codes. Codes never change meaning and are never reused."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    title: str
    explanation: str
    example: str = ""
    fix: str = ""
    #: `hint` for a diagnostic that never fails `--strict`; otherwise taken from the code.
    level: str = ""


CATALOG: dict[str, Entry] = {
    # --- K00xx: general ---------------------------------------------------------------
    "K0001": Entry("Python exception during build", "The scene code raised an ordinary Python exception."),
    # --- K01xx: object lifecycle ---------------------------------------------------
    "K0101": Entry(
        "object not in the scene",
        "Creating an object does not put it in the scene. `.to()` only animates objects that have entered, "
        "via `s.add(obj)` or an entrance verb (`k.draw`, `k.write`, `k.fade_in`, `k.grow`).",
        "c = k.Circle()\ns.play(c.to(x=2))",
        "s.play(k.draw(c))\ns.play(c.to(x=2))",
    ),
    "K0102": Entry(
        "object already removed",
        "The object left the scene (`s.remove`, `k.fade_out`, `k.shrink`) before the animation's time. "
        "Bring it back with an entrance verb or animate it before it exits.",
    ),
    "K0103": Entry(
        "object with two parents",
        "An object belongs to exactly one group. To show the same visual in two places, copy it "
        "(`obj.copy()`); to change groups while keeping its position, use `k.reparent(obj, new_parent)`.",
    ),
    "K0104": Entry(
        "outside scene construction",
        "Objects, signals and animations belong to a scene. Create them inside the function decorated with "
        "`@k.scene` (or inside a clip, a handler or a component's `build()`).",
    ),
    "K0105": Entry("invalid argument", "An argument has a type or value the API does not accept."),
    "K0106": Entry("unknown prop", "The object has no such prop. See `kinemo docs <Type>`."),
    # --- K02xx: animations ---------------------------------------------------------
    "K0201": Entry(
        "two animations on the same prop",
        "Two animations write the same prop of the same object over overlapping intervals. "
        "Chain them (`k.seq`) or, if summing them is intended, use `blend=\"add\"` on the second one.",
    ),
    "K0202": Entry("invalid duration", "Durations and waits must be finite, non-negative numbers."),
    "K0203": Entry("not an animation", "`s.play`/`s.start` take `k.Animation` values (verbs, `.to()`, clips)."),
    "K0204": Entry(
        "non-reversible animation in during",
        "`s.during` reverts what it applied when the block ends; it only accepts state changes (`.to`) and "
        "`k.indicate`. Entrance/exit verbs have no reverse.",
    ),
    "K0205": Entry(
        "type without interpolation",
        "Lists and custom types must declare how to interpolate: `k.signal([...], lerp=k.lerp.pointwise)` "
        "or `lerp=None` to switch in a single step.",
    ),
    # --- K03xx: reactive system ----------------------------------------------------
    "K0301": Entry(
        "tracked read outside a reactive context",
        "`x()` only works inside prop lambdas, `k.computed` and `.map` functions. In the scene body, "
        "read the value at the cursor with `x.now`.",
    ),
    "K0302": Entry(
        "x.now inside a lambda",
        "`x.now` inside a lambda would freeze the value at build time. Use `x()` so "
        "the lambda follows the signal.",
    ),
    "K0303": Entry("derived values are read-only", "Derived values are recomputed from their sources; animate the source."),
    "K0304": Entry(
        "signal used as a boolean",
        "`if signal:` has no single value: the signal changes over time. Use `x.now > 2` to "
        "decide at the cursor, or `k.when(x > 2, ...)` to react during playback.",
    ),
    "K0305": Entry(
        "signal converted to a number",
        "Functions like `math.sin` need a number; a signal is a value over time. Use `k.sin(x)` "
        "(native) or `x.map(k.python(math.sin))`.",
    ),
    "K0306": Entry("write inside a derived value", "Derived values are pure: they do not write to signals."),
    "K0310": Entry(
        "untraceable function",
        "The function uses something that cannot be compiled to the IR (math.*, if on a symbolic value, "
        "external libraries). Replace it with the native `k` building blocks or accept the cost with `k.python(fn)`.",
    ),
    # --- K04xx: layout -------------------------------------------------------------
    "K0401": Entry(
        "axis held by a constraint",
        "The object's position comes from a constraint (`place`, a container or a binding). Change the constraint "
        "with an animation via `.to_place(...)`, release it with `.to(..., unpin=True)` (or `.unpin()` at "
        "the cursor), or drop a binding with `.unbind()`.",
    ),
    "K0402": Entry("constraint cycle", "The constraints depend on each other in a cycle; break one of them."),
    "K0403": Entry(
        "conflicting constraints",
        "Two constraints compete for the same axis. Remove one or mark the weaker one with `weak=True`.",
    ),
    "K0404": Entry("unknown anchor", "Valid anchors: center, top, bottom, left, right and combinations such as top-left."),
    # --- K05xx: resolve ------------------------------------------------------------
    "K0501": Entry("event loop", "Events and handlers did not converge within 8 passes."),
    # --- K06xx: components ---------------------------------------------------------
    "K0601": Entry("signal in a static field", "Declare the field as `k.Prop[T]` to accept reactive values."),
    "K0602": Entry("unassigned out", "Every `k.Out` must be assigned in `build()`."),
    # --- K07xx: events -------------------------------------------------------------
    "K0702": Entry("event did not happen before the timeout", "No trigger before the timeout."),
    "K0703": Entry("event already happened", "The event happened before the cursor; use `s.start` instead of the earlier `play`."),
    # --- K08xx: text ---------------------------------------------------------------
    "K0801": Entry("unsupported LaTeX command", "Use `engine=\"tex\"` for packages the built-in engine does not cover."),
    "K0802": Entry("unknown code language", "`k.Code` highlights the languages listed in the message; `lang=\"text\"` shows any code without colors."),
    # --- K11xx: Manim names --------------------------------------------------------
    "K1101": Entry("Manim name", "Manim verbs have a direct equivalent in `k.` (see the Manim → kinemo table)."),
    "K1102": Entry("Manim `.animate`", "In kinemo, an animated state change is `s.play(obj.to(...))`."),
    "K1103": Entry("Manim `self.play`", "The scene receives `s: k.Scene`; use `s.play(...)`."),
    "K1104": Entry("Manim ValueTracker", "Use `k.signal(value)`."),
    "K1105": Entry("Manim updater", "Pass a signal or a lambda to the prop: `obj.set(x=other.x)`."),
    "K1106": Entry("Manim direction constant", "Position comes from constraints (`place`) or from `x=`/`y=`."),
    # --- K12xx: data ---------------------------------------------------------------
    "K1201": Entry("data without Arrow", "The object does not implement the Arrow PyCapsule Interface."),
    "K1202": Entry("missing column", "The table has no column with that name; check `x=`, `y=` and `key=`."),
    "K1203": Entry("column with the wrong type", "Chart values need a numeric column (int, float or decimal)."),
    "K1204": Entry("duplicate key", "Each row of a chart needs a unique key (`key=`); aggregate the data or pick another column."),
    "K1401": Entry(
        "TTS command failed",
        "The command provider (`[tts] provider = \"command\"`) has no command, could not start, exited with an "
        "error or wrote no audio. The message quotes the end of its error output.",
        fix="Run the command by hand with a short text; check `[tts] command` in kinemo.toml.",
    ),
    # --- warnings ------------------------------------------------------------------
    "W0110": Entry("play with at=", "`play(..., at=)` does not move the cursor; use `s.start(..., at=)` to make that explicit."),
    "W0310": Entry("lambda in a loop", "The lambda captures the loop variable by reference; use `lambda i=i:` or `.map`."),
    "W0311": Entry("captured Python list", "Plain lists are not tracked; use `k.list([...])`."),
    "W0312": Entry("eased clock", "A signal used as a clock must advance linearly; use `k.time.map(...)`."),
    "W0701": Entry("handler object never removed", "Objects created in handlers should leave the scene."),
    "W0801": Entry("morph without matches", "The shapes have nothing in common; the morph does a warp + crossfade."),
    "W0901": Entry("too many individual objects", "Use vectorized types (`k.Points`, `k.VectorField`)."),
    "W1001": Entry("outside the safe area", "The object extends beyond the frame's safe area. Objects entirely offstage are not reported; for one cropped on purpose, `bleed=True`."),
    "W1002": Entry("text over text", "Two texts overlap by more than 10% of their area."),
    "W1003": Entry("low contrast", "Contrast between text and background is below 4.5:1."),
    "W1004": Entry("small text", "Text smaller than 18 px at the final resolution."),
    "W1005": Entry("invisible object", "Object invisible for more than 3 s, never removed and not seen again."),
    "W1006": Entry("visual noise", "More than 12 short simultaneous animations."),
    "W1007": Entry("static scene", "More than 8 s without visual change."),
    "W1301": Entry("parameter read with .now", "It is fixed at build time and does not become an interactive control."),
    "W1302": Entry("k.python depending on a parameter", "It cannot be precomputed for the interactive web player."),
    "W1401": Entry("voice without a TTS provider", "No provider configured: silence with an estimated duration."),
    "W1404": Entry(
        "stale narration",
        "A beat of a `k.Script` has recorded audio made from a different text (per `audio/manifest.json`): "
        "the script changed after the audio was made.",
        fix="Make the audio again: `kinemo voice <scene file>` (only missing and stale beats), or `--force <id>`.",
    ),
    "W1403": Entry(
        "content runs past the narration",
        "The animations inside a `with s.voice(...)` block last more than 0.25 s longer than its narration, "
        "so the next line starts late and the silence shows.",
        fix="Shorten or speed up the animations, sync them to the line with `v.at(...)`, or lengthen the narration.",
    ),
    "W1405": Entry(
        "narration without audio yet",
        "A line has no audio and this build does not make it (`kinemo check` never does; `[tts] on_build = "
        "\"estimate\"`, the default for the command provider): its length is estimated from `[tts] wpm`.",
        fix="`kinemo voice <scene file>` makes every missing line in one run; `kinemo render` makes them before rendering.",
        level="hint",
    ),
    "W1402": Entry(
        "unknown TTS provider",
        "`[tts] provider` in kinemo.toml names a provider that is not installed (a typo, or its package is missing): "
        "the voice becomes silence with an estimated duration.",
        fix="Install `kinemo-tts-<name>`, or use one of the installed providers the message lists.",
    ),
}


def explain(code: str) -> str:
    e = CATALOG.get(code.upper())
    if e is None:
        return f"{code}: unknown code"
    parts = [f"{code.upper()} — {e.title}", "", e.explanation]
    if e.example:
        parts += ["", "Example that triggers it:", *("    " + line for line in e.example.splitlines())]
    if e.fix:
        parts += ["", "Fix:", *("    " + line for line in e.fix.splitlines())]
    return "\n".join(parts)
