"""The animation at the top of the README: `kinemo render docs/media/hero.py --out docs/media/hero.gif`."""

import kinemo as k

SOURCE = '''x = k.signal(-2.0)
curve = ax.plot(f)
dot = k.Dot().place(at=curve.point_at(x))
tan = curve.tangent_at(x, length=3)
slope = k.Text(lambda: f"slope {curve.slope_at(x)():+.2f}")
s.play(x.to(2.5), duration=3)'''


def f(x: float) -> float:
    return 0.15 * x**3 - 0.9 * x + 1.5


@k.scene(fps=30)
def hero(s: k.Scene):
    # Fixed positions: the tangent reaches past the axes, and a container around them would
    # re-center as it moves.
    code = k.Code(SOURCE, lang="python", size=0.24, x=-3.1)
    ax = k.Axes(x=(-3, 3, 1), y=(-1, 5, 1), width=5.2, height=4.6, grid=True, position=(4.5, 0.0))
    x = k.signal(-2.0)
    curve = ax.plot(f, color=k.YELLOW)
    dot = k.Dot(r=0.1, fill=k.RED).place(at=curve.point_at(x))
    tan = curve.tangent_at(x, length=3, stroke=k.RED, enter_with_axes=False)
    slope = k.Text(lambda: f"slope {curve.slope_at(x)():+.2f}".replace("-", "−"), size=0.35).place(at=(4.5, 2.87))
    s.play(k.write(code), k.draw(ax), k.draw(curve), duration=1.5)
    s.play(k.fade_in(dot, tan, slope), duration=0.5)
    s.play(x.to(2.5), duration=3)
    s.play(x.to(-2.0), duration=2)
    s.wait(0.3)
