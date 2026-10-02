"""`k.movie`: several scenes composed into one output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Sequence

from .diagnostics import KinemoError
from .scene.decorator import SceneDef

if TYPE_CHECKING:
    from .scene.scene import Scene


@dataclass(frozen=True)
class Transition:
    kind: str
    duration: float = 0.0


cut = Transition("cut")


def crossfade(duration: float = 0.5) -> Transition:
    """The end of one scene dissolves into the start of the next."""
    return Transition("crossfade", float(duration))


def morph_cut(duration: float = 0.5) -> Transition:
    """Objects with the same `key=` in neighbouring scenes travel across the cut
    (rendered as a crossfade of the two scenes)."""
    return Transition("crossfade", float(duration))


@dataclass
class Movie:
    scenes: list[SceneDef]
    transitions: list[Transition] = field(default_factory=list)
    name: str = "movie"

    def build(self, params: dict[str, object] | None = None) -> list[Scene]:
        """Build every scene of the movie."""
        return [s.build(params) for s in self.scenes]

    def render(self, path: str, format: str = "mp4", quality: str = "final", progress: Callable[[int, int], object] | None = None) -> None:
        """Render the movie to one video file, joining scenes with their transitions."""
        from ._core import render_movie

        built = self.build()
        joins = [(t.kind, t.duration) for t in self.transitions]
        joins += [("cut", 0.0)] * (len(built) - 1 - len(joins))
        render_movie([b.builder for b in built], joins, path, format, quality, progress)


def movie(scenes: Sequence[SceneDef], transitions: Sequence[Transition] = (), *, name: str = "movie") -> Movie:
    """`k.movie([intro, pythagoras], transitions=[k.crossfade(0.5)])`."""
    for s in scenes:
        if not isinstance(s, SceneDef):
            raise KinemoError.make("K0105", f"k.movie takes scenes (@k.scene), got {type(s).__name__}")
    if len(transitions) > max(0, len(scenes) - 1):
        raise KinemoError.make("K0105", "there are more transitions than joins between scenes")
    return Movie(list(scenes), list(transitions), name)
