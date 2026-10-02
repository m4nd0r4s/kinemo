import kinemo as k


def f(x):
    return x * x


@k.scene
def integral_area(s: k.Scene):
    ax = k.Axes(x=(0, 1.5, 0.5), y=(0, 2, 0.5)).place(at="center")
    curve = ax.plot(f, color=k.BLUE)
    ax.area(curve, domain=(0, 1), fill=k.BLUE, fill_opacity=0.3)
    eq = k.Math(r"\int_0^1 x^2 \, dx = \frac{1}{3}").place(at="top", margin=0.5)
    s.play(k.draw(ax))
    s.play(k.write(eq))
    s.wait(0.5)
