"""Interactive lessons: `s.ask` stops playback for a question; `q.correct()` and `q.wrong()`
hold what plays for each outcome.

A lesson stays one timeline. The question is an instant; its branches are built one after the
other right after it, each starting from the state at the question, and the lesson continues
after the last one from the state at the end of the correct branch. The player (and
`kinemo dev`) jumps between those stretches; a video plays the correct path.
"""

from __future__ import annotations

import json
import math
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, Literal, Sequence

from .._runtime.spans import Span, user_span
from ..diagnostics import KinemoError
from ..params import Choice, Float, Int, Param, Point, TextParam

if TYPE_CHECKING:
    from .._core import Builder
    from ..reactive.signal import Signal
    from .scene import Scene

Then = Literal["retry", "continue"]
#: Words read per second, for W1504 (a quiz prompt and its options against `think=`).
READING_WORDS_PER_SECOND = 3.0
THENS = ("retry", "continue")


def _structure_error(message: str, span: Span, fix: tuple[str, str | None]) -> KinemoError:
    return KinemoError.make("K1501", message, spans=[span], fixes=[fix])


class Question:
    """A question asked with `s.ask`. `q.value` is the learner's answer as a signal;
    `with q.correct():` and `with q.wrong():` hold what plays after each kind of answer."""

    def __init__(self, scene: "Scene", qid: str, t: float, prompt: str, answer: dict[str, Any], value: "Signal[Any]", span: Span) -> None:
        self._scene = scene
        self.id = qid
        self.t = t
        self.prompt = prompt
        self._answer = answer
        self._value = value
        self._span = span
        self._default = answer_default(answer, value)
        self._branches: list[dict[str, Any]] = []
        b = scene._b
        self._frozen = b.freeze()
        #: Ops after this position belong to the question's branches.
        self._since = b.log_position()
        #: Where the lesson continues, and the log position at that moment: a branch must open
        #: there (right after the question or its previous branch).
        self.resume = t + 1.0 / scene.config.fps
        self._open_at = (self.resume, self._since)
        self._correct_end: tuple[int, float] | None = None
        #: The quiz stretch a video plays instead of stopping (`{t0, reveal, t1}`).
        self._quiz: dict[str, float] | None = None

    def _build_quiz(self, think: float, at: str) -> None:
        """The quiz stretch, right after the question and before its branches: it starts from
        the question's state and leaves it as it was."""
        from .quiz import build_quiz

        s, b = self._scene, self._scene._b
        s.cursor = self.resume
        before = len(s._nodes)  # pyright: ignore[reportPrivateUsage]
        built = build_quiz(s, self.prompt, self._answer, self._default, think, at, self._span)
        self._quiz = {key: built[key] for key in ("t0", "reveal", "t1")}
        self._lint_quiz(s._nodes[:before], built["rect"], think, at)  # pyright: ignore[reportPrivateUsage]
        self._reset(self._frozen, self.t, self._quiz["t1"])
        self.resume = self._quiz["t1"]
        self._open_at = (self.resume, b.log_position())

    def _lint_quiz(self, scene_nodes: list[Any], rect: tuple[float, float, float, float], think: float, at: str) -> None:
        """W1503: the band covers text of the scene; W1504: the prompt takes longer to read
        than the time given."""
        s, b = self._scene, self._scene._b
        t = self._quiz["t0"] if self._quiz else self.t
        covered = []
        for node in scene_nodes:
            if getattr(node, "kind", None) not in ("text", "math", "code") or not b.present(node._id, t):
                continue
            box = [json.loads(b.derived(node._id, side, t, True))["Float"] for side in ("left", "bottom", "right", "top")]
            if box[0] < rect[2] and rect[0] < box[2] and box[1] < rect[3] and rect[1] < box[3]:
                covered.append(node._label())
        if covered:
            others = [p for p in ("top", "bottom", "left", "right") if p != at]
            s.lints.warn(
                "W1503",
                f"the quiz band of '{self.id}' covers {', '.join(covered[:3])}{' and more' if len(covered) > 3 else ''}",
                spans=[self._span],
                time=t,
                fixes=[(f"put the band elsewhere: quiz_at=\"{others[0]}\" (or {', '.join(repr(o) for o in others[1:])})", None), ("or make room for it in the scene", None)],
            )
        words = len(self.prompt.split()) + sum(len(str(o).split()) for o in self._answer.get("options", []))
        if words / READING_WORDS_PER_SECOND > think:
            s.lints.warn(
                "W1504",
                f"'{self.id}' has {words} words to read in think={think:g} s",
                spans=[self._span],
                fixes=[(f"give more time: think={math.ceil(words / READING_WORDS_PER_SECOND)}", None), ("or shorten the prompt", None)],
            )

    @property
    def value(self) -> "Signal[Any]":
        """The learner's answer, as a signal: the default until they answer."""
        return self._value

    def correct(self) -> Any:
        """`with q.correct():` what plays after a correct answer; the lesson then goes on."""
        return self._branch("correct", "continue")

    def wrong(self, then: Then = "retry") -> Any:
        """`with q.wrong():` what plays after a wrong answer; then the question is asked again
        (`then="retry"`) or the lesson goes on (`then="continue"`)."""
        if then not in THENS:
            raise KinemoError.make("K0105", f"then={then!r}: use 'retry' or 'continue'", spans=[user_span()])
        self._check_wrong_reachable(user_span())
        return self._branch("wrong", then)

    @contextmanager
    def _branch(self, on: str, then: str) -> Iterator[None]:
        s, b = self._scene, self._scene._b
        span = user_span()
        if s.__dict__.get("_open_branch") is not None:
            raise _structure_error("a branch cannot hold another question's branch", span, ("close the first branch before opening the next", None))
        if any(br["on"] == on for br in self._branches):
            raise _structure_error(f"the question '{self.id}' already has a {on} branch", span, (f"put everything for a {on} answer in one `with q.{on}():`", None))
        if (s.cursor, b.log_position()) != self._open_at:
            raise _structure_error(
                f"the {on} branch of '{self.id}' must come right after its question (or its other branch)",
                span,
                ("move the `with` block up, right after `s.ask(...)`", None),
            )
        t0 = s.cursor
        if self._branches:
            # The previous branch left the state of the continuation: start from the question's.
            self._reset(self._frozen, self.t, t0)
        s.__dict__["_open_branch"] = self
        try:
            yield
        except BaseException:
            s.__dict__["_open_branch"] = None
            raise
        s.__dict__["_open_branch"] = None
        t1 = max(s.cursor, s._max_end, t0)
        self._branches.append({"on": on, "t0": t0, "t1": t1, "then": then, "span": span.ir()})
        if on == "correct":
            self._correct_end = (b.freeze(), t1)
        else:
            frozen, reference = self._correct_end or (self._frozen, self.t)
            self._reset(frozen, reference, t1)
        s.cursor = t1
        s._max_end = max(s._max_end, t1)
        self.resume = t1
        self._open_at = (t1, b.log_position())
        s._record("branch", t0, t1, f"{self.id}: {on}", span)

    def _reset(self, frozen: int, reference: float, t: float) -> None:
        s = self._scene
        for signal, src in json.loads(s._b.reset_touched(frozen, self._since, reference, t)):
            s._base[signal] = src

    def _check_wrong_reachable(self, span: Span) -> None:
        a = self._answer
        unreachable = False
        if a["kind"] == "choice":
            unreachable = len(a["correct"]) == len(a["options"])
        elif a["kind"] == "number" and a["lo"] is not None and a["hi"] is not None:
            unreachable = a["correct"] - a["tolerance"] <= a["lo"] and a["hi"] <= a["correct"] + a["tolerance"]
        if unreachable:
            self._scene.lints.warn(
                "W1501",
                f"every answer to '{self.id}' is correct: its wrong branch never plays",
                spans=[span],
                fixes=[("leave out a correct option, or narrow the tolerance", None)],
            )

    def _ir(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "t": self.t,
            "prompt": self.prompt,
            "answer": self._answer,
            "signal": self._value._id,
            "default": self._default,
            "branches": self._branches,
            "resume": self.resume,
            "quiz": self._quiz,
            "span": self._span.ir(),
        }


def answer_default(answer: dict[str, Any], value: "Signal[Any]") -> Any:
    """The answer signal's starting value in the terms the player grades: an option index, a
    number, `[x, y]` or a text."""
    start = json.loads(value._scene._b.eval_signal(value._id, 0.0))  # pyright: ignore[reportPrivateUsage]
    (payload,) = start.values() if isinstance(start, dict) else (None,)
    if answer["kind"] == "choice":
        return answer["options"].index(payload) if payload in answer["options"] else 0
    if answer["kind"] == "point":
        return list(payload) if payload is not None else [0.0, 0.0]
    return payload


def _number(value: object, what: str, span: Span) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise KinemoError.make("K0105", f"{what} must be a number, not {value!r}", spans=[span])
    return float(value)


def answer_ir(kind: Param, correct: Any, tolerance: float, span: Span) -> dict[str, Any]:
    """The IR of an answer of kind `kind` (a parameter type) whose correct value is `correct`."""
    if correct is None:
        raise KinemoError.make("K0105", "s.ask needs correct=: the answer that counts as right", spans=[span], fixes=[("give it", 's.ask("...", k.Choice(["1", "4"]), correct="4")')])
    tolerance = _number(tolerance, "tolerance", span)
    if tolerance < 0:
        raise KinemoError.make("K0105", f"tolerance must be >= 0, not {tolerance}", spans=[span])
    if isinstance(kind, Choice):
        options = [str(o) for o in kind.options]
        wanted = list(correct) if isinstance(correct, list | tuple | set) else [correct]
        indices = []
        for w in wanted:
            if str(w) not in options:
                raise KinemoError.make("K0105", f"correct={w!r} is not one of the options", spans=[span], fixes=[(f"use one of {', '.join(options)}", None)])
            indices.append(options.index(str(w)))
        return {"kind": "choice", "options": options, "correct": sorted(set(indices))}
    if isinstance(kind, Float | Int):
        value = _number(correct, "correct", span)
        lo, hi = kind.lo, kind.hi
        if (lo is not None and value < lo - tolerance) or (hi is not None and value > hi + tolerance):
            raise KinemoError.make("K0105", f"correct={value:g} is outside the range [{lo:g}, {hi:g}]", spans=[span], fixes=[("widen the range or fix the answer", None)])
        step = 1.0 if isinstance(kind, Int) else None
        return {"kind": "number", "lo": lo, "hi": hi, "step": step, "correct": value, "tolerance": tolerance}
    if isinstance(kind, Point):
        if not isinstance(correct, Sequence) or len(correct) != 2:
            raise KinemoError.make("K0105", f"correct= for a k.Point is (x, y), not {correct!r}", spans=[span])
        x, y = (_number(c, "correct", span) for c in correct)
        return {"kind": "point", "correct": [x, y], "tolerance": tolerance}
    if isinstance(kind, TextParam):
        texts = [str(c) for c in (correct if isinstance(correct, list | tuple | set) else [correct])]
        return {"kind": "text", "correct": texts}
    raise KinemoError.make(
        "K0105",
        f"{type(kind).__name__} cannot be a lesson's answer",
        spans=[span],
        fixes=[("use k.Choice, k.Float, k.Int, k.Point or k.Str", None)],
    )


class LessonMixin:
    _b: "Builder"
    cursor: float
    _max_end: float

    def answer(self, kind: Param, name: str | None = None) -> "Signal[Any]":
        """An answer the scene can use before its question is asked. `kind` is any answer kind
        (`k.Float(0, 6)`, `k.Choice([...])`, `k.Point()`...). `name=` names it in diagnostics. It
        holds the default until the learner answers: `slope = s.answer(k.Float(0, 6))`, draw
        with `slope`, then `s.ask("Turn the line until it touches", slope, correct=4)`."""
        from ..params import _param_signal_class  # pyright: ignore[reportPrivateUsage]
        from ..reactive.signal import signal

        if not isinstance(kind, Param):
            raise KinemoError.make("K0105", f"s.answer takes an answer kind such as k.Float(0, 6), not {kind!r}", spans=[user_span()])
        base = signal(kind.default, lerp="linear" if kind.kind in ("float", "vec2") else None, kind=kind.kind or "str")
        value = _param_signal_class()(self, base._id, base.kind, base.lerp)
        kinds: dict[int, Param] = self.__dict__.setdefault("_answer_kinds", {})
        label = name or f"answer {len(kinds) + 1}"
        object.__setattr__(value, "_param_name", label)
        kinds[value._id] = kind
        self._param_signals[value._id] = label  # type: ignore[attr-defined]
        return value

    def ask(
        self,
        prompt: str,
        answer: "Param | Signal[Any]",
        *,
        correct: Any = None,
        tolerance: float = 0.0,
        name: str | None = None,
        think: float | None = None,
        quiz_at: Literal["bottom", "top", "left", "right"] = "bottom",
    ) -> Question:
        """Stop playback for a question and wait for the learner's answer. `prompt` is the
        question, shown beside the frame. `answer` is the kind of answer: `k.Choice([...])` to
        pick one, `k.Float(lo, hi)` for a slider, `k.Float()` for a typed number, `k.Int`,
        `k.Point` to drag, `k.Str` to type; or a signal from `s.answer(...)` that the scene
        already uses. `correct=` is what counts as right (a list for several). `tolerance=` is
        how far a number or point may be off. `name=` is the question's id for a host platform
        (`q1`, `q2`... by default). `think=` is the time a quiz video gives to pause and answer
        (5 s by default), and `quiz_at=` where its band goes (`"bottom"`, `"top"`, `"left"` or
        `"right"` of the safe area). Then `with q.correct():` and `with q.wrong():` hold what
        plays after each kind of answer: `q = s.ask("Slope at x = 2?", k.Choice(["1", "2", "4"]),
        correct="4")`."""
        span = user_span()
        if self.__dict__.get("_open_branch") is not None:
            raise _structure_error("a question cannot be asked inside another question's branch", span, ("ask it after the branches", None))
        kinds: dict[int, Param] = self.__dict__.setdefault("_answer_kinds", {})
        if isinstance(answer, Param):
            value = self.answer(answer)
            kind = answer
        elif getattr(answer, "_id", None) in kinds:
            value, kind = answer, kinds[answer._id]  # type: ignore[union-attr]
        else:
            raise KinemoError.make("K0105", f"s.ask needs an answer kind (k.Choice, k.Float...) or s.answer(...), not {answer!r}", spans=[span])
        questions: list[Question] = self.__dict__.setdefault("_questions", [])
        qid = name or f"q{len(questions) + 1}"
        if any(q.id == qid for q in questions):
            raise KinemoError.make("K0105", f"two questions are named '{qid}'", spans=[span], fixes=[("give each question its own name=", None)])
        self._param_signals[value._id] = qid  # type: ignore[attr-defined]
        object.__setattr__(value, "_param_name", qid)
        ir = answer_ir(kind, correct, tolerance, span)
        t = self.cursor
        if self._max_end > t + 1e-6:
            self.lints.warn(  # type: ignore[attr-defined]
                "W1502",
                f"something is still moving when '{qid}' is asked (until t = {self._max_end:.2f} s): playback stops mid-motion",
                spans=[span],
                fixes=[("let it finish first", f"s.wait({self._max_end - t:.2f})")],
            )
        q = Question(self, qid, t, str(prompt), ir, value, span)  # type: ignore[arg-type]
        from .quiz import THINK

        wait = THINK if think is None else float(think)
        if not math.isfinite(wait) or wait < 0:
            raise KinemoError.make("K0105", f"think= is a number of seconds >= 0, not {think!r}", spans=[span])
        from .quiz import PLACES

        if quiz_at not in PLACES:
            raise KinemoError.make("K0105", f"quiz_at={quiz_at!r}: use one of {', '.join(PLACES)}", spans=[span])
        q._build_quiz(wait, quiz_at)
        questions.append(q)
        self.cursor = q.resume
        self._record("ask", t, q.resume, f"{qid}: {prompt}", span)  # type: ignore[attr-defined]
        return q


def lesson_questions(s: "Scene") -> None:
    """End of the build: the questions go into the IR."""
    questions: list[Question] = s.__dict__.get("_questions", [])
    if questions:
        s._b.set_questions(json.dumps([q._ir() for q in questions]))  # pyright: ignore[reportPrivateUsage]
