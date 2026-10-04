"""`[tts] provider = "command"`: narration made by an external program, so a voice that lives
in another environment (another Python, a heavy model) needs no package in kinemo's.

The command is an argv list, in one of two forms:

- **One line per run:** `{text_file}` (a UTF-8 file with the text), `{out}` (the WAV to write)
  and `{voice}` are replaced.
- **Every line in one run:** `{lines_file}` is replaced by a UTF-8 JSON file listing the lines,
  `[{"text": ..., "out": ..., "voice": ...}]`; the program writes every `out`. A model is then
  loaded once for all the lines `kinemo voice` makes.

When the program also writes `<out>.json` with `{"word_times": [...]}` (seconds), those are
the words' start times."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from typing import Callable, Sequence

from ..diagnostics import KinemoError
from .tts import Speech

#: Lines of the program's error output quoted when it fails.
ERROR_LINES = 6
#: How often a batch run is checked for finished lines (seconds).
POLL = 0.2

#: A line to make: its text, its voice and the WAV to write.
Line = tuple[str, "str | None", str]


class CommandProvider:
    def __init__(self, argv: Sequence[str], cwd: str) -> None:
        self.argv = list(argv)
        self.cwd = cwd
        # The command is part of the cache key: changing it makes new audio.
        self.name = "command-" + hashlib.sha256("\0".join(self.argv).encode()).hexdigest()[:10]

    @property
    def batch(self) -> bool:
        """Whether the command takes every line at once (`{lines_file}`)."""
        return any("{lines_file}" in part for part in self.argv)

    def synthesize(self, text: str, voice: str | None, out_path: str) -> Speech:
        return self.synthesize_many([(text, voice, out_path)])[0]

    def synthesize_many(self, lines: Sequence[Line], progress: Callable[[int, int], object] | None = None) -> list[Speech]:
        """Make every line: one run of a `{lines_file}` command, or one run per line.
        `progress(done, total)` is called as lines are written."""
        if not self.batch:
            speeches = []
            for done, (text, voice, out_path) in enumerate(lines, 1):
                speeches.append(self._run_one(text, voice, out_path))
                if progress:
                    progress(done, len(lines))
            return speeches
        self._run_batch(lines, progress)
        return [_speech(out_path) for _, _, out_path in lines]

    def _run_one(self, text: str, voice: str | None, out_path: str) -> Speech:
        text_file = _temporary(".txt", text)
        try:
            done = self._run({"text_file": text_file, "out": out_path, "voice": voice or ""})
        finally:
            os.unlink(text_file)
        _check(done)
        if not os.path.exists(out_path):
            raise _failed(f"the TTS command finished without writing {out_path}")
        return _speech(out_path)

    def _run_batch(self, lines: Sequence[Line], progress: Callable[[int, int], object] | None) -> None:
        for _, _, out_path in lines:
            # A line counts as made once its file appears; stale files would count too early.
            if os.path.exists(out_path):
                os.unlink(out_path)
        listing = [{"text": text, "out": out_path, "voice": voice or ""} for text, voice, out_path in lines]
        lines_file = _temporary(".json", json.dumps(listing, ensure_ascii=False))
        try:
            done = self._run({"lines_file": lines_file}, lambda: _report(lines, progress))
        finally:
            os.unlink(lines_file)
        _check(done)
        missing = [out_path for _, _, out_path in lines if not os.path.exists(out_path)]
        if missing:
            raise _failed(f"the TTS command finished without writing {len(missing)} of {len(lines)} line(s): {', '.join(missing[:3])}")
        _report(lines, progress)

    def _run(self, values: dict[str, str], poll: Callable[[], object] | None = None) -> subprocess.CompletedProcess[str]:
        argv = [part.format_map(_Values(values)) for part in self.argv]
        # Output goes to files, not pipes: a chatty program would block on a full pipe while
        # it is being polled.
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                process = subprocess.Popen(argv, cwd=self.cwd, stdout=out, stderr=err)
            except OSError as error:
                raise _failed(f"could not start {self.argv[0]!r}: {error}") from error
            while True:
                try:
                    process.wait(timeout=POLL)
                    break
                except subprocess.TimeoutExpired:
                    if poll is not None:
                        poll()
            texts = []
            for stream in (out, err):
                stream.seek(0)
                texts.append(stream.read().decode("utf-8", errors="replace"))
        return subprocess.CompletedProcess(argv, process.returncode, texts[0], texts[1])


class _Values(dict[str, str]):
    """Placeholders of the other form are left as written (`{out}` in a batch command)."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _temporary(suffix: str, content: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as fh:
        fh.write(content)
        return fh.name


def _report(lines: Sequence[Line], progress: Callable[[int, int], object] | None) -> None:
    if progress:
        progress(sum(os.path.exists(out_path) for _, _, out_path in lines), len(lines))


def _check(done: subprocess.CompletedProcess[str]) -> None:
    if done.returncode != 0:
        tail = "\n".join((done.stderr or done.stdout).strip().splitlines()[-ERROR_LINES:])
        raise _failed(f"the TTS command exited with {done.returncode}" + (f":\n{tail}" if tail else ""))


def _speech(out_path: str) -> Speech:
    from .voice import audio_duration

    return Speech(out_path, audio_duration(out_path), _word_times(out_path))


def _word_times(out_path: str) -> list[float]:
    try:
        with open(f"{out_path}.json", encoding="utf-8") as fh:
            return [float(t) for t in json.load(fh).get("word_times", [])]
    except (OSError, ValueError, AttributeError):
        return []


def _failed(message: str) -> KinemoError:
    return KinemoError.make(
        "K1401",
        message,
        fixes=[("run the command by hand with a short text to see the error", None)],
    )
