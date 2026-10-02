import kinemo as k


@k.scene
def parabola(s: k.Scene):
    ax = k.Axes(x=(-2, 2, 1), y=(0, 4, 1), labels=("x", "y")).place(at="center")
    ax.plot(lambda x: x * x, domain=(-2, 2), color=k.YELLOW, label="y = x²")
    s.play(k.draw(ax), duration=2)
    s.wait(0.5)
