// Shared state, DOM references, a tiny event bus and formatting helpers.
"use strict";

const $ = (id) => document.getElementById(id);

export const view = {
  frameCanvas: $("frame"),
  highlightCanvas: $("highlight"),
  frameWrap: $("frame-wrap"),
  stage: $("stage"),
  sceneTitle: $("scene-title"),
  buildStatus: $("build-status"),
  connection: $("connection"),
  errorOverlay: $("error-overlay"),
  errorBody: $("error-body"),
  toast: $("toast"),
  outliner: $("outliner-tree"),
  outlinerFilter: $("outliner-filter"),
  inspectorEmpty: $("inspector-empty"),
  inspectorObject: $("inspector-object"),
  problems: $("problems"),
  play: $("play"),
  speed: $("speed"),
  time: $("time"),
  timeTotal: $("time-total"),
  frameNumber: $("frame-number"),
  loop: $("loop"),
  groupRepeats: $("group-repeats"),
  zoomIn: $("zoom-in"),
  zoomOut: $("zoom-out"),
  zoomFit: $("zoom-fit"),
  timeline: $("timeline"),
  timelineContent: $("timeline-content"),
  ruler: $("ruler"),
  marks: $("marks"),
  lanes: $("lanes"),
  playhead: $("playhead"),
};

export const state = {
  meta: null,
  version: 0,
  t: 0,
  playing: false,
  speed: 1,
  selectedIds: [], // objects whose boxes ride along with frames; the first is inspected
  selectedBar: null, // index into meta.timeline of the bar shown in the inspector
  boxes: new Map(), // object id → [x0, y0, x1, y1] in frame pixels, from the last frame
  overlay: null,
  pickedObject: null,
  editing: false, // a value or an object is being dragged: keep the inspector still
  zoom: 1,
  expandedGroups: new Set(),
};

// ---- event bus: modules talk through named events instead of importing each other ---

const listeners = new Map();

export function listen(name, fn) {
  if (!listeners.has(name)) listeners.set(name, []);
  listeners.get(name).push(fn);
}

export function emit(name, ...args) {
  for (const fn of listeners.get(name) || []) fn(...args);
}

// ---- timing ---------------------------------------------------------------------------

export const fps = () => (state.meta ? state.meta.render.fps : 30);
export const duration = () => (state.meta ? state.meta.duration : 0);
export const frameCount = () => (state.meta ? state.meta.render.frame_count : 1);
export const lastFrameTime = () => Math.max(0, (frameCount() - 1) / fps());
export const frameIndex = (t) => Math.min(frameCount() - 1, Math.max(0, Math.round(t * fps())));
export const frameTime = () => frameIndex(state.t) / fps();

// ---- DOM and formatting -----------------------------------------------------------

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "style") node.style.cssText = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) node.setAttribute(k, v);
  }
  for (const c of children) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

export function basename(path) {
  return (path || "").split(/[\\/]/).pop();
}

export function editorUrl(file, line) {
  return `vscode://file/${encodeURI(file)}:${line || 1}`;
}

export function sourceLink(span, text) {
  if (!span || !span.file) return el("span", {}, text || "—");
  const label = text || `${basename(span.file)}:${span.line}`;
  return el("a", { href: editorUrl(span.file, span.line), title: `${span.file}:${span.line}` }, label);
}

/** Key of a span, as `kinemo.editing.scene_index.span_key` computes it. */
export function spanKey(span) {
  if (!span || !span.file) return null;
  return `${span.file}:${span.line}:${span.col || 0}:${span.end_line || 0}:${span.end_col || 0}`;
}

export function colorHex(c) {
  const h = (x) => Math.round(Math.max(0, Math.min(1, x)) * 255).toString(16).padStart(2, "0");
  return `#${h(c[0])}${h(c[1])}${h(c[2])}${c[3] < 1 ? h(c[3]) : ""}`;
}

export function objectName(id) {
  const info = state.meta && state.meta.objects[String(id)];
  return info ? info.label : `#${id}`;
}

export function formatNumber(x) {
  if (Number.isInteger(x)) return String(x);
  return String(Math.round(x * 1000) / 1000);
}

export function formatValue(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v === "None" ? "none" : v;
  const [tag, x] = Object.entries(v)[0] || [];
  switch (tag) {
    case "Float": return formatNumber(x);
    case "Int": return String(x);
    case "Bool": return String(x);
    case "Str": return JSON.stringify(x);
    case "Vec2": return `(${x[0].toFixed(2)}, ${x[1].toFixed(2)})`;
    case "Color": {
      const hex = colorHex(x);
      return el("span", {}, el("span", { class: "swatch", style: `background:${hex}` }), hex);
    }
    case "Object": return objectName(x);
    case "List": {
      const text = (item) => {
        const f = formatValue(item);
        return f instanceof Node ? f.textContent : f;
      };
      return x.length <= 4 ? `[${x.map(text).join(", ")}]` : `[${x.length} items]`;
    }
    default: return JSON.stringify(v);
  }
}

/** Whether object `id` is in the scene at time `t`, from its presence toggles. */
export function presentAt(id, t) {
  const info = state.meta && state.meta.objects[String(id)];
  if (!info) return false;
  let present = false;
  for (const [at, value] of info.presence || []) {
    if (at <= t + 1e-9) present = value;
  }
  return present;
}

let toastTimer = null;
export function toast(message, kind = "info") {
  view.toast.textContent = message;
  view.toast.className = `toast ${kind}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => view.toast.classList.add("hidden"), kind === "error" ? 6000 : 2500);
}
