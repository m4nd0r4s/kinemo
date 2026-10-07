// Source edits: find the call argument behind a value (via `meta.sources`, keyed by span)
// and offer an editor for it: the whole literal, or each number inside a computed one.
// Typing commits; dragging a number sends live edits (the scene rebuilds from the edited
// text) and commits on release; Esc cancels a drag.
"use strict";

import { colorField } from "./colorpicker.js";
import { requestId, send } from "./connection.js";
import { colorHex, el, formatNumber, listen, spanKey, state, toast } from "./state.js";
import { boolField, choiceField, numberField, textField, vectorField } from "./widgets.js";

/** Live edits sent no more often than this while dragging. */
const LIVE_INTERVAL_MS = 50;
export { DRAG_THRESHOLD_PX } from "./widgets.js";

const liveResults = new Map(); // edit id → callback once that live build is published
let cancelDrag = null;

export function siteByKey(key) {
  const site = key && state.meta && state.meta.sources[key];
  return site ? { key, site } : null;
}

export function siteFor(span) {
  return siteByKey(spanKey(span));
}

export function argumentFor(site, target) {
  return site.arguments.find((a) => a.param === target) || null;
}

/**
 * What edits prop `name` of an inspected object: `{key, site, target, argument, insertable}`,
 * or null when no call of the scene sets it (a verb's opacity, a container's layout).
 */
export function propEditor(object, name) {
  const source = object.prop_sources && object.prop_sources[name];
  if (!source) return null;
  const span = source.kind === "default" ? object.span : source.span;
  const found = siteFor(span);
  if (!found) return null;
  const { key, site } = found;
  let target = name;
  let argument = argumentFor(site, name);
  if (!argument && (name === "fill" || name === "stroke") && argumentFor(site, "color")) {
    target = "color";
    argument = argumentFor(site, "color");
  }
  // Only a prop the code never set can be added; one set through another argument (a
  // square's `w` from `side`) is edited through that argument instead.
  const insertable = !argument && source.kind === "default" && (site.accepts || []).includes(name);
  if (!argument && !insertable) return null;
  return { key, site, target, argument, insertable };
}

export function sendEdit(changes, live, onPublished) {
  const id = requestId();
  if (live && onPublished) liveResults.set(id, onPublished);
  send({ type: "edit", id, live, changes });
  return id;
}

/** Sent when a drag is cancelled: rebuilds from the file on disk. */
export function revertLive() {
  send({ type: "edit", id: requestId(), live: false, changes: [] });
}

function onEditResult(msg) {
  const callback = liveResults.get(msg.id);
  liveResults.delete(msg.id);
  if (!msg.ok) toast(msg.message, "error");
  else if (callback) callback();
}

/** Throttles live edits; `flush` sends the last pending one at once. */
export function liveSender(send) {
  let last = 0;
  let pending = null;
  let timer = null;
  const fire = () => {
    timer = null;
    last = performance.now();
    if (pending) send(...pending);
    pending = null;
  };
  return {
    push(...args) {
      pending = args;
      const wait = LIVE_INTERVAL_MS - (performance.now() - last);
      if (wait <= 0) fire();
      else if (!timer) timer = setTimeout(fire, wait);
    },
    cancel() {
      clearTimeout(timer);
      timer = null;
      pending = null;
    },
  };
}

/** Starts a drag session; Esc calls `onCancel`. Returns a function that ends it. */
export function beginDrag(onCancel) {
  state.editing = true;
  cancelDrag = onCancel;
  return () => {
    state.editing = false;
    cancelDrag = null;
  };
}

// ---- value editors ------------------------------------------------------------------

const LITERAL_TYPES = { number: "number", string: "string", bool: "bool", vector: "vector", color: "color", ease: "ease" };
const VALUE_TYPES = { Float: "number", Int: "number", Str: "string", Bool: "bool", Color: "color", Vec2: "vector" };

/** The kind of value the parameter takes: declared by the API, else read from the literal. */
function typeOf(editor, current) {
  const declared = editor.site.types && editor.site.types[editor.target];
  const written = editor.argument && LITERAL_TYPES[editor.argument.kind];
  // What the code wrote wins over a declared type it does not fit (a range tuple where the
  // annotation reads as a number); a string stays a choice or a color when declared so.
  const fits = !declared || !written || written === declared.type || (written === "string" && ["choice", "color"].includes(declared.type)) || (written === "vector" && declared.vector);
  if (declared && fits) return declared;
  if (editor.argument) return written ? { type: written } : null;
  const tag = current && typeof current === "object" ? Object.keys(current)[0] : null;
  return VALUE_TYPES[tag] ? { type: VALUE_TYPES[tag] } : null;
}

function currentLiteral(current) {
  const [tag, x] = Object.entries(current || {})[0] || [];
  if (tag === "Color") return colorHex(x);
  return tag ? x : null;
}

const pythonVector = (v) => `(${v.map(formatNumber).join(", ")})`;

/** Live edits while a number is dragged; Esc reverts to the file on disk. */
function dragHooks(sendLive) {
  const sender = liveSender(sendLive);
  return {
    begin(onCancel) {
      const end = beginDrag(() => {
        sender.cancel();
        end();
        onCancel();
        revertLive();
      });
      return () => {
        sender.cancel();
        end();
      };
    },
    live: (value) => sender.push(value),
  };
}

/** Two numbers whose values become `changes(point)`: several arguments edited at once
 * (an object's position is its `x` and `y`, or `place(at=...)`). */
export function pointEditor(initial, changes) {
  return vectorField(initial, (v, live) => sendEdit(changes(v), live), {
    dragFor: (toPoint) => dragHooks((v) => sendEdit(changes(toPoint(v)), true)),
  });
}

/**
 * Editor for the argument behind `editor` (see `propEditor`), with a widget fit for the
 * parameter's type. `point` is where a choice-or-point parameter (`at=`) starts as a point.
 */
export function valueEditor(editor, current, { point = null, fallback = null } = {}) {
  const { argument, site } = editor;
  if (argument && !argument.kind) return expressionEditor(editor);
  const type = typeOf(editor, current);
  if (!type) return null;
  const literal = argument ? argument.value : fallback ?? currentLiteral(current);
  const write = (text, live) => sendEdit([{ site: editor.key, target: editor.target, value: text }], live);
  const range = type.range || null;
  const dragFor = (toValue) => dragHooks((v) => write(pythonVector(toValue(v)), true));
  switch (type.type) {
    case "number":
      return numberField(literal ?? 0, (v, live) => write(formatNumber(v), live), { range, drag: dragHooks((v) => write(formatNumber(v), true)) });
    case "vector":
      return vectorField(literal, (v, live) => write(pythonVector(v), live), { dragFor });
    case "string":
      return textField(literal, (v) => write(JSON.stringify(v), false));
    case "bool":
      return boolField(literal, (v) => write(v ? "True" : "False", false));
    case "choice":
      return choiceField(type.choices, literal, (c) => write(JSON.stringify(c), false), {
        point: type.vector ? point : null,
        onPoint: type.vector ? (v, live) => write(pythonVector(v), live) : null,
        numberOptions: { dragFor },
      });
    case "ease": {
      const eases = (state.meta.palette && state.meta.palette.eases) || [];
      if (!site.alias) return el("code", { class: "computed", title: "import kinemo as k to pick an easing" }, argument ? argument.text : "—");
      const name = typeof literal === "string" ? literal.replace(/^ease\./, "") : "smooth";
      return choiceField(eases, name, (n) => write(`${site.alias}.ease.${n}`, false));
    }
    case "color": {
      const hex = argument ? argument.hex || (argument.kind === "string" ? argument.value : null) : currentLiteral(current);
      return colorField({ hex, label: argument ? argument.text : null, alias: site.alias, onCode: (code) => write(code, false) });
    }
    default:
      return null;
  }
}

/**
 * A computed argument: its code, read-only, with each number written inside it editable in
 * place (`title.x + 1.2`, `lambda x: 3 * x - 0.75 * x**2`). An integer stays an integer.
 */
export function expressionEditor(editor) {
  const { argument } = editor;
  const numbers = (editor.target && argument.numbers) || [];
  if (!numbers.length) return el("code", { class: "computed", title: "computed in the code: edit it there" }, argument.text);
  const parts = [];
  let at = 0;
  numbers.forEach((number, index) => {
    parts.push(argument.text.slice(at, number.offset));
    const integer = /^[+-]?\d+$/.test(number.text);
    const text = (v) => (integer ? String(Math.round(v)) : formatNumber(v));
    const write = (v, live) => sendEdit([{ site: editor.key, target: editor.target, number: index, value: text(v) }], live);
    parts.push(numberField(number.value, write, { integer, drag: dragHooks((v) => write(v, true)) }));
    at = number.offset + number.text.length;
  });
  parts.push(argument.text.slice(at));
  return el("code", { class: "computed expression", title: "computed in the code: drag or click a number to change it" }, ...parts);
}

/** "×N" marker for a call that runs several times (a loop): editing changes every run. */
export function runsBadge(site) {
  if (!site || site.runs <= 1) return null;
  return el("span", { class: "runs", title: `this line runs ${site.runs} times: an edit changes every run` }, `×${site.runs}`);
}

export function installEditing() {
  listen("message:edit_result", onEditResult);
  listen("escape", () => cancelDrag && cancelDrag());
}
