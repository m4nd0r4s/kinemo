"""Load scene code from edited text instead of the file on disk.

While a value is dragged in the preview, each step rebuilds the scene from the edited text
without touching the file; the file is written once, when the drag ends.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import linecache
import os
import sys
from contextlib import contextmanager
from types import CodeType
from typing import Iterator, Sequence


class TextLoader(importlib.machinery.SourceFileLoader):
    """Loads a module from `text`, compiled as if it were the file at `path`."""

    def __init__(self, fullname: str, path: str, text: str) -> None:
        super().__init__(fullname, path)
        self.text = text

    def get_code(self, fullname: str) -> CodeType:  # pyright: ignore[reportIncompatibleMethodOverride]
        return compile(self.text, self.path, "exec", dont_inherit=True)

    def get_source(self, fullname: str) -> str:
        return self.text


class _OverrideFinder(importlib.abc.MetaPathFinder):
    def __init__(self, texts: dict[str, str]) -> None:
        self.texts = texts

    def find_spec(self, fullname: str, path: Sequence[str] | None, target: object = None) -> importlib.machinery.ModuleSpec | None:
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.origin is None:
            return None
        origin = os.path.abspath(spec.origin)
        if origin not in self.texts:
            return None
        return importlib.machinery.ModuleSpec(fullname, TextLoader(fullname, origin, self.texts[origin]), origin=origin)


@contextmanager
def source_overrides(texts: dict[str, str]) -> Iterator[None]:
    """Imports of the files in `texts` (absolute path → text) read the text instead; source
    lookups (`linecache`, used for spans and names) see it too."""
    finder = _OverrideFinder(texts)
    saved = {path: linecache.cache.get(path) for path in texts}
    for path, text in texts.items():
        lines = [line + "\n" for line in text.split("\n")]
        linecache.cache[path] = (len(text), None, lines, path)
    sys.meta_path.insert(0, finder)
    try:
        yield
    finally:
        sys.meta_path.remove(finder)
        for path, entry in saved.items():
            if entry is None:
                linecache.cache.pop(path, None)
            else:
                linecache.cache[path] = entry
