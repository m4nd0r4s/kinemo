// Narration, sounds and music of the scene, played in sync with the playhead (Web Audio), with
// a mute switch. Clips are scheduled from the playhead when playback starts, loops or changes
// speed, and again if the playhead drifts from the audio clock (a seek while playing). Music
// is mixed like the render: it fades in and out and drops to `duck` while a voice speaks.
"use strict";

import { listen, state } from "./state.js";

const MUTE_KEY = "kinemo-dev-muted";
/** Seconds the playhead may drift from the audio before the clips are scheduled again. */
const DRIFT = 0.15;
/** Music level automation: samples per second, and the ramps into and out of a duck
 *  (the render's compressor attacks in 20 ms and releases in 300 ms). */
const LEVEL_RATE = 50;
const DUCK_ATTACK = 0.02;
const DUCK_RELEASE = 0.3;

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

/** The track entry (role, duck, fade) of the played clip `index`. */
function trackOf(index) {
  return ((state.meta && state.meta.tracks) || []).find((track) => track.index === index);
}

/** Level of a music clip at scene time `t` (0..1, before its gain): its fades and the duck
 *  while any voice sounds. Exported for checks from the console. */
export function musicLevel(track, voices, t) {
  const end = state.meta.duration;
  let level = 1;
  if (track.fade > 0) {
    level *= Math.min(1, Math.max(0, (t - track.start) / track.fade));
    level *= Math.min(1, Math.max(0, (end - t) / track.fade));
  }
  if (track.duck > 0 && track.duck < 1) {
    let depth = 0; // 1 inside a voice, ramping at its edges
    for (const [a, b] of voices) {
      if (t >= a - DUCK_ATTACK && t <= b + DUCK_RELEASE) {
        const into = Math.min(1, (t - (a - DUCK_ATTACK)) / DUCK_ATTACK);
        const out = t > b ? 1 - (t - b) / DUCK_RELEASE : 1;
        depth = Math.max(depth, Math.max(0, Math.min(into, out)));
      }
    }
    level *= 1 - depth * (1 - track.duck);
  }
  return level;
}

/** Schedule `gain` to follow the music level from scene time `from`, at playback `speed`. */
function automateMusic(gain, track, base, from, clock, speed) {
  const voices = ((state.meta && state.meta.tracks) || []).filter((t) => t.role === "voice" && t.index !== null).map((t) => [t.start, t.end]);
  const until = state.meta.duration;
  const samples = Math.max(2, Math.ceil((until - from) * LEVEL_RATE));
  const curve = new Float32Array(samples);
  for (let i = 0; i < samples; i++) curve[i] = base * musicLevel(track, voices, from + ((until - from) * i) / (samples - 1));
  gain.gain.setValueCurveAtTime(curve, clock, Math.max(0.01, (until - from) / speed));
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
    const track = trackOf(i);
    if (track && track.role === "music") automateMusic(gain, track, clip.gain, Math.max(from, clip.t), clock + Math.max(0, (clip.t - from) / speed), speed);
    source.connect(gain).connect(ctx.destination);
    const delay = Math.max(0, (clip.t - from) / speed);
    source.start(clock + delay, Math.max(0, from - clip.t));
    // Music stops with the scene, like the render.
    if (track && track.role === "music") source.stop(clock + Math.max(0, (state.meta.duration - from) / speed));
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
