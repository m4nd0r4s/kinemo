"""`[editor] command` decides how the `kinemo dev` page opens source lines: a URL scheme for
known editors, otherwise a command `kinemo dev` runs with `{file}` and `{line}`."""

from __future__ import annotations

import shlex
import sys
import time
from pathlib import Path

from kinemo.cli.editor_links import editor_meta, open_in_editor


def test_known_editors_open_by_url() -> None:
    assert editor_meta("vscode")["url"] == "vscode://file/{path}:{line}"
    assert editor_meta("IDEA")["url"].startswith("idea://open?file={path_query}")
    assert editor_meta("cursor")["url"].startswith("cursor://")


def test_any_other_editor_is_a_command() -> None:
    assert editor_meta("emacsclient -n +{line} {file}") == {"name": "emacsclient -n +{line} {file}", "command": True}


def wait_for(path: Path) -> str:
    for _ in range(100):
        if path.exists() and path.read_text(encoding="utf-8"):
            return path.read_text(encoding="utf-8")
        time.sleep(0.05)
    raise AssertionError(f"{path} was not written")


def test_the_command_gets_the_file_and_line(tmp_path: Path) -> None:
    log = tmp_path / "opened.txt"
    script = tmp_path / "editor.py"
    script.write_text(f"import sys\nopen({str(log)!r}, 'w').write(' '.join(sys.argv[1:]))\n", encoding="utf-8")
    command = f"{shlex.quote(sys.executable)} {shlex.quote(str(script))} +{{line}} {{file}}"
    assert open_in_editor(command, "/abs/scene.py", 12, str(tmp_path)) is None
    assert wait_for(log) == "+12 /abs/scene.py"


def test_a_command_without_file_gets_it_appended(tmp_path: Path) -> None:
    log = tmp_path / "opened.txt"
    script = tmp_path / "editor.py"
    script.write_text(f"import sys\nopen({str(log)!r}, 'w').write(' '.join(sys.argv[1:]))\n", encoding="utf-8")
    assert open_in_editor(f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}", "/abs/scene.py", 3, str(tmp_path)) is None
    assert wait_for(log) == "/abs/scene.py"


def test_a_missing_program_is_reported() -> None:
    assert "could not run" in (open_in_editor("no-such-editor-xyz {file}", "/a.py", 1, ".") or "")
