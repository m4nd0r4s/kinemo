"""A one-minute tour of kinemo, for sharing it: `kinemo render docs/media/launch.py`."""

import math

import kinemo as k

# A heart, for the epicycles to draw.
HEART = [(16 * math.sin(t) ** 3 / 6, (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 6) for t in (2 * math.pi * i / 200 for i in range(200))]


def captioned(text: str) -> k.Group:
    """A caption on a dark plate, readable over anything."""
    label = k.Text(text, size=0.4)
    plate = k.RoundedRect(w=float(label.width.now) + 0.6, h=0.75, radius=0.15, fill=k.BLACK, fill_opacity=0.8, stroke_width=0.0)
    return k.Group(plate, label).place(at="top", margin=0.5)


@k.clip
def title(s: k.Scene) -> None:
    card = k.TitleCard("kinemo", kicker="Python in, animation out", subtitle="explanatory animations with a live preview").place(at="center")
    s.play(k.draw(card), duration=2.5)
    s.wait(1.5)
    s.play(k.fade_out(card), duration=0.5)


@k.clip
def theorem(s: k.Scene) -> None:
    caption = captioned("Math, without a LaTeX install")
    tri = k.Triangle.right(3, 4, scale=0.6).place(at="center")
    squares = [k.Square.on(side, outward=True, fill_opacity=0.2) for side in tri.sides]
    eq = k.Math(r"a^2 + b^2 = c^2").place(at="bottom", margin=0.5)
    s.play(k.fade_in(caption), k.draw(tri), duration=1.0)
    s.play(k.stagger([k.grow(q) for q in squares], lag=0.2))
    s.play(k.write(eq))
    with s.during(squares[0].to(color=k.YELLOW), squares[1].to(color=k.YELLOW)):
        s.play(k.indicate(squares[2], color=k.GREEN))
    s.wait(1)
    s.play(k.fade_out(caption, tri, *squares, eq), duration=0.5)


@k.clip
def linear_map(s: k.Scene) -> None:
    plane = k.NumberPlane(x=(-7, 7, 1), y=(-4, 4, 1))
    caption = captioned("Linear algebra you can watch")
    s.play(k.draw(plane), k.fade_in(caption), duration=1.5)
    s.play(plane.apply([[1, 1], [0, 1]]), duration=2)
    s.play(plane.apply([[0, -1], [1, 0]]), duration=2)
    s.wait(0.5)
    s.play(k.fade_out(plane, caption), duration=0.5)


@k.clip
def sorting(s: k.Scene) -> None:
    caption = captioned("Algorithms, step by step")
    row = k.Row(*[k.Bar(v, label=True) for v in [5, 2, 8, 1, 9, 3, 7, 4]], gap=0.2, align="bottom").place(at="bottom", margin=1.9)
    s.play(k.fade_in(caption), k.stagger([k.grow(b, from_="bottom") for b in row], lag=0.05))
    count = len(row)
    with s.tempo(1.5, to=6):
        for i in range(count):
            for j in range(count - 1 - i):
                a, b = row[j], row[j + 1]
                with s.during(a.to(color=k.YELLOW), b.to(color=k.YELLOW), duration=0.2):
                    if a.value.now > b.value.now:
                        s.play(row.swap(j, j + 1), duration=0.4)
                    else:
                        s.wait(0.2)
            s.play(row[count - 1 - i].to(color=k.GREEN), duration=0.2)
    s.wait(0.5)
    s.play(k.fade_out(caption, row), duration=0.5)


@k.clip
def data(s: k.Scene) -> None:
    caption = captioned("Data, straight from your dataframe")
    before = {"source": ["solar", "wind", "hydro", "gas"], "twh": [12, 30, 25, 40]}
    after = {"source": ["solar", "wind", "hydro", "gas"], "twh": [45, 38, 24, 18]}
    chart = k.BarChart(before, x="source", y="twh", key="source").place(at="center")
    s.play(k.fade_in(caption), k.draw(chart), duration=1.5)
    s.wait(0.5)
    s.play(chart.to(data=after), duration=2)
    s.wait(1)
    s.play(k.fade_out(caption, chart), duration=0.5)


@k.clip
def fourier(s: k.Scene) -> None:
    caption = captioned("Fourier circles that draw")
    epicycles = k.Epicycles(HEART, n=30, color=k.RED).place(at="center")
    s.play(k.fade_in(caption), k.draw(epicycles), duration=1)
    s.play(epicycles.run(turns=1), duration=6)
    s.wait(0.5)
    s.play(k.fade_out(caption, epicycles), duration=0.5)


@k.clip
def closing(s: k.Scene) -> None:
    install = k.Code("pip install kinemo\nkinemo new my-video\nkinemo dev scene.py", lang="bash", size=0.45).place(at="center")
    link = k.Text("github.com/m4nd0r4s/kinemo", size=0.4).place(below=install, gap=0.6)
    s.play(k.write(install), duration=2)
    s.play(k.fade_in(link), duration=0.5)
    s.wait(2.5)


@k.scene(fps=30)
def launch(s: k.Scene):
    for part in (title, theorem, linear_map, sorting, data, fourier, closing):
        s.play(part())
