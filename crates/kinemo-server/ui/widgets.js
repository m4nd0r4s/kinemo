// Value widgets. Each calls `onValue(value, live)`: numbers report live values while
// dragged and a final one on release; the others report once.
"use strict";

import { formatNumber, el, toast } from "./state.js";

/** Pixels the pointer must travel before a press on a number becomes a drag. */
export const DRAG_THRESHOLD_PX = 3;

/**
 * A number: drag sideways to change it (Shift ×10, Alt ×0.1), click to type. `range`
 * clamps it; `drag` hooks a drag session (`begin(cancel) → end`, `live(value)`).
 */
export function numberField(initial, onValue, { range = null, drag, integer = false } = {}) {
  const field = el("span", { class: "edit number", title: "drag to change · click to type" }, formatNumber(initial));
  const clamp = (v) => (range ? Math.min(range[1], Math.max(range[0], v)) : v);
  let start = null;
  field.addEventListener("pointerdown", (e) => {
    if (field.querySelector("input")) return;
    e.preventDefault();
    field.setPointerCapture(e.pointerId);
    start = { x: e.clientX, value: initial, dragging: false };
  });
  field.addEventListener("pointermove", (e) => {
    if (!start) return;
    const dx = e.clientX - start.x;
    if (!start.dragging && Math.abs(dx) < DRAG_THRESHOLD_PX) return;
    if (!start.dragging) {
      start.dragging = true;
      const session = start;
      session.end = drag.begin(() => {
        field.textContent = formatNumber(session.value);
        start = null;
      });
    }
    const base = range ? range[1] - range[0] : Math.max(1, Math.abs(start.value));
    const scale = (e.shiftKey ? 10 : e.altKey ? 0.1 : 1) * 0.005 * base;
    const moved = start.value + dx * scale;
    const value = clamp(integer ? Math.round(moved) : Math.round(moved * 1000) / 1000);
    field.textContent = formatNumber(value);
    start.current = value;
    drag.live(value);
  });
  field.addEventListener("pointerup", () => {
    if (!start) return;
    const session = start;
    start = null;
    if (!session.dragging) {
      return typeInto(field, formatNumber(initial), (text) => {
        const value = Number(text);
        if (Number.isFinite(value)) onValue(clamp(value), false);
        else toast(`not a number: ${text}`, "error");
      });
    }
    session.end();
    if (session.current !== undefined) onValue(session.current, false);
  });
  return field;
}

/**
 * A point: its coordinates as two numbers, each dragged or typed on its own. `dragFor(toPoint)`
 * gives the drag hooks of one coordinate, `toPoint` turning it into the whole point.
 */
export function vectorField(initial, onValue, { dragFor } = {}) {
  const value = [...(initial || [0, 0])];
  const withPart = (i) => (v) => {
    const next = [...value];
    next[i] = v;
    return next;
  };
  const part = (i) => numberField(value[i], (v, live) => onValue(withPart(i)(v), live), { drag: dragFor(withPart(i)) });
  return el("span", { class: "edit vector" }, "(", part(0), ", ", part(1), ")");
}

export function textField(initial, onValue) {
  const field = el("span", { class: "edit string", title: "click to edit" }, JSON.stringify(initial ?? ""));
  field.addEventListener("click", () => typeInto(field, initial ?? "", (v) => onValue(v, false)));
  return field;
}

export function boolField(initial, onValue) {
  const box = el("input", { type: "checkbox", class: "edit bool" });
  box.checked = Boolean(initial);
  box.addEventListener("change", () => onValue(box.checked, false));
  return box;
}

/**
 * One of fixed `choices`. With `point` (the value to start from), the select also offers a
 * point and shows two numbers while the value is one (`place(at="top")` or `at=(1, 2)`).
 */
export function choiceField(choices, current, onChoice, { point = null, onPoint = null, numberOptions } = {}) {
  const isPoint = Array.isArray(current);
  const select = el("select", { class: "edit choice" });
  for (const choice of choices) select.append(el("option", { value: choice }, choice));
  if (onPoint) select.append(el("option", { value: "\u0000point" }, "point (x, y)"));
  if (!isPoint && current !== null && current !== undefined && !choices.includes(current)) {
    select.prepend(el("option", { value: current }, `${current} (not a listed value)`));
  }
  select.value = isPoint ? "\u0000point" : current ?? choices[0];
  select.addEventListener("change", () => {
    if (select.value === "\u0000point") onPoint(point || [0, 0], false);
    else onChoice(select.value);
  });
  if (!isPoint) return select;
  return el("span", { class: "edit choice-point" }, select, vectorField(current, onPoint, numberOptions));
}

/** Replaces `field`'s content with a text input; Enter or blur commits, Esc restores. */
export function typeInto(field, text, onCommit) {
  const before = field.textContent;
  const input = el("input", { class: "edit-input", value: text });
  field.replaceChildren(input);
  input.focus();
  input.select();
  let done = false;
  const finish = (commit) => {
    if (done) return;
    done = true;
    field.textContent = before;
    if (commit && input.value !== text) onCommit(input.value);
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") finish(true);
    else if (e.key === "Escape") finish(false);
    e.stopPropagation();
  });
  input.addEventListener("blur", () => finish(true));
}
