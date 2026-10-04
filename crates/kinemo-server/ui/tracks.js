// Audio tracks under the animation lanes: Narration, Sounds and Music, one clip per line or
// file over the time it sounds. Narration still estimated (no audio yet) is drawn dashed.
// Clicking a clip selects it: the inspector shows its text, words and sources.
"use strict";

import { selectClip } from "./selection.js";
import { basename, duration, el, listen, state, view } from "./state.js";

const TRACKS = [
  { role: "voice", name: "Narration" },
  { role: "sound", name: "Sounds" },
  { role: "music", name: "Music" },
];

const percent = (t) => `${(100 * t) / Math.max(duration(), 1e-9)}%`;

function clipNode(clip, index) {
  const narration = clip.narration;
  const estimated = narration && narration.timing === "estimated";
  const length = clip.end - clip.start;
  const where = clip.span ? `\n${basename(clip.span.file)}:${clip.span.line}` : "";
  const node = el(
    "div",
    {
      class: `clip ${clip.role}${estimated ? " estimated" : ""}${state.selectedClip === index ? " selected" : ""}`,
      style: `left:${percent(clip.start)};width:${length > 0 ? percent(length) : "3px"}`,
      title: `${narration ? narration.text : clip.label}\n${clip.start.toFixed(2)}–${clip.end.toFixed(2)} s${estimated ? " · estimated (no audio yet)" : ""}${where}`,
      "data-start": clip.start,
      "data-end": clip.end,
    },
    narration && narration.beat ? el("span", { class: "beat" }, narration.beat) : null,
    narration ? narration.text : clip.label
  );
  node.addEventListener("pointerdown", (e) => e.stopPropagation()); // a click selects, it does not scrub
  node.addEventListener("click", () => selectClip(index));
  return node;
}

function renderTracks() {
  const clips = (state.meta && state.meta.tracks) || [];
  const rows = [];
  for (const track of TRACKS) {
    const members = clips.map((clip, index) => [clip, index]).filter(([clip]) => clip.role === track.role);
    if (!members.length) continue;
    rows.push(
      el(
        "div",
        { class: `track ${track.role}` },
        el("span", { class: "track-name" }, track.name),
        ...members.map(([clip, index]) => clipNode(clip, index))
      )
    );
  }
  view.tracks.replaceChildren(...rows);
  updateClips();
}

function updateClips() {
  for (const clip of view.tracks.querySelectorAll(".clip")) {
    clip.classList.toggle("active", state.t >= +clip.dataset.start && state.t < +clip.dataset.end);
  }
}

export function installTracks() {
  listen("scene", renderTracks);
  listen("selection", renderTracks);
  listen("time", updateClips);
}
