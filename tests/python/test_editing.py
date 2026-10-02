"""Editing scene source from the preview: call sites found by span, literal arguments
rewritten in place, defaults added, computed values left alone."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from kinemo.cli.loader import build, find_scenes, load_module
from kinemo.editing.call_sites import SourceFile
from kinemo.editing.overrides import source_overrides
from kinemo.editing.scene_index import SceneIndex, index_scene, span_key
from kinemo.editing.source_edit import Change, EditError, apply_changes

SCENE = '''import kinemo as k


@k.scene
def demo(s: k.Scene):
    gap = 0.4
    dot = k.Dot(r=0.2, color=k.RED)
    box = k.Square(1.6).place(at=(1, -1))
    title = k.Text("hello", size=0.5).place(above=box, gap=gap)
    s.add(dot, box, title)
    s.play(dot.to(x=3), duration=0.4)
    for _ in range(3):
        s.play(box.to(rotate=30))
'''


def built(path: Path, text: str | None = None) -> tuple[Any, SceneIndex, SourceFile]:
    module = load_module(str(path), text)
    result = build(find_scenes(module)[0])
    assert result.scene is not None, result.diagnostics
    source = SourceFile(str(path), text if text is not None else path.read_text())
    ir = json.loads(result.scene.builder.to_json())
    return result.scene, index_scene(result.scene, ir, {str(path): source}), source


@pytest.fixture
def scene_file(tmp_path: Path) -> Path:
    path = tmp_path / "scene.py"
    path.write_text(SCENE)
    return path


def node(scene: Any, name: str) -> Any:
    return next(n for n in scene._nodes if n._name == name)


def test_constructor_sites_bind_positional_arguments(scene_file: Path) -> None:
    scene, index, _ = built(scene_file)
    box = index.sites[span_key(node(scene, "box")._span)]
    assert box.site.callee == "k.Square"
    side = box.site.positional(0)
    assert side is not None and side.kind == "number" and side.value == 1.6
    assert dict(box.params)[0] == "side"


def test_place_and_play_calls_are_indexed(scene_file: Path) -> None:
    scene, index, _ = built(scene_file)
    place = index.sites[span_key(node(scene, "box")._place_log[0][2])]
    at = place.site.keyword("at")
    assert at is not None and at.kind == "vector" and at.value == [1, -1]
    title_place = index.sites[span_key(node(scene, "title")._place_log[0][2])]
    gap = title_place.site.keyword("gap")
    assert gap is not None and gap.kind is None  # a variable: computed, not editable
    play = next(e for e in scene._log if "dot.to" in e.label)
    duration = index.sites[span_key(play.call)].site.keyword("duration")
    assert duration is not None and duration.value == 0.4


def test_a_call_in_a_loop_counts_its_runs(scene_file: Path) -> None:
    scene, index, _ = built(scene_file)
    rotate = next(e for e in scene._log if "box.to" in e.label)
    assert index.sites[span_key(rotate.call)].runs == 3
    title = node(scene, "title")  # its glyph runs are parts, not runs of the line
    assert index.sites[span_key(title._span)].runs == 1


def test_editing_a_literal_rewrites_only_its_characters(scene_file: Path) -> None:
    scene, index, source = built(scene_file)
    dot = index.sites[span_key(node(scene, "dot")._span)]
    text = apply_changes(source, [Change(dot.site, "r", "0.35")])
    assert "    dot = k.Dot(r=0.35, color=k.RED)\n" in text
    assert text.replace("r=0.35", "r=0.2") == SCENE


def test_a_default_prop_is_added_as_a_keyword(scene_file: Path) -> None:
    scene, index, source = built(scene_file)
    title = index.sites[span_key(node(scene, "title")._span)]
    text = apply_changes(source, [Change(title.site, "rotate", "15")])
    assert 'k.Text("hello", size=0.5, rotate=15).place(' in text


def test_several_keywords_go_into_empty_parentheses(tmp_path: Path) -> None:
    path = tmp_path / "scene.py"
    path.write_text(SCENE.replace("k.Dot(r=0.2, color=k.RED)", "k.Dot()"))
    scene, index, source = built(path)
    dot = index.sites[span_key(node(scene, "dot")._span)]
    text = apply_changes(source, [Change(dot.site, "x", "1"), Change(dot.site, "y", "2")])
    assert "k.Dot(x=1, y=2)" in text


def test_computed_values_and_bad_text_are_refused(scene_file: Path) -> None:
    scene, index, source = built(scene_file)
    title_place = index.sites[span_key(node(scene, "title")._place_log[0][2])]
    with pytest.raises(EditError, match="computed"):
        apply_changes(source, [Change(title_place.site, "gap", "0.5")])
    dot = index.sites[span_key(node(scene, "dot")._span)]
    with pytest.raises(EditError, match="not a valid value"):
        apply_changes(source, [Change(dot.site, "r", "0.3 +")])


def test_an_edited_text_builds_without_touching_the_file(scene_file: Path) -> None:
    scene, index, source = built(scene_file)
    dot = index.sites[span_key(node(scene, "dot")._span)]
    text = apply_changes(source, [Change(dot.site, "r", "0.9")])
    with source_overrides({str(scene_file): text}):
        live, _, _ = built(scene_file, text)
    ir = json.loads(live.builder.to_json())
    radius = next(sig for sig in ir["signals"] if sig["owner"] == [node(live, "dot")._id, "r"])
    assert radius["initial"] == {"Float": 0.9}
    assert scene_file.read_text() == SCENE


TYPED = '''import kinemo as k


@k.scene
def typed(s: k.Scene):
    title = k.Text("hi", align="center", fill=k.theme.accent).place(at="top", margin=0.5)
    row = k.Row(k.Dot(), k.Dot(), align="bottom")
    s.add(title, row)
    s.play(title.to(opacity=0.5, fill="#ff0000"), ease=k.ease.out_back)
'''


def test_parameters_carry_the_kind_of_value_they_take(tmp_path: Path) -> None:
    path = tmp_path / "scene.py"
    path.write_text(TYPED)
    scene, index, _ = built(path)
    sites = index.json()
    by_callee = {site["callee"]: site for site in sites.values()}
    text = by_callee["k.Text"]
    assert text["types"]["align"]["type"] == "choice" and "center" in text["types"]["align"]["choices"]
    assert text["types"]["fill"] == {"type": "color"}
    fill = next(a for a in text["arguments"] if a["keyword"] == "fill")
    assert fill["kind"] == "color" and fill["value"] == "theme.accent" and fill["hex"] == index.colors["theme.accent"]
    place = sites[span_key(node(scene, "title")._place_log[0][2])]
    assert place["types"]["at"]["type"] == "choice" and place["types"]["at"]["vector"] is True
    to = by_callee["title.to"]
    assert to["types"]["opacity"] == {"type": "number", "range": [0, 1]}
    assert to["types"]["fill"] == {"type": "color"}
    play = by_callee["s.play"]
    assert play["types"]["ease"] == {"type": "ease"}
    ease = next(a for a in play["arguments"] if a["keyword"] == "ease")
    assert ease["kind"] == "ease" and ease["value"] == "ease.out_back"
    assert by_callee["k.Row"]["types"]["align"]["type"] == "choice"
    assert play["alias"] == "k"


def test_optional_parameters_can_be_added_with_their_defaults(tmp_path: Path) -> None:
    path = tmp_path / "scene.py"
    path.write_text(TYPED)
    scene, index, source = built(path)
    play = next(entry for entry in index.sites.values() if entry.site.callee == "s.play")
    assert play.defaults == {"duration": 1.0, "ease": "ease.smooth"}  # `at=` would move the play
    to = next(entry for entry in index.sites.values() if entry.site.callee == "title.to")
    assert to.defaults["delay"] == 0.0 and to.accepts is not None and "delay" in to.accepts
    text = apply_changes(source, [Change(play.site, "duration", "2")])
    assert "ease=k.ease.out_back, duration=2)" in text


def test_the_palette_is_ordered_by_hue_then_grays() -> None:
    from kinemo.editing.scene_index import palette_colors
    from kinemo.theme.tokens import DEFAULT

    names = [n for n in palette_colors(DEFAULT) if not n.startswith("theme.")]
    assert names[:3] == ["RED", "ORANGE", "YELLOW"] and names[-1] == "BLACK"


def test_positional_arguments_bind_to_their_parameter_on_every_call(tmp_path: Path) -> None:
    path = tmp_path / "scene.py"
    path.write_text(
        "import kinemo as k\n\n@k.scene\ndef bound(s: k.Scene):\n    x = k.signal(0.0)\n"
        "    dot = k.Dot()\n    s.play(k.fade_in(dot), duration=0.5)\n    s.play(x.to(2.5))\n"
    )
    _, index, _ = built(path)
    sites = {entry.site.callee: entry for entry in index.sites.values()}
    assert dict(sites["x.to"].params)[0] == "value"
    assert "ease" in sites["k.fade_in"].types  # the verb's own parameters, not dot's methods
