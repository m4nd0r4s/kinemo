"""`k.when(cond, action)`: when a condition becomes true, something enters the timeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .._runtime.context import current_scene
from .._runtime.spans import Span, user_span
from ..diagnostics import KinemoError
from ..reactive.expr import Expr, lift
from .event import EventSource

if TYPE_CHECKING:
    from ..anim.animation import Animation
    from ..values.aliases import BoolVal
    from .event import P


@dataclass
class Effect:
    cond: Expr
    #: The source fired on each edge (the user's event, or a private one starting an animation).
    action: EventSource[Any]
    once: bool
    rearm: Expr | None
    since: float
    owner: Any
    span: Span


def when(cond: BoolVal, action: Animation | EventSource[P], *, once: bool = False, rearm: BoolVal | None = None) -> Effect:
    """Edge-triggered effect: on false → true, start `action` (an animation) or fire it
    (an event). Valid from the cursor on; inside a component, only while it is in the scene."""
    from ..anim.animation import Animation

    s = current_scene()
    span = user_span()
    if not isinstance(action, Animation | EventSource):
        raise KinemoError.make(
            "K0105",
            f"k.when expects an animation or an event, got {type(action).__name__}",
            spans=[span],
            fixes=[("trigger an animation", "k.when(x >= 2, k.flash(dot))"), ("or emit an event", "k.when(soc >= 1, self.full)")],
        )
    owner = s._building_component()
    if isinstance(action, EventSource):
        source = action
    else:
        source = EventSource(s, "when", owner)
        source.on(lambda sc, e: sc.start(action, at=e.time))
    effect = Effect(lift(cond), source, once, lift(rearm) if rearm is not None else None, s.cursor, owner, span)
    s._events.effects.append(effect)
    return effect
