"""`k.Script("script.md")`: the narration of a scene kept outside its code, addressed by beat
(`s.voice(script["B03"])`).

A Markdown script has one heading per beat whose first word is the beat's id
(`### B03 · The slope`), and the beat's narration on `> ` lines below it. A JSON script maps
ids to text (`{"B03": "..."}`). A beat's recorded audio is found by convention:
`audio/B03.wav` (or `.mp3`, ...) next to the script. `audio/manifest.json` remembers the text
each audio was made from, so a beat whose text changed afterwards is reported (W1404)."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Iterator

from .._runtime.spans import user_span
from ..diagnostics import KinemoError

#: A heading opens a beat; its id is the first word (`### B03 · The slope` → `B03`).
_HEADING = re.compile(r"^#{1,6}\s+(?P<id>[^\s·:—-]+)")
_QUOTE = re.compile(r"^>\s?(?P<text>.*)$")
#: Folder of the beats' audio, next to the script.
AUDIO_FOLDER = "audio"
MANIFEST = "manifest.json"
AUDIO_EXTENSIONS = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac")


def text_hash(text: str) -> str:
    """What `audio/manifest.json` stores for a beat's text (whitespace-insensitive)."""
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ScriptLine:
    """One beat of a script: its id, its narration and where its audio is (or would be)."""

    id: str
    text: str
    #: Folder of the script's audio (`audio/` next to the script).
    audio_folder: str

    @property
    def audio(self) -> str | None:
        """The beat's recorded audio, if it exists."""
        for extension in AUDIO_EXTENSIONS:
            path = os.path.join(self.audio_folder, self.id + extension)
            if os.path.isfile(path):
                return path
        return None

    @property
    def audio_target(self) -> str:
        """Where generated audio for this beat goes (`audio/<id>.wav`)."""
        return os.path.join(self.audio_folder, self.id + ".wav")

    def is_stale(self) -> bool:
        """Its audio was made from a different text (per the manifest)."""
        made_from = read_manifest(self.audio_folder).get(self.id)
        return made_from is not None and self.audio is not None and made_from != text_hash(self.text)


class Script:
    """`k.Script("script.md")`: narration by beat. `script["B03"]` is a line for `s.voice`."""

    def __init__(self, path: str) -> None:
        from ..objects.media_paths import resolve_media_path

        self.path = resolve_media_path(path, "k.Script")
        with open(self.path, encoding="utf-8") as fh:
            source = fh.read()
        beats = _parse_json(source, self.path) if self.path.lower().endswith(".json") else _parse_markdown(source)
        folder = os.path.join(os.path.dirname(self.path), AUDIO_FOLDER)
        self._lines = {beat: ScriptLine(beat, text, folder) for beat, text in beats.items()}

    @property
    def ids(self) -> list[str]:
        """Beat ids in script order."""
        return list(self._lines)

    def __getitem__(self, beat: str) -> ScriptLine:
        line = self._lines.get(beat)
        if line is None:
            close = difflib.get_close_matches(beat, self.ids, n=1)
            raise KinemoError.make(
                "K0105",
                f"{os.path.basename(self.path)} has no beat {beat!r}",
                spans=[user_span()],
                fixes=[(f"did you mean {close[0]!r}?" if close else f"beats: {', '.join(self.ids) or 'none'}", None)],
            )
        return line

    def __iter__(self) -> Iterator[ScriptLine]:
        return iter(self._lines.values())

    def __len__(self) -> int:
        return len(self._lines)


def _parse_markdown(source: str) -> dict[str, str]:
    beats: dict[str, list[str]] = {}
    current: str | None = None
    for raw in source.splitlines():
        line = raw.strip()
        heading = _HEADING.match(line)
        if heading:
            current = str(heading["id"])
            beats.setdefault(current, [])
            continue
        quote = _QUOTE.match(line)
        if quote and current is not None and quote["text"].strip():
            beats[current].append(quote["text"].strip())
    return {beat: " ".join(lines) for beat, lines in beats.items() if lines}


def _parse_json(source: str, path: str) -> dict[str, str]:
    try:
        data = json.loads(source)
    except ValueError as error:
        raise KinemoError.make("K0105", f"k.Script: {os.path.basename(path)} is not valid JSON: {error}", spans=[user_span()]) from error
    if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
        raise KinemoError.make("K0105", 'k.Script: a JSON script maps beat ids to text: {"B01": "..."}', spans=[user_span()])
    return {str(k): v for k, v in data.items()}


def read_manifest(audio_folder: str) -> dict[str, str]:
    try:
        with open(os.path.join(audio_folder, MANIFEST), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def write_manifest(audio_folder: str, entries: dict[str, str]) -> None:
    os.makedirs(audio_folder, exist_ok=True)
    with open(os.path.join(audio_folder, MANIFEST), "w", encoding="utf-8") as fh:
        json.dump(dict(sorted(entries.items())), fh, indent=2)
        fh.write("\n")
