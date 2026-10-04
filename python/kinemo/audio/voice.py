"""`with s.voice(...)`: a block that lasts at least as long as its narration."""

from __future__ import annotations

import os
import re
import subprocess
import wave
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator

from ..diagnostics import KinemoError
from .tts import Speech, TTSProvider, cache_path, estimate, installed_providers, load_provider, read_cached, write_cached

if TYPE_CHECKING:
    from ..scene.scene import Scene
    from .script import ScriptLine
    from .voice_handle import Voice

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
    _, words, _ = parse(text)
    if cfg.tts_provider == "command":
        if not cfg.tts_command:
            raise KinemoError.make(
                "K1401",
                '[tts] provider = "command" needs a command',
                fixes=[("add it to kinemo.toml", '[tts] command = ["python", "voice.py", "{text_file}", "{out}"]')],
            )
        from .command_provider import CommandProvider

        provider: TTSProvider | None = CommandProvider(cfg.tts_command, cfg.root)
    else:
        provider = load_provider(cfg.tts_provider)
    if provider is None and cfg.tts_provider:
        installed = installed_providers()
        s.lints.warn(
            "W1402",
            f"TTS provider {cfg.tts_provider!r} is not installed: the voice becomes silence with an estimated duration",
            fixes=[(f"installed providers: {', '.join(installed)}" if installed else f"install the package kinemo-tts-{cfg.tts_provider}", None)],
        )
        return estimate(words, cfg.tts_wpm)
    if provider is None:
        s.lints.warn(
            "W1401",
            "no TTS provider: the voice becomes silence with an estimated duration",
            fixes=[("install and configure a provider", 'kinemo.toml: [tts] provider = "piper"')],
        )
        return estimate(words, cfg.tts_wpm)
    plain, _, _ = parse(text)
    path = cache_path(cfg.cache_dir, provider.name, voice, plain)
    cached = read_cached(path)
    if cached is not None:
        return cached
    speech = with_word_times(provider.synthesize(plain, voice, path), len(words))
    write_cached(path, speech)
    return speech


def with_word_times(speech: Speech, count: int) -> Speech:
    """Providers that give no word times get them spread over the audio."""
    if len(speech.word_times) >= count:
        return speech
    return Speech(speech.path, speech.duration, [speech.duration * i / max(1, count) for i in range(count)])


#: Content may run this far past the narration before W1403 (seconds).
OVERRUN_TOLERANCE = 0.25


class VoiceMixin:
    cursor: float

    @contextmanager
    def voice(self, narration: "str | ScriptLine", *, text: str | None = None, voice: str | None = None, gain: float = 1.0) -> Iterator[Voice]:
        """Narrate (TTS text, an audio file, or a beat of a `k.Script`); the block lasts
        max(audio, content) and gives a `Voice` to sync with what is said (`v.at(0.5)`,
        `v.at("the slope")`).

        With an audio file, `text=` is what it says: its words get times and marks. A script
        beat uses its recorded audio when it exists and adds the marks `<id>` and `<id>.end`.
        Marked words `[cateto]{c1}` become marks at the instant they are spoken."""
        from .._runtime.spans import user_span
        from .script import ScriptLine
        from .voice_handle import Voice

        s: Any = self
        span = user_span()
        start = s.cursor
        beat: ScriptLine | None = narration if isinstance(narration, ScriptLine) else None
        if beat is not None:
            if beat.is_stale():
                s.lints.warn(
                    "W1404",
                    f"the audio of beat {beat.id} was made from a different text",
                    spans=[span],
                    fixes=[("make it again", f"kinemo voice <scene file> --force {beat.id}")],
                )
            text, source = beat.text, beat.audio or beat.text
        elif isinstance(narration, str):
            source = narration
        else:
            raise KinemoError.make(
                "K0105",
                f"s.voice takes text, an audio file or a script beat, got {type(narration).__name__}",
                spans=[span],
            )
        if source.lower().endswith(AUDIO_EXTENSIONS):
            from ..objects.media_paths import resolve_media_path

            source = resolve_media_path(source, "s.voice")
            _, words, marks = parse(text) if text is not None else ("", [], {})
            duration = audio_duration(source)
            # Spread over the audio until the words are aligned to it.
            speech = Speech(source, duration, [duration * i / max(1, len(words)) for i in range(len(words))])
        else:
            _, words, marks = parse(source)
            speech = synthesize(s, source, voice)
        if speech.path:
            s._b.add_audio(speech.path, start, float(gain))
        for name, index in marks.items():
            when = start + (speech.word_times[index] if index < len(speech.word_times) else speech.duration * index / max(1, len(words)))
            s._b.add_mark(when, name, False)
            s._marks.append((name, when, False, s._b.log_position()))
        line = Voice(s, start, speech.duration, words, speech.word_times, span)
        if beat is not None:
            for name, when in ((beat.id, line.start), (f"{beat.id}.end", line.end)):
                s._b.add_mark(when, name, False)
                s._marks.append((name, when, False, s._b.log_position()))
        yield line
        overrun = s.cursor - line.end
        if overrun > OVERRUN_TOLERANCE:
            s.lints.warn(
                "W1403",
                f"the content of this voice block runs {overrun:.1f} s past its narration",
                spans=[span],
                fixes=[("shorten or speed up the animations, or lengthen the narration", None)],
            )
        s.cursor = max(s.cursor, line.end)
