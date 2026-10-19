"""`kinemo render --format lesson`: a folder that plays the scene as an interactive lesson in
any browser, from any static host: the player (HTML, JS and the WebAssembly core), the scene's
IR with the formula layouts and code tokens baked natively, and its audio and images.

    <out>/<scene>/index.html        the lesson
    <out>/<scene>/embed-test.html   the lesson embedded in a page, with the events it reports
    <out>/<scene>/embed.js          `<kinemo-lesson src="...">` for host pages
    <out>/<scene>/lesson.json       IR, baked layouts, audio and images
"""

from __future__ import annotations

import html
import json
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..diagnostics import KinemoError

if TYPE_CHECKING:
    from ..scene.scene import Scene

PLAYER = Path(__file__).parent / "player"
#: Copied as they are; `index.html` and `embed-test.html` get the title.
FILES = ("player.js", "lesson.js", "render_worker.js", "player.css", "embed.js", "pkg/kinemo_web.js", "pkg/kinemo_web_bg.wasm")
PAGES = ("index.html", "embed-test.html")
FORMAT_VERSION = 1


def player_available() -> bool:
    return (PLAYER / "pkg" / "kinemo_web_bg.wasm").is_file()


def _copy_media(path: str, folder: Path, sub: str, index: int) -> str | None:
    """Copy `path` into `folder/sub/` as `<index><ext>`; its URL in the lesson, or None when missing."""
    if not os.path.isfile(path):
        return None
    name = f"{index}{os.path.splitext(path)[1].lower()}"
    (folder / sub).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, folder / sub / name)
    return f"{sub}/{name}"


def _image_paths(ir: dict[str, Any]) -> list[str]:
    """Every file an image's `src` names over the scene."""
    paths: list[str] = []
    for obj in ir["objects"]:
        sid = obj.get("props", {}).get("src")
        if sid is None:
            continue
        signal = ir["signals"][sid]
        values = [signal["initial"]] + [e.get("src", e.get("to", {})).get("v") for e in signal.get("timeline", [])]
        for value in values:
            if isinstance(value, dict) and isinstance(value.get("Str"), str) and value["Str"] and value["Str"] not in paths:
                paths.append(value["Str"])
    return paths


def lesson_data(s: "Scene", title: str, folder: Path) -> dict[str, Any]:
    """`lesson.json`: copies the audio and images into `folder` on the way."""
    b = s.builder
    ir = json.loads(b.to_json())
    audio = []
    for index, clip in enumerate(ir.get("audio", [])):
        url = _copy_media(clip["path"], folder, "audio", index)
        if url is not None:
            audio.append({"url": url, "t": clip["t"], "gain": clip.get("gain", 1.0)})
    images = []
    for index, path in enumerate(_image_paths(ir)):
        url = _copy_media(path, folder, "images", index)
        if url is not None:
            images.append({"path": path, "url": url})
    baked = json.loads(b.baked_layouts(s.config.fps))
    return {"format": "kinemo-lesson", "version": FORMAT_VERSION, "title": title, "ir": ir, "baked": baked, "audio": audio, "images": images}


def export(s: "Scene", out: str, name: str) -> str:
    """Write the lesson folder `<out>/<name>/`; returns the path of its `index.html`."""
    if not player_available():
        raise KinemoError.make(
            "K1502",
            "this kinemo install has no lesson player",
            fixes=[("in a source checkout, build it first", "python scripts/build_player.py")],
        )
    folder = Path(out) / name
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "pkg").mkdir(parents=True)
    title = s.config.name or name
    for page in PAGES:
        text = (PLAYER / page).read_text(encoding="utf-8").replace("{title}", html.escape(title))
        (folder / page).write_text(text, encoding="utf-8")
    for file in FILES:
        shutil.copyfile(PLAYER / file, folder / file)
    data = lesson_data(s, title, folder)
    (folder / "lesson.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    return str(folder / "index.html")
