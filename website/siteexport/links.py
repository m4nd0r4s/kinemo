"""Check the built site: every relative link and image resolves to a file, and every
`#anchor` to an element of the target page."""

from __future__ import annotations

import re
from pathlib import Path

_REF = re.compile(r'(?:href|src|poster)="([^"]+)"')
_ID = re.compile(r'\bid="([^"]+)"')


def broken_links(out: Path, ignore: tuple[str, ...] = ()) -> list[str]:
    """`page: target` for each internal reference that does not resolve. Targets starting
    with one of `ignore` (site paths such as `media/`) are skipped."""
    ids: dict[Path, set[str]] = {}

    def anchors(page: Path) -> set[str]:
        if page not in ids:
            ids[page] = set(_ID.findall(page.read_text())) if page.suffix == ".html" else set()
        return ids[page]

    problems: list[str] = []
    for page in sorted(out.rglob("*.html")):
        for target in _REF.findall(page.read_text()):
            if re.match(r"[a-z][a-z0-9+.-]*:", target) or target.startswith("//"):
                continue
            path_part, _, anchor = target.partition("#")
            path_part = path_part.split("?", 1)[0]
            resolved = (page.parent / path_part).resolve() if path_part else page
            site_path = resolved.relative_to(out.resolve()).as_posix() if resolved.is_relative_to(out.resolve()) else str(resolved)
            if any(site_path.startswith(prefix) for prefix in ignore):
                continue
            label = f"{page.relative_to(out)}: {target}"
            if not resolved.exists():
                problems.append(label)
            elif anchor and resolved.suffix == ".html" and anchor not in anchors(resolved):
                problems.append(label)
    return problems
