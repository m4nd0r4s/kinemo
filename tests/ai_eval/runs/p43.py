import kinemo as k


class Ball(k.State):
    y: float = 3.0
    v: float = 0.0
    floor: k.Event


def step(st: Ball, dt: float) -> Ball:
    v = st.v - 9.8 * dt
    y = st.y + v * dt
    if y <= -2.5 and v < 0:
        st.floor.emit()
        return st.replace(y=-2.5, v=-v * 0.7)
    return st.replace(y=y, v=v)


@k.scene
def wait_for_event(s: k.Scene):
    sim = k.simulate(step, Ball(), dt=1 / 240, until=4)
    ball = k.Circle(r=0.3, fill=k.ORANGE, fill_opacity=1, y=sim.y)
    s.add(ball)
    s.start(sim)
    s.wait_for(sim.floor)
    notice = k.Text("Hit the floor!").place(at="top", margin=0.8)
    s.play(k.write(notice))
    s.wait_for(sim.done)
