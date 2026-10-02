"""Small, exact source-line rewrites used by lint fixes."""

from __future__ import annotations

from ..diagnostics import Edit, Fix


def char_column(line: str, byte_column: int) -> int:
    """`ast` columns are UTF-8 byte offsets; convert to a `str` index."""
    return len(line.encode("utf-8")[:byte_column].decode("utf-8", errors="ignore"))


def indentation(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def matching_paren(text: str, open_index: int) -> int | None:
    """Index of the `)` closing the `(` at `open_index`, skipping string literals."""
    depth = 0
    quote: str | None = None
    i = open_index
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def with_keyword_in_call(line: str, method: str, keyword: str, value: str) -> str | None:
    """`line` with `keyword=value` set in the last `.method(...)` call on it.

    Replaces an existing `keyword=...` argument, or appends one. `None` when the call
    does not open and close on this line.
    """
    start = line.rfind(f".{method}(")
    if start < 0:
        return None
    open_index = start + len(method) + 1
    close_index = matching_paren(line, open_index)
    if close_index is None:
        return None
    inside = line[open_index + 1 : close_index]
    marker = f"{keyword}="
    if marker in inside:
        kw_start = open_index + 1 + inside.index(marker)
        value_start = kw_start + len(marker)
        value_end = value_start
        depth = 0
        while value_end < close_index:
            ch = line[value_end]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "," and depth == 0:
                break
            value_end += 1
        return line[:value_start] + value + line[value_end:]
    separator = ", " if inside.strip() else ""
    return line[:close_index] + f"{separator}{keyword}={value}" + line[close_index:]


def line_fix(description: str, file: str, line_number: int, new_line: str) -> Fix:
    """A safe fix replacing the whole line `line_number` (1-based) of `file` with `new_line`."""
    return Fix(description, new_line.strip(), (Edit(file, line_number, new_line.rstrip("\n")),))


def read_line(file: str, line_number: int) -> str | None:
    try:
        with open(file, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None
    return lines[line_number - 1] if 0 < line_number <= len(lines) else None
