"""`kinemo voice`: make the narration of a scene file — only the lines that have no audio yet or
whose text changed since their audio was made.

The scenes are built without synthesizing (lines without audio are estimated), their lines
are listed, and the missing or stale ones are made with the provider `kinemo.toml` selects:
a `k.Script` beat is written to `audio/<id>.wav` next to the script (with its word times in
`<id>.wav.json` and its text hash in `audio/manifest.json`); a line written in the scene goes
to the cache, where builds find it."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass

from ..audio.script import read_manifest, text_hash, write_manifest
from ..audio.tts import cache_path, read_cached, write_cached
from ..audio.voice import NarrationLine, collecting_lines, configured_provider, with_word_times
from ..diagnostics import KinemoError
from ..project import ProjectConfig
from ..project import load as load_project
from .loader import LoadError, build, find_scenes, load_module, select
from .progress import finished, reporter


@dataclass
class Plan:
    line: NarrationLine
    #: `ok`, `missing` (no audio yet) or `stale` (made from another text).
    state: str


def plan(lines: list[NarrationLine], force: set[str]) -> list[Plan]:
    """What to do for each distinct line."""
    seen: set[tuple[str | None, str]] = set()
    out: list[Plan] = []
    for line in lines:
        key = (line.beat, line.text)
        if key in seen:
            continue
        seen.add(key)
        out.append(Plan(line, _state(line, force)))
    return out


def _state(line: NarrationLine, force: set[str]) -> str:
    if line.beat is not None and (line.beat in force or "all" in force):
        return "stale"
    if line.audio is None:
        return "missing"
    if line.beat is not None and line.audio_target is not None:
        made_from = read_manifest(os.path.dirname(line.audio_target)).get(line.beat)
        if made_from is not None and made_from != text_hash(line.text):
            return "stale"
    return "ok"


def make(item: Plan, cfg: ProjectConfig) -> str:
    """Synthesize one line with the provider of `cfg`; returns where its audio is."""
    provider = configured_provider(cfg)
    if provider is None:
        raise KinemoError.make(
            "K1401",
            "kinemo voice needs a TTS provider",
            fixes=[("configure one in kinemo.toml", '[tts] provider = "command"  (or an installed provider)')],
        )
    line = item.line
    words = line.text.split()
    if line.beat is not None and line.audio_target is not None:
        target = line.audio_target
        os.makedirs(os.path.dirname(target), exist_ok=True)
        speech = with_word_times(provider.synthesize(line.text, line.voice, target), words)
        with open(f"{target}.json", "w", encoding="utf-8") as fh:
            json.dump({"word_times": speech.word_times}, fh)
        folder = os.path.dirname(target)
        manifest = read_manifest(folder)
        manifest[line.beat] = text_hash(line.text)
        write_manifest(folder, manifest)
        return target
    path = cache_path(cfg.cache_dir, provider.name, line.voice, line.text)
    if read_cached(path) is None:
        speech = with_word_times(provider.synthesize(line.text, line.voice, path), words)
        write_cached(path, speech)
    return path


def run(args: argparse.Namespace) -> int:
    try:
        module = load_module(args.file)
    except LoadError as e:
        print(e.diagnostic.render())
        return 1
    force = {beat.strip() for beat in (args.force or "").split(",") if beat.strip()}
    # The project of the scene file (the CLI itself lives elsewhere).
    cfg = load_project(os.path.dirname(os.path.abspath(args.file)))
    status = 0
    for defn in select(find_scenes(module), args.scene):
        with collecting_lines():
            result = build(defn, args.params)
        if result.scene is None:
            print("\n".join(d.render() for d in result.diagnostics))
            status = 1
            continue
        items = plan(list(result.scene.__dict__.get("_narration", [])), force)
        todo = [item for item in items if item.state != "ok"]
        print(f"{defn.name}: {len(items)} line(s), {len(todo)} to make")
        for item in items:
            label = item.line.beat or "(inline)"
            print(f"  {item.state:8} {label:10} {item.line.text[:60]}")
        if args.check:
            status = max(status, 1 if todo else 0)
            continue
        report = reporter(args.progress, defn.name)
        path = ""
        for done, item in enumerate(todo, 1):
            try:
                path = make(item, cfg)
            except KinemoError as error:
                print(error.diagnostic.render())
                return 1
            report(done, len(todo))
            print(f"  made     {item.line.beat or '(inline)':10} {path}")
        if todo:
            finished(args.progress, defn.name, os.path.dirname(path))
    return status
