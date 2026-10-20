// The lesson player: plays a lesson exported with `kinemo render --format lesson`, stops at each
// question for an answer (HTML controls, not drawn on the canvas) and plays the branch the
// answer takes. Frames come from a worker running the WebAssembly core; audio plays from the
// lesson's files. Embedded in a page, it reports what happens to the host (see `embed.js`).
import { closeEnough, exactAnswer, grade, Route, signalValue, sliderStep } from "./lesson.js";

const PROTOCOL = 1;
/** Frame sizes the player steps down through when frames take too long (16:9). */
const SIZES = [960, 800, 640, 480, 384];
/** A frame should take less than this (30 frames per second, with room for the page). */
const BUDGET_MS = 28;

const $ = (id) => document.getElementById(id);
const view = {
  stage: $("stage"),
  canvas: $("frame"),
  handle: $("handle"),
  play: $("play"),
  restart: $("restart"),
  scrub: $("scrub"),
  time: $("time"),
  panel: $("question"),
  note: $("note"),
  status: $("status"),
};
const context = view.canvas.getContext("2d");
const params = new URLSearchParams(location.search);

const lesson = await (await fetch("lesson.json")).json();
const scene = lesson.ir;
const route = new Route(scene.questions || []);
const duration = scene.duration;
const host = window.parent !== window ? window.parent : null;
let grading = params.get("grading") === "host" ? "host" : "player";

// ---- events for the host page ------------------------------------------------------------

function emit(type, detail = {}) {
  const message = { source: "kinemo", version: PROTOCOL, type, ...detail };
  if (host) host.postMessage(message, "*");
  document.dispatchEvent(new CustomEvent(`kinemo:${type}`, { detail: message }));
}

function describe(question) {
  const out = { id: question.id, kind: question.answer.kind, prompt: question.prompt };
  if (question.answer.kind === "choice") out.options = question.answer.options;
  if (question.answer.kind === "number") Object.assign(out, { lo: question.answer.lo, hi: question.answer.hi });
  return out;
}

// ---- frames ----------------------------------------------------------------------------------

const worker = new Worker(new URL("./render_worker.js", import.meta.url), { type: "module" });
let sizeIndex = 0;
let pending = null; // id of the frame being drawn by the worker
let wanted = 0; // time of the latest frame asked for
let nextId = 1;
let loaded = false;
/** Bumped by every answer the scene uses: a frame drawn before it is out of date. */
let answers = 0;
let pendingAnswers = 0;
const recent = [];

function frameSize() {
  const css = view.canvas.getBoundingClientRect().width || 640;
  const cap = SIZES[sizeIndex];
  const width = Math.max(2, Math.min(cap, Math.round(css * (window.devicePixelRatio || 1))));
  const height = Math.round((width * scene.config.height) / scene.config.width);
  return [width - (width % 2), height - (height % 2)];
}

function requestFrame(t) {
  wanted = t;
  if (!loaded || pending !== null) return;
  const [width, height] = frameSize();
  pending = nextId++;
  pendingAnswers = answers;
  worker.postMessage({ type: "frame", id: pending, t, width, height });
}

function adapt(ms) {
  recent.push(ms);
  if (recent.length < 12) return;
  const slow = [...recent].sort((a, b) => a - b)[Math.floor(recent.length * 0.9)];
  recent.length = 0;
  if (slow > BUDGET_MS && sizeIndex < SIZES.length - 1) sizeIndex++;
}

worker.onmessage = ({ data }) => {
  if (data.type === "ready") return ready(data.duration);
  if (data.type === "error") return fail(data.message);
  if (data.type !== "frame") return;
  pending = null;
  if (view.canvas.width !== data.width || view.canvas.height !== data.height) {
    view.canvas.width = data.width;
    view.canvas.height = data.height;
  }
  context.putImageData(new ImageData(new Uint8ClampedArray(data.pixels), data.width, data.height), 0, 0);
  if (state.playing) adapt(data.ms);
  if (Math.abs(data.t - wanted) > 1e-9 || pendingAnswers !== answers) requestFrame(wanted);
};

function fail(message) {
  pending = null;
  view.status.textContent = `This lesson could not play: ${message}`;
  view.status.hidden = false;
  emit("error", { message });
}

// ---- audio ---------------------------------------------------------------------------------

const clips = (lesson.audio || []).map((clip) => ({ ...clip, element: Object.assign(new Audio(clip.url), { preload: "auto", volume: Math.min(1, clip.gain ?? 1) }) }));

function stopAudio() {
  for (const clip of clips) clip.element.pause();
}

/** Clips that sound between `from` and `to`; on a jump, the ones already under way at `to`. */
function playAudio(from, to, jumped) {
  for (const clip of clips) {
    const length = clip.element.duration || 0;
    const starts = clip.t > from && clip.t <= to;
    const underway = jumped && clip.t <= to && to < clip.t + length;
    if (starts || underway) {
      clip.element.currentTime = Math.max(0, to - clip.t);
      clip.element.play().catch(() => {});
    }
  }
}

// ---- playback ------------------------------------------------------------------------------

const state = { t: 0, playing: false, reached: 0, asking: null, startedAt: 0, startedT: 0, finished: false };

function format(t) {
  const s = Math.max(0, Math.floor(t));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function show(t) {
  state.t = Math.min(Math.max(0, t), duration);
  state.reached = Math.max(state.reached, state.t);
  view.scrub.max = String(duration);
  view.scrub.value = String(state.t);
  view.scrub.style.setProperty("--reached", `${(100 * state.reached) / Math.max(duration, 1e-9)}%`);
  view.time.textContent = `${format(state.t)} / ${format(duration)}`;
  requestFrame(state.t);
}

function play() {
  if (state.asking) return;
  if (state.t >= duration - 1e-6) restart();
  state.playing = true;
  state.finished = false;
  state.startedAt = performance.now();
  state.startedT = state.t;
  view.play.setAttribute("aria-label", "Pause");
  view.play.dataset.state = "playing";
  playAudio(state.t - 1e-6, state.t, true);
  requestAnimationFrame(tick);
}

function pause() {
  state.playing = false;
  view.play.setAttribute("aria-label", "Play");
  view.play.dataset.state = "paused";
  stopAudio();
}

function jump(t) {
  state.startedAt = performance.now();
  state.startedT = t;
  stopAudio();
  show(t);
  playAudio(t - 1e-6, t, true);
}

function restart() {
  close();
  route.playing = null;
  stopAudio();
  show(0);
}

function tick(now) {
  if (!state.playing) return;
  const from = state.t;
  const to = Math.min(duration, state.startedT + (Math.max(0, now - state.startedAt) / 1000));
  const next = route.advance(from, to);
  if (next && next.stop !== undefined) {
    pause();
    show(next.stop);
    ask(next.question);
    return;
  }
  if (next && next.jump !== undefined) {
    jump(next.jump);
    requestAnimationFrame(tick);
    return;
  }
  playAudio(from, to, false);
  show(to);
  if (to >= duration) {
    pause();
    state.finished = true;
    emit("finished");
    return;
  }
  requestAnimationFrame(tick);
}

// ---- questions -------------------------------------------------------------------------------

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) node.setAttribute(k, v);
  }
  node.append(...children.filter((c) => c !== null && c !== undefined));
  return node;
}

function setAnswer(question, value) {
  worker.postMessage({ type: "set", signal: question.signal, value: signalValue(question.answer, value) });
  answers++;
  requestFrame(state.t);
}

/** Scene units ↔ the canvas on the page. */
function toPage([x, y]) {
  const rect = view.canvas.getBoundingClientRect();
  return [(x / scene.config.frame_w + 0.5) * rect.width, (0.5 - y / scene.config.frame_h) * rect.height];
}

function fromPage(clientX, clientY) {
  const rect = view.canvas.getBoundingClientRect();
  return [((clientX - rect.left) / rect.width - 0.5) * scene.config.frame_w, (0.5 - (clientY - rect.top) / rect.height) * scene.config.frame_h];
}

const round = (v) => Math.round(v * 100) / 100;

/** The controls for one kind of answer: `{ nodes, value(), cleanup() }`. */
function controls(question) {
  const answer = question.answer;
  if (answer.kind === "choice") {
    const buttons = answer.options.map((option, index) => el("button", { type: "button", class: "option", onclick: () => submit(question, index) }, option));
    return { nodes: [el("div", { class: "options", role: "group", "aria-labelledby": "prompt" }, ...buttons)] };
  }
  if (answer.kind === "number" && answer.lo !== null && answer.hi !== null) {
    const step = sliderStep(answer);
    const decimals = Math.max(0, -Math.floor(Math.log10(step) + 1e-9));
    const output = el("output", { for: "answer-slider" });
    const slider = el("input", { id: "answer-slider", type: "range", min: answer.lo, max: answer.hi, step, value: question.default ?? answer.lo, "aria-labelledby": "prompt" });
    const update = (send) => {
      output.textContent = Number(slider.value).toFixed(decimals);
      if (send) setAnswer(question, Number(slider.value));
    };
    // Buttons for the last step: a finger is wider than one step of the slider.
    const nudge = (direction) => {
      const next = Math.min(answer.hi, Math.max(answer.lo, Number(slider.value) + direction * step));
      slider.value = String(Math.round(next / step) * step);
      update(true);
    };
    slider.addEventListener("input", () => update(true));
    update(false);
    const less = el("button", { type: "button", class: "nudge", "aria-label": `Decrease by ${step}`, onclick: () => nudge(-1) }, "−");
    const more = el("button", { type: "button", class: "nudge", "aria-label": `Increase by ${step}`, onclick: () => nudge(1) }, "+");
    return { nodes: [el("div", { class: "slider" }, less, slider, more, output)], value: () => Number(slider.value) };
  }
  if (answer.kind === "number") {
    const field = el("input", { type: "number", step: "any", inputmode: "decimal", "aria-labelledby": "prompt" });
    return { nodes: [field], value: () => (field.value === "" ? null : Number(field.value)) };
  }
  if (answer.kind === "point") {
    let point = Array.isArray(question.default) ? [...question.default] : [0, 0];
    const fields = ["x", "y"].map((axis, i) => {
      const field = el("input", { type: "number", step: "0.1", value: round(point[i]), "aria-label": axis });
      field.addEventListener("input", () => move([i === 0 ? Number(field.value) : point[0], i === 1 ? Number(field.value) : point[1]], false));
      return field;
    });
    const place = () => {
      const [left, top] = toPage(point);
      view.handle.style.left = `${left}px`;
      view.handle.style.top = `${top}px`;
    };
    const move = (p, updateFields = true) => {
      point = p.map(round);
      place();
      if (updateFields) fields.forEach((f, i) => (f.value = String(point[i])));
      setAnswer(question, point);
    };
    const drag = (e) => move(fromPage(e.clientX, e.clientY));
    const down = (e) => {
      e.preventDefault();
      view.stage.setPointerCapture(e.pointerId);
      drag(e);
      view.stage.addEventListener("pointermove", drag);
      view.stage.addEventListener("pointerup", () => view.stage.removeEventListener("pointermove", drag), { once: true });
    };
    const keys = (e) => {
      const step = e.shiftKey ? 1 : 0.1;
      const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] }[e.key];
      if (!d) return;
      e.preventDefault();
      move([point[0] + d[0], point[1] + d[1]]);
    };
    view.stage.addEventListener("pointerdown", down);
    view.handle.addEventListener("keydown", keys);
    view.handle.hidden = false;
    view.stage.classList.add("dragging");
    place();
    return {
      nodes: [el("div", { class: "point" }, el("span", {}, "Drag the point, or type it:"), ...fields)],
      value: () => point,
      cleanup: () => {
        view.stage.removeEventListener("pointerdown", down);
        view.handle.removeEventListener("keydown", keys);
        view.handle.hidden = true;
        view.stage.classList.remove("dragging");
      },
    };
  }
  const field = el("input", { type: "text", autocomplete: "off", spellcheck: "false", "aria-labelledby": "prompt" });
  return { nodes: [field], value: () => field.value };
}

function close() {
  if (state.asking && state.asking.cleanup) state.asking.cleanup();
  state.asking = null;
  view.panel.hidden = true;
  view.panel.replaceChildren();
}

function ask(question, feedback = "") {
  close();
  const parts = controls(question);
  const check = parts.value
    ? el("button", { type: "button", class: "check", onclick: () => {
        const value = parts.value();
        if (value !== null && value !== undefined && !(typeof value === "number" && Number.isNaN(value))) submit(question, value);
      } }, "Check")
    : null;
  const nodes = [el("p", { id: "prompt", class: "prompt" }, question.prompt), ...parts.nodes, check, el("p", { class: "feedback", "aria-live": "polite" }, feedback)];
  view.panel.append(...nodes.filter(Boolean));
  view.panel.hidden = false;
  state.asking = { question, cleanup: parts.cleanup };
  const first = view.panel.querySelector("button, input");
  if (first) first.focus({ preventScroll: true });
  emit("question", describe(question));
}

/** Where playback goes once `question` is known to be right or wrong. */
let noteTimer = 0;

/** A short line under the controls, gone after a few seconds. */
function note(text) {
  view.note.textContent = text;
  view.note.hidden = false;
  clearTimeout(noteTimer);
  noteTimer = setTimeout(() => (view.note.hidden = true), 4000);
}

function proceed(question, correct, value) {
  // Right, but not exactly: say the exact answer, and the scene takes it before going on.
  const close = correct && value !== undefined ? closeEnough(question.answer, value) : null;
  if (close) {
    setAnswer(question, exactAnswer(question.answer));
    note(close);
  }
  const { to } = route.outcome(question, correct);
  const branch = question.branches.find((b) => b.on === (correct ? "correct" : "wrong"));
  emit("result", { id: question.id, correct, by: grading });
  if (branch) emit("branch", { id: question.id, on: branch.on, then: branch.then });
  if (to === null) {
    const feedback = view.panel.querySelector(".feedback");
    if (feedback) feedback.textContent = "Not quite. Try again.";
    return;
  }
  close();
  show(to);
  play();
}

function submit(question, value) {
  emit("answer", { id: question.id, value });
  if (grading === "host") {
    state.asking.awaiting = value;
    const feedback = view.panel.querySelector(".feedback");
    if (feedback) feedback.textContent = "Checking…";
    return;
  }
  proceed(question, grade(question.answer, value), value);
}

// ---- commands from the host page --------------------------------------------------------------

function command(message) {
  switch (message.type) {
    case "play":
      return play();
    case "pause":
      return pause();
    case "restart":
      restart();
      return play();
    case "grading":
      grading = message.by === "host" ? "host" : "player";
      return;
    case "result": {
      const asking = state.asking;
      if (asking && asking.question.id === message.id) proceed(asking.question, Boolean(message.correct), asking.awaiting);
      return;
    }
    case "goto": {
      const question = route.questions.find((q) => q.id === message.id);
      if (!question) return;
      pause();
      route.playing = null;
      show(question.t);
      ask(question);
      return;
    }
  }
}

window.addEventListener("message", (event) => {
  const message = event.data;
  if (event.source !== host || !message || message.target !== "kinemo") return;
  command(message);
});

// ---- page --------------------------------------------------------------------------------------

function ready() {
  loaded = true;
  view.status.hidden = true;
  show(0);
  emit("loaded", { duration, questions: route.questions.map(describe) });
  if (params.get("autoplay") === "1") play();
}

view.play.addEventListener("click", () => (state.playing ? pause() : play()));
view.restart.addEventListener("click", () => {
  restart();
  play();
});
view.scrub.addEventListener("input", () => {
  const t = Math.min(Number(view.scrub.value), state.reached);
  close();
  route.playing = null;
  if (state.playing) jump(t);
  else show(t);
});
document.addEventListener("keydown", (e) => {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLButtonElement) return;
  if (e.code === "Space") {
    e.preventDefault();
    state.playing ? pause() : play();
  }
});
new ResizeObserver(() => requestFrame(state.t)).observe(view.canvas);

document.title = lesson.title || "Lesson";
worker.postMessage({ type: "load", ir: JSON.stringify(scene), baked: JSON.stringify(lesson.baked || {}), images: lesson.images || [] });
