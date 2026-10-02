from dataclasses import dataclass

import kinemo as k


@dataclass
class Impact:
    force: float


class Ball(k.State):
    y: float = 4.0
    v: float = 0.0
    bounce: k.Event[Impact]


def step(st: Ball, dt: float) -> Ball:
    v = st.v - 9.8 * dt
    y = st.y + v * dt
    if y < 0:
        y, v = -y, -v * 0.8
        if abs(v) < 0.5:                      # at rest: no infinitesimal bounces
            y, v = 0.0, 0.0
        else:
            st.bounce.emit(Impact(force=abs(v)))
    return st.replace(y=y, v=v)


@k.scene
def bounce(s: k.Scene):
    floor = k.Line(length=10).place(at="bottom", margin=1)
    sim = k.simulate(step, Ball(), dt=1/240, until=12)
    ball = k.Circle(r=0.3, fill=k.theme.accent, fill_opacity=1).place(above=floor, gap=sim.y)
    s.add(floor, ball)

    @sim.bounce.on
    def _(s: k.Scene, e: k.EventInfo[Impact]) -> None:
        s.play(k.squash(ball, amount=e.data.force / 20), duration=0.15)

    s.start(sim)
    s.wait_for(sim.bounce, count=3, timeout=12)
    s.play(k.write(k.Text("3 bounces").place(at="top", margin=0.6)))
    s.wait_for(sim.done)
