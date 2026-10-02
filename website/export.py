"""Export the data the kinemo website shows (videos, real `kinemo check` output, timings).

    .venv/bin/python website/export.py      # or, in website/: npm run export

Then build the site with `npm run build` in website/. See website/README.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from siteexport.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
