"""Per-scene registry: event sources, explicit firings, handlers and effects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .event import EventSource
    from .when import Effect


@dataclass
class Handler:
    fn: Callable[..., object]
    once: bool


@dataclass(frozen=True)
class Firing:
    t: float
    data: Any = None


@dataclass
class EventRegistry:
    sources: list["EventSource[Any]"] = field(default_factory=list)
    #: Firings from `emit()` in the build, clips and handlers.
    explicit: dict[int, list[Firing]] = field(default_factory=dict)
    #: Firings produced while resolving (simulations); cleared at every pass.
    generated: dict[int, list[Firing]] = field(default_factory=dict)
    handlers: dict[int, list[Handler]] = field(default_factory=dict)
    effects: list["Effect"] = field(default_factory=list)

    def register(self, src: "EventSource[Any]") -> int:
        self.sources.append(src)
        return len(self.sources) - 1

    def fire(self, src: "EventSource[Any]", t: float, data: Any, generated: bool = False) -> None:
        target = self.generated if generated else self.explicit
        target.setdefault(src._id, []).append(Firing(t, data))

    def handle(self, src: "EventSource[Any]", fn: Callable[..., object], once: bool) -> None:
        self.handlers.setdefault(src._id, []).append(Handler(fn, once))

    def copy(self) -> "EventRegistry":
        return EventRegistry(
            list(self.sources),
            {k: list(v) for k, v in self.explicit.items()},
            {k: list(v) for k, v in self.generated.items()},
            {k: list(v) for k, v in self.handlers.items()},
            list(self.effects),
        )
