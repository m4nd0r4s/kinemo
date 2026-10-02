"""Results of timeline calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..events.event import EventSource


@dataclass(frozen=True)
class TimeSpan:
    """Where a `play`/`start` landed. `h.done` is an event at its end."""

    start: float
    end: float
    _scene: Any = field(default=None, repr=False, compare=False)

    @property
    def duration(self) -> float:
        """Length of the span in seconds."""
        return self.end - self.start

    @property
    def done(self) -> EventSource[None]:
        """Event fired at the end of the span (`s.wait_for(h.done)`)."""
        from ..events.event import EventSource

        cached: EventSource[None] | None = self.__dict__.get("_done")
        if cached is None:
            end = self.end
            cached = EventSource(self._scene, "done", None, computed=lambda: [(end, None)])
            object.__setattr__(self, "_done", cached)
        return cached
