"""A `kinemo dev` session: builds the scene from disk (or from edited text, while a value
is dragged), publishes it to the preview server and applies source edits from the page."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..diagnostics import Diagnostic
from ..editing.call_sites import SourceFile
from ..editing.overrides import source_overrides
from ..editing.scene_index import SceneIndex, easing_names, index_scene
from ..editing.source_edit import Change, EditError, apply_changes, bound_argument
from ..project import load as load_project
from .dev_meta import diagnostics_json, preview_meta
from .editor_links import editor_meta, open_in_editor
from .loader import BuildResult, LoadError, build, find_scenes, load_module

if TYPE_CHECKING:
    from .._core import PreviewServer

_PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_local(file: str | None, root: str) -> bool:
    if not file:
        return False
    file = os.path.abspath(file)
    return file.startswith(root + os.sep) and not file.startswith(_PACKAGE_DIR) and "site-packages" not in file


def local_modules(root: str) -> dict[str, str]:
    """Imported modules (name → file) that live under `root`, outside kinemo itself."""
    out: dict[str, str] = {}
    for name, module in list(sys.modules.items()):
        file = getattr(module, "__file__", None)
        if _is_local(file, root):
            out[name] = os.path.abspath(file)  # type: ignore[arg-type]
    return out


def forget_local_modules(root: str) -> None:
    """Drops local modules from `sys.modules` so the next load imports them fresh."""
    for name in local_modules(root):
        sys.modules.pop(name, None)


def read_text(path: str) -> str | None:
    """A file's exact text (line endings kept), or `None` when it cannot be read."""
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read()
    except OSError:
        return None


@dataclass
class Session:
    path: str
    scene_name: str | None
    params: dict[str, Any]
    server: "PreviewServer"
    watched: set[str] = field(default_factory=lambda: set[str]())
    #: Debug overlays requested with `--debug` (layout, safe).
    debug: tuple[str, ...] = ()
    #: Text of every watched file at the last build from disk: edits apply to it, and are
    #: refused when the file no longer matches (edited elsewhere in the meantime).
    texts: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    index: SceneIndex | None = None

    @property
    def root(self) -> str:
        return os.path.dirname(os.path.abspath(self.path))

    # ---- building ------------------------------------------------------------------------
    def rebuild(self) -> bool:
        """Loads the file fresh, builds the chosen scene and publishes it (or the error)."""
        return self._build(None)

    def _build(self, overrides: dict[str, str] | None) -> bool:
        live = overrides is not None
        main = os.path.abspath(self.path)
        forget_local_modules(self.root)
        try:
            with source_overrides(overrides or {}):
                module = load_module(self.path, (overrides or {}).get(main))
        except LoadError as e:
            if not live:
                self._remember_files(main)
            return self._fail([e.diagnostic])
        if not live:
            self._remember_files(main)
        scenes = find_scenes(module)
        names = [s.name for s in scenes]
        if not scenes:
            return self._fail([Diagnostic("K0001", "error", f"no scenes (@k.scene) in {self.path}")])
        chosen = [s for s in scenes if s.name == self.scene_name] if self.scene_name else scenes[:1]
        if not chosen:
            return self._fail([Diagnostic("K0001", "error", f"scene '{self.scene_name}' not found (available: {', '.join(names)})")])
        with source_overrides(overrides or {}):
            result = build(chosen[0], self.params)
        if result.scene is None:
            return self._fail(result.diagnostics)
        ir_json = result.scene.builder.to_json()
        ir = json.loads(ir_json)
        texts = {**self.texts, **(overrides or {})}
        sources = {path: SourceFile(path, text) for path, text in texts.items()}
        index = index_scene(result.scene, ir, sources)
        if not live:
            self.index = index
        # Edits always refer to the text on disk, so a live build keeps the disk index.
        editable = (self.index or index).json()
        meta = preview_meta(self.path, result, names, ir, sources, editable)
        meta["debug"] = list(self.debug)
        meta["palette"] = {"colors": (self.index or index).colors, "eases": easing_names()}
        meta["live"] = live
        meta["editor"] = editor_meta(load_project(os.path.dirname(os.path.abspath(self.path))).editor)
        version = self.server.set_scene(result.scene.builder, json.dumps(meta))
        if not live:
            self._report(result, version)
            self._check_determinism(chosen[0], ir_json)
        return True

    def _remember_files(self, main: str) -> None:
        self.watched = {main} | set(local_modules(self.root).values())
        self.texts = {path: text for path in self.watched if (text := read_text(path)) is not None}

    def _report(self, result: BuildResult, version: int) -> None:
        assert result.scene is not None
        errors = sum(1 for d in result.diagnostics if d.level == "error")
        lints = len(result.diagnostics) - errors
        print(
            f"kinemo dev: scene '{result.definition.name}' v{version} — {result.scene.duration:.2f} s"
            + (f", {errors} error(s)" if errors else "")
            + (f", {lints} warning(s)" if lints else ""),
            flush=True,
        )

    def _check_determinism(self, definition: Any, first: str) -> None:
        """Build again and compare: handlers and `.map` functions must be pure, and a
        different second build means the cache and the parallel render can't be trusted."""
        try:
            second = definition.build(self.params).builder.to_json()
        except Exception:  # noqa: BLE001 - the published build already succeeded
            return
        if first != second:
            print(
                "kinemo dev: warning — two consecutive builds of the same source gave different results; "
                "handlers, .map functions and k.python must be pure (no global state, clock or "
                "randomness outside the scene seed)",
                flush=True,
            )

    def _fail(self, diagnostics: list[Diagnostic]) -> bool:
        self.server.set_error(json.dumps(diagnostics_json(diagnostics)))
        print("kinemo dev: build failed; keeping the last good version", flush=True)
        for d in diagnostics:
            print(d.render(), flush=True)
        return False

    # ---- edits from the page -------------------------------------------------------------
    def process_edits(self, requests: list[dict[str, Any]]) -> None:
        """Applies queued edits in order. A live edit followed by any other edit is stale
        (the drag moved on), so only the last live one is built."""
        for i, request in enumerate(requests):
            if request.get("type") == "open":
                self.open_in_editor(str(request.get("file", "")), int(request.get("line") or 1))
                continue
            if request.get("live") and i < len(requests) - 1:
                continue
            self.apply_edit(request)

    def open_in_editor(self, file: str, line: int) -> None:
        """A click on a source link, for an `[editor] command` the page cannot open by URL."""
        cfg = load_project(os.path.dirname(os.path.abspath(self.path)))
        error = open_in_editor(cfg.editor, file, line, cfg.root)
        if error is not None:
            print(f"kinemo dev: {error}", flush=True)

    def apply_edit(self, request: dict[str, Any]) -> bool:
        live = bool(request.get("live"))
        if not live and not request.get("changes"):
            # A cancelled drag: show the version on disk again.
            ok = self.rebuild()
            self._notify(request, ok, "")
            return ok
        try:
            texts = self.edited_texts(request.get("changes") or [])
        except EditError as e:
            self._notify(request, False, str(e))
            return False
        if live:
            self._build(texts)
        else:
            for path, text in texts.items():
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(text)
            changed = ", ".join(sorted(os.path.basename(p) for p in texts))
            print(f"kinemo dev: edited {changed} from the preview", flush=True)
        self._notify(request, True, "")
        return True

    def edited_texts(self, changes: list[dict[str, Any]]) -> dict[str, str]:
        """New text of each file the changes touch (all or nothing)."""
        if self.index is None:
            raise EditError("no scene has been built yet")
        by_file: dict[str, list[Change]] = {}
        sources: dict[str, SourceFile] = {}
        for change in changes:
            entry = self.index.sites.get(str(change.get("site")))
            if entry is None:
                raise EditError("this code changed since the preview was built; it reloads with the new version")
            target = str(change.get("target"))
            if bound_argument(entry.site, target, entry.params) is None and (entry.accepts is None or target not in entry.accepts):
                raise EditError(f"{entry.site.callee}(...) does not set {target}")
            by_file.setdefault(entry.source.path, []).append(Change(entry.site, target, str(change.get("value")), entry.params))
            sources[entry.source.path] = entry.source
        out: dict[str, str] = {}
        for path, file_changes in by_file.items():
            if read_text(path) != self.texts.get(path):
                raise EditError(f"{os.path.basename(path)} changed since the preview was built; it reloads now")
            out[path] = apply_changes(sources[path], file_changes)
        return out

    def _notify(self, request: dict[str, Any], ok: bool, message: str) -> None:
        notify = getattr(self.server, "notify", None)
        if notify is not None:
            notify(json.dumps({"type": "edit_result", "id": request.get("id"), "ok": ok, "message": message, "live": bool(request.get("live"))}))
