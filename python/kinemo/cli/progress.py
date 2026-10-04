"""Progress of long commands (`render`, `voice`) on stderr: a bar for people, or one JSON
object per line for tools (`--progress json`)."""

from __future__ import annotations

import json
import sys
from typing import Callable

#: `report(done, total)`.
Reporter = Callable[[int, int], None]


def reporter(style: str, name: str) -> Reporter:
    """A progress callback for one scene (or movie) named `name`."""
    if style == "json":
        return lambda done, total: _emit({"event": "progress", "scene": name, "done": done, "total": total})
    if style == "none":
        return lambda done, total: None
    return _bar(name)


def finished(style: str, name: str, path: str) -> None:
    """The output of `name` is written."""
    if style == "json":
        _emit({"event": "done", "scene": name, "path": path})


def _emit(event: dict[str, object]) -> None:
    sys.stderr.write(json.dumps(event) + "\n")
    sys.stderr.flush()


def _bar(name: str) -> Reporter:
    def report(done: int, total: int) -> None:
        if done == total or done % 10 == 0:
            width = 30
            filled = int(width * done / total) if total else width
            sys.stderr.write(f"\r  {name} [{'#' * filled}{'.' * (width - filled)}] {done}/{total}")
            if done == total:
                sys.stderr.write("\n")
            sys.stderr.flush()

    return report
