import kinemo as k


@k.scene
def sine_dot(s: k.Scene):
    ax = k.Axes(x=(0, 6.5, 1), y=(-1.5, 1.5, 0.5)).place(at="center")
    curve = ax.plot(k.sin, domain=(0, k.tau), color=k.YELLOW)
    x = k.signal(0.0)
    dot = k.Dot(r=0.12, fill=k.RED).place(at=curve.point_at(x))
    label = k.Text(lambda: f"x = {x():.2f}", size=0.5).place(at="top", margin=0.6)
    s.play(k.draw(ax), k.fade_in(dot, label))
    s.play(x.to(k.tau), duration=4, ease=k.ease.linear)
    s.wait(0.5)
