"""`[audio] trim_silence`: the silence around a narration line (TTS models and recordings often
add some) is cut when the line is measured, so timing and the mix use the trimmed audio."""

from __future__ import annotations

import array
import hashlib
import os
import subprocess

#: Samples quieter than this (of full scale) count as silence.
THRESHOLD = 0.01
#: Silence kept before the first and after the last sound, in seconds.
MARGIN = 0.05
_RATE = 16000


def trim_silence(path: str, cache_dir: str) -> tuple[str, float, float]:
    """`(trimmed audio, seconds removed at the start, trimmed duration)`. A clip that is all
    silence is returned as is."""
    with open(path, "rb") as fh:
        key = hashlib.sha256(fh.read()).hexdigest()[:24]
    out = os.path.join(cache_dir, "trimmed", f"{key}.wav")
    first, last, total = _sound_bounds(path)
    if last <= first:
        return path, 0.0, total
    start = max(0.0, first - MARGIN)
    end = min(total, last + MARGIN)
    if not os.path.exists(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", path, "-ss", f"{start:.4f}", "-t", f"{end - start:.4f}", out],
            check=True,
        )
    return out, start, end - start


def _sound_bounds(path: str) -> tuple[float, float, float]:
    """Seconds of the first and last sample above the threshold, and the clip's length."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(_RATE), "-"],
        capture_output=True,
        check=True,
    ).stdout
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) - len(raw) % 2])
    limit = int(THRESHOLD * 32767)
    first = next((i for i, v in enumerate(samples) if abs(v) > limit), None)
    last = next((len(samples) - 1 - i for i, v in enumerate(reversed(samples)) if abs(v) > limit), None)
    total = len(samples) / _RATE
    if first is None or last is None:
        return 0.0, 0.0, total
    return first / _RATE, last / _RATE, total
