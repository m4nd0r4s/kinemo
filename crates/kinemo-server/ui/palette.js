// Editor mode, first step: a palette that adds objects to the scene. Pick a tool, click the
// frame: the preview writes the object (placed where you clicked) and its entrance at the
// playhead into the scene function. Esc puts the tool down.
"use strict";

import { sendEdit } from "./editing.js";
import { el, listen, state, toast, view } from "./state.js";

/** [kind, glyph, label]: what `kinemo.editing.statements.OBJECT_KINDS` knows how to write. */
const TOOLS = [
  ["text", "T", "Text"],
  ["math", "∑", "Math"],
  ["circle", "○", "Circle"],
  ["square", "□", "Square"],
  ["arrow", "→", "Arrow"],
  ["axes", "⊥", "Axes"],
];

let armed = null;
const buttons = new Map();

export function armedTool() {
  return armed;
}

function arm(kind) {
  armed = armed === kind ? null : kind;
  for (const [k, button] of buttons) button.classList.toggle("armed", k === armed);
  view.frameWrap.classList.toggle("placing", armed !== null);
}

/** The scene line the new statements go after: the last statement of the scene function that
 * started at or before the playhead (null: the start of the scene, so at its end of setup). */
export function afterLine() {
  const fn = state.meta && state.meta.scene_function;
  if (!fn) return null;
  let best = null;
  for (const statement of state.meta.statements || []) {
    if (statement.file !== fn.file) continue;
    const started = statement.runs.filter((run) => run.start <= state.t + 1e-6);
    if (!started.length) continue;
    const start = Math.max(...started.map((run) => run.start));
    if (!best || start > best.start || (start === best.start && statement.line > best.line)) best = { start, line: statement.line };
  }
  return best ? best.line : null;
}

/** A click on the frame with a tool armed: add the object there. `point` is in canvas pixels. */
export function placeAt(point) {
  const kind = armed;
  arm(null);
  const render = state.meta && state.meta.render;
  if (!render || !state.meta.scene_function) return toast("this scene can't be edited from the preview", "error");
  const canvas = view.frameCanvas;
  const x = (point.x / canvas.width - 0.5) * render.frame_w;
  const y = (0.5 - point.y / canvas.height) * render.frame_h;
  sendEdit([{ op: "add", kind, at: [x, y], after: afterLine() }], false);
}

export function installPalette() {
  const bar = el("div", { class: "palette", role: "toolbar", title: "add an object: pick one, then click the frame" });
  for (const [kind, glyph, label] of TOOLS) {
    const button = el("button", { class: "palette-tool", title: `${label}: click the frame to place it`, onclick: () => arm(kind) }, glyph);
    buttons.set(kind, button);
    bar.append(button);
  }
  // In the stage's corner, outside the frame: it never covers the scene.
  view.frameWrap.parentElement.append(bar);
  listen("escape", () => armed && arm(null));
}

/** `[verb, label]`: what `kinemo.editing.statements.ANIMATION_VERBS` writes. */
export const ANIMATIONS = [
  ["fade_in", "Fade in"],
  ["draw", "Draw"],
  ["write", "Write"],
  ["grow", "Grow"],
  ["indicate", "Indicate"],
  ["fade_out", "Fade out"],
  ["shrink", "Shrink"],
];

/** Buttons that add `s.play(k.<verb>(name))` for the selected object at the playhead. */
export function animationButtons(name) {
  return el(
    "div",
    { class: "animate-buttons" },
    ...ANIMATIONS.map(([verb, label]) =>
      el("button", { class: "ghost small", title: `s.play(k.${verb}(${name})) at the playhead`, onclick: () => sendEdit([{ op: "animate", object: name, verb, after: afterLine() }], false) }, label)
    )
  );
}
