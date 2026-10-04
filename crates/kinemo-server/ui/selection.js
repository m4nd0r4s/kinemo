// Selection: one object (picked on the canvas or in the outliner) or a timeline bar (its
// objects are boxed). The first selected object is inspected; its snapshot refreshes as
// frames arrive, a few times per second while playing.
"use strict";

import { requestId, send } from "./connection.js";
import { emit, frameTime, listen, state } from "./state.js";

const INSPECT_INTERVAL_PLAYING_MS = 250;
let inspectInFlight = false;
let lastInspectAt = 0;

export function pickAt(x, y) {
  send({ type: "pick", x, y, t: frameTime(), id: requestId() });
}

export function selectObject(id) {
  state.selectedIds = [id];
  state.selectedBar = null;
  state.selectedClip = null;
  emit("selection");
  inspectNow();
}

export function selectBar(index) {
  const bar = state.meta && state.meta.timeline[index];
  if (!bar) return;
  state.selectedBar = index;
  state.selectedClip = null;
  state.selectedIds = [...bar.objects];
  state.pickedObject = null;
  emit("selection");
  emit("inspector");
}

/** An audio clip of the tracks (narration, sound, music). */
export function selectClip(index) {
  if (!state.meta || !state.meta.tracks || !state.meta.tracks[index]) return;
  state.selectedClip = index;
  state.selectedBar = null;
  state.selectedIds = [];
  state.pickedObject = null;
  state.boxes = new Map();
  emit("selection");
  emit("inspector");
}

export function clearSelection() {
  state.selectedIds = [];
  state.selectedBar = null;
  state.selectedClip = null;
  state.pickedObject = null;
  state.boxes = new Map();
  emit("selection");
  emit("inspector");
}

function inspectNow() {
  if (!state.selectedIds.length) return;
  inspectInFlight = send({ type: "inspect", object: state.selectedIds[0], t: frameTime(), id: requestId() });
  lastInspectAt = performance.now();
}

function refreshInspector() {
  if (!state.selectedIds.length || state.selectedBar !== null || state.editing || inspectInFlight) return;
  if (state.playing && performance.now() - lastInspectAt < INSPECT_INTERVAL_PLAYING_MS) return;
  inspectNow();
}

function onPick(msg) {
  const isInspect = msg.x === undefined;
  if (isInspect) inspectInFlight = false;
  const object = msg.object;
  if (!object) {
    // A click on the background, or the inspected object is gone after a rebuild.
    if (!isInspect || state.selectedBar === null) clearSelection();
    return;
  }
  if (isInspect && object.id !== state.selectedIds[0]) return; // stale answer
  if (!isInspect) {
    state.selectedIds = [object.id];
    state.selectedBar = null;
    state.selectedClip = null;
    state.boxes = new Map([[object.id, object.pixel_bbox]]);
    emit("selection");
  }
  if (state.selectedBar !== null) return;
  state.pickedObject = object;
  emit("inspector", msg.t);
}

export function installSelection() {
  listen("message:pick", onPick);
  listen("frame", refreshInspector);
  listen("paused", () => state.selectedBar === null && !state.editing && inspectNow());
  listen("escape", () => {
    if (!state.editing) clearSelection();
  });
  listen("scene", () => {
    if (state.selectedClip !== null) {
      // The clip list is rebuilt: keep the same line selected if it is still there.
      if (!(state.meta.tracks || [])[state.selectedClip]) state.selectedClip = null;
      emit("inspector");
      return;
    }
    if (state.selectedBar !== null && !(state.meta.timeline[state.selectedBar])) state.selectedBar = null;
    if (state.selectedBar !== null) {
      state.selectedIds = [...state.meta.timeline[state.selectedBar].objects];
      emit("inspector");
    } else if (!state.editing) {
      inspectNow();
    }
  });
}
