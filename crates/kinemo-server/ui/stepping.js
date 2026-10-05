// Stepping through statements, debugger style: next / previous statement move the playhead to
// the next / previous run start of any statement (F10 / Shift+F10, or the buttons of the Code
// tab); "run to line" plays until the next run of the line picked in the code view (F8).
"use strict";

import { pause, play, setTime } from "./playback.js";
import { listen, state, toast } from "./state.js";

/** Every run start of every statement, sorted. */
function starts() {
  const out = new Set();
  for (const entry of (state.meta && state.meta.statements) || []) for (const run of entry.runs) out.add(run.start);
  return [...out].sort((a, b) => a - b);
}

export function stepNext() {
  const next = starts().find((t) => t > state.t + 1e-6);
  if (next === undefined) return toast("No statement runs after this instant");
  pause();
  setTime(next, true);
}

export function stepPrevious() {
  const previous = starts().filter((t) => t < state.t - 1e-6).pop();
  if (previous === undefined) return toast("No statement runs before this instant");
  pause();
  setTime(previous, true);
}

/** Play until the next run of the picked line (pausing there). */
export function runToLine() {
  const picked = state.pickedLine;
  if (!picked) return toast("Click a line of the code first");
  const entry = ((state.meta && state.meta.statements) || []).find((s) => s.file === picked.file && s.line === picked.line);
  const run = entry && entry.runs.find((r) => r.start > state.t + 1e-6);
  if (!run) return toast(entry ? "That line does not run again after this instant" : "That line schedules nothing");
  pause();
  state.stopAt = run.start;
  play();
}

export function installStepping() {
  window.addEventListener("keydown", (e) => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
    if (e.key === "F10") {
      e.preventDefault();
      e.shiftKey ? stepPrevious() : stepNext();
    } else if (e.key === "F8") {
      e.preventDefault();
      runToLine();
    }
  });
  document.getElementById("step-previous").addEventListener("click", stepPrevious);
  document.getElementById("step-next").addEventListener("click", stepNext);
  document.getElementById("run-to-line").addEventListener("click", runToLine);
  listen("scene", () => {
    if (state.pickedLine && !(state.meta.code || {})[state.pickedLine.file]) state.pickedLine = null;
  });
}
