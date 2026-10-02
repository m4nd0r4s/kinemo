// Markdown → HTML for the docs: CommonMark with tables, Shiki-highlighted code, GitHub-style
// heading ids (the anchors the docs link to, checked by tests/python/test_doc_links.py) and
// links rewritten from `.md` files to the site's pages.

import MarkdownIt, { type Env as MarkdownEnv, type Token } from "markdown-it";
import type { Highlighter } from "shiki";
import { highlightBlock } from "./highlight";

export interface Heading {
  level: number;
  id: string;
  text: string;
}

export interface Rendered {
  html: string;
  title: string;
  headings: Heading[];
}

/** Maps a link target as written in the Markdown file to the href on the page, or `null` to keep it. */
export type LinkResolver = (target: string) => string | null;

/** GitHub-style anchor of a heading (the rule tests/python/test_doc_links.py checks). */
export function slug(heading: string): string {
  const text = heading.replace(/[`*_]|<[^>]+>/g, "").trim().toLowerCase();
  return text.replace(/[^\p{L}\p{N}\- ]/gu, "").replaceAll(" ", "-");
}

function plain(inline: Token): string {
  return (inline.children ?? [])
    .filter((child) => child.type === "text" || child.type === "code_inline")
    .map((child) => child.content)
    .join("");
}

/** What a render passes to the parser rules: how to resolve links, and where headings go. */
type Env = MarkdownEnv & { resolve: LinkResolver; headings: Heading[] };

export function createRenderer(highlighter: Highlighter): (text: string, resolve: LinkResolver) => Rendered {
  const md = new MarkdownIt("commonmark", { html: true, highlight: (code, lang) => highlightBlock(highlighter, code.replace(/\n$/, ""), lang) });
  md.enable("table");
  md.renderer.rules.table_open = () => '<div class="table-wrap"><table>\n';
  md.renderer.rules.table_close = () => "</table></div>\n";
  md.core.ruler.push("kinemo_headings", (state) => {
    (state.env as Env).headings = numberHeadings(state.tokens, (type) => new state.Token(type, "", 0));
  });
  md.core.ruler.push("kinemo_links", (state) => rewriteLinks(state.tokens, (state.env as Env).resolve));

  return (text, resolve) => {
    const env: Env = { resolve, headings: [] };
    const html = md.render(text, env);
    return { html, title: env.headings.find((h) => h.level === 1)?.text ?? "", headings: env.headings };
  };
}

function numberHeadings(tokens: Token[], newToken: (type: string) => Token): Heading[] {
  const seen = new Map<string, number>();
  const out: Heading[] = [];
  tokens.forEach((token, i) => {
    if (token.type !== "heading_open") return;
    const inline = tokens[i + 1];
    const base = slug(inline.content);
    const n = seen.get(base) ?? 0;
    seen.set(base, n + 1);
    const id = n === 0 ? base : `${base}-${n}`;
    token.attrSet("id", id);
    const level = Number(token.tag.slice(1));
    out.push({ level, id, text: plain(inline) });
    if (level === 2 || level === 3) {
      // A visible link to the section, for copying.
      const permalink = newToken("html_inline");
      permalink.content = `<a class="permalink" href="#${id}" aria-label="Link to this section">#</a>`;
      inline.children?.push(permalink);
    }
  });
  return out;
}

function rewriteLinks(tokens: Token[], resolve: LinkResolver): void {
  for (const token of tokens) {
    for (const child of token.children ?? []) {
      const attribute = child.type === "link_open" ? "href" : child.type === "image" ? "src" : null;
      if (!attribute) continue;
      const target = String(child.attrGet(attribute) ?? "");
      if (/^[a-z][a-z0-9+.-]*:/.test(target)) {
        if (child.type === "link_open") child.attrSet("rel", "noopener");
        continue;
      }
      const resolved = resolve(target);
      if (resolved !== null) child.attrSet(attribute, resolved);
    }
  }
}
