import kinemo as k

FLOOR = -3.0
R = 0.4


class Ball(k.State):
    y: float = 3.0
    v: float = 0.0


def step(st: Ball, dt: float) -> Ball:
    v = st.v - 9.8 * dt
    y = st.y + v * dt
    if y < FLOOR + R and v < 0:
        y = FLOOR + R
        v = -v * 0.8
    return st.replace(y=y, v=v)


@k.scene
def bouncing_ball(s: k.Scene):
    floor = k.Line(start=(-5, FLOOR), end=(5, FLOOR), stroke=k.GRAY)
    sim = k.simulate(step, Ball(), dt=1 / 240, until=5)
    ball = k.Circle(r=R, y=sim.y, fill=k.ORANGE, fill_opacity=1)
    s.add(floor, ball)
    s.start(sim)
    s.wait_for(sim.done)
