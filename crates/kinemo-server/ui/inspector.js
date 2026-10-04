// The inspector: the selected object's props (each with where it came from, editable when
// the code wrote it as a literal), or the selected timeline bar's call arguments.
"use strict";

import { clipSections } from "./clip_inspector.js";
import { positionEditor } from "./canvas.js";
import { pointEditor, propEditor, runsBadge, siteByKey, siteFor, valueEditor } from "./editing.js";
import { selectObject, clearSelection } from "./selection.js";
import { basename, editorLink, el, formatValue, listen, objectName, sourceLink, state, view } from "./state.js";

function sourceCell(source) {
  if (!source) return el("td", { class: "source" }, "");
  const kind = source.kind;
  let label = kind;
  if (kind === "animation") label = source.running ? `animation ${source.t0.toFixed(2)}–${source.t1.toFixed(2)}` : `animation (end ${source.t1.toFixed(2)})`;
  else if (kind === "set") label = `set @${source.t.toFixed(2)}`;
  else if (kind === "binding") label = "binding";
  else if (kind === "initial") label = "construction";
  else if (kind === "default") return el("td", { class: "source default", title: "not set in the scene: the prop's default" }, "default");
  const found = siteFor(source.span);
  const link = source.span && source.span.file ? sourceLink(source.span, `${label} :${source.span.line}`) : label;
  return el("td", { class: `source ${kind}` }, link, found ? runsBadge(found.site) : null);
}

function valueCell(object, name) {
  const current = object.props[name];
  const editor = propEditor(object, name);
  const shown = formatValue(current);
  if (!editor) return el("td", { class: "value" }, shown);
  const field = valueEditor(editor, current);
  if (!field) return el("td", { class: "value" }, shown);
  const source = object.prop_sources[name];
  const running = source && source.kind === "animation" && source.running;
  // While an animation runs, the literal is its target, not the value shown at this instant.
  return el("td", { class: "value" }, running ? el("span", { class: "now" }, shown, " → ") : null, field);
}

function argumentRows(site, key, filter = () => true, options = {}) {
  return site.arguments.filter(filter).map((argument) => {
    const editor = { key, site, target: argument.param || argument.keyword, argument, insertable: false };
    const name = argument.keyword || argument.param || `#${argument.index}`;
    const field = argument.param || argument.keyword ? valueEditor(editor, null, options) : el("code", { class: "computed" }, argument.text);
    return el("tr", {}, el("td", { class: "name" }, name), el("td", { class: "value", colspan: 2 }, field || argument.text));
  });
}

/** Optional parameters the call leaves out (`duration=`, `ease=`), shown with their default
 * and added to the call when edited. */
function missingRows(site, key) {
  const present = new Set(site.arguments.map((a) => a.param || a.keyword));
  return Object.entries(site.defaults || {})
    .filter(([name]) => !present.has(name))
    .map(([name, value]) => {
      const editor = { key, site, target: name, argument: null, insertable: true };
      const field = valueEditor(editor, null, { fallback: value });
      return el("tr", { class: "unset" }, el("td", { class: "name" }, name), el("td", { class: "value" }, field), el("td", { class: "source default" }, "default"));
    });
}

function positionRows(object) {
  const source = object.position_source || {};
  const rows = [];
  const drag = positionEditor(object);
  rows.push(
    el(
      "tr",
      {},
      el("td", { class: "name" }, "position"),
      el("td", { class: "value" }, positionValue(object, drag)),
      el("td", { class: "source", title: drag.changes ? "drag the object on the canvas to move it" : drag.reason }, positionText(source), drag.changes ? " ✥" : "")
    )
  );
  if (source.kind === "place" && source.span) {
    const found = siteFor(source.span);
    if (found) rows.push(...argumentRows(found.site, found.key, () => true, { point: object.position.map((v) => Math.round(v * 100) / 100) }));
  }
  const [bx0, by0, bx1, by1] = object.bbox;
  rows.push(el("tr", {}, el("td", { class: "name" }, "bbox"), el("td", { class: "value", colspan: 2 }, `[${bx0.toFixed(2)}, ${by0.toFixed(2)} → ${bx1.toFixed(2)}, ${by1.toFixed(2)}]`)));
  return rows;
}

/** The position, as two editable numbers when the code positions the object with literals. */
function positionValue(object, drag) {
  const [x, y] = object.position;
  if (!drag.changes) return `(${x.toFixed(2)}, ${y.toFixed(2)})`;
  const start = [Math.round(x * 1000) / 1000, Math.round(y * 1000) / 1000];
  return pointEditor(start, ([nx, ny]) => drag.changes(nx - start[0], ny - start[1]));
}

function positionText(src) {
  if (src.kind === "container") return `container ${objectName(src.container)}`;
  if (src.kind === "place") {
    const p = src.placement || {};
    const where = p.side ? `${p.side}=${objectName(p.target)}` : p.at ? `at=${p.at}` : "at=point";
    return src.span ? sourceLink(src.span, `place(${where}) :${src.span.line}`) : `place(${where})`;
  }
  return "free (x, y)";
}

function renderObject(object, t) {
  const label = object.label || object.name || `${object.kind}#${object.id}`;
  const rows = Object.keys(object.props).sort().map((name) =>
    el("tr", {}, el("td", { class: "name" }, name), valueCell(object, name), sourceCell(object.prop_sources && object.prop_sources[name]))
  );
  const ancestors = (object.ancestors || []).map((a) =>
    el("div", { class: "object-where" }, el("a", { href: "#", onclick: (e) => (e.preventDefault(), selectObject(a.id)) }, a.label || `${a.kind}#${a.id}`), " ", sourceLink(a.span))
  );
  const construction = siteFor(object.span);
  const constructionRows = construction ? argumentRows(construction.site, construction.key) : [];
  fill(
    head(label, object.kind),
    el("div", { class: "object-where" }, sourceLink(object.span), construction ? runsBadge(construction.site) : null, `  · id ${object.id}`),
    constructionRows.length ? el("div", { class: "section-title" }, `Construction · ${construction.site.callee}(…)`) : null,
    constructionRows.length ? el("table", { class: "props" }, ...constructionRows) : null,
    el("div", { class: "section-title" }, "Layout"),
    el("table", { class: "props" }, ...positionRows(object)),
    el("div", { class: "section-title" }, `Props at t = ${(t ?? state.t).toFixed(2)} s`),
    el("table", { class: "props" }, ...rows),
    ancestors.length ? el("div", { class: "section-title" }, "Inside") : null,
    ...ancestors
  );
  show(true);
}

function renderBar(bar) {
  const animation = siteByKey(bar.site);
  const call = bar.call !== bar.site ? siteByKey(bar.call) : null;
  const sections = [];
  if (animation) {
    sections.push(el("div", { class: "section-title" }, `Animation · ${animation.site.callee}(…)`, runsBadge(animation.site)));
    sections.push(el("table", { class: "props" }, ...argumentRows(animation.site, animation.key), ...missingRows(animation.site, animation.key)));
  }
  if (call) {
    sections.push(el("div", { class: "section-title" }, `Timing · ${call.site.callee}(…)`, runsBadge(call.site)));
    const timing = [...argumentRows(call.site, call.key, (a) => a.keyword !== null), ...missingRows(call.site, call.key)];
    sections.push(el("table", { class: "props" }, ...timing));
  }
  fill(
    head(bar.label, "animation"),
    el("div", { class: "object-where" }, editorLink(bar.file, bar.line, `${basename(bar.file)}:${bar.line}`), `  · ${bar.start.toFixed(2)}–${bar.end.toFixed(2)} s`),
    el("pre", { class: "code" }, bar.code),
    ...sections,
    bar.objects.length ? el("div", { class: "section-title" }, "Objects") : null,
    ...bar.objects.map((id) => el("div", { class: "object-where" }, el("a", { href: "#", onclick: (e) => (e.preventDefault(), selectObject(id)) }, objectName(id))))
  );
  show(true);
}

function head(label, kind) {
  return el(
    "div",
    { class: "object-head" },
    el("span", { class: "object-label" }, label),
    el("span", { class: "object-kind" }, kind),
    el("span", { class: "spacer" }),
    el("button", { class: "ghost", title: "Clear (Esc)", onclick: clearSelection }, "✕")
  );
}

/** Shows `nodes` in the inspector; conditional sections pass `null`, which is skipped. */
function fill(...nodes) {
  view.inspectorObject.replaceChildren(...nodes.filter((n) => n !== null && n !== undefined && n !== false));
}

function show(visible) {
  view.inspectorObject.classList.toggle("hidden", !visible);
  view.inspectorEmpty.classList.toggle("hidden", visible);
}

function renderClip(clip) {
  const kind = { voice: "narration", sound: "sound", music: "music" }[clip.role] || clip.role;
  const words = clip.label.split(/\s+/);
  const title = clip.narration && clip.narration.beat ? clip.narration.beat : words.length > 5 ? `${words.slice(0, 5).join(" ")}…` : clip.label;
  fill(head(title, kind), ...clipSections(clip));
  show(true);
}

function render(t) {
  if (state.editing) return;
  if (state.selectedClip !== null && state.meta && state.meta.tracks) return renderClip(state.meta.tracks[state.selectedClip]);
  if (state.selectedBar !== null && state.meta) return renderBar(state.meta.timeline[state.selectedBar]);
  if (state.pickedObject && state.selectedIds.length) return renderObject(state.pickedObject, t);
  show(false);
}

export function installInspector() {
  listen("inspector", render);
}
