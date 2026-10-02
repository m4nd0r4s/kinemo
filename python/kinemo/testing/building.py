"""`build(scene)`: run a scene's build phase in a test and fail loudly on diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Union

from ..cli.check import scene_report, timeline_entries
from ..cli.loader import BuildResult
from ..cli.loader import build as build_result
from ..cli.output import exit_code
from ..diagnostics import Diagnostic
from ..scene.decorator import SceneDef, scene
from ..scene.scene import Scene


class SceneBuildError(AssertionError):
    """The scene failed to build (or, with `strict=True`, built with warnings).

    The message is the rendered diagnostics, exactly as `kinemo check` prints them;
    `.diagnostics` holds the `Diagnostic` objects. Subclasses `AssertionError` so pytest
    reports it as a test failure rather than an internal error."""

    def __init__(self, scene_name: str, diagnostics: list[Diagnostic]) -> None:
        self.scene_name = scene_name
        self.diagnostics = diagnostics
        rendered = "\n\n".join(d.render() for d in diagnostics)
        super().__init__(f"scene '{scene_name}' failed to build:\n{rendered}")


@dataclass
class BuiltScene:
    """A successfully built scene: its timeline, diagnostics (lints) and the `Scene` itself."""

    result: BuildResult

    @property
    def definition(self) -> SceneDef:
        return self.result.definition

    @property
    def name(self) -> str:
        return self.result.definition.name

    @property
    def scene(self) -> Scene:
        assert self.result.scene is not None
        return self.result.scene

    @property
    def duration(self) -> float:
        """Total duration in seconds, tail included."""
        return self.scene.duration

    @property
    def marks(self) -> dict[str, float]:
        """`s.mark(name)` instants, in seconds."""
        return dict(self.scene.marks)

    @property
    def timeline(self) -> list[dict[str, Any]]:
        """Every play/wait in time order: `{start, end, label, file, line}` (as in `kinemo check --json`)."""
        return timeline_entries(self.result)

    @property
    def diagnostics(self) -> list[Diagnostic]:
        """Non-fatal diagnostics found by the build and the lints (warnings and hints)."""
        return list(self.result.diagnostics)

    @property
    def lint_codes(self) -> list[str]:
        """Just the codes of `diagnostics`, handy for `assert "W1001" not in built.lint_codes`."""
        return [d.code for d in self.result.diagnostics]

    def report(self) -> dict[str, Any]:
        """This scene's entry of `kinemo check --json`."""
        return scene_report(self.result)

    def __repr__(self) -> str:
        return f"<BuiltScene {self.name!r} {self.duration:.2f} s, {len(self.result.diagnostics)} diagnostic(s)>"


SceneLike = Union[SceneDef, Callable[..., None], BuiltScene]


def build(scene_def: SceneLike, params: dict[str, Any] | None = None, *, strict: bool = False) -> BuiltScene:
    """Build `scene_def` (a `@k.scene` function) and return the result.

    - `params`: values for the scene's `params=` (as `kinemo check --param`).
    - `strict`: also fail on warnings, as `kinemo check --strict` and CI do.

    Raises `SceneBuildError` (an `AssertionError`) with the rendered diagnostics when the
    build fails. A plain `def body(s)` is accepted and wrapped with `@k.scene`; an already
    built `BuiltScene` is returned unchanged (when no `params` are given)."""
    if isinstance(scene_def, BuiltScene):
        if params is None:
            if strict:
                _raise_if_failing(scene_def.result, strict)
            return scene_def
        scene_def = scene_def.definition
    definition = scene_def if isinstance(scene_def, SceneDef) else scene(scene_def)
    result = build_result(definition, params)
    _raise_if_failing(result, strict)
    return BuiltScene(result)


def _raise_if_failing(result: BuildResult, strict: bool) -> None:
    if result.scene is None or exit_code(result.diagnostics, strict) != 0:
        failing = ("error", "warning") if strict else ("error",)
        shown = [d for d in result.diagnostics if d.level in failing] or result.diagnostics
        raise SceneBuildError(result.definition.name, shown)
