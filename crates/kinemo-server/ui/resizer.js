// The timeline's height: drag the handle above the transport to give the lanes and audio
// tracks more (or less) room; double-click it to go back to fitting the content. The height
// is remembered per browser.
"use strict";

import { view } from "./state.js";

const KEY = "kinemo-dev-timeline-height";
const MIN = 60;
const MAX_SHARE = 0.75; // of the window height

function remembered() {
  try {
    const value = Number(localStorage.getItem(KEY));
    return value > 0 ? value : null;
  } catch {
    return null;
  }
}

function remember(height) {
  try {
    if (height === null) localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, String(Math.round(height)));
  } catch {
    // private window: the height lasts for this page only
  }
}

function apply(height) {
  if (height === null) {
    view.timeline.style.height = "";
    view.timeline.style.maxHeight = "";
    return;
  }
  const clamped = Math.min(Math.max(MIN, height), window.innerHeight * MAX_SHARE);
  view.timeline.style.height = `${clamped}px`;
  view.timeline.style.maxHeight = "none";
}

export function installResizer() {
  const handle = document.getElementById("timeline-resizer");
  apply(remembered());
  let start = null;
  // Window listeners, as for scrubbing: the pointer leaves the thin handle while dragging.
  handle.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    start = { y: e.clientY, height: view.timeline.getBoundingClientRect().height };
    handle.classList.add("dragging");
  });
  window.addEventListener("pointermove", (e) => {
    if (start) apply(start.height + (start.y - e.clientY));
  });
  const end = () => {
    if (!start) return;
    start = null;
    handle.classList.remove("dragging");
    remember(view.timeline.getBoundingClientRect().height);
  };
  window.addEventListener("pointerup", end);
  window.addEventListener("pointercancel", end);
  handle.addEventListener("dblclick", () => {
    apply(null);
    remember(null);
  });
  window.addEventListener("resize", () => apply(remembered()));
}
