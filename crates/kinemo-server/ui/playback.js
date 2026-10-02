// Playhead, playback (with speed) and keyboard shortcuts.
"use strict";

import { requestFrame } from "./frames.js";
import { emit, fps, frameIndex, lastFrameTime, state, view } from "./state.js";

let playStartedAt = 0;
let playStartedT = 0;

export function setTime(t, force = false) {
  state.t = Math.min(Math.max(0, t), lastFrameTime());
  view.time.textContent = `${(frameIndex(state.t) / fps()).toFixed(2)} s`;
  requestFrame(state.t, force);
  emit("time", state.t);
}

export function play() {
  if (!state.meta) return;
  if (state.t >= lastFrameTime() - 1e-9) state.t = 0;
  state.playing = true;
  playStartedAt = performance.now();
  playStartedT = state.t;
  view.play.textContent = "❚❚";
  requestAnimationFrame(tick);
}

export function pause() {
  const was = state.playing;
  state.playing = false;
  view.play.textContent = "▶";
  if (was) emit("paused");
}

function tick(now) {
  if (!state.playing) return;
  let t = playStartedT + ((now - playStartedAt) / 1000) * state.speed;
  const end = lastFrameTime();
  if (t > end) {
    if (view.loop.checked) {
      playStartedAt = now;
      playStartedT = 0;
      t = 0;
    } else {
      setTime(end);
      pause();
      return;
    }
  }
  setTime(t);
  requestAnimationFrame(tick);
}

function setSpeed(speed) {
  if (state.playing) {
    playStartedT = state.t;
    playStartedAt = performance.now();
  }
  state.speed = speed;
}

export function step(frames) {
  pause();
  setTime((frameIndex(state.t) + frames) / fps(), true);
}

export function installPlayback() {
  window.addEventListener("keydown", (e) => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
    if (e.code === "Space") {
      e.preventDefault();
      state.playing ? pause() : play();
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      step(e.shiftKey ? -10 : -1);
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      step(e.shiftKey ? 10 : 1);
    } else if (e.key === "Home") {
      pause();
      setTime(0);
    } else if (e.key === "End") {
      pause();
      setTime(lastFrameTime());
    } else if (e.key === "Escape") {
      emit("escape");
    }
  });
  view.play.addEventListener("click", () => (state.playing ? pause() : play()));
  view.speed.addEventListener("change", () => setSpeed(Number(view.speed.value)));
  document.getElementById("step-back").addEventListener("click", () => step(-1));
  document.getElementById("step-forward").addEventListener("click", () => step(1));
}
