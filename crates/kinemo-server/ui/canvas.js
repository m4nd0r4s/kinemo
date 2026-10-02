// The frame canvas: a click picks the object under the pointer; dragging the selected
// object edits the code that positions it (`place(at=(x, y))`, or literal `x`/`y`), live
// while dragging and written to the file on release.
"use strict";

import { argumentFor, beginDrag, DRAG_THRESHOLD_PX, liveSender, propEditor, revertLive, sendEdit, siteFor } from "./editing.js";
import { redrawHighlightLayer, setDragOffset } from "./frames.js";
import { pickAt } from "./selection.js";
import { formatNumber, listen, state, toast, view } from "./state.js";

function framePoint(e) {
  const rect = view.frameCanvas.getBoundingClientRect();
  return {
    x: ((e.clientX - rect.left) * view.frameCanvas.width) / rect.width,
    y: ((e.clientY - rect.top) * view.frameCanvas.height) / rect.height,
  };
}

const value = (v) => (v && typeof v === "object" ? Object.values(v)[0] : v);

/**
 * How dragging the inspected object edits the code: `{changes(dx, dy)}` in world units, or
 * `{reason}` when its position is not a literal the preview may rewrite.
 */
export function positionEditor(object) {
  const source = object.position_source || {};
  if (source.kind === "container") return { reason: "positioned by its container" };
  if (source.kind === "place") {
    const found = siteFor(source.span);
    const at = found && argumentFor(found.site, "at");
    if (!at || at.kind !== "vector") return { reason: "positioned by a constraint (place)" };
    return {
      changes: (dx, dy) => [{ site: found.key, target: "at", value: `(${formatNumber(at.value[0] + dx)}, ${formatNumber(at.value[1] + dy)})` }],
    };
  }
  const moving = ["x", "y"].find((name) => {
    const source = object.prop_sources[name];
    return source && source.kind === "animation" && source.running;
  });
  if (moving) return { reason: `${moving} is animating here; move the playhead past the animation to drag its target` };
  const axes = ["x", "y"].map((name) => {
    const editor = propEditor(object, name);
    if (!editor || (editor.argument && editor.argument.kind !== "number")) return null;
    const base = editor.argument ? editor.argument.value : value(object.props[name]);
    return { editor, base };
  });
  if (axes.some((a) => !a)) return { reason: "its position is computed in the code" };
  return {
    changes: (dx, dy) =>
      axes.map(({ editor, base }, i) => ({ site: editor.key, target: editor.target, value: formatNumber(base + (i ? dy : dx)) })),
  };
}

/** Dragged distances snap to this many world units (a clean number in the code). */
const SNAP = 0.01;

function worldDelta(px, py) {
  const render = state.meta.render;
  const snap = (v) => Math.round(v / SNAP) * SNAP;
  return [snap((px * render.frame_w) / render.width), snap((-py * render.frame_h) / render.height)];
}

function inside(box, p) {
  return box && p.x >= box[0] - 3 && p.x <= box[2] + 3 && p.y >= box[1] - 3 && p.y <= box[3] + 3;
}

export function installCanvas() {
  let press = null;
  const canvas = view.frameCanvas;
  canvas.addEventListener("pointerdown", (e) => {
    const point = framePoint(e);
    const object = state.pickedObject;
    const primary = state.selectedIds[0];
    const onSelection = object && object.id === primary && state.selectedBar === null && inside(state.boxes.get(primary), point);
    press = { start: point, object: onSelection ? object : null, dragging: false };
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!press || !press.object) return;
    const point = framePoint(e);
    const px = point.x - press.start.x, py = point.y - press.start.y;
    if (!press.dragging) {
      if (Math.hypot(px, py) < DRAG_THRESHOLD_PX) return;
      const editor = positionEditor(press.object);
      if (!editor.changes) {
        toast(`can't drag ${press.object.label || "this object"}: ${editor.reason}`, "error");
        press.object = null;
        return;
      }
      Object.assign(press, startDrag(editor));
    }
    press.move(px, py);
  });
  canvas.addEventListener("pointerup", (e) => {
    if (!press) return;
    const session = press;
    press = null;
    if (session.dragging) return session.release();
    const point = framePoint(e);
    if (Math.hypot(point.x - session.start.x, point.y - session.start.y) < DRAG_THRESHOLD_PX) pickAt(point.x, point.y);
  });
  // The drag offset is dropped once the scene rebuilt from the written file arrives.
  listen("scene", () => {
    if (!state.editing && !state.meta.live) setDragOffset(null);
  });
}

function startDrag(editor) {
  let delta = [0, 0]; // pixels moved so far
  let applied = [0, 0]; // pixels already shown by the latest live build
  const sender = liveSender((dx, dy, px, py) => {
    sendEdit(editor.changes(dx, dy), true, () => {
      applied = [px, py];
      setDragOffset([delta[0] - applied[0], delta[1] - applied[1]]);
    });
  });
  const end = beginDrag(() => {
    sender.cancel();
    end();
    setDragOffset(null);
    revertLive();
  });
  return {
    dragging: true,
    move(px, py) {
      delta = [px, py];
      setDragOffset([px - applied[0], py - applied[1]]);
      sender.push(...worldDelta(px, py), px, py);
    },
    release() {
      sender.cancel();
      end();
      sendEdit(editor.changes(...worldDelta(...delta)), false);
      redrawHighlightLayer();
    },
  };
}
