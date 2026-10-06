"""Offline docs: every canonical example passes `check --strict`, lookups by any alias,
`llms.txt` generation and full coverage of `kinemo.__all__`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import kinemo as k
from kinemo.cli import docs_cmd
from kinemo.docs import catalog, llms, reference, signatures
from kinemo.docs.entry import DocEntry
from kinemo.docs.validation import MAX_EXAMPLE_LINES, check_example

ROOT = Path(__file__).resolve().parents[2]
ENTRIES = catalog.entries()


# ---- canonical examples ---------------------------------------------------------------------

@pytest.mark.parametrize("entry", ENTRIES, ids=[e.symbol for e in ENTRIES])
def test_example_builds_with_zero_diagnostics(entry: DocEntry, tmp_path: Path) -> None:
    report = check_example(entry, directory=str(tmp_path))
    assert report.scenes, f"{entry.symbol}: the example defines no scene"
    assert report.ok, report.render()


@pytest.mark.parametrize("entry", ENTRIES, ids=[e.symbol for e in ENTRIES])
def test_example_is_short_and_self_contained(entry: DocEntry) -> None:
    lines = entry.example.rstrip("\n").splitlines()
    assert len(lines) <= MAX_EXAMPLE_LINES
    assert "import kinemo as k" in lines
    assert "@k.scene" in entry.example


@pytest.mark.parametrize("entry", ENTRIES, ids=[e.symbol for e in ENTRIES])
def test_summary_is_one_paragraph(entry: DocEntry) -> None:
    assert entry.summary and "\n" not in entry.summary


def test_related_symbols_are_documented_or_not_yet_implemented() -> None:
    for e in ENTRIES:
        for symbol in e.related:
            assert catalog.entry(symbol) is not None or not signatures.exists(symbol), (e.symbol, symbol)


def test_check_example_reports_diagnostics() -> None:
    broken = DocEntry("k.draw", "Verbs", "x", "import kinemo as k\n\n@k.scene\ndef c(s: k.Scene):\n    s.play(k.Circle().to(x=1))\n")
    report = check_example(broken)
    assert not report.ok
    assert [d.code for d in report.diagnostics] == ["K0101"]


# ---- coverage -----------------------------------------------------------------------------

def test_every_public_name_is_documented_or_listed_as_internal() -> None:
    assert catalog.coverage_gaps() == [], "document it in kinemo/docs/examples or list it in UNDOCUMENTED_INTERNAL"


def test_redirects_and_internal_names_are_real() -> None:
    for name, target in catalog.DOCUMENTED_BY.items():
        if name in k.__all__:
            assert catalog.entry(target) is not None, (name, target)
    assert set(catalog.UNDOCUMENTED_INTERNAL) <= set(k.__all__)


def test_symbols_are_unique() -> None:
    symbols = [e.symbol for e in ENTRIES]
    assert len(symbols) == len(set(symbols))


def test_missing_symbols_are_skipped() -> None:
    assert signatures.resolve("k.does_not_exist") is signatures.MISSING
    assert signatures.resolve("Scene.does_not_exist") is signatures.MISSING


# ---- lookup -------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("query", "symbol"),
    [
        ("k.draw", "k.draw"),
        ("draw", "k.draw"),
        ("kinemo.draw", "k.draw"),
        ("Scene.play", "Scene.play"),
        ("s.play", "Scene.play"),
        ("play", "Scene.play"),
        ("Axes.plot", "Axes.plot"),
        ("ax.plot", "Axes.plot"),
        ("k.Axes.plot", "Axes.plot"),
        ("@k.scene", "k.scene"),
        ("with s.during", "Scene.during"),
        ("k.draw()", "k.draw"),
        ("k.cos", "k.sin"),
        ("k.Signal", "k.signal"),
        ("x.to", "k.signal"),
        ("Row.swap", "Group.swap"),
        ("Circle.to", "Node.to"),
        ("k.Polygon.regular", "k.Polygon"),
        ("e.value", "k.EventInfo"),
        ("k.red", "k.BLUE"),
    ],
)
def test_lookup_by_alias(query: str, symbol: str) -> None:
    found = catalog.lookup(query)
    assert found.entry is not None, found.suggestions
    assert found.entry.symbol == symbol


def test_morph_lookup_when_implemented() -> None:
    if not signatures.exists("k.morph"):
        pytest.skip("k.morph does not exist yet")
    assert catalog.lookup("k.morph").entry.symbol == "k.morph"  # type: ignore[union-attr]
    assert catalog.lookup("morph").entry.symbol == "k.morph"  # type: ignore[union-attr]


def test_unknown_symbol_gets_suggestions() -> None:
    found = catalog.lookup("fadein")
    assert found.entry is None
    assert "k.fade_in" in found.suggestions


# ---- CLI ----------------------------------------------------------------------------------

def _run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    docs_cmd.add_arguments(parser)
    return docs_cmd.run(parser.parse_args(argv))


def test_cli_prints_signature_summary_example_and_related(capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(["s.play"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("s.play(*anims, duration=None, ease=None, at=None)")
    assert "example:" in out and "@k.scene" in out
    assert "see also: s.start" in out


def test_cli_lists_methods_of_classes(capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(["k.Axes"]) == 0
    out = capsys.readouterr().out
    assert "methods:" in out and "ax.plot(fn" in out


def test_cli_unknown_symbol_exits_1_with_suggestions(capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(["drw"]) == 1
    out = capsys.readouterr().out
    assert "is not documented" in out and "k.draw" in out


def test_cli_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(["ax.plot", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["found"] and payload["canonical"] == "Axes.plot"
    assert payload["signature"].startswith("ax.plot(fn")


def test_cli_without_symbol_lists_areas(capsys: pytest.CaptureFixture[str]) -> None:
    assert _run([]) == 0
    out = capsys.readouterr().out
    assert "Verbs: k.draw" in out


# ---- llms.txt ---------------------------------------------------------------------------

def test_llms_txt_has_every_section() -> None:
    text = llms.generate()
    for heading in ("## Rules", "## Recommended loop for agents", "## API", "## Diagnostics", "## Manim → kinemo"):
        assert heading in text
    assert all(rule.split(".")[0] in text for rule in reference.RULES)
    assert "| K04xx | Layout and constraints |" in text
    assert "`self.play(Create(x))` | `s.play(k.draw(x))`" in text
    for e in ENTRIES:
        assert signatures.display_name(e.symbol) in text
    assert len(text.splitlines()) < 2500


def test_llms_txt_is_deterministic() -> None:
    assert llms.generate() == llms.generate()


def test_manim_rows_need_their_symbols() -> None:
    for row in reference.MANIM_TABLE:
        assert (row in reference.manim_rows()) == all(signatures.exists(s) for s in row.requires)


def test_committed_llms_txt_is_up_to_date() -> None:
    path = ROOT / "docs" / "llms.txt"
    assert path.exists(), "generate with: python -m kinemo.docs.llms > docs/llms.txt"
    assert path.read_text(encoding="utf-8") == llms.generate(), "regenerate: python -m kinemo.docs.llms > docs/llms.txt"
