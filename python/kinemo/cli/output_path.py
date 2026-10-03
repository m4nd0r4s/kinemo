"""`--out` of `render` and `snap`: a folder, where files are named after the scene, or a
single file when the path ends with an output extension (`--out clip.gif`)."""

from __future__ import annotations

import os


def single_file(out: str, extensions: tuple[str, ...]) -> tuple[str, str] | None:
    """`(path, extension)` when `out` names one file with one of `extensions`."""
    extension = os.path.splitext(out)[1].lower().lstrip(".")
    return (out, extension) if extension in extensions else None


def ensure_folder_of(path: str) -> None:
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
