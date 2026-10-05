// The Code tab: the scene's source (meta.code), with the lines whose statements are running at
// the playhead lit (meta.statements) and the one that started last emphasized. "follow" keeps
// the running line in view while playing or scrubbing; scrolling by hand turns it off.
// Selecting a bar or an audio clip shows its line.
"use strict";

import { hasBreakpoint, toggleBreakpoint } from "./breakpoints.js";
import { pause, setTime } from "./playback.js";
import { el, listen, state } from "./state.js";

const PANE_KEY = "kinemo-dev-side-pane";
let file = null; // the file shown
let lineNodes = []; // index i → the node of line i + 1
let lit = []; // nodes lit last time
let scrollingByCode = false;

const $ = (id) => document.getElementById(id);

function codeFiles() {
  return (state.meta && state.meta.code) || {};
}

/** Runs of the shown file's statements, by line. */
function runsByLine() {
  const out = new Map();
  for (const entry of (state.meta && state.meta.statements) || []) {
    if (entry.file === file) out.set(entry.line, entry.runs);
  }
  return out;
}

function chooseFile() {
  const files = Object.keys(codeFiles());
  if (!files.length) return null;
  if (file && files.includes(file)) return file;
  // The scene's own file first.
  return files.includes(state.meta.file) ? state.meta.file : files[0];
}

function renderFiles() {
  const files = Object.entries(codeFiles());
  $("code-files").replaceChildren(
    ...(files.length > 1
      ? files.map(([path, info]) =>
          el("button", { class: `code-file${path === file ? " active" : ""}`, title: path, onclick: () => show(path) }, info.name)
        )
      : files.map(([path, info]) => el("span", { class: "code-file active", title: path }, info.name)))
  );
}

/** The gutter of a line with statements: its time (`1.20s`), a loop's run count (`×3`) or a
 *  mark's name; clicking moves the playhead to the run after it (wrapping to the first). */
function whenNode(runs) {
  if (!runs) return el("span", { class: "when" });
  const marks = runs.filter((r) => r.kind === "mark");
  const text = marks.length === runs.length ? `◆ ${marks[0].label}` : runs.length > 1 ? `×${runs.length}` : `${runs[0].start.toFixed(2)}s`;
  const title = runs.map((r, i) => `${runs.length > 1 ? `${i + 1}. ` : ""}${r.start.toFixed(2)}${r.end > r.start ? `–${r.end.toFixed(2)}` : ""} s  ${r.kind}${r.label ? ` · ${r.label}` : ""}`).join("\n");
  return el(
    "span",
    {
      class: "when",
      title: `${title}\n\nclick: go to ${runs.length > 1 ? "the next run" : "it"}`,
      onclick: () => {
        const next = runs.find((r) => r.start > state.t + 1e-6) || runs[0];
        pause();
        setTime(next.start, true);
      },
    },
    text
  );
}

function renderLines() {
  const info = codeFiles()[file];
  const runs = runsByLine();
  lineNodes = (info ? info.lines : []).map((segments, i) =>
    el(
      "div",
      {
        class: `code-line${runs.has(i + 1) ? " has-runs" : ""}${state.pickedLine && state.pickedLine.file === file && state.pickedLine.line === i + 1 ? " picked" : ""}`,
        "data-line": i + 1,
      },
      el(
        "span",
        {
          class: `ln${hasBreakpoint(file, i + 1) ? " bp" : ""}`,
          title: runs.has(i + 1) ? "click: toggle a breakpoint" : null,
          onclick: () => runs.has(i + 1) && toggleBreakpoint(file, i + 1),
        },
        String(i + 1)
      ),
      whenNode(runs.get(i + 1)),
      el("span", { class: "src", onclick: () => pick(i + 1) }, ...segments.map(([text, kind]) => el("span", { class: `tk-${kind}` }, text)), segments.length ? null : " ")
    )
  );
  $("code-lines").replaceChildren(...lineNodes);
  lit = [];
  updateLit();
}

/** Pick a line (the target of "run to line"). */
function pick(line) {
  state.pickedLine = { file, line };
  for (const node of $("code-lines").querySelectorAll(".code-line.picked")) node.classList.remove("picked");
  if (lineNodes[line - 1]) lineNodes[line - 1].classList.add("picked");
}

function show(path) {
  file = path;
  renderFiles();
  renderLines();
}

/** Light the lines running at the playhead; the latest-started one is the current line. */
function updateLit() {
  for (const node of lit) node.classList.remove("running", "current", "caller");
  lit = [];
  if (!file) return;
  const t = state.t;
  let current = null;
  let currentRun = null;
  let latest = -Infinity;
  for (const [line, runs] of runsByLine()) {
    const node = lineNodes[line - 1];
    if (!node) continue;
    // An instant statement (add, mark, start of length 0) lights for one frame's worth.
    const run = runs.find((r) => t >= r.start - 1e-9 && (t < r.end || (r.end - r.start < 1e-9 && t < r.start + 1 / 30)));
    if (!run) continue;
    node.classList.add("running");
    lit.push(node);
    // The latest-started run is current; on a tie, the innermost (a clip's line over its call).
    const depth = (run.callers || []).length;
    if (run.start > latest + 1e-9 || (Math.abs(run.start - latest) <= 1e-9 && depth >= ((currentRun && currentRun.callers) || []).length)) {
      latest = run.start;
      current = node;
      currentRun = run;
    }
  }
  // The lines that called the current one (a clip's call site, a helper's), in this file.
  for (const caller of (currentRun && currentRun.callers) || []) {
    const node = caller.file === file && lineNodes[caller.line - 1];
    if (node && node !== current) {
      node.classList.add("caller");
      lit.push(node);
    }
  }
  if (current) {
    current.classList.add("current");
    if ($("code-follow").checked && !$("code-pane").classList.contains("hidden")) scrollTo(current);
  }
}

function scrollTo(node) {
  const box = $("code-lines").getBoundingClientRect();
  const r = node.getBoundingClientRect();
  if (r.top >= box.top + 24 && r.bottom <= box.bottom - 24) return;
  scrollingByCode = true;
  node.scrollIntoView({ block: "center" });
  requestAnimationFrame(() => (scrollingByCode = false));
}

/** Show a source line (a selected bar or clip), in its file. */
function reveal(path, line) {
  if (!path || !codeFiles()[path]) return;
  if (path !== file) show(path);
  for (const node of $("code-lines").querySelectorAll(".code-line.selected")) node.classList.remove("selected");
  const node = lineNodes[line - 1];
  if (!node) return;
  node.classList.add("selected");
  scrollTo(node);
}

function onSelection() {
  if (state.selectedBar !== null && state.meta.timeline[state.selectedBar]) {
    const bar = state.meta.timeline[state.selectedBar];
    reveal(bar.file, bar.line);
  } else if (state.selectedClip !== null && state.meta.tracks && state.meta.tracks[state.selectedClip]) {
    const span = state.meta.tracks[state.selectedClip].span;
    if (span) reveal(span.file, span.line);
  }
}

function setPane(pane) {
  const code = pane === "code";
  $("tab-code").classList.toggle("active", code);
  $("tab-inspector").classList.toggle("active", !code);
  $("code-pane").classList.toggle("hidden", !code);
  $("inspector").classList.toggle("hidden", code);
  document.querySelector(".workspace").classList.toggle("code-open", code);
  try {
    localStorage.setItem(PANE_KEY, pane);
  } catch {
    // private window: the choice lasts for this page only
  }
  if (code) updateLit();
}

export function installCodeView() {
  for (const tab of document.querySelectorAll(".side-tab")) tab.addEventListener("click", () => setPane(tab.dataset.pane));
  let saved = "inspector";
  try {
    saved = localStorage.getItem(PANE_KEY) || "inspector";
  } catch {
    // keep the default
  }
  setPane(saved);
  // Scrolling by hand stops following until "follow" is checked again.
  $("code-lines").addEventListener("wheel", () => !scrollingByCode && ($("code-follow").checked = false), { passive: true });
  $("code-follow").addEventListener("change", updateLit);
  listen("scene", () => {
    file = chooseFile();
    renderFiles();
    renderLines();
  });
  listen("time", updateLit);
  listen("selection", onSelection);
  listen("breakpoints", () => {
    for (const node of lineNodes) node.querySelector(".ln").classList.toggle("bp", !!hasBreakpoint(file, Number(node.dataset.line)));
  });
  listen("breakpoint-hit", ({ point }) => {
    if (!$("code-pane").classList.contains("hidden")) reveal(point.file, point.line);
  });
}
