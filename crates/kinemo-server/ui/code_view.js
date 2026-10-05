// The Code tab: the scene's source (meta.code), with the lines whose statements are running at
// the playhead lit (meta.statements) and the one that started last emphasized. "follow" keeps
// the running line in view while playing or scrubbing; scrolling by hand turns it off.
// Selecting a bar or an audio clip shows its line.
"use strict";

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

function renderLines() {
  const info = codeFiles()[file];
  const runs = runsByLine();
  lineNodes = (info ? info.lines : []).map((segments, i) =>
    el(
      "div",
      { class: `code-line${runs.has(i + 1) ? " has-runs" : ""}`, "data-line": i + 1 },
      el("span", { class: "ln" }, String(i + 1)),
      el("span", { class: "src" }, ...segments.map(([text, kind]) => el("span", { class: `tk-${kind}` }, text)), segments.length ? null : " ")
    )
  );
  $("code-lines").replaceChildren(...lineNodes);
  lit = [];
  updateLit();
}

function show(path) {
  file = path;
  renderFiles();
  renderLines();
}

/** Light the lines running at the playhead; the latest-started one is the current line. */
function updateLit() {
  for (const node of lit) node.classList.remove("running", "current");
  lit = [];
  if (!file) return;
  const t = state.t;
  let current = null;
  let latest = -Infinity;
  for (const [line, runs] of runsByLine()) {
    const node = lineNodes[line - 1];
    if (!node) continue;
    // An instant statement (add, mark, start of length 0) lights for one frame's worth.
    const run = runs.find((r) => t >= r.start - 1e-9 && (t < r.end || (r.end - r.start < 1e-9 && t < r.start + 1 / 30)));
    if (!run) continue;
    node.classList.add("running");
    lit.push(node);
    if (run.start >= latest) {
      latest = run.start;
      current = node;
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
}
