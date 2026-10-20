// A lesson's route through its questions (`s.ask`), without any page: grading an answer and
// deciding what plays next. Shared by the lesson player and `kinemo dev`, which serves it from here.
//
// A lesson is one timeline. Playback stops at a question's time; a correct answer plays the
// correct branch (if any) and goes on from `resume`; a wrong one plays the wrong branch (if any),
// then asks again (`then: "retry"`) or goes on (`then: "continue"`).
"use strict";

const EPSILON = 1e-6;

/** Whether `value` answers `answer` correctly (the IR's `Answer::grade`): an option index, a
 *  number, an `[x, y]` point or a text. */
export function grade(answer, value) {
  switch (answer.kind) {
    case "choice":
      return Number.isInteger(value) && answer.correct.includes(value);
    case "number":
      return typeof value === "number" && Math.abs(value - answer.correct) <= answer.tolerance + 1e-9;
    case "point":
      return Array.isArray(value) && value.length === 2 && Math.hypot(value[0] - answer.correct[0], value[1] - answer.correct[1]) <= answer.tolerance + 1e-9;
    case "text":
      return typeof value === "string" && answer.correct.some((c) => c.trim().toLowerCase() === value.trim().toLowerCase());
    default:
      return false;
  }
}

/** The exact answer, in the terms `grade` takes, for kinds where an answer within the
 *  tolerance still differs from it (a number, a point); null for the others. */
export function exactAnswer(answer) {
  if (answer.kind === "number") return answer.correct;
  if (answer.kind === "point") return answer.correct;
  return null;
}

/** How a right answer that is not the exact one is told: "Close enough: the answer is 2.", or
 *  null when `value` is the exact answer (or the kind has no tolerance). */
export function closeEnough(answer, value) {
  const exact = exactAnswer(answer);
  if (exact === null) return null;
  const round = (v) => Math.round(v * 1e6) / 1e6;
  if (answer.kind === "number") {
    return round(value) === round(exact) ? null : `Close enough: the answer is ${round(exact)}.`;
  }
  const [x, y] = value;
  return round(x) === round(exact[0]) && round(y) === round(exact[1]) ? null : `Close enough: the answer is (${round(exact[0])}, ${round(exact[1])}).`;
}

/** The step of a number answer's slider: its own `step`, else the largest round step that a
 *  tolerance can still catch (so the right value is a position a finger can land on), else a
 *  hundredth of the range. */
export function sliderStep(answer) {
  if (answer.step) return answer.step;
  const range = answer.hi - answer.lo;
  const limit = answer.tolerance > 0 ? answer.tolerance : range / 100;
  for (let power = 10 ** Math.ceil(Math.log10(Math.max(limit, 1e-9))); ; power /= 10) {
    for (const m of [5, 2, 1]) if (m * power <= limit + 1e-12 && m * power <= range) return m * power;
  }
}

/** The IR value the answer signal takes for `value` (what the scene sees). */
export function signalValue(answer, value) {
  switch (answer.kind) {
    case "choice":
      return { Str: answer.options[value] };
    case "number":
      return { Float: value };
    case "point":
      return { Vec2: value };
    default:
      return { Str: String(value) };
  }
}

export class Route {
  constructor(questions) {
    this.questions = [...(questions || [])].sort((a, b) => a.t - b.t);
    this.playing = null; // { question, branch } while a branch plays
  }

  /** Playback moves from `from` to `to`: `{ stop, question }` to stop and ask, `{ jump }` to go
   *  on elsewhere, or null. */
  advance(from, to) {
    if (this.playing) {
      const { question, branch } = this.playing;
      if (Math.max(from, to) < branch.t0 - EPSILON || Math.min(from, to) > branch.t1 + EPSILON) {
        this.playing = null; // the playhead left the branch (scrubbed away)
      } else if (to >= branch.t1 - EPSILON) {
        this.playing = null;
        if (branch.then === "retry") return { stop: question.t, question };
        if (Math.abs(question.resume - branch.t1) > EPSILON) return { jump: question.resume };
        from = branch.t1; // on from the branch's end, which may be the next question
      } else {
        return null;
      }
    }
    for (const question of this.questions) {
      if (from <= question.t + EPSILON && to >= question.t - EPSILON) return { stop: question.t, question };
    }
    return null;
  }

  /** The learner answered `question` with `value`, graded here: `{ correct, to }` where
   *  playback goes (`to` is null when the question is asked again right away). */
  answered(question, value) {
    return this.outcome(question, grade(question.answer, value));
  }

  /** `question` was answered and graded elsewhere (a host platform): right or wrong. */
  outcome(question, correct) {
    const branch = question.branches.find((b) => b.on === (correct ? "correct" : "wrong"));
    if (branch) {
      this.playing = { question, branch };
      return { correct, to: branch.t0 };
    }
    return { correct, to: correct ? question.resume : null };
  }

  /** Play `branch` of `question` from its start (picked on a timeline). */
  enter(question, branch) {
    this.playing = { question, branch };
    return branch.t0;
  }
}
