"""The statements of a scene for the dev editor's code view: every run of a statement that
schedules time or acts at the cursor, by file and line, and the highlighted source of the files
the scene ran."""

from __future__ import annotations

from pathlib import Path

import pytest

from kinemo.cli.dev_meta import code_files, scene_statements
from kinemo.cli.loader import build, find_scenes, load_module

SCENE = '''import kinemo as k


@k.scene
def steps(s: k.Scene):
    dot = k.Dot()
    s.add(dot)
    s.mark("start")
    for i in range(3):
        s.play(dot.to(x=i), duration=0.5)
    s.start(k.indicate(dot), duration=0.4)
    s.wait(1)
    with s.tempo(2):
        s.play(dot.to(y=1), duration=1)
    s.remove(dot)
'''


def statements(tmp_path: Path) -> dict[int, list[dict[str, object]]]:
    scene = tmp_path / "scene.py"
    scene.write_text(SCENE, encoding="utf-8")
    result = build(find_scenes(load_module(str(scene)))[0], {})
    assert result.scene is not None, [d.render() for d in result.diagnostics]
    found = scene_statements(result)
    assert {entry["file"] for entry in found} == {str(scene.resolve())}
    return {int(entry["line"]): entry["runs"] for entry in found}  # type: ignore[misc]


def test_each_statement_has_its_runs(tmp_path: Path) -> None:
    lines = statements(tmp_path)
    assert [r["kind"] for r in lines[7]] == ["add"] and lines[7][0]["label"] == "dot"
    assert lines[8][0]["kind"] == "mark" and lines[8][0]["label"] == "start"
    loop = lines[10]
    assert [r["kind"] for r in loop] == ["play"] * 3
    assert [(r["start"], r["end"]) for r in loop] == [(0.0, 0.5), (0.5, 1.0), (1.0, 1.5)]
    assert lines[11][0]["kind"] == "start" and lines[11][0]["start"] == 1.5
    assert (lines[12][0]["kind"], lines[12][0]["start"], lines[12][0]["end"]) == ("wait", 1.5, 2.5)
    assert lines[15][0]["kind"] == "remove"


def test_tempo_warps_the_runs_inside_it(tmp_path: Path) -> None:
    lines = statements(tmp_path)
    run = lines[14][0]
    assert run["start"] == pytest.approx(2.5) and run["end"] == pytest.approx(3.0)


def test_the_source_is_sent_highlighted_line_by_line(tmp_path: Path) -> None:
    scene = tmp_path / "scene.py"
    scene.write_text(SCENE, encoding="utf-8")
    result = build(find_scenes(load_module(str(scene)))[0], {})
    files = code_files(scene_statements(result))
    (entry,) = files.values()
    lines = entry["lines"]
    assert entry["name"] == "scene.py" and len(lines) == len(SCENE.splitlines())
    assert "".join(text for text, _ in lines[9]) == SCENE.splitlines()[9]
    assert ["for", "keyword"] in lines[8]


def test_voice_blocks_and_v_at_are_statements(tmp_path: Path) -> None:
    scene = tmp_path / "scene.py"
    scene.write_text(
        'import kinemo as k\n\n\n@k.scene\ndef talk(s: k.Scene):\n'
        '    with s.voice("one two three four") as v:  # kinemo: allow W1401\n'
        '        v.at("three")\n'
        '        s.play(k.fade_in(k.Dot()), duration=0.2)\n',
        encoding="utf-8",
    )
    result = build(find_scenes(load_module(str(scene)))[0], {})
    lines = {entry["line"]: entry["runs"] for entry in scene_statements(result)}
    assert lines[6][0]["kind"] == "voice" and lines[6][0]["label"] == "one two three four"
    assert lines[7][0]["kind"] == "wait" and lines[7][0]["end"] > lines[7][0]["start"]


CLIP_SCENE = '''import kinemo as k


@k.clip
def pop(s, obj):
    s.play(k.indicate(obj), duration=0.3)
    s.wait(0.1)


def twice(s, obj):
    s.play(pop(obj))
    s.play(pop(obj))


@k.scene
def calls(s: k.Scene):
    dot = k.Dot()
    s.add(dot)
    twice(s, dot)
'''


def test_runs_inside_clips_and_helpers_know_their_callers(tmp_path: Path) -> None:
    scene = tmp_path / "scene.py"
    scene.write_text(CLIP_SCENE, encoding="utf-8")
    result = build(find_scenes(load_module(str(scene)))[0], {})
    lines = {entry["line"]: entry["runs"] for entry in scene_statements(result)}
    inner = lines[6]
    assert [[c["line"] for c in run["callers"]] for run in inner] == [[11, 19], [12, 19]]
    assert [c["line"] for c in lines[11][0]["callers"]] == [19]
    assert lines[18][0]["callers"] == []


def test_script_beats_are_statements_of_the_script_file(tmp_path: Path) -> None:
    (tmp_path / "script.md").write_text("# Talk\n\n### B01 · One\n\n> One two.\n\n### B02 · Two\n\n> Three four.\n", encoding="utf-8")
    scene = tmp_path / "scene.py"
    scene.write_text(
        'import kinemo as k\n\nscript = k.Script("script.md")\n\n\n@k.scene\ndef talk(s: k.Scene):\n'
        '    with s.voice(script["B01"]):  # kinemo: allow W1401\n        s.wait(0.2)\n'
        '    with s.voice(script["B02"]):  # kinemo: allow W1401\n        s.wait(0.2)\n',
        encoding="utf-8",
    )
    result = build(find_scenes(load_module(str(scene)))[0], {})
    statements = scene_statements(result)
    script = str((tmp_path / "script.md").resolve())
    beats = {entry["line"]: entry["runs"][0] for entry in statements if entry["file"] == script}
    assert set(beats) == {3, 7}
    assert beats[3]["label"].startswith("B01 · estimated") and beats[7]["start"] == beats[3]["end"]
    files = code_files(statements)
    assert files[script]["name"] == "script.md" and "".join(t for t, _ in files[script]["lines"][2]) == "### B01 · One"
