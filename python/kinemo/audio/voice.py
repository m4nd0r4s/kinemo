"""`with s.voice(...)`: a block that lasts at least as long as its narration."""

from __future__ import annotations

import os
import re
import subprocess
import wave
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator

from .tts import Speech, cache_path, estimate, installed_providers, load_provider, read_cached, write_cached

if TYPE_CHECKING:
    from ..scene.scene import Scene

#: `[cateto]{c1}`: the word "cateto", whose instant becomes `s.marks["c1"]`.
_MARKED = re.compile(r"\[([^\]]+)\]\{([A-Za-z_]\w*)\}")
AUDIO_EXTENSIONS = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac")


def parse(text: str) -> tuple[str, list[str], dict[str, int]]:
    """Plain text, its words, and the word index of every marked word."""
    marks: dict[str, int] = {}
    plain_parts: list[str] = []
    pos = 0
    for m in _MARKED.finditer(text):
        plain_parts.append(text[pos : m.start()])
        words_before = len("".join(plain_parts).split())
        marks[m.group(2)] = words_before
        plain_parts.append(m.group(1))
        pos = m.end()
    plain_parts.append(text[pos:])
    plain = "".join(plain_parts)
    return plain, plain.split(), marks


def audio_duration(path: str) -> float:
    if path.lower().endswith(".wav"):
        with wave.open(path) as w:
            return w.getnframes() / float(w.getframerate())
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
        encoding="utf-8",
    )
    return float(out.stdout.strip())


def synthesize(s: "Scene", text: str, voice: str | None) -> Speech:
    from ..project import project_config

    cfg = project_config()
    provider = load_provider(cfg.tts_provider)
    _, words, _ = parse(text)
    if provider is None and cfg.tts_provider:
        installed = installed_providers()
        s.lints.warn(
            "W1402",
            f"TTS provider {cfg.tts_provider!r} is not installed: the voice becomes silence with an estimated duration",
            fixes=[(f"installed providers: {', '.join(installed)}" if installed else f"install the package kinemo-tts-{cfg.tts_provider}", None)],
        )
        return estimate(words)
    if provider is None:
        s.lints.warn(
            "W1401",
            "no TTS provider: the voice becomes silence with an estimated duration",
            fixes=[("install and configure a provider", 'kinemo.toml: [tts] provider = "piper"')],
        )
        return estimate(words)
    plain, _, _ = parse(text)
    path = cache_path(cfg.cache_dir, provider.name, voice, plain)
    cached = read_cached(path)
    if cached is not None:
        return cached
    speech = provider.synthesize(plain, voice, path)
    write_cached(path, speech)
    return speech


class VoiceMixin:
    cursor: float

    @contextmanager
    def voice(self, narration: str, *, voice: str | None = None, gain: float = 1.0) -> Iterator[None]:
        """Narrate (TTS text or an audio file); the block lasts max(audio, content).

        Marked words `[cateto]{c1}` become marks at the instant they are spoken."""
        s: Any = self
        start = s.cursor
        if narration.lower().endswith(AUDIO_EXTENSIONS):
            from ..objects.media_paths import resolve_media_path

            narration = resolve_media_path(narration, "s.voice")
            speech = Speech(narration, audio_duration(narration))
            marks: dict[str, int] = {}
            words: list[str] = []
        else:
            _, words, marks = parse(narration)
            speech = synthesize(s, narration, voice)
        if speech.path:
            s._b.add_audio(speech.path, start, float(gain))
        for name, index in marks.items():
            when = start + (speech.word_times[index] if index < len(speech.word_times) else speech.duration * index / max(1, len(words)))
            s._b.add_mark(when, name, False)
            s._marks.append((name, when, False, s._b.log_position()))
        yield
        s.cursor = max(s.cursor, start + speech.duration)
