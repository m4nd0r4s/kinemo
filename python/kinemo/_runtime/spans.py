"""Capture the user's source location for every IR node and diagnostic."""

from __future__ import annotations

import linecache
import os
import sys
import sysconfig
from dataclasses import dataclass
from types import CodeType, FrameType

_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass(frozen=True)
class Span:
    """A place in a source file. `col` is a 0-based character index on `line`. When the span
    covers an expression (a call captured by `user_span`), `end_line`/`end_col` mark its end
    (exclusive); `end_line == 0` means the span is a single point."""

    file: str
    line: int
    col: int = 0
    end_line: int = 0
    end_col: int = 0

    def ir(self) -> dict[str, object]:
        out: dict[str, object] = {"file": self.file, "line": self.line, "col": self.col}
        if self.end_line:
            out["end_line"] = self.end_line
            out["end_col"] = self.end_col
        return out

    def short(self) -> str:
        return f"{os.path.basename(self.file)}:{self.line}"

    def source_line(self) -> str:
        return linecache.getline(self.file, self.line).strip() if self.line > 0 else ""


UNKNOWN = Span("<unknown>", 0)


def _is_internal(filename: str) -> bool:
    path = os.path.abspath(filename)
    return (
        path.startswith(_PKG_DIR + os.sep)
        or filename.startswith("<frozen")
        or os.path.basename(path) == "contextlib.py"
    )


def user_span(skip: int = 1) -> Span:
    """First stack frame outside the kinemo package, covering the call being executed there
    (the exact expression, so tools can find and edit its arguments)."""
    frame = sys._getframe(skip)
    while frame is not None:
        if not _is_internal(frame.f_code.co_filename):
            return _call_span(frame)
        frame = frame.f_back
    return UNKNOWN


#: Folders of the standard library and installed packages: never part of a user call stack.
_LIBRARIES = tuple(
    os.path.abspath(p) + os.sep for p in {sysconfig.get_path(name) for name in ("stdlib", "platstdlib", "purelib", "platlib")} if p
)
#: Deepest user call chain recorded.
STACK_LIMIT = 8


def user_stack(skip: int = 1, root: CodeType | None = None) -> tuple[Span, ...]:
    """The user frames calling the current one, innermost first: the scene's lines that led to
    this call, through clips, components and helper functions (kinemo, the standard library
    and installed packages are left out). It stops at `root` (the scene function), so the code
    that built the scene (a script, a test) is not part of it."""
    frame = sys._getframe(skip)
    out: list[Span] = []
    while frame is not None and len(out) < STACK_LIMIT:
        name = frame.f_code.co_filename
        path = os.path.abspath(name)
        if not _is_internal(name) and not path.startswith(_LIBRARIES) and not name.startswith("<"):
            out.append(_call_span(frame))
        if root is not None and frame.f_code is root:
            break
        frame = frame.f_back
    return tuple(out)


def _call_span(frame: FrameType) -> Span:
    file, line = frame.f_code.co_filename, frame.f_lineno
    positions = list(frame.f_code.co_positions())
    index = frame.f_lasti // 2
    if not 0 <= index < len(positions):
        return Span(file, line)
    start_line, end_line, start_byte, end_byte = positions[index]
    if start_line is None or start_line != line or end_line is None or start_byte is None or end_byte is None:
        return Span(file, line)
    start_text = linecache.getline(file, start_line)
    end_text = start_text if end_line == start_line else linecache.getline(file, end_line)
    return Span(file, line, _char_index(start_text, start_byte), end_line, _char_index(end_text, end_byte))


def _char_index(text: str, byte_offset: int) -> int:
    """Code positions are UTF-8 byte offsets; spans use `str` indices."""
    return len(text.encode("utf-8")[:byte_offset].decode("utf-8", errors="ignore"))


def created_by_user(obj: object) -> bool:
    """Whether the code that constructed `obj` is user code (not kinemo internals)."""
    frame = sys._getframe(1)
    while frame is not None and frame.f_locals.get("self") is obj:
        frame = frame.f_back
    return frame is not None and not _is_internal(frame.f_code.co_filename)
