// Questions of an interactive lesson (`s.ask`) in the preview: playback stops at each one and a
// panel over the frame takes the answer (a slider or a dragged point moves the scene live);
// then playback goes on along the branch the answer takes. Each branch is a band on the
// timeline: clicking one plays it.
"use strict";

import { send } from "./connection.js";
import { Route, signalValue, sliderStep } from "./lesson.js";
import { addStopCheck, play, setTime } from "./playback.js";
import { el, formatNumber, listen, state, view } from "./state.js";

let route = new Route([]);
let routeKey = "";
let asking = null; // { question, panel }

function setAnswer(question, value) {
  send({ type: "answer", signal: question.signal, value: signalValue(question.answer, value) });
}

function close() {
  if (asking) asking.panel.remove();
  asking = null;
  view.frameCanvas.classList.remove("answering");
}

function submit(question, value) {
  const { to } = route.answered(question, value);
  const feedback = asking && asking.panel.querySelector(".question-feedback");
  if (to === null) {
    if (feedback) feedback.textContent = "Not quite. Try again.";
    return;
  }
  close();
  setTime(to, true);
  play();
}

/** The controls of one answer kind; `value()` reads the current answer. */
function controls(question) {
  const answer = question.answer;
  if (answer.kind === "choice") {
    const buttons = answer.options.map((option, index) => el("button", { class: "question-option", onclick: () => submit(question, index) }, option));
    return { nodes: [el("div", { class: "question-options" }, ...buttons)], value: null };
  }
  if (answer.kind === "number" && answer.lo !== null && answer.hi !== null) {
    const step = sliderStep(answer);
    const shown = el("span", { class: "question-value" }, "");
    const slider = el("input", { type: "range", min: answer.lo, max: answer.hi, step, value: question.default ?? answer.lo });
    const show = () => (shown.textContent = formatNumber(Number(slider.value)));
    slider.addEventListener("input", () => {
      show();
      setAnswer(question, Number(slider.value));
    });
    return { nodes: [el("div", { class: "question-slider" }, slider, shown)], value: () => Number(slider.value), init: show };
  }
  if (answer.kind === "number") {
    const field = el("input", { type: "number", step: "any", class: "question-field" });
    return { nodes: [field], value: () => (field.value === "" ? null : Number(field.value)) };
  }
  if (answer.kind === "point") {
    let point = null;
    const shown = el("span", { class: "question-value" }, "drag on the frame");
    view.frameCanvas.classList.add("answering");
    const render = state.meta.render;
    const move = (e) => {
      const rect = view.frameCanvas.getBoundingClientRect();
      point = [((e.clientX - rect.left) / rect.width - 0.5) * render.frame_w, (0.5 - (e.clientY - rect.top) / rect.height) * render.frame_h];
      shown.textContent = `(${point[0].toFixed(2)}, ${point[1].toFixed(2)})`;
      setAnswer(question, point);
    };
    const down = (e) => {
      if (!asking) return;
      e.stopPropagation();
      move(e);
      const up = () => window.removeEventListener("pointermove", move);
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up, { once: true });
    };
    view.frameCanvas.addEventListener("pointerdown", down, { capture: true });
    return { nodes: [shown], value: () => point, cleanup: () => view.frameCanvas.removeEventListener("pointerdown", down, { capture: true }) };
  }
  const field = el("input", { type: "text", class: "question-field", spellcheck: "false" });
  return { nodes: [field], value: () => field.value };
}

function ask(question) {
  close();
  const parts = controls(question);
  const check = parts.value
    ? el("button", { class: "question-check", onclick: () => {
        const value = parts.value();
        if (value !== null && value !== undefined) submit(question, value);
      } }, "Check")
    : null;
  const panel = el(
    "div",
    { class: "question-panel", role: "dialog", "aria-label": "Question" },
    el("div", { class: "question-prompt" }, question.prompt),
    ...parts.nodes,
    check,
    el("div", { class: "question-feedback", "aria-live": "polite" }),
  );
  view.stage.append(panel);
  asking = { question, panel };
  const removal = panel.remove.bind(panel);
  panel.remove = () => {
    if (parts.cleanup) parts.cleanup();
    removal();
  };
  if (parts.init) parts.init();
  const first = panel.querySelector("button, input");
  if (first) first.focus();
}

/** Branch bands under the ruler: where each answer's stretch of the timeline lies. */
function renderBands() {
  const total = Math.max(state.meta.duration, 1e-9);
  const pct = (t) => `${(100 * t) / total}%`;
  const bands = [];
  for (const question of route.questions) {
    bands.push(el("div", { class: "question-mark", style: `left:${pct(question.t)}`, title: `${question.id}: ${question.prompt}` }, "?"));
    for (const branch of question.branches) {
      const label = `${question.id} ${branch.on === "correct" ? "✓" : "✗"}`;
      bands.push(
        el(
          "div",
          {
            class: `branch-band ${branch.on}`,
            style: `left:${pct(branch.t0)};width:${pct(Math.max(branch.t1 - branch.t0, 0))}`,
            title: `${question.id}, ${branch.on} answer: ${branch.t0.toFixed(2)}–${branch.t1.toFixed(2)} s (click to play)`,
            onclick: (e) => {
              e.stopPropagation();
              close();
              setTime(route.enter(question, branch), true);
              play();
            },
          },
          label,
        ),
      );
    }
  }
  view.branches.replaceChildren(...bands);
}

export function installQuestions() {
  addStopCheck((from, to) => {
    const next = route.advance(from, to);
    if (next && next.stop !== undefined) queueMicrotask(() => ask(next.question));
    return next;
  });
  listen("scene", () => {
    const questions = state.meta.questions || [];
    // An answer republishes the scene with the same questions: keep the branch being played.
    const key = JSON.stringify(questions);
    if (key !== routeKey) route = new Route(questions);
    routeKey = key;
    if (asking) {
      const same = questions.find((q) => q.id === asking.question.id);
      same ? (asking.question = same) : close();
    }
    renderBands();
  });
  listen("time", (t) => {
    if (asking && Math.abs(t - asking.question.t) > 1e-6) close();
  });
  listen("escape", close);
}
