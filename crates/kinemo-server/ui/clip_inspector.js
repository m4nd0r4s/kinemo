// The inspector of an audio clip: for narration, its full text with each word's time (a click
// moves the playhead there), the beat and its script line, the audio file and where the word
// times come from, the warnings on its line, and a button that plays just that line.
"use strict";

import { pause, playRange, setTime } from "./playback.js";
import { basename, el, sourceLink, state } from "./state.js";

const TIMING = {
  provider: "from the TTS provider",
  aligned: "aligned to the audio (speech recognition)",
  syllables: "estimated from syllables",
  estimated: "estimated: no audio yet",
};

/** Warnings and errors reported on the clip's source line (W1403, W1404, W1405, ...). */
function diagnosticsOn(span) {
  if (!span || !state.meta) return [];
  return state.meta.diagnostics.filter((d) => d.spans.some((s) => s.file === span.file && s.line === span.line));
}

function wordNodes(words) {
  return words.flatMap(([word, start], i) => [
    i ? " " : null,
    el("span", { class: "word", title: `${start.toFixed(2)} s`, onclick: () => (pause(), setTime(start, true)) }, word),
  ]).filter((node) => node !== null);
}

export function clipSections(clip) {
  const narration = clip.narration;
  const sections = [
    el(
      "div",
      { class: "object-where" },
      clip.span ? sourceLink(clip.span) : null,
      `  · ${clip.start.toFixed(2)}–${clip.end.toFixed(2)} s`
    ),
    el("div", { class: "clip-actions" }, el("button", { class: "ghost", onclick: () => playRange(clip.start, clip.end) }, "▶ play this line")),
  ];
  if (narration) {
    sections.push(el("div", { class: "section-title" }, "Text"));
    sections.push(el("p", { class: "clip-text" }, ...(narration.words.length ? wordNodes(narration.words) : [narration.text])));
  }
  const rows = [];
  if (narration && narration.beat) {
    const script = narration.script;
    rows.push(["beat", script ? sourceLink({ file: script.file, line: script.line || 1 }, `${narration.beat} · ${basename(script.file)}:${script.line}`) : narration.beat]);
  }
  rows.push(["audio", clip.file ? el("span", { title: clip.file }, basename(clip.file)) : "none yet"]);
  if (narration) rows.push(["word times", TIMING[narration.timing] || narration.timing]);
  if (narration && narration.voice) rows.push(["voice", narration.voice]);
  rows.push(["gain", String(clip.gain)]);
  if (clip.role === "music") rows.push(["duck", String(clip.duck)], ["fade", `${clip.fade} s`]);
  sections.push(el("div", { class: "section-title" }, "Audio"));
  sections.push(el("table", { class: "props" }, ...rows.map(([name, value]) => el("tr", {}, el("td", { class: "name" }, name), el("td", { class: "value" }, value)))));
  const problems = diagnosticsOn(clip.span);
  if (problems.length) {
    sections.push(el("div", { class: "section-title" }, "Problems"));
    sections.push(...problems.map((d) => el("div", { class: `clip-problem ${d.level}` }, el("strong", {}, d.code), ` ${d.message}`)));
  }
  return sections;
}
