"""Project configuration from `kinemo.toml` (decorator > kinemo.toml > defaults; CLI wins)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any


@dataclass(frozen=True)
class ProjectConfig:
    root: str
    scene: dict[str, Any] = field(default_factory=dict)
    #: `[presets.<name>]`: named sets of scene defaults, chosen with `@k.scene(preset="name")`.
    presets: dict[str, dict[str, Any]] = field(default_factory=dict)
    render: dict[str, Any] = field(default_factory=dict)
    lints_allow: tuple[str, ...] = ()
    tts_provider: str | None = None
    #: `[tts] command` of the command provider, as an argv list.
    tts_command: tuple[str, ...] = ()
    #: Speaking rate of the estimate used when there is no audio (`[tts] wpm`).
    tts_wpm: float = 150.0
    #: `[tts] on_build`: `synthesize` (lines without audio are made while the scene builds) or
    #: `estimate` (they stay estimated until `kinemo voice` or `kinemo render` makes them).
    #: Unset: `estimate` for the command provider (a model load per line), else `synthesize`.
    tts_on_build: str | None = None
    #: `[audio] loudness`: integrated loudness target of rendered audio, in LUFS.
    audio_loudness: float | None = None
    #: `[audio] trim_silence`: trim the silence around each narration line.
    audio_trim_silence: bool = False
    #: `[align] model`: the speech model that aligns words to narration audio (`kinemo[align]`).
    align_model: str = "base.en"
    cache_dir: str = ".kinemo-cache"
    editor: str = "vscode"
    python_workers_threshold: float = 2.0


def find_root(start: str) -> str | None:
    path = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(path, "kinemo.toml")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def synthesizes_on_build(cfg: ProjectConfig) -> bool:
    """Whether a build makes the audio of lines that have none (`[tts] on_build`)."""
    if cfg.tts_on_build is not None:
        return cfg.tts_on_build != "estimate"
    return cfg.tts_provider != "command"


@lru_cache(maxsize=8)
def load(start: str) -> ProjectConfig:
    root = find_root(start)
    if root is None:
        return ProjectConfig(root=os.path.abspath(start))
    with open(os.path.join(root, "kinemo.toml"), "rb") as fh:
        data = tomllib.load(fh)
    tts = data.get("tts", {})
    cache = data.get("cache", {})
    return ProjectConfig(
        root=root,
        scene=dict(data.get("scene", {})),
        presets={name: dict(values) for name, values in data.get("presets", {}).items()},
        render=dict(data.get("render", {})),
        lints_allow=tuple(data.get("lints", {}).get("allow", ())),
        tts_provider=tts.get("provider"),
        tts_command=_argv(tts.get("command", ())),
        tts_wpm=float(tts.get("wpm", 150.0)),
        tts_on_build=tts.get("on_build"),
        audio_loudness=float(data["audio"]["loudness"]) if "loudness" in data.get("audio", {}) else None,
        audio_trim_silence=bool(data.get("audio", {}).get("trim_silence", False)),
        align_model=str(data.get("align", {}).get("model", "base.en")),
        cache_dir=os.path.join(root, cache.get("dir", ".kinemo-cache")),
        editor=data.get("editor", {}).get("command", "vscode"),
        python_workers_threshold=float(data.get("python", {}).get("workers_threshold", 2.0)),
    )


def _argv(command: Any) -> tuple[str, ...]:
    """`command` as written in kinemo.toml: a list of arguments, or one string split like a shell."""
    if isinstance(command, str):
        import shlex

        return tuple(shlex.split(command))
    return tuple(str(part) for part in command)


def project_config() -> ProjectConfig:
    """Configuration of the project containing the scene being loaded (its file's folder,
    found by `kinemo.toml` upwards), else of the working directory."""
    from ._runtime.spans import user_span

    span = user_span()
    if os.path.isfile(span.file):
        return load(os.path.dirname(os.path.abspath(span.file)))
    return load(os.getcwd())
