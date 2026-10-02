// The documentation pages: which Markdown file becomes which page, in what order, how links
// between them resolve, and the search index. Read from the repository's docs/ at build time.

import fs from "node:fs";
import path from "node:path";
import { getHighlighter } from "./highlight";
import { createRenderer, type Rendered } from "./markdown";

/** The repository (the site is built from website/). */
export const ROOT = path.resolve(process.cwd(), "..");
export const DOCS = path.join(ROOT, "docs");

export const SECTIONS = ["Overview", "Guide", "Reference", "Examples", "Project"] as const;
export type Section = (typeof SECTIONS)[number];

export interface DocPage {
  /** Markdown file, absolute. */
  source: string;
  /** Site path of the page, with a trailing slash (`/docs/guide/timeline/`). */
  url: string;
  /** Route parameter of `/docs/[...slug]` (`guide/timeline`; empty for the overview). */
  slug: string;
  section: Section;
  /** Position in an ordered section (the guides), shown in the navigation. */
  number: number | null;
  title: string;
  rendered: Rendered;
}

/** Repository folders the docs link to, and the page that stands for them on the site. */
const REPOSITORY_LINKS: Record<string, string> = { [path.join(ROOT, "examples")]: "/docs/examples/" };

/** Images and other files next to the docs, served under /docs/ at the same relative path. */
export const DOC_ASSETS = path.join(DOCS, "examples", "images");

function orderedLinks(index: string): string[] {
  const seen: string[] = [];
  for (const match of fs.readFileSync(index, "utf8").matchAll(/\]\(([^)\s#]+\.md)(?:#[^)\s]*)?\)/g)) {
    const file = path.resolve(path.dirname(index), match[1]);
    if (path.dirname(file) === path.dirname(index) && file !== index && !seen.includes(file)) seen.push(file);
  }
  return seen;
}

function discover(): Omit<DocPage, "title" | "rendered">[] {
  const page = (source: string, slug: string, section: Section, number: number | null = null) => ({
    source,
    slug,
    url: slug ? `/docs/${slug}/` : "/docs/",
    section,
    number,
  });
  const pages = [page(path.join(DOCS, "README.md"), "", "Overview")];
  const guides = fs.readdirSync(path.join(DOCS, "guide")).filter((f) => f.endsWith(".md")).sort();
  guides.forEach((file, i) => pages.push(page(path.join(DOCS, "guide", file), `guide/${file.replace(/^\d+-/, "").replace(/\.md$/, "")}`, "Guide", i + 1)));
  for (const [folder, section] of [["reference", "Reference"], ["examples", "Examples"]] as const) {
    const index = path.join(DOCS, folder, "README.md");
    pages.push(page(index, folder, section));
    const listed = orderedLinks(index);
    const rest = fs.readdirSync(path.join(DOCS, folder)).filter((f) => f.endsWith(".md") && f !== "README.md").map((f) => path.join(DOCS, folder, f)).filter((f) => !listed.includes(f)).sort();
    for (const file of [...listed, ...rest]) pages.push(page(file, `${folder}/${path.basename(file, ".md")}`, section));
  }
  for (const [file, slug] of [["caveats.md", "caveats"], ["status.md", "status"], ["specs.md", "specification"]]) {
    pages.push(page(path.join(DOCS, file), slug, "Project"));
  }
  return pages;
}

/** Relative link from the page at `from` (a URL ending in `/`) to the site path `to`
 * (a page ending in `/`, or a file), keeping any `#anchor`. */
export function relativeUrl(from: string, to: string): string {
  const [target, hash] = to.split("#");
  const strip = (p: string) => p.replace(/\/$/, "") || "/";
  const link = path.posix.relative(strip(from), strip(target));
  const folder = target.endsWith("/");
  const href = link === "" ? "./" : folder ? `${link}/` : link;
  return hash ? `${href}#${hash}` : href;
}

let cache: DocPage[] | null = null;

export async function docPages(): Promise<DocPage[]> {
  if (cache) return cache;
  const render = createRenderer(await getHighlighter());
  const found = discover();
  const bySource = new Map(found.map((p) => [p.source, p]));
  cache = found.map((p) => {
    const resolve = (target: string): string | null => {
      if (!target || target.startsWith("#")) return null;
      const [file, anchor] = target.split("#");
      const suffix = anchor ? `#${anchor}` : "";
      const absolute = path.resolve(path.dirname(p.source), file);
      const linked = bySource.get(absolute);
      if (linked) return relativeUrl(p.url, linked.url + suffix);
      if (absolute === path.join(DOCS, "llms.txt")) return relativeUrl(p.url, "/llms.txt");
      if (REPOSITORY_LINKS[absolute]) return relativeUrl(p.url, REPOSITORY_LINKS[absolute] + suffix);
      if (absolute.startsWith(DOCS + path.sep) && fs.existsSync(absolute)) {
        return relativeUrl(p.url, `/docs/${path.relative(DOCS, absolute).split(path.sep).join("/")}`);
      }
      return null;
    };
    const rendered = render(fs.readFileSync(p.source, "utf8"), resolve);
    return { ...p, title: rendered.title || path.basename(p.source, ".md"), rendered };
  });
  return cache;
}

export function neighbours(pages: DocPage[], page: DocPage): [DocPage | null, DocPage | null] {
  const same = pages.filter((p) => p.section === page.section);
  const i = same.indexOf(page);
  return [same[i - 1] ?? null, same[i + 1] ?? null];
}

export interface NavGroup {
  section: Section;
  items: { url: string; title: string; number: number | null }[];
}

export function navigation(pages: DocPage[]): NavGroup[] {
  return SECTIONS.map((section) => ({
    section,
    items: pages
      .filter((p) => p.section === section)
      .map((p) => ({ url: p.url, number: p.number, title: p.slug === "reference" || p.slug === "examples" ? "Overview" : p.title })),
  }));
}

// ---- search ---------------------------------------------------------------------------

export interface SearchEntry {
  page: string;
  section: string;
  url: string;
  text: string;
}

const clean = (fragment: string) =>
  fragment.replace(/<[^>]+>/g, " ").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&").replace(/\s+/g, " ").trim();

/** One entry per section (h2 to h4: the reference documents each symbol under an h4). */
export function searchIndex(pages: DocPage[]): SearchEntry[] {
  const out: SearchEntry[] = [];
  for (const page of pages) {
    for (const chunk of page.rendered.html.split(/(?=<h[234] id=")/)) {
      const match = chunk.match(/^<h([234]) id="([^"]+)">([\s\S]*?)<\/h\1>/);
      const section = match ? clean(match[3]).replace(/#$/, "").trim() : "";
      const text = clean(match ? chunk.slice(match[0].length) : chunk);
      if (!section && !text) continue;
      out.push({ page: page.title, section, url: page.url.slice(1) + (match ? `#${match[2]}` : ""), text: text.slice(0, 280) });
    }
  }
  return out;
}
