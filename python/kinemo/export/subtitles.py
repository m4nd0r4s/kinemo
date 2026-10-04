"""Subtitles from a scene's narration: SRT and WebVTT cues of at most two lines of 42
characters, timed by the words (aligned, from the provider, or estimated)."""

from __future__ import annotations

from typing import Sequence

from ..audio.voice import NarrationLine

#: Characters per subtitle line, and lines per cue (common broadcast and web limits).
LINE_LENGTH = 42
LINES_PER_CUE = 2


def cues(lines: Sequence[NarrationLine]) -> list[tuple[float, float, str]]:
    """`(start, end, text)` cues; a cue never runs past the end of its narration line."""
    out: list[tuple[float, float, str]] = []
    for line in lines:
        words = list(line.words) or [(w, line.start, line.end) for w in line.text.split()]
        groups = _groups(words)
        for i, group in enumerate(groups):
            start = group[0][0][1]
            end = groups[i + 1][0][0][1] if i + 1 < len(groups) else line.end
            out.append((start, max(end, start + 0.1), "\n".join(" ".join(w for w, _, _ in row) for row in group)))
    return out


Word = tuple[str, float, float]


def _groups(words: list[Word]) -> list[list[list[Word]]]:
    """Words packed into rows of at most `LINE_LENGTH` characters, and rows into cues of at
    most `LINES_PER_CUE`; a sentence end that fills more than a row closes its cue."""
    cues: list[list[list[Word]]] = [[[]]]
    for word in words:
        row = cues[-1][-1]
        if row and len(" ".join(w for w, _, _ in row + [word])) > LINE_LENGTH:
            if len(cues[-1]) < LINES_PER_CUE:
                cues[-1].append([])
            else:
                cues.append([[]])
        cues[-1][-1].append(word)
        if word[0].endswith((".", "!", "?")) and sum(len(" ".join(w for w, _, _ in r)) for r in cues[-1]) > LINE_LENGTH // 2:
            cues.append([[]])
    return [cue for cue in cues if cue[0]]


def _clock(seconds: float, separator: str) -> str:
    millis = int(round(max(0.0, seconds) * 1000))
    hours, rest = divmod(millis, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def srt(lines: Sequence[NarrationLine]) -> str:
    blocks = [f"{i}\n{_clock(a, ',')} --> {_clock(b, ',')}\n{text}\n" for i, (a, b, text) in enumerate(cues(lines), 1)]
    return "\n".join(blocks)


def vtt(lines: Sequence[NarrationLine]) -> str:
    blocks = [f"{_clock(a, '.')} --> {_clock(b, '.')}\n{text}\n" for a, b, text in cues(lines)]
    return "WEBVTT\n\n" + "\n".join(blocks)
