"""`[tts] provider = "command"`: narration made by an external program, so a voice that lives
in another environment (another Python, a heavy model) needs no package in kinemo's.

The command is an argv list; `{text_file}` (a UTF-8 file with the text), `{out}` (the WAV to
write) and `{voice}` are replaced. When the program also writes `{out}.json` with
`{"word_times": [...]}` (seconds), those are the words' start times."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from typing import Sequence

from ..diagnostics import KinemoError
from .tts import Speech

#: Lines of the program's error output quoted when it fails.
ERROR_LINES = 6


class CommandProvider:
    def __init__(self, argv: Sequence[str], cwd: str) -> None:
        self.argv = list(argv)
        self.cwd = cwd
        # The command is part of the cache key: changing it makes new audio.
        self.name = "command-" + hashlib.sha256("\0".join(self.argv).encode()).hexdigest()[:10]

    def synthesize(self, text: str, voice: str | None, out_path: str) -> Speech:
        from .voice import audio_duration

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
            fh.write(text)
            text_file = fh.name
        try:
            values = {"text_file": text_file, "out": out_path, "voice": voice or ""}
            argv = [part.format(**values) for part in self.argv]
            done = subprocess.run(argv, cwd=self.cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        except OSError as error:
            raise _failed(f"could not start {self.argv[0]!r}: {error}") from error
        finally:
            os.unlink(text_file)
        if done.returncode != 0:
            tail = "\n".join((done.stderr or done.stdout).strip().splitlines()[-ERROR_LINES:])
            raise _failed(f"the TTS command exited with {done.returncode}" + (f":\n{tail}" if tail else ""))
        if not os.path.exists(out_path):
            raise _failed(f"the TTS command finished without writing {out_path}")
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
