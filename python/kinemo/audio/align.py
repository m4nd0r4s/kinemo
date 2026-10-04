"""When each word of a narration is said, for audio that came without word times (a recorded
file, a provider that gives none).

With the optional extra (`pip install kinemo[align]`, faster-whisper), the audio is
transcribed with word timestamps and the transcription is matched to the known text by
sequence alignment, so recognition mistakes only blur the words they touch. Without it, the
times are estimated in proportion to each word's syllables (and the pauses its punctuation
implies). Alignments are cached by audio and text."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from functools import lru_cache
from typing import Any

#: Model used when `[align] model` is not set.
DEFAULT_MODEL = "base.en"
_VOWEL_GROUPS = re.compile(r"[aeiouy]+", re.IGNORECASE)
_LETTERS = re.compile(r"[^\w]+", re.UNICODE)


def word_times(audio: str, words: list[str], duration: float, cache_dir: str, model: str = DEFAULT_MODEL) -> tuple[list[float], str]:
    """Start of each of `words` in `audio` (seconds), and how they were found: `"aligned"` or
    `"estimated"`."""
    if not words:
        return [], "aligned"
    aligned = _aligned(audio, words, cache_dir, model)
    if aligned is not None:
        return aligned, "aligned"
    return estimate_by_syllables(words, duration), "estimated"


def aligner_available() -> bool:
    try:
        import faster_whisper  # noqa: F401  # pyright: ignore[reportUnusedImport, reportMissingImports]
    except ImportError:
        return False
    return True


# ---- estimate ----------------------------------------------------------------------------


def syllables(word: str) -> int:
    """Rough syllable count of an English (or similar) word; numbers count as their digits."""
    letters = _LETTERS.sub("", word.lower())
    if letters.isdigit():
        return max(1, len(letters))
    groups = len(_VOWEL_GROUPS.findall(letters))
    if letters.endswith("e") and groups > 1 and not letters.endswith(("le", "ee")):
        groups -= 1
    # "ia" is usually two syllables (tri-an-gle), but not in -cia/-tia/-sia (spe-cial).
    groups += len(re.findall(r"(?<![cts])ia", letters))
    return max(1, groups)


def _weight(word: str) -> float:
    """Time a word takes, in syllables, plus the pause after a comma or a full stop."""
    pause = 1.5 if word.endswith((".", "!", "?", ":", ";")) else 0.7 if word.endswith((",", "—", "–")) else 0.0
    return syllables(word) + pause


def estimate_by_syllables(words: list[str], duration: float) -> list[float]:
    """Word starts spread over `duration` in proportion to each word's syllables."""
    weights = [_weight(w) for w in words]
    total = sum(weights) or 1.0
    starts, elapsed = [], 0.0
    for weight in weights:
        starts.append(duration * elapsed / total)
        elapsed += weight
    return starts


# ---- alignment ---------------------------------------------------------------------------


def _normalized(word: str) -> str:
    return _LETTERS.sub("", word.lower())


def match(words: list[str], heard: list[tuple[str, float]], duration: float) -> list[float]:
    """Start times for `words` from the transcription `heard` (`(word, start)`): matched words
    take the heard time; the others are spread between their matched neighbours."""
    script = [_normalized(w) for w in words]
    spoken = [_normalized(w) for w, _ in heard]
    times: list[float | None] = [None] * len(words)
    for block in difflib.SequenceMatcher(a=script, b=spoken, autojunk=False).get_matching_blocks():
        for offset in range(block.size):
            times[block.a + offset] = heard[block.b + offset][1]
    return _fill_gaps(times, words, duration)


def _fill_gaps(times: list[float | None], words: list[str], duration: float) -> list[float]:
    known = [(i, t) for i, t in enumerate(times) if t is not None]
    if not known:
        return estimate_by_syllables(words, duration)
    out = list(times)
    anchors = [(-1, 0.0), *known, (len(words), duration)]
    for (i0, t0), (i1, t1) in zip(anchors, anchors[1:]):
        if i1 - i0 <= 1:
            continue
        # The unmatched words share the stretch after the previous matched word (which keeps
        # its own time) up to the next one, by syllables.
        first = max(i0, 0)
        local = estimate_by_syllables(words[first:i1], max(0.0, t1 - t0))
        for i in range(i0 + 1, i1):
            out[i] = t0 + local[i - first]
    return [float(t) for t in out]  # type: ignore[arg-type]


def _aligned(audio: str, words: list[str], cache_dir: str, model: str) -> list[float] | None:
    if not aligner_available():
        return None
    key = _cache_key(audio, words, model)
    path = os.path.join(cache_dir, "align", f"{key}.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return [float(t) for t in json.load(fh)]
    except (OSError, ValueError):
        pass
    heard, duration = _transcribe(audio, model)
    times = match(words, heard, duration)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(times, fh)
    return times


def _cache_key(audio: str, words: list[str], model: str) -> str:
    digest = hashlib.sha256()
    with open(audio, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    digest.update("\0".join([model, *words]).encode("utf-8"))
    return digest.hexdigest()[:24]


@lru_cache(maxsize=2)
def _model(name: str) -> Any:
    from faster_whisper import WhisperModel  # pyright: ignore[reportMissingImports]

    return WhisperModel(name, device="cpu", compute_type="int8")


#: Sample rate the speech model expects.
SAMPLE_RATE = 16000


def _samples(audio: str) -> Any:
    """Mono float32 samples at 16 kHz, decoded by ffmpeg (which kinemo already needs)."""
    import subprocess

    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", audio, "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


def _transcribe(audio: str, model: str) -> tuple[list[tuple[str, float]], float]:
    samples = _samples(audio)
    segments, _ = _model(model).transcribe(samples, word_timestamps=True, beam_size=1, vad_filter=False)
    heard = [(w.word.strip(), float(w.start)) for segment in segments for w in (segment.words or [])]
    return heard, len(samples) / SAMPLE_RATE
