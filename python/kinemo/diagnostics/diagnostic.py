"""The diagnostic model shared by errors, lints and `kinemo check --json`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Sequence

from .._runtime.spans import Span, user_span

Level = Literal["error", "warning", "hint"]


@dataclass(frozen=True)
class Edit:
    """Exact text replacement of a whole source line (1-based)."""

    file: str
    line: int
    replacement: str

    def json(self) -> dict[str, object]:
        return {"file": self.file, "line": self.line, "replacement": self.replacement}


@dataclass(frozen=True)
class Fix:
    description: str
    code: str | None = None
    edits: tuple[Edit, ...] = ()

    def json(self) -> dict[str, object]:
        return {"description": self.description, "code": self.code, "edits": [e.json() for e in self.edits]}


@dataclass
class Diagnostic:
    code: str
    level: Level
    message: str
    spans: list[Span] = field(default_factory=list)
    span_notes: list[str] = field(default_factory=list)
    time: float | None = None
    objects: list[str] = field(default_factory=list)
    fixes: list[Fix] = field(default_factory=list)

    def json(self) -> dict[str, object]:
        """The diagnostic as the stable JSON object of `kinemo check --json`."""
        return {
            "code": self.code,
            "level": self.level,
            "message": self.message,
            "spans": [{"file": s.file, "line": s.line, "col": s.col} for s in self.spans],
            "time": self.time,
            "objects": self.objects,
            "fixes": [f.json() for f in self.fixes],
        }

    def render(self) -> str:
        """The diagnostic as terminal text: code, message, source lines, instant and fixes."""
        level = self.level
        out = [f"{self.code} {level}: {self.message}"]
        for i, s in enumerate(self.spans):
            note = self.span_notes[i] if i < len(self.span_notes) else ""
            src = s.source_line()
            line = f"  --> {s.short():<18} {src}"
            if note:
                line += f"   ← {note}"
            out.append(line.rstrip())
        if self.time is not None:
            out.append(f"   t = {self.time:.2f} s")
        numbered = len(self.fixes) > 1
        for i, f in enumerate(self.fixes, 1):
            label = f"fix {i}" if numbered else "fix"
            out.append(f"  {label}: {f.description}")
            if f.code:
                out.extend("         " + c for c in f.code.splitlines())
        out.append(f"  more: kinemo explain {self.code}")
        return "\n".join(out)


FixSpec = tuple[str, "str | None"]


class KinemoError(Exception):
    """A build error. Always carries a diagnostic with a stable code and, when possible, a fix."""

    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.render())
        self.diagnostic = diagnostic

    @classmethod
    def make(
        cls,
        code: str,
        message: str,
        *,
        fixes: Sequence[FixSpec | Fix] = (),
        spans: Sequence[Span] = (),
        notes: Sequence[str] = (),
        time: float | None = None,
        objects: Sequence[str] = (),
    ) -> "KinemoError":
        span_list = list(spans) or [user_span()]
        fix_list = [f if isinstance(f, Fix) else Fix(f[0], f[1]) for f in fixes]
        return cls(
            Diagnostic(code, "error", message, span_list, list(notes), time, list(objects), fix_list)
        )



def replace_line(description: str, code: str, span: Span) -> Fix:
    """A safe, mechanically applicable fix: replace the whole offending line with `code`."""
    try:
        with open(span.file, encoding="utf-8") as fh:
            line = fh.readlines()[span.line - 1]
        indent = line[: len(line) - len(line.lstrip())]
    except (OSError, IndexError):
        return Fix(description, code)
    return Fix(description, code, (Edit(span.file, span.line, indent + code),))
