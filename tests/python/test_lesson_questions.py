"""Questions and branches (`s.ask`, `q.correct()`, `q.wrong()`): each branch starts from the
state at the question, and the lesson continues from the end of the correct branch."""

from __future__ import annotations

import json
from typing import Any

import pytest

import kinemo as k
from kinemo.diagnostics import KinemoError
from conftest import build, ir


def value(scene: k.Scene, signal: int, t: float) -> Any:
    raw = json.loads(scene.builder.eval_signal(signal, t))
    (payload,) = raw.values()
    return payload


def prop(scene: k.Scene, node: k.Node, name: str) -> int:
    return ir(scene)["objects"][node._id]["props"][name]


def lesson(order: tuple[str, ...]) -> tuple[k.Scene, dict[str, Any]]:
    seen: dict[str, Any] = {}

    def body(s: k.Scene) -> None:
        dot = k.Dot(x=-2)
        s.add(dot)
        s.play(dot.to(x=0))
        q = s.ask("What is the slope at x = 2?", k.Choice(["1", "2", "4"]), correct="4")
        for outcome in order:
            if outcome == "wrong":
                with q.wrong():
                    hint = k.Text("Look at the tangent", y=2)
                    s.play(k.write(hint))
                    s.play(dot.to(x=3, fill=k.RED))
                    seen["hint"] = hint
            else:
                with q.correct():
                    yes = k.Text("Right!", y=-2)
                    s.play(k.write(yes))
                    s.play(dot.to(x=-3))
                    seen["yes"] = yes
        s.play(dot.to(y=1))
        seen["dot"], seen["q"] = dot, q

    return build(body), seen


@pytest.mark.parametrize("order", [("wrong", "correct"), ("correct", "wrong")])
def test_every_branch_starts_from_the_question_and_the_lesson_goes_on_from_the_correct_one(order: tuple[str, ...]) -> None:
    scene, seen = lesson(order)
    (question,) = ir(scene)["questions"]
    branches = {b["on"]: b for b in question["branches"]}
    x, fill = prop(scene, seen["dot"], "x"), prop(scene, seen["dot"], "fill")
    at_question = value(scene, x, question["t"])
    white = value(scene, fill, question["t"])
    for branch in branches.values():
        assert value(scene, x, branch["t0"]) == pytest.approx(at_question)
        assert value(scene, fill, branch["t0"]) == pytest.approx(white)
    wrong, correct = branches["wrong"], branches["correct"]
    assert value(scene, x, wrong["t1"] - 1e-6) == pytest.approx(3.0, abs=1e-3)
    assert value(scene, x, correct["t1"] - 1e-6) == pytest.approx(-3.0, abs=1e-3)
    # The lesson continues from the end of the correct branch, whichever came last.
    assert value(scene, x, question["resume"]) == pytest.approx(-3.0, abs=1e-3)
    assert value(scene, fill, question["resume"]) == pytest.approx(white)
    assert question["resume"] == max(wrong["t1"], correct["t1"])
    b = scene.builder
    hint, yes = seen["hint"], seen["yes"]
    assert b.present(hint._id, wrong["t1"] - 1e-6) and not b.present(hint._id, correct["t0"] + 1e-6)
    assert b.present(yes._id, question["resume"] + 0.5)
    assert wrong["then"] == "retry" and correct["then"] == "continue"


def test_the_question_holds_one_frame_and_the_answer_is_a_signal() -> None:
    @build
    def scene(s: k.Scene) -> None:
        s.wait(1)
        slope = s.answer(k.Float(0, 6, default=1))
        line = k.Line((0, 0), (1, 1))
        s.add(line)
        line.rotation = slope
        q = s.ask("Turn the line until it touches the curve", slope, correct=4, tolerance=0.2, name="tangent")
        assert q.value is slope
        with q.correct():
            s.wait(1)

    (question,) = ir(scene)["questions"]
    assert question["id"] == "tangent" and question["t"] == 1.0
    assert question["branches"][0]["t0"] == pytest.approx(1.0 + 1 / scene.config.fps)
    assert question["answer"] == {"kind": "number", "lo": 0.0, "hi": 6.0, "step": None, "correct": 4.0, "tolerance": 0.2}
    assert ir(scene)["signals"][question["signal"]]["initial"] == {"Float": 1.0}


@pytest.mark.parametrize(
    ("kind", "correct", "expected"),
    [
        (k.Float(), 2.5, {"kind": "number", "lo": None, "hi": None, "step": None, "correct": 2.5, "tolerance": 0.0}),
        (k.Int(0, 10), 3, {"kind": "number", "lo": 0.0, "hi": 10.0, "step": 1.0, "correct": 3.0, "tolerance": 0.0}),
        (k.Point(), (1, 2), {"kind": "point", "correct": [1.0, 2.0], "tolerance": 0.0}),
        (k.Str(), ["slope", "gradient"], {"kind": "text", "correct": ["slope", "gradient"]}),
        (k.Choice(["a", "b", "c"]), ["a", "c"], {"kind": "choice", "options": ["a", "b", "c"], "correct": [0, 2]}),
    ],
)
def test_answer_kinds(kind: Any, correct: Any, expected: dict[str, Any]) -> None:
    @build
    def scene(s: k.Scene) -> None:
        s.ask("?", kind, correct=correct)

    assert ir(scene)["questions"][0]["answer"] == expected


def test_a_video_plays_the_correct_path() -> None:
    scene, _ = lesson(("wrong", "correct"))
    (question,) = ir(scene)["questions"]
    wrong, correct = question["branches"]
    path = json.loads(scene.builder.video_path())
    assert path == [[0.0, wrong["t0"]], [correct["t0"], correct["t1"]], [question["resume"], scene.duration]]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("q = s.ask('?', k.Choice(['1', '4']), correct='3')", "not one of the options"),
        ("q = s.ask('?', k.Choice(['1', '4']))", "needs correct="),
        ("q = s.ask('?', k.Float(0, 1), correct=5)", "outside the range"),
        ("q = s.ask('?', k.Bool(), correct=True)", "cannot be a lesson's answer"),
        ("q = s.ask('?', k.Choice(['1', '4']), correct='4')\ns.wait(1)\nwith q.correct():\n    pass", "right after its question"),
        ("q = s.ask('?', k.Choice(['1', '4']), correct='4')\nwith q.correct():\n    s.ask('again?', k.Str(), correct='x')", "inside another question's branch"),
        ("q = s.ask('?', k.Choice(['1', '4']), correct='4')\nwith q.wrong():\n    pass\nwith q.wrong():\n    pass", "already has a wrong branch"),
    ],
)
def test_mistakes_are_errors(body: str, message: str) -> None:
    def scene(s: k.Scene) -> None:
        exec(body, {"k": k, "s": s})

    with pytest.raises(KinemoError, match=message):
        build(scene)


def lint_codes(scene: k.Scene) -> set[str]:
    return {d.code for d in scene.lints.items}


def test_lints_for_questions() -> None:
    @build
    def scene(s: k.Scene) -> None:
        dot = k.Dot()
        s.add(dot)
        s.start(dot.to(x=3, duration=2))
        q = s.ask("?", k.Choice(["yes", "of course"]), correct=["yes", "of course"])
        with q.wrong():
            pass

    assert {"W1501", "W1502"} <= lint_codes(scene)
