// Color editor: a swatch that opens a popover with kinemo's palette (written as `k.RED`),
// the theme's tokens (`k.theme.accent`) and a free color (picker or hex, written as
// "#rrggbb").
"use strict";

import { el, state } from "./state.js";

let open = null; // the popover currently shown

function close() {
  if (!open) return;
  open.remove();
  open = null;
}

function swatch(hex, title, onPick) {
  return el("button", { class: "swatch-button", style: `background:${hex}`, title, onclick: onPick });
}

/**
 * `hex` is the current color, `label` how the code writes it (`k.RED`), `alias` the name
 * kinemo is imported as (named colors need it), `onCode(text)` receives the Python source.
 */
export function colorField({ hex, label, alias, onCode }) {
  const shown = hex || "#ffffff";
  const field = el(
    "span",
    { class: "edit color-field", title: "click to choose a color" },
    el("span", { class: "swatch", style: `background:${shown}` }),
    label || shown
  );
  field.addEventListener("click", (e) => {
    e.stopPropagation();
    if (open && open.dataset.owner === String(field.dataset.id)) return close();
    openPopover(field, shown, alias, (code) => {
      close();
      onCode(code);
    });
  });
  return field;
}

function openPopover(field, current, alias, pick) {
  close();
  const colors = (state.meta && state.meta.palette && state.meta.palette.colors) || {};
  const named = Object.entries(colors).filter(([name]) => !name.startsWith("theme."));
  const theme = Object.entries(colors).filter(([name]) => name.startsWith("theme."));
  const code = (name, hex) => (alias ? `${alias}.${name}` : JSON.stringify(hex));
  const custom = el("input", { type: "color", class: "picker", value: current.slice(0, 7) });
  const hexInput = el("input", { class: "hex-input", value: current.slice(0, 7), spellcheck: "false" });
  custom.addEventListener("input", () => (hexInput.value = custom.value));
  hexInput.addEventListener("input", () => {
    if (/^#[0-9a-fA-F]{6}$/.test(hexInput.value)) custom.value = hexInput.value;
  });
  const apply = () => {
    const value = hexInput.value.trim();
    if (/^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$/.test(value)) pick(JSON.stringify(value.toLowerCase()));
  };
  hexInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") apply();
    e.stopPropagation();
  });
  open = el(
    "div",
    { class: "color-popover" },
    el("div", { class: "popover-title" }, "Palette"),
    el("div", { class: "swatches" }, ...named.map(([name, hex]) => swatch(hex, `${alias || "k"}.${name}  ${hex}`, () => pick(code(name, hex))))),
    theme.length && alias ? el("div", { class: "popover-title" }, "Theme") : null,
    theme.length && alias
      ? el("div", { class: "swatches" }, ...theme.map(([name, hex]) => swatch(hex, `${alias}.${name}  ${hex}`, () => pick(`${alias}.${name}`))))
      : null,
    el("div", { class: "popover-title" }, "Custom"),
    el("div", { class: "custom-row" }, custom, hexInput, el("button", { onclick: apply }, "Apply"))
  );
  open.addEventListener("pointerdown", (e) => e.stopPropagation());
  document.body.append(open);
  const box = field.getBoundingClientRect();
  const width = open.offsetWidth;
  open.style.left = `${Math.max(8, Math.min(window.innerWidth - width - 8, box.left))}px`;
  open.style.top = `${Math.min(window.innerHeight - open.offsetHeight - 8, box.bottom + 6)}px`;
}

export function installColorPicker() {
  window.addEventListener("pointerdown", close);
  window.addEventListener(
    "keydown",
    (e) => {
      if (e.key === "Escape" && open) {
        e.stopPropagation();
        close();
      }
    },
    true
  );
}
