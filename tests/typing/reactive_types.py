"""Signals and expressions: `k.signal`, operators, `.now`, `.to`, `.map`, natives."""

from typing import assert_type

import kinemo as k


def parabola(x: float) -> float:
    return x * x


def marker(radius: k.Val[float]) -> k.Dot:
    """`k.Val[T]` in a user's own helper: a value, a signal or a lambda."""
    return k.Dot(r=radius)


@k.scene
def reactive_types(s: k.Scene) -> None:
    x = k.signal(1.0)
    assert_type(x, k.Signal[float])
    assert_type(x.now, float)
    assert_type(x + 1, k.Expr[float])
    assert_type(2 * x - 1, k.Expr[float])
    assert_type(x / 2 + x**2, k.Expr[float])
    assert_type(-x, k.Expr[float])
    assert_type(x > 1, k.Expr[bool])
    assert_type((x > 1) & (x < 3), k.Expr[bool])
    assert_type(x.to(2.5, duration=1), k.Animation)
    assert_type(x.map(parabola), k.Expr[float])
    assert_type(x.map(lambda v: k.mix(k.RED, k.BLUE, v)), k.Expr[k.Color])
    assert_type(k.sin(x), k.Expr[float])
    assert_type(k.sin(0.5), float)
    assert_type(k.max(0, x), k.Expr[float])
    assert_type(k.clamp(x, 0, 1), k.Expr[float])
    assert_type(k.vec(x, 1.0), k.Expr[k.Vec])
    assert_type(k.time, k.Expr[float])
    assert_type(k.computed(lambda: x() * 2), k.Expr[float])

    on = k.signal(True)
    assert_type(on, k.Signal[bool])
    name = k.signal("a")
    assert_type(name, k.Signal[str])
    assert_type(name + "b", k.Expr[str])
    point = k.signal((0.0, 1.0))
    assert_type(point, k.Signal[k.Vec])
    assert_type(point.now.x, float)

    items = k.list([5, 2, 8])
    assert_type(items, k.ListSignal[int])
    assert_type(items[0], int)
    items.append(3)

    total = x + 1
    total.to(3)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType] - a derived value has no .to
    float(x)  # pyright: ignore[reportArgumentType] - a signal is not a number
    x.set("text")  # pyright: ignore[reportArgumentType]

    marker(x)
    marker(2.0)
    marker(lambda: x() + 1)
    marker("large")  # pyright: ignore[reportArgumentType]
    s.play(x.to(3))
