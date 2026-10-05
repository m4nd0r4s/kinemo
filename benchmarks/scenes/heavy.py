"""Heavy scenes: text, math, code, mass objects, a graph and a deformed plane."""

import math
import kinemo as k


@k.scene
def text_wall(s: k.Scene):
    lines = [k.Text(f"Line {i}: the quick brown fox jumps over the lazy dog", size=0.28) for i in range(14)]
    col = k.Column(*lines, gap=0.08).place(at="center")
    s.play(k.stagger([k.write(t) for t in lines], lag=0.1))
    s.play(col.to(scale=0.8), duration=2)


@k.scene
def formulas(s: k.Scene):
    eqs = [k.Math(tex, size=0.5) for tex in (r"e^{i\pi}+1=0", r"\int_0^1 x^2\,dx=\frac13", r"\sum_{n=1}^\infty \frac1{n^2}=\frac{\pi^2}6", r"\nabla\cdot E=\frac{\rho}{\varepsilon_0}")]
    col = k.Column(*eqs, gap=0.4).place(at="center")
    s.play(k.stagger([k.write(e) for e in eqs], lag=0.3))
    s.play(col.to(rotate=10), duration=2)


@k.scene
def code_typing(s: k.Scene):
    src = "\n".join(f"def f{i}(x):\n    return x * {i} + sum(range({i}))" for i in range(6))
    code = k.Code(src, lang="python").place(at="center")
    s.play(k.write(code), duration=4)


@k.scene
def points_cloud(s: k.Scene):
    n = 20000
    xy = [(6 * math.cos(i * 0.618) * (i / n) ** 0.5, 3.5 * math.sin(i * 0.618) * (i / n) ** 0.5) for i in range(n)]
    pts = k.Points(xy, radius=0.015)
    s.play(k.fade_in(pts))
    s.play(pts.to(rotate=90), duration=3)


@k.scene
def graph_net(s: k.Scene):
    names = [f"n{i}" for i in range(24)]
    edges = [(names[i], names[(i * 7 + 3) % 24]) for i in range(24)] + [(names[i], names[i + 1]) for i in range(23)]
    g = k.Graph(names, edges, layout="force", radius=0.2, size=0.18)
    s.play(k.draw(g))
    s.play(g.relayout("circle"), duration=2)


@k.scene
def plane_warp(s: k.Scene):
    plane = k.NumberPlane()
    plane.polygon([(0, 0), (1, 0), (1, 1), (0, 1)], fill=k.YELLOW)
    s.play(k.draw(plane))
    s.play(plane.apply([[1, 1], [0, 1]]), duration=2)
    s.play(plane.apply(lambda x, y: (x + 0.3 * math.sin(y), y + 0.3 * math.sin(x))), duration=2)
