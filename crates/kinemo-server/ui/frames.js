// Frames: at most one request in flight; newer playhead positions replace the pending
// one, so playback drops frames when behind. Selection boxes and debug overlays arrive in
// the frame header and are drawn on the highlight canvas over the image.
"use strict";

import { requestId, send } from "./connection.js";
import { emit, frameIndex, listen, state, view } from "./state.js";

let inFlight = false;
let pendingT = null;
let lastRequested = -1;

const debugFlags = () => (state.meta && state.meta.debug) || [];

export function requestFrame(t, force = false) {
  if (!state.meta) return;
  const index = frameIndex(t);
  if (!force && index === lastRequested && pendingT === null) return;
  if (inFlight) {
    pendingT = t; // newest wins: intermediate frames are dropped
    return;
  }
  const request = { type: "frame", t, id: requestId() };
  if (state.selectedIds.length) request.select = state.selectedIds;
  if (debugFlags().length) request.overlay = true;
  if (send(request)) {
    inFlight = true;
    lastRequested = index;
  }
}

async function onFrameMessage(buffer) {
  const headerLength = new DataView(buffer).getUint32(0, false);
  const header = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 4, headerLength)));
  const png = new Blob([new Uint8Array(buffer, 4 + headerLength)], { type: "image/png" });
  try {
    const bitmap = await createImageBitmap(png);
    drawFrame(bitmap, header);
  } finally {
    inFlight = false;
    if (pendingT !== null) {
      const t = pendingT;
      pendingT = null;
      requestFrame(t, true);
    }
  }
}

function drawFrame(bitmap, header) {
  const canvas = view.frameCanvas;
  if (canvas.width !== header.width || canvas.height !== header.height) {
    canvas.width = view.highlightCanvas.width = header.width;
    canvas.height = view.highlightCanvas.height = header.height;
    view.frameWrap.style.aspectRatio = `${header.width} / ${header.height}`;
  }
  canvas.getContext("2d").drawImage(bitmap, 0, 0);
  bitmap.close && bitmap.close();
  view.frameNumber.textContent = `frame ${header.frame}`;
  if (header.selection !== undefined) {
    state.boxes = new Map(header.selection.map((b) => [b.id, b.pixel_bbox]));
  } else if (!state.selectedIds.length) {
    state.boxes = new Map();
  }
  if (header.overlay) state.overlay = header.overlay;
  redrawHighlightLayer();
  emit("frame", header);
}

// ---- highlight layer ----------------------------------------------------------------

/** Pixel offset applied to the primary selection while it is dragged on the canvas. */
let dragOffset = null;

export function setDragOffset(offset) {
  dragOffset = offset;
  redrawHighlightLayer();
}

export function redrawHighlightLayer() {
  const c = view.highlightCanvas;
  const ctx = c.getContext("2d");
  ctx.clearRect(0, 0, c.width, c.height);
  drawOverlay(ctx);
  state.selectedIds.forEach((id, i) => {
    const box = state.boxes.get(id);
    if (!box) return;
    const [dx, dy] = i === 0 && dragOffset ? dragOffset : [0, 0];
    drawBox(ctx, [box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy], i === 0);
  });
}

function drawBox(ctx, [x0, y0, x1, y1], primary) {
  ctx.save();
  ctx.strokeStyle = primary ? "#f5c542" : "rgba(245, 197, 66, 0.55)";
  ctx.lineWidth = primary ? 1.5 : 1;
  ctx.setLineDash([5, 4]);
  ctx.strokeRect(x0 - 2, y0 - 2, x1 - x0 + 4, y1 - y0 + 4);
  ctx.restore();
}

function drawOverlay(ctx) {
  const overlay = state.overlay;
  if (!overlay) return;
  const flags = debugFlags();
  if (flags.includes("layout")) {
    ctx.save();
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(80, 200, 255, 0.8)";
    const centers = {};
    for (const box of overlay.boxes) {
      const [x0, y0, x1, y1] = box.bbox;
      if (x1 - x0 < 0.5 && y1 - y0 < 0.5) continue;
      ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
      centers[box.id] = [(x0 + x1) / 2, (y0 + y1) / 2];
    }
    ctx.strokeStyle = ctx.fillStyle = "rgba(255, 110, 200, 0.9)";
    for (const rel of overlay.relations) {
      const a = centers[rel.from], b = centers[rel.to];
      if (!a || !b) continue;
      ctx.beginPath();
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0], b[1]);
      ctx.stroke();
      ctx.fillText(rel.side || "", (a[0] + b[0]) / 2 + 4, (a[1] + b[1]) / 2 - 4);
    }
    ctx.restore();
  }
  if (flags.includes("safe")) {
    const [x0, y0, x1, y1] = overlay.safe;
    ctx.save();
    ctx.strokeStyle = "rgba(255, 90, 90, 0.8)";
    ctx.setLineDash([8, 6]);
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
    ctx.restore();
  }
}

export function installFrames() {
  listen("message:frame", onFrameMessage);
  listen("connected", () => {
    inFlight = false;
    lastRequested = -1;
    if (state.meta) requestFrame(state.t, true);
  });
  listen("selection", () => {
    redrawHighlightLayer();
    requestFrame(state.t, true);
  });
}
