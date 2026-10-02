// kinemo dev preview page: wires the modules together and connects to the server.
"use strict";

import { installCanvas } from "./canvas.js";
import { installColorPicker } from "./colorpicker.js";
import { connect } from "./connection.js";
import { installEditing } from "./editing.js";
import { installFrames } from "./frames.js";
import { installInspector } from "./inspector.js";
import { installOutliner } from "./outliner.js";
import { installPlayback, setTime } from "./playback.js";
import { installProblems } from "./problems.js";
import { installSelection, selectBar, selectObject } from "./selection.js";
import { emit, lastFrameTime, listen, state } from "./state.js";
import { installTimeline } from "./timeline.js";

/**
 * The page can open on a given state, for links and screenshots:
 * `#t=1.5` (instant), `select=dot` (an object, by label), `bar=2` (a timeline bar).
 */
function applyLocationHash() {
  const params = new URLSearchParams(location.hash.slice(1));
  if (params.has("t")) state.t = Math.min(Math.max(0, Number(params.get("t")) || 0), lastFrameTime());
  if (params.has("bar")) return selectBar(Number(params.get("bar")));
  const label = params.get("select");
  const found = label && Object.entries(state.meta.objects).find(([, info]) => info.label === label);
  if (found) selectObject(Number(found[0]));
}

function onScene(msg) {
  const first = !state.meta;
  state.meta = msg.meta;
  state.version = msg.version;
  if (!first) state.t = Math.min(state.t, lastFrameTime()); // keep the playhead on reload
  emit("scene");
  if (first) applyLocationHash();
  setTime(state.t, true);
}

installFrames();
installPlayback();
installSelection();
installEditing();
installColorPicker();
installCanvas();
installInspector();
installOutliner();
installTimeline();
installProblems();
listen("message:scene", onScene);
listen("message:notice", (msg) => console.info("kinemo:", msg.message));
connect();
