// The timeline: one bar per play/start (hover shows the code), marks (names stacked so they
// never overlap), zero-length entries as ticks in their own row, scrubbing, zoom
// (Ctrl/⌘ + wheel, or the buttons) and bars from one statement in a loop grouped into one.
// Clicking a bar selects it: its objects are boxed and its arguments appear in the inspector.
"use strict";

import { pause, setTime } from "./playback.js";
import { selectBar } from "./selection.js";
import { basename, duration, el, listen, openInEditor, state, view } from "./state.js";

const MAX_ZOOM = 64;
const percent = (t) => `${(100 * t) / Math.max(duration(), 1e-9)}%`;

function niceStep(visibleSeconds) {
  const target = visibleSeconds / 10;
  for (const s of [0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60]) if (s >= target) return s;
  return 120;
}

/** Bars as drawn: each repeated statement collapses into one bar unless expanded. */
function displayedBars() {
  const bars = state.meta.timeline.map((bar, index) => ({ ...bar, indices: [index] }));
  if (!view.groupRepeats.checked) return bars;
  const groups = new Map();
  for (const bar of bars) {
    if (!groups.has(bar.group)) groups.set(bar.group, []);
    groups.get(bar.group).push(bar);
  }
  const out = [];
  for (const [group, members] of groups) {
    if (members.length < 2 || state.expandedGroups.has(group)) {
      out.push(...members);
      continue;
    }
    out.push({
      ...members[0],
      label: `${members[0].label} ×${members.length}`,
      start: Math.min(...members.map((m) => m.start)),
      end: Math.max(...members.map((m) => m.end)),
      indices: members.map((m) => m.indices[0]),
      collapsed: true,
    });
  }
  return out.sort((a, b) => a.start - b.start || a.end - b.end);
}

/** Greedy lane packing: each bar goes into the first lane where it does not overlap. */
function packLanes(bars) {
  const laneEnds = [];
  const minGap = (duration() * 0.004) / state.zoom;
  return bars.map((bar) => {
    let lane = laneEnds.findIndex((end) => end <= bar.start + 1e-9);
    if (lane < 0) {
      lane = laneEnds.length;
      laneEnds.push(0);
    }
    laneEnds[lane] = Math.max(bar.end, bar.start + minGap);
    return lane;
  });
}

/** Line height of a row of mark names, in pixels. */
const MARK_ROW = 13;

/** Marks at one instant share one label (`B01.end · B02`). */
function markGroups() {
  const groups = [];
  for (const mark of [...state.meta.marks].sort((a, b) => a.t - b.t)) {
    const last = groups[groups.length - 1];
    if (last && Math.abs(last.t - mark.t) < 1e-6) last.marks.push(mark);
    else groups.push({ t: mark.t, marks: [mark] });
  }
  return groups;
}

/** Mark names in rows: each goes into the first row where it does not overlap the previous one. */
function renderMarks(total) {
  const width = view.timelineContent.getBoundingClientRect().width || 1;
  const rowEnds = [];
  const labels = [];
  const lines = [];
  for (const group of markGroups()) {
    const names = group.marks.map((m) => m.name || "◆");
    const text = names.join(" · ");
    const x = (group.t / Math.max(total, 1e-9)) * width;
    let row = rowEnds.findIndex((end) => end <= x);
    if (row < 0) {
      row = rowEnds.length;
      rowEnds.push(0);
    }
    rowEnds[row] = x + text.length * 6.2 + 10;
    const title = group.marks.map((m) => `${m.name || "mark"} @ ${m.t.toFixed(2)} s`).join("\n");
    const unnamed = group.marks.every((m) => !m.name);
    labels.push(el("div", { class: `mark-label${unnamed ? " unnamed" : ""}`, style: `left:${percent(group.t)};top:${row * MARK_ROW}px`, title }, text));
    lines.push(el("div", { class: `mark${unnamed ? " unnamed" : ""}`, style: `left:${percent(group.t)}`, title }));
  }
  view.markLabels.style.height = `${Math.max(1, rowEnds.length) * MARK_ROW + 2}px`;
  view.markLabels.replaceChildren(...labels);
  view.marks.replaceChildren(...lines);
}

function renderTimeline() {
  if (!state.meta) return;
  view.timelineContent.style.width = `${100 * state.zoom}%`;
  const total = duration();
  const step = niceStep(total / state.zoom);
  const ticks = [];
  for (let t = 0; t <= total + 1e-9; t += step) ticks.push(el("div", { class: "tick", style: `left:${percent(t)}` }, `${+t.toFixed(2)}s`));
  view.ruler.replaceChildren(...ticks);
  renderMarks(total);
  const all = displayedBars();
  const isInstant = (bar) => bar.end - bar.start <= 1e-9;
  view.instants.replaceChildren(...all.filter(isInstant).map(barNode));
  const bars = all.filter((bar) => !isInstant(bar));
  const lanes = packLanes(bars);
  const laneNodes = [];
  bars.forEach((bar, i) => {
    while (laneNodes.length <= lanes[i]) laneNodes.push(el("div", { class: "lane" }));
    laneNodes[lanes[i]].append(barNode(bar));
  });
  view.lanes.replaceChildren(...laneNodes);
  updateBars();
}

function barNode(bar) {
  const instant = bar.end - bar.start <= 1e-9;
  const selected = bar.indices.includes(state.selectedBar);
  const hint = bar.collapsed ? "click: select · double-click: expand" : "click: select · ⌘/Ctrl+click: open in editor";
  const node = el(
    "div",
    {
      class: `bar${instant ? " instant" : ""}${bar.collapsed ? " collapsed" : ""}${selected ? " selected" : ""}`,
      style: `left:${percent(bar.start)};width:${instant ? "3px" : percent(bar.end - bar.start)}`,
      title: `${bar.label}\n${bar.start.toFixed(2)}–${bar.end.toFixed(2)} s · ${basename(bar.file)}:${bar.line}\n\n${bar.code}\n\n${hint}`,
      "data-start": bar.start,
      "data-end": bar.end,
    },
    instant ? null : bar.label,
    instant ? null : el("span", { class: "line" }, `:${bar.line}`)
  );
  node.addEventListener("pointerdown", (e) => {
    if (e.metaKey || e.ctrlKey) {
      e.stopPropagation();
      openInEditor(bar.file, bar.line);
    }
  });
  node.addEventListener("click", () => selectBar(bar.indices[0]));
  node.addEventListener("dblclick", () => {
    const expanded = state.expandedGroups;
    expanded.has(bar.group) ? expanded.delete(bar.group) : expanded.add(bar.group);
    renderTimeline();
  });
  return node;
}

function updateBars() {
  view.playhead.style.left = percent(state.t);
  for (const bar of view.timelineContent.querySelectorAll(".bar")) {
    bar.classList.toggle("active", state.t >= +bar.dataset.start && state.t < +bar.dataset.end);
  }
}

// ---- zoom and scrubbing ---------------------------------------------------------------

function setZoom(zoom, anchorClientX) {
  const box = view.timeline.getBoundingClientRect();
  const anchor = anchorClientX === undefined ? box.width / 2 : anchorClientX - box.left;
  const anchorFraction = (view.timeline.scrollLeft + anchor) / (box.width * state.zoom);
  state.zoom = Math.min(MAX_ZOOM, Math.max(1, zoom));
  renderTimeline();
  view.timeline.scrollLeft = anchorFraction * box.width * state.zoom - anchor;
}

function timeFromPointer(event) {
  const rect = view.timelineContent.getBoundingClientRect();
  const x = Math.min(Math.max(event.clientX - rect.left, 0), rect.width);
  return (x / rect.width) * duration();
}

function installScrubbing() {
  // Window listeners rather than pointer capture, so clicks still reach the bars.
  let dragging = false;
  view.timelineContent.addEventListener("pointerdown", (e) => {
    if (!state.meta || e.button !== 0) return;
    dragging = true;
    pause();
    setTime(timeFromPointer(e));
  });
  window.addEventListener("pointermove", (e) => {
    if (dragging) setTime(timeFromPointer(e));
  });
  const stop = () => (dragging = false);
  window.addEventListener("pointerup", stop);
  window.addEventListener("pointercancel", stop);
  view.timeline.addEventListener(
    "wheel",
    (e) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      e.preventDefault();
      setZoom(state.zoom * Math.exp(-e.deltaY * 0.01), e.clientX);
    },
    { passive: false }
  );
  // The buttons zoom around the playhead, so it stays in view.
  const playheadX = () => view.playhead.getBoundingClientRect().left;
  view.zoomIn.addEventListener("click", () => setZoom(state.zoom * 2, playheadX()));
  view.zoomOut.addEventListener("click", () => setZoom(state.zoom / 2, playheadX()));
  view.zoomFit.addEventListener("click", () => setZoom(1));
  view.groupRepeats.addEventListener("change", renderTimeline);
}

export function installTimeline() {
  installScrubbing();
  listen("scene", renderTimeline);
  // Mark names are stacked by their width on screen.
  window.addEventListener("resize", renderTimeline);
  listen("selection", renderTimeline);
  listen("time", updateBars);
}
