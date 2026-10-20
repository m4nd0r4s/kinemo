// `node --test python/kinemo/export/player/lesson.test.mjs`: a lesson's route through its questions.
import assert from "node:assert/strict";
import { test } from "node:test";

import { Route, closeEnough, grade, signalValue, sliderStep } from "./lesson.js";

const q1 = {
  id: "q1", t: 2, resume: 5, answer: { kind: "number", correct: 76, tolerance: 4 },
  branches: [{ on: "wrong", t0: 2.02, t1: 4, then: "retry" }, { on: "correct", t0: 4, t1: 5, then: "continue" }],
};
const q2 = {
  id: "q2", t: 5, resume: 6.5, answer: { kind: "choice", options: ["2", "4"], correct: [1] },
  branches: [{ on: "correct", t0: 5.02, t1: 6, then: "continue" }, { on: "wrong", t0: 6, t1: 6.5, then: "continue" }],
};

test("a wrong answer plays its branch and asks again; a right one goes on to the next question", () => {
  const route = new Route([q2, q1]);
  assert.equal(route.advance(1.9, 2.05).stop, 2);
  assert.deepEqual(route.answered(q1, 50), { correct: false, to: 2.02 });
  assert.equal(route.advance(2.5, 3), null);
  assert.deepEqual(route.advance(3, 4.01), { stop: 2, question: q1 });
  assert.deepEqual(route.answered(q1, 75), { correct: true, to: 4 });
  // The correct branch ends where the next question is asked.
  assert.equal(route.advance(4.98, 5.03).stop, 5);
});

test("after a branch the lesson resumes past the other branches", () => {
  const route = new Route([q1, q2]);
  assert.deepEqual(route.answered(q2, 1), { correct: true, to: 5.02 });
  assert.deepEqual(route.advance(5.9, 6.05), { jump: 6.5 });
  assert.deepEqual(route.answered(q2, 0), { correct: false, to: 6 });
  assert.equal(route.advance(6.4, 6.6), null);
});

test("without a branch for the outcome: a right answer resumes, a wrong one is asked again", () => {
  const bare = { id: "q", t: 1, resume: 1.02, answer: { kind: "text", correct: ["slope"] }, branches: [] };
  const route = new Route([bare]);
  assert.deepEqual(route.answered(bare, " Slope "), { correct: true, to: 1.02 });
  assert.deepEqual(route.answered(bare, "rate"), { correct: false, to: null });
});

test("a host's grade overrides the player's", () => {
  const route = new Route([q1]);
  assert.deepEqual(route.outcome(q1, true), { correct: true, to: 4 });
  assert.deepEqual(route.outcome(q1, false), { correct: false, to: 2.02 });
});

test("grading and the value the scene sees", () => {
  assert.ok(grade({ kind: "point", correct: [1, 2], tolerance: 0.5 }, [1.3, 2.3]));
  assert.ok(!grade({ kind: "point", correct: [1, 2], tolerance: 0.5 }, [2, 2]));
  assert.ok(grade({ kind: "choice", correct: [0, 2] }, 2) && !grade({ kind: "choice", correct: [0, 2] }, "2"));
  assert.deepEqual(signalValue(q2.answer, 1), { Str: "4" });
  assert.deepEqual(signalValue({ kind: "point" }, [1, 2]), { Vec2: [1, 2] });
});

test("a slider steps so the right value is a position a finger can land on", () => {
  assert.equal(sliderStep({ lo: 0, hi: 4, step: null, tolerance: 0.15 }), 0.1);
  assert.equal(sliderStep({ lo: 0, hi: 90, step: null, tolerance: 3 }), 2);
  assert.equal(sliderStep({ lo: 0, hi: 10, step: 1, tolerance: 0 }), 1);
  assert.equal(sliderStep({ lo: 0, hi: 4, step: null, tolerance: 0 }), 0.02);
  assert.equal(sliderStep({ lo: 0, hi: 1, step: null, tolerance: 5 }), 1);
});

test("a right answer within the tolerance is told the exact one", () => {
  const number = { kind: "number", correct: 2, tolerance: 0.25 };
  assert.equal(closeEnough(number, 2.2), "Close enough: the answer is 2.");
  assert.equal(closeEnough(number, 2), null);
  assert.equal(closeEnough({ kind: "point", correct: [1, 2], tolerance: 0.5 }, [1.2, 2]), "Close enough: the answer is (1, 2).");
  assert.equal(closeEnough({ kind: "choice", correct: [1] }, 1), null);
});
