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
    render: dict[str, Any] = field(default_factory=dict)
    lints_allow: tuple[str, ...] = ()
    tts_provider: str | None = None
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
        render=dict(data.get("render", {})),
        lints_allow=tuple(data.get("lints", {}).get("allow", ())),
        tts_provider=tts.get("provider"),
        cache_dir=os.path.join(root, cache.get("dir", ".kinemo-cache")),
        editor=data.get("editor", {}).get("command", "vscode"),
        python_workers_threshold=float(data.get("python", {}).get("workers_threshold", 2.0)),
    )


def project_config() -> ProjectConfig:
    """Configuration of the project containing the scene being loaded (its file's folder,
    found by `kinemo.toml` upwards), else of the working directory."""
    from ._runtime.spans import user_span

    span = user_span()
    if os.path.isfile(span.file):
        return load(os.path.dirname(os.path.abspath(span.file)))
    return load(os.getcwd())
