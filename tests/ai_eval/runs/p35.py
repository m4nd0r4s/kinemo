import kinemo as k


def sine(x):
    return k.sin(x)


def cosine(x):
    return k.cos(x)


@k.scene
def sine_cosine(s: k.Scene):
    ax = k.Axes(x=(0, 6.5, 1), y=(-1.5, 1.5, 0.5), labels=("x", "y")).place(at="center")
    ax.plot(sine, color=k.BLUE, label="sin x")
    ax.plot(cosine, color=k.RED, label="cos x")
    s.play(k.draw(ax), duration=2)
    s.wait(0.5)
