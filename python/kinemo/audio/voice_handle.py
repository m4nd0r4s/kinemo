"""`with s.voice(...) as v`: the narration line as an object, to sync animations with what is
being said (`v.at(0.5)`, `v.at("the slope")`) instead of hand-tuned waits."""

from __future__ import annotations

import difflib
import re
from typing import TYPE_CHECKING, Any

from ..diagnostics import KinemoError

if TYPE_CHECKING:
    from .._runtime.spans import Span

#: Letters and digits of a word, for matching phrases (`"Slope,"` → `"slope"`).
_TOKEN = re.compile(r"[^\w]+", re.UNICODE)


def _normalized(word: str) -> str:
    return _TOKEN.sub("", word.lower())


class Voice:
    """A narration line: when it starts and ends in the scene, and when each word is said.

    `v.at(...)` waits until a point of the line; `v.time(...)` gives the same instant without
    waiting. A point is a fraction of the line (`0.5`) or a phrase (`"the slope"`)."""

    def __init__(self, scene: Any, start: float, duration: float, words: list[str], word_times: list[float], span: "Span") -> None:
        self._scene = scene
        self._span = span
        #: When the line starts, in scene seconds.
        self.start = start
        #: Length of the narration in seconds.
        self.duration = duration
        starts = [start + t for t in word_times[: len(words)]]
        ends = starts[1:] + [start + duration]
        #: `(word, start, end)` of every word, in scene seconds.
        self.words: list[tuple[str, float, float]] = list(zip(words, starts, ends))

    @property
    def end(self) -> float:
        """When the narration ends, in scene seconds."""
        return self.start + self.duration

    def time(self, where: float | str, occurrence: int = 1) -> float:
        """The instant of a point of the line: a fraction (`0.5`) or a phrase (`"the slope"`,
        its `occurrence`-th appearance)."""
        if isinstance(where, str):
            return self._phrase_time(where, occurrence)
        fraction = float(where)
        if not 0.0 <= fraction <= 1.0:
            raise KinemoError.make("K0105", f"v.at/v.time takes a fraction between 0 and 1, got {fraction}", spans=[self._span])
        return self.start + fraction * self.duration

    def at(self, where: float | str, occurrence: int = 1) -> float:
        """Wait (move the cursor) until a point of the line; returns that instant. Already
        past it, the cursor stays."""
        when = self.time(where, occurrence)
        before = self._scene.cursor
        self._scene.cursor = max(before, when)
        self._scene._record("wait", before, self._scene.cursor, f"v.at({where!r})")
        return when

    def _phrase_time(self, phrase: str, occurrence: int) -> float:
        wanted = [_normalized(w) for w in phrase.split() if _normalized(w)]
        spoken = [_normalized(w) for w, _, _ in self.words]
        if not wanted:
            raise KinemoError.make("K0105", "v.at/v.time needs a phrase with at least one word", spans=[self._span])
        found = [i for i in range(len(spoken) - len(wanted) + 1) if spoken[i : i + len(wanted)] == wanted]
        if len(found) >= occurrence >= 1:
            return self.words[found[occurrence - 1]][1]
        line = " ".join(w for w, _, _ in self.words)
        if found:
            message = f"{phrase!r} appears {len(found)} time(s) in the narration, not {occurrence}"
            fixes = [(f"use occurrence=1..{len(found)}", None)]
        else:
            close = difflib.get_close_matches(" ".join(wanted), [" ".join(spoken[i : i + len(wanted)]) for i in range(len(spoken))], n=1)
            message = f"{phrase!r} is not in the narration: {line!r}"
            fixes = [(f"did you mean {close[0]!r}?", None)] if close else [("use words of the narration", None)]
        raise KinemoError.make("K0105", message, spans=[self._span], fixes=fixes)

    def __repr__(self) -> str:
        return f"<Voice {self.start:.2f}–{self.end:.2f} s, {len(self.words)} words>"
