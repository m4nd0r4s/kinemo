"""`--out` of `kinemo render` and `kinemo snap` (a folder, or one file named by its extension), `--progress`,
and snapshots at marks (`--at B03+50%`, `--at marks`, `--sheet`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kinemo.cli.main import main

SCENES = '''import kinemo as k


@k.scene
def first(s: k.Scene):
    s.mark("B01")
    s.play(k.fade_in(k.Circle()), duration=0.2)
    s.mark("B01.end")


@k.scene
def second(s: k.Scene):
    s.play(k.fade_in(k.Square()), duration=0.2)
'''

PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def scenes(tmp_path: Path) -> Path:
    path = tmp_path / "scenes.py"
    path.write_text(SCENES, encoding="utf-8")
    return path


def test_snap_writes_one_named_file(scenes: Path, tmp_path: Path) -> None:
    shot = tmp_path / "shots" / "first.png"
    assert main(["snap", str(scenes), "--scene", "first", "--at", "0.1", "--out", str(shot)]) == 0
    assert shot.read_bytes().startswith(PNG)


def test_render_takes_the_format_from_the_file_name(scenes: Path, tmp_path: Path) -> None:
    still = tmp_path / "still.png"
    assert main(["render", str(scenes), "--scene", "second", "--quality", "draft", "--out", str(still)]) == 0
    assert still.read_bytes().startswith(PNG)


def test_one_file_for_several_outputs_is_refused(scenes: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["render", str(scenes), "--out", str(tmp_path / "both.mp4")]) == 2
    assert "pass --scene NAME" in capsys.readouterr().out
    assert main(["snap", str(scenes), "--scene", "first", "--out", str(tmp_path / "two.png")]) == 2
    assert "one --at" in capsys.readouterr().out


def test_a_conflicting_format_is_refused(scenes: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["render", str(scenes), "--scene", "first", "--format", "mp4", "--out", str(tmp_path / "clip.gif")]) == 2
    assert "--format is mp4" in capsys.readouterr().out


def test_a_folder_still_gets_files_named_after_scenes(scenes: Path, tmp_path: Path) -> None:
    folder = tmp_path / "frames"
    assert main(["snap", str(scenes), "--at", "0.1", "--out", str(folder)]) == 0
    assert sorted(p.name for p in folder.iterdir()) == ["first_0.1.png", "second_0.1.png"]


def test_render_reports_progress_as_json_lines(scenes: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    still = tmp_path / "clip.gif"
    assert main(["render", str(scenes), "--scene", "first", "--quality", "draft", "--progress", "json", "--out", str(still)]) == 0
    events = [json.loads(line) for line in capsys.readouterr().err.splitlines() if line.startswith("{")]
    assert events[0]["event"] == "progress" and events[0]["scene"] == "first"
    assert events[-2]["done"] == events[-2]["total"]
    assert events[-1] == {"event": "done", "scene": "first", "path": str(still)}


def test_snap_at_marks_and_shifted_marks(scenes: Path, tmp_path: Path) -> None:
    folder = tmp_path / "shots"
    assert main(["snap", str(scenes), "--scene", "first", "--at", "marks,B01+50%,B01.end-0.05", "--out", str(folder)]) == 0
    assert sorted(p.name for p in folder.iterdir()) == ["first_B01+50%.png", "first_B01.end-0.05.png", "first_B01.end.png", "first_B01.png"]


def test_an_unknown_instant_lists_the_marks(scenes: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["snap", str(scenes), "--scene", "first", "--at", "B09+1", "--out", str(tmp_path)]) == 2
    out = capsys.readouterr().out
    assert "unknown instant 'B09+1'" in out and "B01, B01.end" in out


def test_snap_sheet_writes_one_contact_sheet(scenes: Path, tmp_path: Path) -> None:
    sheet = tmp_path / "sheet.png"
    assert main(["snap", str(scenes), "--scene", "first", "--at", "0,marks,end", "--sheet", "--columns", "2", "--out", str(sheet)]) == 0
    data = sheet.read_bytes()
    assert data.startswith(PNG)
    width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    assert width > height > 0  # 2 columns, 2 rows of 16:9 frames


def test_check_json_lists_the_marks(scenes: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["check", "--json", "--scene", "first", str(scenes)])
    report = json.loads(capsys.readouterr().out)
    assert report["scenes"][0]["marks"] == {"B01": 0.0, "B01.end": pytest.approx(0.2)}
