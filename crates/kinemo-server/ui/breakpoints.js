// Breakpoints on statements of the code view. Click a line number to toggle one; while playing,
// the preview pauses exactly where a run of that statement starts and selects it. A line with
// several runs (a loop) can break on one run only. Breakpoints are remembered per browser by
// file, line and the line's text, and found again by that text after an edit (orphaned when
// the line is gone).
"use strict";

import { setBreakCheck } from "./playback.js";
import { selectBar } from "./selection.js";
import { basename, el, emit, listen, state } from "./state.js";

const KEY = "kinemo-dev-breakpoints";
/** How far (lines) a breakpoint is searched for by its text after an edit. */
const REANCHOR = 40;

/** [{ file, line, text, enabled, run (1-based or 0 for any), orphan }] */
let points = load();

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
    localStorage.setItem(KEY, JSON.stringify(points.map(({ orphan, ...rest }) => rest)));
  } catch {
    // private window: breakpoints last for this page only
  }
}

function lineText(file, line) {
  const info = state.meta && state.meta.code && state.meta.code[file];
  const segments = info && info.lines[line - 1];
  return segments ? segments.map(([text]) => text).join("").trim() : null;
}

function runsOf(file, line) {
  const entry = ((state.meta && state.meta.statements) || []).find((s) => s.file === file && s.line === line);
  return entry ? entry.runs : [];
}

/** After a rebuild: follow each breakpoint's text to its new line, or mark it orphaned. */
function reanchor() {
  for (const point of points) {
    if (!state.meta.code || !state.meta.code[point.file]) {
      point.orphan = true;
      continue;
    }
    if (lineText(point.file, point.line) === point.text && runsOf(point.file, point.line).length) {
      point.orphan = false;
      continue;
    }
    let found = null;
    for (let d = 1; d <= REANCHOR && found === null; d++) {
      for (const line of [point.line - d, point.line + d]) {
        if (line > 0 && lineText(point.file, line) === point.text && runsOf(point.file, line).length) {
          found = line;
          break;
        }
      }
    }
    point.orphan = found === null;
    if (found !== null) point.line = found;
  }
  save();
}

export function hasBreakpoint(file, line) {
  return points.find((p) => p.file === file && p.line === line && !p.orphan) || null;
}

export function toggleBreakpoint(file, line) {
  const existing = hasBreakpoint(file, line);
  if (existing) points = points.filter((p) => p !== existing);
  else if (runsOf(file, line).length) points.push({ file, line, text: lineText(file, line) || "", enabled: true, run: 0 });
  save();
  emit("breakpoints");
}

/** The first breakpoint run that starts in (from, to]: where playback stops. */
function firstHit(from, to) {
  let best = null;
  for (const point of points) {
    if (!point.enabled || point.orphan) continue;
    runsOf(point.file, point.line).forEach((run, i) => {
      if (point.run && point.run !== i + 1) return;
      if (point.caller && !(run.callers || []).some((c) => `${c.file}:${c.line}` === point.caller)) return;
      if (run.start > from + 1e-9 && run.start <= to + 1e-9 && (!best || run.start < best.run.start)) best = { point, run };
    });
  }
  return best;
}

function onHit(hit) {
  state.lastHit = { file: hit.point.file, line: hit.point.line, start: hit.run.start };
  // A play/start run is a timeline bar: select it, so the inspector shows its arguments.
  const index = state.meta.timeline.findIndex(
    (bar) => Math.abs(bar.start - hit.run.start) < 1e-6 && bar.line === hit.point.line && bar.file === hit.point.file
  );
  if (index >= 0) selectBar(index);
  emit("breakpoint-hit", hit);
}

function renderList() {
  const box = document.getElementById("code-breakpoints");
  if (!box) return;
  if (!points.length) {
    box.replaceChildren(el("div", { class: "hint" }, "Click a line number to stop there while playing."));
    return;
  }
  const rows = points.map((point) => {
    const runs = point.orphan ? [] : runsOf(point.file, point.line);
    const runChoice =
      runs.length > 1
        ? el(
            "select",
            {
              class: "bp-run",
              title: "Break on every run, or on one",
              onchange: (e) => {
                point.run = Number(e.currentTarget.value);
                save();
              },
            },
            el("option", { value: "0" }, "every run"),
            ...runs.map((_, i) => el("option", { value: String(i + 1) }, `run ${i + 1} of ${runs.length}`))
          )
        : null;
    if (runChoice) runChoice.value = String(point.run || 0);
    // A line reached from several call sites (a clip used in two places) can stop for one.
    const callers = [...new Map(runs.filter((r) => r.callers && r.callers.length).map((r) => [`${r.callers[0].file}:${r.callers[0].line}`, r.callers[0]])).values()];
    const callerChoice =
      callers.length > 1
        ? el(
            "select",
            {
              class: "bp-run",
              title: "Break when called from anywhere, or from one call site",
              onchange: (e) => {
                point.caller = e.currentTarget.value || null;
                save();
              },
            },
            el("option", { value: "" }, "any caller"),
            ...callers.map((c) => el("option", { value: `${c.file}:${c.line}` }, `from ${basename(c.file)}:${c.line}`))
          )
        : null;
    if (callerChoice) callerChoice.value = point.caller || "";
    return el(
      "div",
      { class: `bp-row${point.orphan ? " orphan" : ""}` },
      el("input", {
        type: "checkbox",
        title: "Enabled",
        ...(point.enabled ? { checked: "" } : {}),
        onchange: (e) => {
          point.enabled = e.currentTarget.checked;
          save();
        },
      }),
      el("span", { class: "bp-where", title: point.text }, `${basename(point.file)}:${point.line}`, point.orphan ? " (line gone)" : ""),
      runChoice,
      callerChoice,
      el("button", { class: "ghost bp-remove", title: "Remove", onclick: () => ((points = points.filter((p) => p !== point)), save(), emit("breakpoints")) }, "✕")
    );
  });
  box.replaceChildren(
    el(
      "div",
      { class: "bp-head" },
      el("span", { class: "section-title" }, `Breakpoints (${points.length})`),
      el("span", { class: "spacer" }),
      el("button", { class: "ghost", onclick: () => ((points = []), save(), emit("breakpoints")) }, "clear all")
    ),
    ...rows
  );
}

export function installBreakpoints() {
  setBreakCheck((from, to) => {
    const hit = firstHit(from, to);
    if (!hit) return null;
    queueMicrotask(() => onHit(hit));
    return hit.run.start;
  });
  listen("scene", () => {
    reanchor();
    renderList();
    emit("breakpoints");
  });
  listen("breakpoints", renderList);
}
