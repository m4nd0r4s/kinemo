"""Markdown API reference (`docs/reference/`): the committed pages match the generator,
every public name and catalog example is in them, and every internal link resolves."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import kinemo as k
from kinemo.cli.main import parser as cli_parser
from kinemo.diagnostics import CATALOG
from kinemo.docs import catalog
from kinemo.docs.markdown import generate
from kinemo.docs.markdown.cli_page import EXAMPLES, _subcommands
from kinemo.docs.markdown.symbol_sections import _example_body
from kinemo.docs.markdown.symbols import all_symbols, symbols_by_area

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "docs" / "reference"
REGENERATE = "regenerate: python -m kinemo.docs.markdown docs/reference"
PAGES = generate()
ALL_TEXT = "\n".join(PAGES.values())
ANCHOR = re.compile(r'<a id="([^"]+)"></a>')
LINK = re.compile(r"\]\(([^)\s]+)\)")


# ---- up to date ------------------------------------------------------------------------------

def test_generator_is_deterministic() -> None:
    assert generate() == PAGES


@pytest.mark.parametrize("name", sorted(PAGES))
def test_committed_page_is_up_to_date(name: str) -> None:
    path = REFERENCE / name
    assert path.exists(), f"docs/reference/{name} is missing; {REGENERATE}"
    assert path.read_text(encoding="utf-8") == PAGES[name], f"docs/reference/{name} is stale; {REGENERATE}"


def test_no_stale_pages_are_committed() -> None:
    committed = {p.name for p in REFERENCE.glob("*.md")}
    assert committed == set(PAGES), f"unexpected pages {sorted(committed - set(PAGES))}; delete them"


# ---- coverage --------------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(k.__all__))
def test_every_public_name_is_in_the_reference(name: str) -> None:
    assert f"`k.{name}`" in ALL_TEXT
    documented = [s for s in all_symbols() if s.qualified == f"k.{name}"]
    assert len(documented) == 1, f"k.{name} must have exactly one section"
    symbol = documented[0]
    assert f'<a id="{symbol.anchor}"></a>' in PAGES[symbol.page]
    assert f"({symbol.page}#{symbol.anchor})" in PAGES["README.md"], "missing from the index"


def test_every_catalog_entry_and_example_is_in_the_reference() -> None:
    for entry in catalog.entries():
        assert _example_body(entry) in ALL_TEXT, f"{entry.symbol}: example missing"


def test_public_class_members_have_sections() -> None:
    for owner, member in (
        ("Scene", "play"), ("Scene", "wait_for"), ("Scene", "voice"), ("Node", "place"), ("Node", "unpin"),
        ("Node", "edge"), ("Group", "swap"), ("Group", "fit"), ("Text", "find_all"), ("Text", "chars"),
        ("Axes", "plot"), ("Axes", "local_point"), ("Axes", "bars"), ("Plot", "tangent_at"),
        ("Signal", "now"), ("Signal", "unbind"), ("Expr", "map"), ("EventSource", "emit"),
    ):
        anchor = f"{owner.lower()}-{member}"
        assert f'<a id="{anchor}"></a>' in ALL_TEXT, f"{owner}.{member} has no section"


def test_object_classes_have_props_tables() -> None:
    objects = PAGES["objects.md"]
    assert "| `r` | float | `1.0` | linear |" in objects
    assert "Props inherited from [`k.Node`](object-state.md#k-node)" in objects


def test_anchors_are_unique_and_links_resolve() -> None:
    anchors = {name: ANCHOR.findall(text) for name, text in PAGES.items()}
    for name, ids in anchors.items():
        assert len(ids) == len(set(ids)), f"{name}: duplicate anchors"
    for name, text in PAGES.items():
        for target in LINK.findall(text):
            if target.startswith(("http://", "https://")):
                continue
            file, _, fragment = target.partition("#")
            file = file or name
            assert file in PAGES, f"{name}: link to missing page {target}"
            assert not fragment or fragment in anchors[file], f"{name}: link to missing anchor {target}"


def test_one_page_per_area() -> None:
    for area in symbols_by_area():
        page = re.sub(r"[^a-z0-9_]+", "-", area.lower()).strip("-") + ".md"
        assert page in PAGES and f"# {area}\n" in PAGES[page]


# ---- other pages -----------------------------------------------------------------------------

def test_every_diagnostic_code_is_documented() -> None:
    text = PAGES["diagnostics.md"]
    for code, item in CATALOG.items():
        assert f'<a id="{code.lower()}"></a>' in text
        assert f"### {code}: {item.title}" in text


def test_every_subcommand_is_documented_with_examples() -> None:
    text = PAGES["cli.md"]
    for name, _, sub in _subcommands(cli_parser()):
        assert f"## `kinemo {name}`" in text
        assert EXAMPLES.get(name), f"kinemo {name}: add usage examples in cli_page.EXAMPLES"
        for action in sub._actions:
            for option in action.option_strings:
                assert f"`{option}" in text or f", {option}" in text, f"kinemo {name} {option}"


def test_configuration_lists_toml_keys_sizes_and_quality() -> None:
    from kinemo.scene.config import SIZES

    text = PAGES["configuration.md"]
    for key in ("[scene] size", "[lints] allow", "[tts] provider", "[cache] dir", "[editor] command",
                "[python] workers_threshold"):
        assert f"`{key}`" in text
    for size in SIZES:
        assert f'`"{size}"`' in text
    assert "`draft`" in text and "`final`" in text
