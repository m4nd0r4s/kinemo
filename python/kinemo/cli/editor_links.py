"""Which editor the `kinemo dev` page opens on a click (`[editor] command` in kinemo.toml).

A known editor opens through its URL scheme, straight from the page. Anything else is a
command run by `kinemo dev` itself, with `{file}` and `{line}` replaced (the file is appended
when the command has no `{file}`): `emacsclient -n +{line} {file}`, `nvim --server ... --remote {file}`."""

from __future__ import annotations

import shlex
import subprocess
from typing import Any

#: URL templates: `{path}` is the URI-encoded absolute path, `{path_query}` the same encoded for
#: a query string, `{line}` the line number.
URL_EDITORS = {
    "vscode": "vscode://file/{path}:{line}",
    "vscode-insiders": "vscode-insiders://file/{path}:{line}",
    "cursor": "cursor://file/{path}:{line}",
    "windsurf": "windsurf://file/{path}:{line}",
    "zed": "zed://file/{path}:{line}",
    "idea": "idea://open?file={path_query}&line={line}",
    "pycharm": "pycharm://open?file={path_query}&line={line}",
    "sublime": "subl://open?url=file://{path_query}&line={line}",
}


def editor_meta(editor: str) -> dict[str, Any]:
    """What the page needs: a URL template, or that `kinemo dev` runs the command."""
    template = URL_EDITORS.get(editor.strip().lower())
    if template is not None:
        return {"name": editor, "url": template}
    return {"name": editor, "command": True}


def open_in_editor(editor: str, file: str, line: int, cwd: str) -> str | None:
    """Run the editor command for `file:line`; returns an error message, or None."""
    argv = shlex.split(editor)
    if not argv:
        return "[editor] command is empty"
    values = {"file": file, "line": str(max(1, int(line)))}
    if not any("{file}" in part for part in argv):
        argv.append("{file}")
    argv = [part.replace("{file}", values["file"]).replace("{line}", values["line"]) for part in argv]
    try:
        subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as error:
        return f"could not run the editor command {argv[0]!r}: {error}"
    return None
