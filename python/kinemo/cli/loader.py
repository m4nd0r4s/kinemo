"""Load a scene file, find its scenes and build them, turning failures into diagnostics."""

from __future__ import annotations

import importlib.util
import linecache
import os
import sys
import traceback
from dataclasses import dataclass, field
from types import ModuleType

from .._runtime.spans import Span
from ..diagnostics import Diagnostic, KinemoError
from ..editing.overrides import TextLoader
from ..scene.decorator import SceneDef
from ..scene.scene import Scene


class LoadError(Exception):
    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


def load_module(path: str, text: str | None = None) -> ModuleType:
    """Imports the scene file fresh; `text` replaces its contents (a live edit)."""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise SystemExit(f"kinemo: file not found: {path}")
    linecache.checkcache()  # spans and names read source lines; the files may have changed
    name = "_kinemo_scene_" + os.path.splitext(os.path.basename(path))[0]
    loader = TextLoader(name, path, text) if text is not None else None
    spec = importlib.util.spec_from_file_location(name, path, loader=loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(path))
    try:
        sys.modules[name] = module
        spec.loader.exec_module(module)
    except KinemoError as e:
        raise LoadError(e.diagnostic) from e
    except Exception as e:  # noqa: BLE001 - surfaced as a diagnostic
        raise LoadError(python_error(e, path)) from e
    finally:
        sys.path.remove(os.path.dirname(path))
    return module


def find_scenes(module: ModuleType) -> list[SceneDef]:
    return [v for v in vars(module).values() if isinstance(v, SceneDef)]


def select(scenes: list[SceneDef], name: str | None) -> list[SceneDef]:
    if name is None:
        return scenes
    chosen = [s for s in scenes if s.name == name]
    if not chosen:
        names = ", ".join(s.name for s in scenes) or "none"
        raise SystemExit(f"kinemo: scene '{name}' not found (available: {names})")
    return chosen


@dataclass
class BuildResult:
    definition: SceneDef
    scene: Scene | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.scene is not None and not any(d.level == "error" for d in self.diagnostics)


def build(defn: SceneDef, params: dict[str, object] | None = None) -> BuildResult:
    try:
        s = defn.build(params)
    except KinemoError as e:
        return BuildResult(defn, None, [e.diagnostic])
    except Exception as e:  # noqa: BLE001
        return BuildResult(defn, None, [python_error(e, None)])
    from ..lints import run_lints

    return BuildResult(defn, s, run_lints(s))


def python_error(e: BaseException, path: str | None) -> Diagnostic:
    """A plain Python exception during build, located at the deepest user frame."""
    if isinstance(e, SyntaxError) and e.filename:
        return Diagnostic("K0001", "error", f"SyntaxError: {e.msg}", [Span(e.filename, e.lineno or 0, e.offset or 0)])
    frames = traceback.extract_tb(e.__traceback__)
    manim = _manim_name(e)
    pkg = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    stdlib = os.path.dirname(os.__file__)
    user = [
        f
        for f in frames
        if not os.path.abspath(f.filename).startswith((pkg, stdlib)) and "site-packages" not in f.filename
    ]
    span = Span(user[-1].filename, user[-1].lineno or 0) if user else Span(path or "<unknown>", 0)
    if manim is not None:
        return Diagnostic(manim.code, "error", manim.message, [span], fixes=manim.fixes)
    return Diagnostic("K0001", "error", f"{type(e).__name__}: {e}", [span])


def _manim_name(e: BaseException) -> Diagnostic | None:
    """`Create(circle)` written from Manim habit (`from manim import *`) is a NameError;
    answer it like `k.Create` with the kinemo form."""
    if not isinstance(e, NameError) or not e.name:
        return None
    from ..diagnostics.manim import module_attribute

    found = module_attribute(e.name)
    return found.diagnostic if found is not None else None
