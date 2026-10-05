// The data `website/export.py` writes (src/lib/generated/site-data.json): real output of
// kinemo, produced from the repository before the site is built.

/** A highlighted piece of a code line; `color` is a CSS value such as `var(--shiki-token-keyword)`. */
export interface Token {
  content: string;
  color?: string;
}

export interface Bar {
  start: number;
  end: number;
  label: string;
  line: number;
}

export interface Example {
  name: string;
  title: string;
  about: string;
  features: string[];
  duration: number;
}

export interface Run {
  command: string;
  output: string;
}

export interface Timing {
  what: string;
  budget: string;
  measured: string;
  ok: boolean;
}

/** The docs versions the site publishes (website/siteexport/versions.py). */
export interface DocsVersions {
  /** The release `/docs/latest/` shows (`dev` when the checkout has no release tag). */
  latest: string;
  /** Newest first: the newest release of each minor version. */
  releases: { id: string; tag: string }[];
}

export interface SiteData {
  version: string;
  docs_versions: DocsVersions;
  hero: { name: string; source: string; duration: number; bars: Bar[] };
  examples: Example[];
  checks: { timeline: Run; constraint: Run; manim: Run; json: Run };
  edit: { before: string; after: string; line: number };
  timings: Timing[];
  machine: string;
}

/** Escaped text with `backticks` as <code> (the examples' descriptions use them). */
export function inlineCode(text: string): string {
  const escaped = text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
  return escaped.replace(/`([^`]+)`/g, "<code>$1</code>");
}
