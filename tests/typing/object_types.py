"""Object props are typed signals; constructors and `.to`/`.set` take typed keywords."""

from typing import assert_type

import kinemo as k


@k.scene
def object_types(s: k.Scene) -> None:
    title = k.Text("Hello", size=0.6).place(at="top", margin=0.5)
    assert_type(title, k.Text)
    assert_type(title.color.now, k.Color)
    assert_type(title.text.now, str)
    size: k.Signal[float] = title.size
    assert_type(size.now, float)
    dot = k.Dot(r=0.1, fill=k.RED, x=lambda: k.time() * 0.5)
    assert_type(dot.x.now, float)
    assert_type(dot.r.now, float)
    assert_type(dot.left.now, float)
    assert_type(dot.center.now, k.Vec)
    assert_type(dot.world.position.now, k.Vec)
    assert_type(dot.edge("right"), k.Expr[k.Vec])
    rect = k.Rect(w=2, h=1, radius=0.1, stroke=k.theme.fg, fill_opacity=0.5)
    assert_type(rect.w.now, float)
    assert_type(rect.to(w=3, color=k.BLUE, duration=0.5), k.Animation)
    assert_type(rect.set(opacity=0.5), k.Rect)

    bars = k.Row(*[k.Bar(v, label=True) for v in [3, 1, 2]], gap=0.2)
    assert_type(bars, k.Row[k.Bar])
    assert_type(bars[0].value.now, float)
    for bar in bars:
        assert_type(bar, k.Bar)

    ax = k.Axes(x=(0, 6, 1), y=(0, 4, 1), grid=True)
    assert_type(ax.x_range.now, k.Vec)
    curve = ax.plot(lambda x: 0.1 * x * x, color=k.YELLOW)
    assert_type(curve.point_at(k.signal(1.0)), k.Expr[k.Vec])
    assert_type(curve.slope_at(2.0), k.Expr[float])

    k.Circle(r=1, rr=2)  # pyright: ignore[reportCallIssue] - unknown constructor keyword
    k.Circle(r=1, opacity="x")  # pyright: ignore[reportArgumentType]
    dot.r = 3  # pyright: ignore[reportAttributeAccessIssue] - props change with .set/.to
    dot.nope  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    k.Circel  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    title.place(at="middle")  # pyright: ignore[reportArgumentType] - not an anchor

    s.play(k.write(title), k.fade_in(dot, rect, shift=(0, 0.2)))
    s.play(k.indicate(dot, color=k.GREEN), ease=k.ease.out_back)
    s.wait(0.5)
