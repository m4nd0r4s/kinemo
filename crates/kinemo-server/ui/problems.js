// Build status, the build-error overlay and the diagnostics list.
"use strict";

import { pause, setTime } from "./playback.js";
import { basename, el, listen, sourceLink, state, view } from "./state.js";

let dismissed = false;

export function setBuildStatus(ok, diagnostics) {
  const errors = (diagnostics || []).filter((d) => d.level === "error").length;
  const warnings = (diagnostics || []).length - errors;
  view.buildStatus.className = `build-status ${ok && !errors ? "ok" : "failed"}`;
  const parts = [ok ? (state.meta && state.meta.live ? "live edit" : "build ok") : "build failed"];
  if (errors) parts.push(`${errors} error(s)`);
  if (warnings) parts.push(`${warnings} warning(s)`);
  view.buildStatus.textContent = parts.join(" · ");
}

function diagnosticNode(d) {
  const span = d.spans && d.spans[0];
  return el(
    "div",
    { class: "diagnostic" },
    el("div", { class: "where" }, span ? sourceLink(span) : null, d.time !== null && d.time !== undefined ? `  t = ${d.time.toFixed(2)} s` : ""),
    el("pre", {}, d.rendered || `${d.code}: ${d.message}`)
  );
}

function onBuildError(msg) {
  setBuildStatus(false, msg.diagnostics);
  if (dismissed) return;
  view.errorBody.replaceChildren(...msg.diagnostics.map(diagnosticNode));
  view.errorOverlay.classList.remove("hidden");
}

function renderProblems(diagnostics) {
  if (!diagnostics || !diagnostics.length) return view.problems.replaceChildren();
  view.problems.replaceChildren(
    el("div", { class: "section-title" }, "Diagnostics"),
    ...diagnostics.map((d) => {
      const span = d.spans && d.spans[0];
      return el(
        "div",
        { class: `problem ${d.level}` },
        el("span", { class: "code" }, d.code),
        d.message,
        " ",
        span ? sourceLink(span, `:${span.line}`) : null,
        d.time !== null && d.time !== undefined
          ? el("a", { href: "#", onclick: (e) => (e.preventDefault(), pause(), setTime(d.time)) }, ` ${d.time.toFixed(2)} s`)
          : null
      );
    })
  );
}

function onScene() {
  const meta = state.meta;
  dismissed = false;
  view.errorOverlay.classList.add("hidden");
  const scenes = meta.scenes && meta.scenes.length > 1 ? ` (of ${meta.scenes.join(", ")})` : "";
  view.sceneTitle.textContent = `${basename(meta.file)} — ${meta.scene}${scenes} — v${state.version}`;
  setBuildStatus(true, meta.diagnostics);
  view.timeTotal.textContent = `/ ${meta.duration.toFixed(2)} s`;
  renderProblems(meta.diagnostics);
}

export function installProblems() {
  listen("message:error", onBuildError);
  listen("scene", onScene);
  document.getElementById("error-dismiss").addEventListener("click", () => {
    dismissed = true;
    view.errorOverlay.classList.add("hidden");
  });
}
