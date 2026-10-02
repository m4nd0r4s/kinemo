"""Where media files (`k.Image`, `k.SVG`) are looked up, and the error when they are missing."""

from __future__ import annotations

import os
from typing import Any

from .._runtime.spans import user_span
from ..diagnostics import KinemoError


def resolve_media_path(path: Any, what: str) -> str:
    """Absolute path of `path`: as given when absolute, else next to the scene file, else
    relative to the working directory. Rendering later reads the file from this path."""
    if not isinstance(path, str | os.PathLike):
        raise KinemoError.make("K0105", f"{what} expects a file path, got {type(path).__name__}", spans=[user_span()])
    raw = os.fspath(path)
    candidates = [raw] if os.path.isabs(raw) else []
    if not candidates:
        span = user_span()
        if os.path.isfile(span.file):
            candidates.append(os.path.join(os.path.dirname(os.path.abspath(span.file)), raw))
        candidates.append(os.path.abspath(raw))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    raise KinemoError.make(
        "K0105",
        f"{what}: file not found: {raw!r}",
        spans=[user_span()],
        fixes=[("relative paths start from the scene file's folder", None)],
    )


def media_error(what: str, path: str, reason: str) -> KinemoError:
    return KinemoError.make("K0105", f"{what}: could not read {os.path.basename(path)!r}: {reason}", spans=[user_span()])
