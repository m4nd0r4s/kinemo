// Syntax highlighting with Shiki's CSS-variables theme: token colors are `var(--shiki-…)`,
// set by code.css, so one highlighted HTML serves the light and the dark theme.

import { createCssVariablesTheme, createHighlighter, type BundledLanguage, type Highlighter } from "shiki";
import type { Token } from "$lib/site-data";

const theme = createCssVariablesTheme({ name: "css-variables", variablePrefix: "--shiki-", variableDefaults: {} });

/** Fence names used in the docs → Shiki languages. */
const LANGUAGES: Record<string, BundledLanguage> = { python: "python", py: "python", bash: "bash", sh: "bash", shell: "bash", toml: "toml", json: "json" };

let highlighter: Highlighter | null = null;

export async function getHighlighter(): Promise<Highlighter> {
  highlighter ??= await createHighlighter({ themes: [theme], langs: [...new Set(Object.values(LANGUAGES))] });
  return highlighter;
}

const escapeHtml = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

/** A `<pre class="code">` block; unknown languages (text, console output) stay plain. */
export function highlightBlock(h: Highlighter, code: string, lang: string): string {
  const language = LANGUAGES[lang.trim()];
  if (!language) return `<pre class="code"><code>${escapeHtml(code)}</code></pre>`;
  const html = h.codeToHtml(code, { lang: language, theme });
  return html.replace(/^<pre class="shiki css-variables"[^>]*>/, `<pre class="code lang-${language}">`);
}

/** The tokens of each line, for code that marks single lines (the landing page's studio). */
export function highlightLines(h: Highlighter, code: string, lang = "python"): Token[][] {
  return h.codeToTokensBase(code, { lang: LANGUAGES[lang] ?? "python", theme }).map((line) =>
    line.map((token) => ({ content: token.content, color: token.color }))
  );
}
