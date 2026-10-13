"""The lint corpus (`tests/lint_corpus/`): each scene's first line says which diagnostics
`kinemo check` must report. A lint change shows here as a false positive (reported, not
expected) or a miss (expected, not reported)."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from kinemo.cli.main import main

CORPUS = Path(__file__).resolve().parents[1] / "lint_corpus"
SCENES = sorted(CORPUS.glob("*.py"))
EXPECT = re.compile(r"^# expect: (?P<codes>.+)$")


def expected_codes(path: Path) -> set[str]:
    first = path.read_text(encoding="utf-8").splitlines()[0]
    match = EXPECT.match(first)
    assert match, f"{path.name}: the first line must be '# expect: CODE, ...' or '# expect: none'"
    codes = match.group("codes").strip()
    return set() if codes == "none" else {c.strip() for c in codes.split(",")}


def test_the_corpus_has_scenes() -> None:
    assert len(SCENES) >= 8


@pytest.mark.parametrize("path", SCENES, ids=[p.stem for p in SCENES])
def test_corpus_scene_reports_exactly_what_it_expects(path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # A copy, so `check` never writes next to the corpus.
    scene = tmp_path / path.name
    shutil.copy(path, scene)
    main(["check", str(scene), "--json"])
    report = json.loads(capsys.readouterr().out)
    reported = {d["code"] for s in report["scenes"] for d in s["diagnostics"] if d["code"][0] == "W"}
    expected = expected_codes(path)
    assert reported == expected, f"{path.name}: false positives {sorted(reported - expected)}, misses {sorted(expected - reported)}"
