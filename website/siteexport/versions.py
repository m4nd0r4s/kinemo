"""The documentation versions the site publishes: the newest release of each minor version
(read from the git tags reachable from the current commit) and `dev`, the docs of the
current checkout.

Each release's `docs/` is extracted with `git archive` into `website/.versions/<minor>/docs/`,
where the site reads it; old versions need no old kinemo, since the reference pages are
committed with the docs."""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any

from .paths import ROOT, WEBSITE

#: Where the releases' docs are extracted.
VERSIONS = WEBSITE / ".versions"
_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def release_tags() -> dict[str, str]:
    """Minor version → its newest patch tag, oldest first (`{"0.10": "v0.10.1", ...}`).
    Only tags reachable from HEAD count, so a local tag on another branch never publishes."""
    run = subprocess.run(["git", "tag", "--merged", "HEAD", "--list", "v*"], cwd=ROOT, capture_output=True, text=True, check=False, encoding="utf-8")
    newest: dict[tuple[int, int], tuple[int, str]] = {}
    for tag in run.stdout.split():
        match = _TAG.match(tag)
        if match is None:
            continue
        major, minor, patch = (int(part) for part in match.groups())
        if (major, minor) not in newest or patch > newest[(major, minor)][0]:
            newest[(major, minor)] = (patch, tag)
    return {f"{major}.{minor}": tag for (major, minor), (_, tag) in sorted(newest.items())}


def extract(tag: str, minor: str) -> bool:
    """`docs/` of `tag` into `.versions/<minor>/docs`; False when the tag has no docs."""
    archive = subprocess.run(["git", "archive", "--format=tar", tag, "docs"], cwd=ROOT, capture_output=True, check=False)
    if archive.returncode != 0:
        return False
    target = VERSIONS / minor
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(target, filter="data")
    return (target / "docs" / "README.md").exists()


def export_versions() -> dict[str, Any]:
    """Extract every release's docs; the site data's `docs_versions`."""
    releases = [{"id": minor, "tag": tag} for minor, tag in release_tags().items() if extract(tag, minor)]
    releases.reverse()  # newest first, as the switcher lists them
    return {"latest": releases[0]["id"] if releases else "dev", "releases": releases}
