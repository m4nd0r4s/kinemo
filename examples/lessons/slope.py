"""An interactive lesson: the derivative as the slope of the tangent.

    kinemo dev examples/lessons/slope.py                         # answer in the preview
    kinemo render examples/lessons/slope.py --format lesson      # a page for the browser
    kinemo render examples/lessons/slope.py                      # a quiz video
"""

import kinemo as k


def f(x: float) -> float:
    return x * x


def say(text: str) -> k.Text:
    return k.Text(text, size=0.4).place(at="bottom", margin=0.6)


@k.scene
def slope(s: k.Scene):
    title = k.Text("The derivative is a slope", size=0.55)
    # The axes keep the right side free for the quiz band of the video (`quiz_at="right"`).
    ax = k.Axes(x=(-1, 3.5, 1), y=(-1, 13, 2), grid=True, labels=("x", "y"), width=8.5, height=5.4).place(at="left", margin=0.8)
    title.place(above=ax, gap=0.25)
    curve = ax.plot(f, color=k.BLUE)
    # The function stays on screen: every question is about it.
    name = k.Math(r"f(x) = x^2", size=0.5, fill=k.BLUE).place(at=ax.point(0.75, 11))
    s.play(k.write(title), k.draw(ax), k.draw(curve))
    s.play(k.write(name))

    # Explore: the secant through P = (1, 1) and a point Q further along the curve. As Q slides
    # down to P, the secant turns into the tangent.
    point = k.Dot(r=0.09, fill=k.YELLOW).place(at=ax.point(1, 1))
    point_label = k.Text("P (1, 1)", size=0.32, fill=k.YELLOW).place(at=ax.point(1.55, 0.2))
    s.play(k.fade_in(point, point_label))
    h = k.signal(1.8)
    rise = 2 + h  # the secant's slope: ((1 + h)² - 1) / h
    secant = k.Line(ax.point(0.5, 1 - 0.5 * rise), ax.point(3.2, 1 + 2.2 * rise), stroke=k.YELLOW)
    q = k.Dot(r=0.09, fill=k.WHITE).place(at=ax.point(1 + h, (1 + h) * (1 + h)))
    q_label = k.Text("Q", size=0.32).place(right_of=q, gap=0.12)
    readout = k.Text(lambda: f"slope of the secant PQ: {2 + h():.2f}", size=0.4).place(at="bottom", margin=0.6)
    s.play(k.fade_in(q, q_label), k.draw(secant), k.write(readout))
    s.wait(0.5)
    s.play(h.to(0.05), duration=4)
    s.wait(0.5)
    s.play(k.fade_out(secant, readout, q, q_label))

    # Question 1: the learner turns a line until it is the tangent at x = 1.
    m = s.answer(k.Float(0, 4, default=0.5), name="slope")
    line = k.Line(ax.point(0, 1 - m), ax.point(2, 1 + m), stroke=k.YELLOW)
    s.play(k.draw(line))
    q1 = s.ask("Turn the line until it just touches the curve at x = 1.", m, correct=2, tolerance=0.25, name="tangent-at-1", quiz_at="right")
    with q1.wrong():
        hint = say("Not yet: the tangent touches the curve at x = 1 without crossing it.")
        s.play(k.write(hint))
        s.wait(2)
    with q1.correct():
        yes = say("That's the tangent. Its slope at x = 1 is 2.")
        s.play(k.write(yes), k.sound(k.sfx.ding(), gain=0.7))
        s.wait(1.5)
        s.play(k.fade_out(yes, line, point, point_label))

    # Question 2: the tangent slides to x = 3.
    x = k.signal(1.0)
    tangent = curve.tangent_at(x, length=2.4, stroke=k.YELLOW, stroke_width=3, enter_with_axes=False)
    dot = k.Dot(r=0.09, fill=k.YELLOW).place(at=curve.point_at(x))
    s.play(k.fade_in(tangent, dot))
    s.play(x.to(3), duration=2)
    q2 = s.ask("The tangent is now at x = 3. What is its slope?", k.Choice(["3", "6", "9"]), correct="6", name="slope-at-3", quiz_at="right")
    with q2.wrong(then="continue"):
        nope = say("It is 6: at x = 3 the slope is twice x.")
        s.play(k.write(nope))
        s.wait(2)
        s.play(k.fade_out(nope))
    with q2.correct():
        right = say("Right: 6, twice x.")
        s.play(k.write(right), k.sound(k.sfx.ding(), gain=0.7))
        s.wait(1.5)
        s.play(k.fade_out(right))

    # Formalize.
    rule = k.Math(r"f(x) = x^2 \quad\Rightarrow\quad f'(x) = 2x", size=0.5).place(at="bottom", margin=0.6)
    s.play(k.write(rule))
    s.play(x.to(0.5), duration=1.5)
    q3 = s.ask("So what is f'(5)?", k.Float(), correct=10, name="slope-at-5", quiz_at="right")
    with q3.wrong(then="continue"):
        s.play(rule.to(fill=k.YELLOW), duration=0.4)
        s.play(rule.to(fill=k.WHITE), duration=0.4)
    with q3.correct():
        s.play(k.sound(k.sfx.ding(), gain=0.7))
    s.play(k.fade_out(rule))
    done = say("The derivative is the slope of the tangent, point by point: f'(5) = 10.")
    s.play(k.write(done))
    s.wait(2)
