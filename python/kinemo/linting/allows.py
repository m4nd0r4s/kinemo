"""W0120: `# kinemo: allow CODE` comments that silence nothing.

An allow outlives what it silenced: a lint gets more precise, the offending code moves. Left in
place, it would hide a real problem on that line later. `kinemo check` compares the comments in
the checked file with the allows that silenced something while building every scene in it.
"""

from __future__ import annotations

import io
import re
import tokenize

from .._runtime.spans import Span
from ..diagnostics import Diagnostic, Fix
from .source_edits import line_fix

MARKER = re.compile(r"#\s*kinemo:\s*allow\b(?P<codes>[^(#]*)")
CODE = re.compile(r"\b[KW]\d{4}\b")


def allow_comments(path: str, text: str) -> list[tuple[int, list[str], str]]:
    """Each `# kinemo: allow ...` comment of `text`: (line, codes, the comment's text)."""
    out: list[tuple[int, list[str], str]] = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return out
    for token in tokens:
        if token.type == tokenize.COMMENT:
            match = MARKER.search(token.string)
            if match:
                out.append((token.start[0], CODE.findall(match.group("codes")), token.string))
    return out


def unused_allows(path: str, text: str, used: set[tuple[str, int, str]]) -> list[Diagnostic]:
    """W0120 for each code of an allow comment in `path` that silenced nothing."""
    lines = text.splitlines()
    out: list[Diagnostic] = []
    for line, codes, comment in allow_comments(path, text):
        unused = [c for c in codes if (path, line, c) not in used]
        if not unused:
            continue
        kept = [c for c in codes if c not in unused]
        source = lines[line - 1]
        if kept:
            match = MARKER.search(comment)
            assert match is not None
            reason = comment[match.end("codes") :]
            new_comment = comment[: match.start("codes")] + " " + ", ".join(kept) + (" " + reason if reason else "")
            new_line = source.replace(comment, new_comment)
            description = f"remove {', '.join(unused)} from the allow comment"
        else:
            new_line = source.replace(comment, "").rstrip()
            description = "remove the allow comment"
        named = ", ".join(unused)
        message = f"# kinemo: allow {named} silences nothing on this line"
        out.append(Diagnostic("W0120", "warning", message, [Span(path, line)], [], None, [], [line_fix(description, path, line, new_line)]))  # type: ignore[arg-type]
    return out
