// The Watch list (Code tab): props pinned from the inspector (☆), shown at the playhead while
// playing, stepping and scrubbing, flashing when they change; numbers get a sparkline over the
// whole scene. Watches are remembered per browser by object label, so they survive rebuilds.
"use strict";

import { requestId, send } from "./connection.js";
import { el, emit, formatValue, frameTime, listen, state } from "./state.js";

const KEY = "kinemo-dev-watches";
const PLAYING_INTERVAL_MS = 250;
const SPARK_SAMPLES = 120;

/** [{ label, prop }] */
let watches = load();
let current = []; // value per watch at the playhead
let spark = []; // sampled values per watch over the scene
let pending = null; // id of the sample request for the playhead
let sparkRequest = null;
let lastAt = 0;

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(saved) ? saved : [];
  } catch {
    return [];
  }
}

function save() {
  try {
    localStorage.setItem(KEY, JSON.stringify(watches));
  } catch {
    // private window: watches last for this page only
  }
}

function objectId(label) {
  const found = Object.entries((state.meta && state.meta.objects) || {}).find(([, info]) => info.label === label);
  return found ? Number(found[0]) : null;
}

export function isWatched(label, prop) {
  return watches.some((w) => w.label === label && w.prop === prop);
}

export function toggleWatch(label, prop) {
  watches = isWatched(label, prop) ? watches.filter((w) => !(w.label === label && w.prop === prop)) : [...watches, { label, prop }];
  save();
  refreshAll();
  emit("watches");
}

function items() {
  return watches.map((w) => ({ object: objectId(w.label) ?? 4294967295, prop: w.prop }));
}

function requestNow() {
  if (!watches.length || !state.meta) return;
  pending = requestId();
  send({ type: "sample", id: pending, items: items(), times: [frameTime()] });
  lastAt = performance.now();
}

function requestSparklines() {
  if (!watches.length || !state.meta) return;
  const d = state.meta.duration;
  const times = Array.from({ length: SPARK_SAMPLES }, (_, i) => (d * i) / (SPARK_SAMPLES - 1));
  sparkRequest = requestId();
  send({ type: "sample", id: sparkRequest, items: items(), times });
}

function refreshAll() {
  current = [];
  spark = [];
  render();
  requestNow();
  requestSparklines();
}

function number(v) {
  if (!v || typeof v !== "object") return null;
  if ("Float" in v) return v.Float;
  if ("Int" in v) return v.Int;
  return null;
}

function sparkline(values) {
  const numbers = (values || []).map(number);
  if (numbers.length < 2 || numbers.some((n) => n === null)) return null;
  const lo = Math.min(...numbers);
  const hi = Math.max(...numbers);
  const span = hi - lo || 1;
  const points = numbers.map((n, i) => `${((i / (numbers.length - 1)) * 100).toFixed(1)},${(16 - ((n - lo) / span) * 14 - 1).toFixed(1)}`).join(" ");
  const x = state.meta ? (frameTime() / Math.max(state.meta.duration, 1e-9)) * 100 : 0;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 100 16");
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("class", "spark");
  svg.innerHTML = `<polyline points="${points}" fill="none" stroke="currentColor" stroke-width="1" vector-effect="non-scaling-stroke"/><line x1="${x}" x2="${x}" y1="0" y2="16" class="spark-head"/>`;
  return svg;
}

function render(changed = new Set()) {
  const box = document.getElementById("code-watches");
  if (!box) return;
  if (!watches.length) {
    box.replaceChildren(el("div", { class: "hint" }, "Pin a prop with ☆ in the inspector to watch it here."));
    return;
  }
  box.replaceChildren(
    el("div", { class: "bp-head" }, el("span", { class: "section-title" }, `Watch (${watches.length})`)),
    ...watches.map((w, i) =>
      el(
        "div",
        { class: `watch-row${changed.has(i) ? " changed" : ""}${objectId(w.label) === null ? " orphan" : ""}` },
        el("span", { class: "watch-name", title: `${w.label}.${w.prop}` }, `${w.label}.${w.prop}`),
        el("span", { class: "watch-value" }, current[i] === undefined ? "…" : formatValue(current[i])),
        sparkline(spark[i]),
        el("button", { class: "ghost bp-remove", title: "Stop watching", onclick: () => toggleWatch(w.label, w.prop) }, "✕")
      )
    )
  );
}

function onSample(msg) {
  if (msg.id === sparkRequest) {
    spark = msg.values.map((row) => row);
    render();
    return;
  }
  if (msg.id !== pending) return;
  pending = null;
  const next = msg.values.map((row) => row[0]);
  const changed = new Set(next.map((v, i) => (JSON.stringify(v) !== JSON.stringify(current[i]) && current[i] !== undefined ? i : -1)).filter((i) => i >= 0));
  current = next;
  render(changed);
}

export function installWatch() {
  listen("message:sample", onSample);
  listen("scene", refreshAll);
  listen("frame", () => {
    if (!watches.length || pending !== null) return;
    if (state.playing && performance.now() - lastAt < PLAYING_INTERVAL_MS) return;
    requestNow();
  });
  render();
}
