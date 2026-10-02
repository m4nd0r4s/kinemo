"""Every relative link in the Markdown docs points to an existing file and anchor."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = sorted([*(ROOT / "docs").rglob("*.md"), ROOT / "README.md"])
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)
EXPLICIT = re.compile(r'<a id="([^"]+)"')
FENCE = re.compile(r"```.*?```", re.S)


def slug(heading: str) -> str:
    """GitHub-style anchor of a heading."""
    text = re.sub(r"[`*_]|<[^>]+>", "", heading).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    text = FENCE.sub("", path.read_text(encoding="utf-8"))
    found = set(EXPLICIT.findall(text))
    seen: dict[str, int] = {}
    for h in HEADING.findall(text):
        base = slug(h)
        n = seen.get(base, 0)
        found.add(base if n == 0 else f"{base}-{n}")
        seen[base] = n + 1
    return found


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: str(p.relative_to(ROOT)))
def test_links_resolve(doc: Path) -> None:
    text = FENCE.sub("", doc.read_text(encoding="utf-8"))
    broken: list[str] = []
    for target in LINK.findall(text) + IMAGE.findall(text):
        if re.match(r"[a-z]+:", target) or target.startswith("#") and False:
            continue
        path_part, _, anchor = target.partition("#")
        dest = doc if not path_part else (doc.parent / path_part).resolve()
        if not dest.exists():
            broken.append(f"{target} (missing file)")
        elif anchor and dest.suffix == ".md" and anchor not in anchors(dest):
            broken.append(f"{target} (missing anchor)")
    assert not broken, "\n".join(broken)
