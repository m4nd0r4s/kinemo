// Narration and sounds of the scene, played in sync with the playhead (Web Audio), with a
// mute switch. Clips are scheduled from the playhead when playback starts, loops or changes
// speed, and again if the playhead drifts from the audio clock (a seek while playing).
"use strict";

import { listen, state } from "./state.js";

const MUTE_KEY = "kinemo-dev-muted";
/** Seconds the playhead may drift from the audio before the clips are scheduled again. */
const DRIFT = 0.15;

let context = null;
let sources = [];
let anchor = null; // { clock, t, speed }: the audio clock at a playhead time
let generation = 0; // bumps on every (re)schedule, so late decodes do not start old clips
const buffers = new Map(); // url → Promise<AudioBuffer | null>
let muted = readMuted();

function readMuted() {
  try {
    return localStorage.getItem(MUTE_KEY) === "1";
  } catch {
    return false;
  }
}

function audioContext() {
  if (!context) context = new AudioContext();
  return context;
}

function clips() {
  return (state.meta && state.meta.audio) || [];
}

function buffer(url) {
  if (!buffers.has(url)) {
    const decoded = fetch(url)
      .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(r.statusText))))
      .then((bytes) => audioContext().decodeAudioData(bytes))
      .catch(() => null);
    buffers.set(url, decoded);
  }
  return buffers.get(url);
}

function stopAll() {
  generation += 1;
  for (const source of sources) {
    try {
      source.stop();
    } catch {
      // already ended
    }
  }
  sources = [];
  anchor = null;
}

/** Start every clip that sounds at or after playhead time `t`. */
async function scheduleFrom(t) {
  stopAll();
  if (muted || !state.playing || clips().length === 0) return;
  const mine = generation;
  const ctx = audioContext();
  await ctx.resume();
  const decoded = await Promise.all(clips().map((clip) => buffer(clip.url)));
  if (mine !== generation || !state.playing) return;
  const speed = state.speed;
  // The playhead moved while decoding: start from where it is now.
  const from = state.t;
  const clock = ctx.currentTime + 0.03;
  anchor = { clock, t: from, speed };
  clips().forEach((clip, i) => {
    const audio = decoded[i];
    if (!audio || clip.t + audio.duration <= from) return;
    const source = ctx.createBufferSource();
    source.buffer = audio;
    source.playbackRate.value = speed;
    const gain = ctx.createGain();
    gain.gain.value = clip.gain;
    source.connect(gain).connect(ctx.destination);
    const delay = Math.max(0, (clip.t - from) / speed);
    source.start(clock + delay, Math.max(0, from - clip.t));
    sources.push(source);
  });
}

function onTime(t) {
  if (!state.playing || !anchor || !context) return;
  const expected = anchor.t + (context.currentTime - anchor.clock) * anchor.speed;
  if (Math.abs(expected - t) > DRIFT) scheduleFrom(t);
}

function setMuted(value) {
  muted = value;
  try {
    localStorage.setItem(MUTE_KEY, muted ? "1" : "0");
  } catch {
    // private window: the choice lasts for this page only
  }
  const button = document.getElementById("mute");
  button.textContent = muted ? "🔇" : "🔊";
  button.title = muted ? "Sound off (M)" : "Sound on (M)";
  if (muted) stopAll();
  else if (state.playing) scheduleFrom(state.t);
}

export function installAudio() {
  const button = document.getElementById("mute");
  button.addEventListener("click", () => setMuted(!muted));
  window.addEventListener("keydown", (e) => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
    if (e.key === "m" || e.key === "M") setMuted(!muted);
  });
  setMuted(muted);
  listen("playing", () => scheduleFrom(state.t));
  listen("paused", stopAll);
  listen("time", onTime);
  listen("scene", () => {
    buffers.clear();
    // Decode ahead, so pressing play starts the sound at once.
    if (!muted) clips().forEach((clip) => buffer(clip.url));
    if (state.playing) scheduleFrom(state.t);
  });
}
