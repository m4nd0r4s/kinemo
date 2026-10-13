"""`k.sfx`: small sound effects for `k.sound`, made by kinemo itself.

Each effect is synthesized the first time it is used (pure Python, a fixed seed) and kept in
the project's cache, so the same file plays in every render and there is no third-party
license to track: `s.start(k.sound(k.sfx.click(), gain=0.5))`.
"""

from __future__ import annotations

import math
import os
import random
import struct
import wave
from typing import Callable

RATE = 44100
#: Bumped when a recipe changes, so cached files are made again.
RECIPE_VERSION = 1

Samples = list[float]


def _decay(n: int, seconds: float) -> Samples:
    """An exponential decay over `n` samples, down to about 1/1000 after `seconds`."""
    k = math.log(1000.0) / max(seconds * RATE, 1.0)
    return [math.exp(-k * i) for i in range(n)]


def _noise(n: int, seed: int) -> Samples:
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(n)]


def _lowpass(samples: Samples, cutoffs: Samples) -> Samples:
    """A one-pole low-pass filter whose cutoff (Hz) changes sample by sample."""
    out: Samples = []
    y = 0.0
    for x, cutoff in zip(samples, cutoffs):
        a = 1.0 - math.exp(-2.0 * math.pi * cutoff / RATE)
        y += a * (x - y)
        out.append(y)
    return out


def _normalize(samples: Samples, peak: float = 0.8) -> Samples:
    top = max((abs(s) for s in samples), default=0.0)
    return [s * peak / top for s in samples] if top > 0 else samples


def _click() -> Samples:
    n = int(0.04 * RATE)
    env = _decay(n, 0.012)
    noise = _noise(n, 1)
    return _normalize([(0.6 * noise[i] + math.sin(2 * math.pi * 2200 * i / RATE)) * env[i] for i in range(n)])


def _tick() -> Samples:
    n = int(0.03 * RATE)
    env = _decay(n, 0.01)
    return _normalize([math.sin(2 * math.pi * 3200 * i / RATE) * env[i] for i in range(n)], 0.6)


def _pop() -> Samples:
    n = int(0.09 * RATE)
    env = _decay(n, 0.07)
    phase, out = 0.0, []
    for i in range(n):
        frequency = 900.0 - 600.0 * i / n
        phase += 2 * math.pi * frequency / RATE
        out.append(math.sin(phase) * env[i] * min(1.0, i / (0.002 * RATE)))
    return _normalize(out)


def _sweep(seconds: float, low: float, high: float, seed: int) -> Samples:
    """Noise through a filter that opens and closes: air moving past."""
    n = int(seconds * RATE)
    shape = [math.sin(math.pi * i / n) for i in range(n)]
    cutoffs = [low + (high - low) * s for s in shape]
    filtered = _lowpass(_noise(n, seed), cutoffs)
    return _normalize([f * s * s for f, s in zip(filtered, shape)], 0.7)


def _swish() -> Samples:
    return _sweep(0.25, 600.0, 5000.0, 2)


def _whoosh() -> Samples:
    return _sweep(0.6, 200.0, 2500.0, 3)


def _ding() -> Samples:
    n = int(1.2 * RATE)
    env = _decay(n, 1.1)
    partials = ((1320.0, 1.0), (3643.0, 0.35), (2640.0, 0.2))
    return _normalize([sum(a * math.sin(2 * math.pi * f * i / RATE) for f, a in partials) * env[i] * min(1.0, i / (0.003 * RATE)) for i in range(n)], 0.6)


RECIPES: dict[str, Callable[[], Samples]] = {
    "click": _click,
    "tick": _tick,
    "pop": _pop,
    "swish": _swish,
    "whoosh": _whoosh,
    "ding": _ding,
}


def _write(path: str, samples: Samples) -> None:
    tmp = f"{path}.tmp{os.getpid()}"
    with wave.open(tmp, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples))
    os.replace(tmp, path)


def effect_path(name: str, cache_dir: str | None = None) -> str:
    """The file of effect `name`, made in the project's cache the first time."""
    if cache_dir is None:
        from ..project import project_config

        cache_dir = project_config().cache_dir
    folder = os.path.join(cache_dir, "sfx")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{name}-v{RECIPE_VERSION}.wav")
    if not os.path.exists(path):
        _write(path, RECIPES[name]())
    return os.path.abspath(path)


class SoundEffects:
    """`k.sfx`: built-in sound effects for `k.sound` (`k.sound(k.sfx.click(), gain=0.5)`).
    Made by kinemo, under its license: click, tick, pop, swish, whoosh, ding."""

    def click(self) -> str:
        """A short click: a key, a button, a cell lighting up."""
        return effect_path("click")

    def tick(self) -> str:
        """A tiny high tick: a counter step, a dial notch."""
        return effect_path("tick")

    def pop(self) -> str:
        """A soft pop: something appearing."""
        return effect_path("pop")

    def swish(self) -> str:
        """A quick swish: a card sliding, a fast move."""
        return effect_path("swish")

    def whoosh(self) -> str:
        """A longer whoosh: a transition, something flying past."""
        return effect_path("whoosh")

    def ding(self) -> str:
        """A bell: a correct answer, a reveal."""
        return effect_path("ding")


sfx = SoundEffects()
