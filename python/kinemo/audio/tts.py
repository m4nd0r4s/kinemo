"""Text-to-speech providers. Each provider is a separate package (`kinemo-tts-<name>`)
exposing an entry point in the `kinemo.tts` group, chosen in `kinemo.toml`."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from importlib import metadata
from typing import Protocol

WORDS_PER_MINUTE = 150.0


@dataclass(frozen=True)
class Speech:
    """Synthesized narration: an audio file, its length and when each word starts."""

    path: str | None
    duration: float
    word_times: list[float] = field(default_factory=list)


class TTSProvider(Protocol):
    name: str

    def synthesize(self, text: str, voice: str | None, out_path: str) -> Speech: ...


def estimate(words: list[str]) -> Speech:
    """Silence with the duration a narrator would take (150 words/min)."""
    per_word = 60.0 / WORDS_PER_MINUTE
    return Speech(None, max(per_word, len(words) * per_word), [i * per_word for i in range(len(words))])


def load_provider(name: str | None) -> TTSProvider | None:
    if not name:
        return None
    for ep in metadata.entry_points(group="kinemo.tts"):
        if ep.name == name:
            factory = ep.load()
            return factory()  # type: ignore[no-any-return]
    return None


def cache_path(cache_dir: str, provider: str, voice: str | None, text: str) -> str:
    key = hashlib.sha256(f"{provider}\0{voice}\0{text}".encode()).hexdigest()[:24]
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{key}.wav")
