"""The website builds from the repository with every internal link and anchor resolving.

Exports the data without rendering videos or measuring timings, builds the SvelteKit site
into a temporary folder (the build itself fails on a broken `#anchor`), then checks every
relative link. Skipped when the site's npm dependencies are not installed (`npm install` in
website/).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WEBSITE = ROOT / "website"

pytestmark = pytest.mark.skipif(
    not (WEBSITE / "node_modules").exists() or shutil.which("npm") is None,
    reason="the website's npm dependencies are not installed",
)

sys.path.insert(0, str(WEBSITE))


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from siteexport.main import export

    out = tmp_path_factory.mktemp("site")
    data = tmp_path_factory.mktemp("data") / "site-data.json"
    export(videos=False, measure=False, data_file=data)
    run = subprocess.run(
        ["npm", "run", "build"], cwd=WEBSITE, env={**os.environ, "KINEMO_SITE_OUT": str(out), "KINEMO_SITE_DATA": str(data)},
        capture_output=True, text=True, check=False,
        encoding="utf-8",
    )
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return out


def test_every_internal_link_resolves(site: Path) -> None:
    from siteexport.links import broken_links

    assert broken_links(site, ignore=("media/",)) == []


def test_every_docs_file_has_a_page(site: Path) -> None:
    pages = {p.relative_to(site).as_posix() for p in site.rglob("index.html")}
    assert {"index.html", "docs/index.html", "docs/guide/getting-started/index.html", "docs/reference/scene/index.html", "docs/caveats/index.html"} <= pages
    guides = len(list((ROOT / "docs" / "guide").glob("*.md")))
    assert len([p for p in pages if p.startswith("docs/guide/")]) == guides


def test_the_search_index_covers_symbols_and_sections(site: Path) -> None:
    index = json.loads((site / "search.json").read_text(encoding="utf-8"))
    sections = {entry["section"] for entry in index}
    assert "Constraints versus animation" in sections
    assert "k.Node.to_place (method)" in sections
    assert all(entry["url"].startswith("docs/") for entry in index)


def test_the_landing_page_shows_real_output(site: Path) -> None:
    page = (site / "index.html").read_text(encoding="utf-8")
    assert "cannot animate x: the axis is held by a constraint" in page
    assert "K1101 error" in page
    assert "examples/derivative.py" in page
