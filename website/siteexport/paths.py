"""Where the export reads from and writes to."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"
WEBSITE = ROOT / "website"
#: Rendered media, reused while the example's source does not change.
CACHE = WEBSITE / ".cache"
#: Videos and posters, served by the site as static files.
MEDIA = WEBSITE / "static" / "media"
#: The data the Svelte pages import.
DATA = WEBSITE / "src" / "lib" / "generated" / "site-data.json"
#: The built site (`npm run build`).
BUILD = WEBSITE / "build"
