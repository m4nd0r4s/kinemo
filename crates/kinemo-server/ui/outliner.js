// The outliner: every object of the scene as a tree (groups, containers, text runs), dimmed
// while absent at the playhead. Clicking selects, so small or hidden objects are reachable.
"use strict";

import { selectObject } from "./selection.js";
import { el, listen, presentAt, state, view } from "./state.js";

/** Groups with more children than this start collapsed (a text's glyph runs). */
const COLLAPSE_ABOVE = 8;
const collapsed = new Set();
const expanded = new Set();

function children() {
  const out = new Map();
  for (const [id, info] of Object.entries(state.meta.objects)) {
    const parent = info.parent === null || info.parent === undefined ? "root" : String(info.parent);
    if (!out.has(parent)) out.set(parent, []);
    out.get(parent).push(id);
  }
  for (const ids of out.values()) ids.sort((a, b) => Number(a) - Number(b));
  return out;
}

function isCollapsed(id, count) {
  if (expanded.has(id)) return false;
  return collapsed.has(id) || count > COLLAPSE_ABOVE;
}

function render() {
  if (!state.meta) return;
  const filter = view.outlinerFilter.value.trim().toLowerCase();
  const tree = children();
  const rows = [];
  const visit = (id, depth) => {
    const info = state.meta.objects[id];
    const kids = tree.get(id) || [];
    const matches = !filter || info.label.toLowerCase().includes(filter) || info.kind.includes(filter);
    const closed = !filter && isCollapsed(id, kids.length);
    if (matches) rows.push(row(id, info, depth, kids.length, closed));
    if (!closed || filter) for (const kid of kids) visit(kid, filter ? depth : depth + 1);
  };
  for (const id of tree.get("root") || []) visit(id, 0);
  view.outliner.replaceChildren(...rows);
  updatePresence();
}

function row(id, info, depth, count, closed) {
  const twisty = count
    ? el("span", { class: "twisty", onclick: (e) => (e.stopPropagation(), toggle(id, closed)) }, closed ? "▸" : "▾")
    : el("span", { class: "twisty" }, "");
  return el(
    "div",
    {
      class: `outline-row${state.selectedIds.includes(Number(id)) ? " selected" : ""}`,
      style: `padding-left:${6 + depth * 12}px`,
      "data-id": id,
      onclick: () => selectObject(Number(id)),
    },
    twisty,
    el("span", { class: "outline-label" }, info.label),
    el("span", { class: "outline-kind" }, count ? `${info.kind} · ${count}` : info.kind)
  );
}

function toggle(id, closed) {
  if (closed) {
    collapsed.delete(id);
    expanded.add(id);
  } else {
    expanded.delete(id);
    collapsed.add(id);
  }
  render();
}

function updatePresence() {
  for (const node of view.outliner.children) {
    node.classList.toggle("absent", !presentAt(Number(node.dataset.id), state.t));
  }
}

function updateSelection() {
  for (const node of view.outliner.children) {
    node.classList.toggle("selected", state.selectedIds.includes(Number(node.dataset.id)));
  }
}

export function installOutliner() {
  listen("scene", render);
  listen("selection", updateSelection);
  listen("time", updatePresence);
  view.outlinerFilter.addEventListener("input", render);
}
