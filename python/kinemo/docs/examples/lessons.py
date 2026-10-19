"""Interactive lessons: questions, answers and branches."""

from __future__ import annotations

from ..entry import DocEntry

ENTRIES = (
    DocEntry(
        "Scene.ask",
        "Interactive lessons",
        "Stops playback for a question; the learner answers in the lesson player (or in "
        "`kinemo dev`). `with q.correct():` and `with q.wrong():` hold what plays for each kind of "
        "answer: each starts from the state at the question, a wrong answer asks again "
        "(`then=\"continue\"` goes on instead), and the lesson continues from the end of the "
        "correct branch. A video plays the correct path.",
        '''
import kinemo as k

@k.scene
def slope(s: k.Scene):
    s.play(k.write(k.Math("f(x) = x^2").place(at="center")))
    q = s.ask("What is the slope of f at x = 2?", k.Choice(["2", "4", "8"]), correct="4")
    with q.wrong():
        s.play(k.write(k.Text("Hint: f'(x) = 2x").place(at="bottom")))
    with q.correct():
        s.play(k.write(k.Text("Right: 2 · 2 = 4").place(at="bottom")))
''',
        related=("Scene.answer", "k.Choice", "k.Point"),
    ),
    DocEntry(
        "Scene.answer",
        "Interactive lessons",
        "An answer the scene uses before its question is asked: the learner moves a slider (or "
        "drags a point) and the frame follows. Until they answer it holds the default; in video, "
        "always. Anything it drives must be native (W1302).",
        '''
import kinemo as k

@k.scene
def tangent(s: k.Scene):
    angle = s.answer(k.Float(0, 90, default=10))
    line = k.Line((-3, 0), (3, 0), rotate=angle).place(at="center")
    s.play(k.draw(line))
    q = s.ask("Turn the line to 45°", angle, correct=45, tolerance=3)
    with q.correct():
        s.play(line.to(stroke=k.GREEN))
''',
        related=("Scene.ask", "k.Float"),
    ),
    DocEntry(
        "k.Point",
        "Interactive lessons",
        "A position as an answer: the learner drags a point, and `correct=(x, y)` with "
        "`tolerance=` grades it. As a scene parameter, `--param target=1,2`.",
        '''
import kinemo as k

@k.scene
def peak(s: k.Scene):
    pick = s.answer(k.Point(default=(0, 0)))
    dot = k.Dot(position=pick, r=0.15)
    s.add(dot)
    q = s.ask("Drag the dot to (2, 1)", pick, correct=(2, 1), tolerance=0.3)
    with q.correct():
        s.play(dot.to(fill=k.GREEN))
''',
        related=("Scene.answer", "Scene.ask"),
    ),
)
