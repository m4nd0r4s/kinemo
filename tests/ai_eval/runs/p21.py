import kinemo as k


def f(x):
    return x**3 - x


@k.scene
def cubic_tangent(s: k.Scene):
    ax = k.Axes(x=(-2, 2, 1), y=(-6, 6, 2)).place(at="center")
    curve = ax.plot(f, color=k.YELLOW)
    x = k.signal(-1.5)
    curve.tangent_at(x, length=2, stroke=k.RED)
    dot = k.Dot(r=0.1, fill=k.RED).place(at=curve.point_at(x))
    label = k.Text(lambda: f"slope = {curve.slope_at(x)():.2f}", size=0.5).place(at="top", margin=0.5)
    s.play(k.draw(ax), k.fade_in(dot, label))
    s.play(x.to(1.5), duration=4)
    s.wait(0.5)
