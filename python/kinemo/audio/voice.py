"""`with s.voice(...)`: a block that lasts at least as long as its narration."""

from __future__ import annotations

import os
import re
import subprocess
import wave
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator

from ..diagnostics import KinemoError
from .tts import Speech, TTSProvider, cache_path, estimate, installed_providers, load_provider, read_cached, write_cached

if TYPE_CHECKING:
    from .._runtime.spans import Span
    from ..project import ProjectConfig
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


#: While `kinemo voice` collects the lines of a scene, nothing is synthesized: lines without
#: audio are estimated, and the command makes their audio afterwards.
_collecting: ContextVar[bool] = ContextVar("kinemo_voice_collecting", default=False)


@contextmanager
def collecting_lines() -> Iterator[None]:
    token = _collecting.set(True)
    try:
        yield
    finally:
        _collecting.reset(token)


@dataclass(frozen=True)
class NarrationLine:
    """A narration line of a built scene, as `check --json` and `kinemo voice` list it."""

    start: float
    end: float
    text: str
    #: The `k.Script` beat it narrates, if any.
    beat: str | None
    #: The audio it plays (None while it is estimated).
    audio: str | None
    voice: str | None
    #: Where its word times come from (see `Speech.timing`).
    timing: str
    #: Where `kinemo voice` writes a script beat's audio.
    audio_target: str | None = None
    #: `(word, start, end)` of every word, in scene seconds.
    words: tuple[tuple[str, float, float], ...] = ()
    #: The `s.voice(...)` line in the scene, and the beat's heading in its script.
    span: "Span | None" = None
    script: tuple[str, int] | None = None

    def json(self) -> dict[str, Any]:
        return {"start": self.start, "end": self.end, "text": self.text, "beat": self.beat, "audio": self.audio, "voice": self.voice, "timing": self.timing}


def configured_provider(cfg: "ProjectConfig | None" = None) -> TTSProvider | None:
    """The TTS provider `kinemo.toml` selects (the command provider, or an installed one); the
    configuration of the scene being built unless `cfg` is given."""
    from ..project import project_config

    cfg = cfg or project_config()
    if cfg.tts_provider != "command":
        return load_provider(cfg.tts_provider)
    if not cfg.tts_command:
        raise KinemoError.make(
            "K1401",
            '[tts] provider = "command" needs a command',
            fixes=[("add it to kinemo.toml", '[tts] command = ["python", "voice.py", "{text_file}", "{out}"]')],
        )
    from .command_provider import CommandProvider

    return CommandProvider(cfg.tts_command, cfg.root)


def synthesize(s: "Scene", text: str, voice: str | None) -> Speech:
    from .._runtime.spans import user_span
    from ..project import project_config, synthesizes_on_build

    cfg = project_config()
    _, words, _ = parse(text)
    provider = configured_provider(cfg)
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
    if _collecting.get() or not synthesizes_on_build(cfg):
        span = user_span()
        s.lints.warn(
            "W1405",
            "this narration has no audio yet: its length is estimated",
            spans=[span],
            fixes=[("make the missing narration", f"kinemo voice {os.path.basename(span.file)}")],
            level="hint",
        )
        return estimate(words, cfg.tts_wpm)
    speech = with_word_times(provider.synthesize(plain, voice, path), words)
    write_cached(path, speech)
    return speech


def recorded_word_times(audio: str) -> list[float]:
    """Word times saved next to an audio file (`B03.wav.json`, written by `kinemo voice`)."""
    import json

    try:
        with open(f"{audio}.json", encoding="utf-8") as fh:
            return [float(t) for t in json.load(fh).get("word_times", [])]
    except (OSError, ValueError, AttributeError):
        return []


def with_word_times(speech: Speech, words: list[str]) -> Speech:
    """Audio without word times (a recording, a provider that gives none) gets them by
    alignment (`kinemo[align]`), or estimated from the words' syllables."""
    if len(speech.word_times) >= len(words) or speech.path is None:
        return speech
    from ..project import project_config
    from .align import word_times

    cfg = project_config()
    times, how = word_times(speech.path, words, speech.duration, cfg.cache_dir, cfg.align_model)
    return Speech(speech.path, speech.duration, times, "aligned" if how == "aligned" else "syllables")


def trimmed(speech: Speech) -> Speech:
    """With `[audio] trim_silence`, the line without the silence around it (word times move
    with the cut)."""
    from ..project import project_config

    cfg = project_config()
    if not cfg.audio_trim_silence or speech.path is None:
        return speech
    from .trim import trim_silence

    path, lead, duration = trim_silence(speech.path, cfg.cache_dir)
    return Speech(path, duration, [max(0.0, t - lead) for t in speech.word_times])


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
            speech = with_word_times(Speech(source, audio_duration(source), recorded_word_times(source)), words)
        else:
            _, words, marks = parse(source)
            speech = synthesize(s, source, voice)
        speech = trimmed(speech)
        if speech.path:
            s._b.add_audio(speech.path, start, float(gain), "voice")
        for name, index in marks.items():
            when = start + (speech.word_times[index] if index < len(speech.word_times) else speech.duration * index / max(1, len(words)))
            s._b.add_mark(when, name, False)
            s._marks.append((name, when, False, s._b.log_position()))
        line = Voice(s, start, speech.duration, words, speech.word_times, span)
        s.__dict__.setdefault("_narration", []).append(
            NarrationLine(
                line.start,
                line.end,
                " ".join(words),
                beat.id if beat else None,
                speech.path,
                voice,
                speech.timing,
                beat.audio_target if beat else None,
                tuple(line.words),
                span,
                (beat.source, beat.line) if beat is not None and beat.source else None,
            )
        )
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
        spoken = " ".join(words)
        s._record("voice", line.start, s.cursor, f"{beat.id} · {spoken}" if beat else spoken, span)
