"""Components: `k.Prop[T]` is `Signal[T]` inside, `k.Out[T]` an expression, `k.Event[P]` a source."""

from dataclasses import dataclass
from typing import assert_type

import kinemo as k

Clock = k.context("clock", default=k.time)


@dataclass
class Impact:
    force: float


class Battery(k.Component):
    power: k.Prop[float] = k.prop(0.0)
    clock: k.Prop[float] = k.from_context(Clock)
    capacity: float = 10.0
    initial: float = k.field(0.2, range=(0, 1))

    soc: k.Out[float]
    full: k.Event
    hit: k.Event[Impact]

    def build(self) -> k.Node:
        assert_type(self.power, k.Signal[float])
        assert_type(self.capacity, float)
        self.soc = k.integrate(self.power / self.capacity, d=self.clock, initial=self.initial, clamp=(0, 1))
        assert_type(self.soc, k.Expr[float])
        assert_type(self.full, k.EventSource[None])
        k.when(self.soc >= 1, self.full, rearm=self.soc < 0.95)
        self.body = k.RoundedRect(w=1.2, h=2.4)
        self.level = k.Rect(w=1.0, h=self.soc * 2.2, fill=self.soc.map(lambda v: k.mix(k.RED, k.GREEN, v)))
        return k.Group(self.body, self.level)


class Ball(k.State):
    y: float = 4.0
    v: float = 0.0
    bounce: k.Event[Impact]


def step(st: Ball, dt: float) -> Ball:
    v = st.v - 9.8 * dt
    if st.y < 0:
        st.bounce.emit(Impact(force=abs(v)))
        st.bounce.emit()  # pyright: ignore[reportCallIssue] - this event carries a payload
    return st.replace(y=st.y + v * dt, v=v)


@k.scene
def component_types(s: k.Scene) -> None:
    with k.provide(Clock, k.time * 2):
        bat = Battery(power=k.sin(k.time), capacity=5)
    assert_type(bat.soc, k.Expr[float])
    assert_type(bat.level, k.Rect)

    @bat.full.on
    def _(s: k.Scene, e: k.EventInfo) -> None:
        assert_type(e.data, None)
        s.play(k.indicate(bat))

    @bat.hit.on
    def _(s: k.Scene, e: k.EventInfo[Impact]) -> None:
        assert_type(e.data.force, float)

    sim = k.simulate(step, Ball(), dt=1 / 240, until=5)
    assert_type(sim.done, k.EventSource[None])
    s.add(bat)
    s.play(bat.to(power=3))
    s.start(sim)
    info = s.wait_for(bat.full, timeout=10)
    assert_type(info, k.EventInfo[None])
