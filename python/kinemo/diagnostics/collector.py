"""Accumulates warnings and hints during build and resolve."""

from __future__ import annotations

from typing import Sequence

from .._runtime.spans import Span, user_span
from .diagnostic import Diagnostic, Fix, FixSpec


class Collector:
    def __init__(self) -> None:
        self.items: list[Diagnostic] = []
        self._allowed: set[str] = set()

    def allow(self, codes: Sequence[str]) -> None:
        self._allowed.update(codes)

    def is_allowed(self, d: Diagnostic) -> bool:
        """Silenced by the project config or a `# kinemo: allow CODE` comment on its lines."""
        return d.code in self._allowed or any(_allowed_inline(s, d.code) for s in d.spans)

    def warn(
        self,
        code: str,
        message: str,
        *,
        fixes: Sequence[FixSpec | Fix] = (),
        spans: Sequence[Span] = (),
        time: float | None = None,
        objects: Sequence[str] = (),
        level: str = "warning",
    ) -> None:
        if code in self._allowed:
            return
        span_list = list(spans) or [user_span()]
        if any(_allowed_inline(s, code) for s in span_list):
            return
        fix_list = [f if isinstance(f, Fix) else Fix(f[0], f[1]) for f in fixes]
        d = Diagnostic(code, level, message, span_list, [], time, list(objects), fix_list)  # type: ignore[arg-type]
        if not any(_same(d, o) for o in self.items):
            self.items.append(d)


def _same(a: Diagnostic, b: Diagnostic) -> bool:
    return a.code == b.code and a.spans[:1] == b.spans[:1] and a.objects == b.objects


def _allowed_inline(s: Span, code: str) -> bool:
    """`# kinemo: allow W1002` on the offending line silences that lint."""
    line = s.source_line()
    marker = "# kinemo: allow"
    if marker not in line:
        return False
    allowed = line.split(marker, 1)[1].replace(",", " ").split()
    return code in allowed
