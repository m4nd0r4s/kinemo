import kinemo as k


def f(x):
    return 2 + 1.5 * k.sin(x)


@k.scene
def growing_plot(s: k.Scene):
    ax = k.Axes(x=(0, 10, 2), y=(0, 4, 1)).place(at="center")
    t = k.signal(0.0)
    ax.plot(f, until=t, color=k.YELLOW)
    s.play(k.draw(ax))
    s.play(t.to(10), duration=4, ease=k.ease.linear)
    s.wait(0.5)
