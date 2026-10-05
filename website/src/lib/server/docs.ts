// The documentation pages: which Markdown file becomes which page, in what order, how links
// between them resolve, and the search index. Every published version has its own pages under
// /docs/<version>/: `dev` reads the repository's docs/, a release reads the docs/ extracted
// from its tag (website/.versions/<minor>/docs, written by `npm run export`), and `latest`
// is the newest release.

import fs from "node:fs";
import path from "node:path";
import { getHighlighter } from "./highlight";
import { createRenderer, type Rendered } from "./markdown";
import { siteData } from "./site-data";

/** The repository (the site is built from website/). */
export const ROOT = path.resolve(process.cwd(), "..");
export const DOCS = path.join(ROOT, "docs");

export interface DocsVersion {
  /** In URLs: `latest`, `0.11`, `dev`. */
  id: string;
  /** In the switcher: `0.11 (latest)`, `dev (unreleased)`. */
  label: string;
  /** The docs folder it is built from. */
  root: string;
}

/** Every published version, `latest` first, then the releases (newest first) and `dev`. */
export function docsVersions(): DocsVersion[] {
  const { latest, releases } = siteData().docs_versions ?? { latest: "dev", releases: [] };
  const release = (id: string) => path.join(process.cwd(), ".versions", id, "docs");
  const out: DocsVersion[] = [{ id: "latest", label: latest === "dev" ? "latest (unreleased)" : `latest (${latest})`, root: latest === "dev" ? DOCS : release(latest) }];
  for (const r of releases) out.push({ id: r.id, label: r.id, root: release(r.id) });
  out.push({ id: "dev", label: "dev (unreleased)", root: DOCS });
  return out;
}

export function docsVersion(id: string): DocsVersion | undefined {
  return docsVersions().find((v) => v.id === id);
}

export const SECTIONS = ["Overview", "Guide", "Reference", "Examples", "Project"] as const;
export type Section = (typeof SECTIONS)[number];

export interface DocPage {
  /** Markdown file, absolute. */
  source: string;
  /** Site path of the page, with a trailing slash (`/docs/latest/guide/timeline/`). */
  url: string;
  /** The page within its version (`guide/timeline`; empty for the overview). */
  slug: string;
  section: Section;
  /** Position in an ordered section (the guides), shown in the navigation. */
  number: number | null;
  title: string;
  rendered: Rendered;
}

/** Images next to a version's docs, served under /docs/<version>/ at the same relative path. */
export function docAssets(version: DocsVersion): string {
  return path.join(version.root, "examples", "images");
}

function orderedLinks(index: string): string[] {
  const seen: string[] = [];
  for (const match of fs.readFileSync(index, "utf8").matchAll(/\]\(([^)\s#]+\.md)(?:#[^)\s]*)?\)/g)) {
    const file = path.resolve(path.dirname(index), match[1]);
    if (path.dirname(file) === path.dirname(index) && file !== index && !seen.includes(file)) seen.push(file);
  }
  return seen;
}

function discover(version: DocsVersion): Omit<DocPage, "title" | "rendered">[] {
  const docs = version.root;
  const page = (source: string, slug: string, section: Section, number: number | null = null) => ({
    source,
    slug,
    url: slug ? `/docs/${version.id}/${slug}/` : `/docs/${version.id}/`,
    section,
    number,
  });
  const pages = [page(path.join(docs, "README.md"), "", "Overview")];
  const guides = fs.readdirSync(path.join(docs, "guide")).filter((f) => f.endsWith(".md")).sort();
  guides.forEach((file, i) => pages.push(page(path.join(docs, "guide", file), `guide/${file.replace(/^\d+-/, "").replace(/\.md$/, "")}`, "Guide", i + 1)));
  for (const [folder, section] of [["reference", "Reference"], ["examples", "Examples"]] as const) {
    const index = path.join(docs, folder, "README.md");
    if (!fs.existsSync(index)) continue;
    pages.push(page(index, folder, section));
    const listed = orderedLinks(index);
    const rest = fs.readdirSync(path.join(docs, folder)).filter((f) => f.endsWith(".md") && f !== "README.md").map((f) => path.join(docs, folder, f)).filter((f) => !listed.includes(f)).sort();
    for (const file of [...listed, ...rest]) pages.push(page(file, `${folder}/${path.basename(file, ".md")}`, section));
  }
  // Older versions may lack some project pages.
  for (const [file, slug] of [["caveats.md", "caveats"], ["status.md", "status"], ["specs.md", "specification"]]) {
    if (fs.existsSync(path.join(docs, file))) pages.push(page(path.join(docs, file), slug, "Project"));
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

const cache = new Map<string, DocPage[]>();

/** The pages of a version (`latest` when not given). */
export async function docPages(id = "latest"): Promise<DocPage[]> {
  const cached = cache.get(id);
  if (cached) return cached;
  const version = docsVersion(id);
  if (!version) throw new Error(`no docs version ${id}`);
  const docs = version.root;
  const render = createRenderer(await getHighlighter());
  const found = discover(version);
  const bySource = new Map(found.map((p) => [p.source, p]));
  const pages = found.map((p) => {
    const resolve = (target: string): string | null => {
      if (!target || target.startsWith("#")) return null;
      const [file, anchor] = target.split("#");
      const suffix = anchor ? `#${anchor}` : "";
      const absolute = path.resolve(path.dirname(p.source), file);
      const linked = bySource.get(absolute);
      if (linked) return relativeUrl(p.url, linked.url + suffix);
      if (absolute === path.join(docs, "llms.txt")) return relativeUrl(p.url, `/docs/${id}/llms.txt`);
      // The repository's examples folder (one level above docs/) stands for the examples page.
      if (absolute === path.join(path.dirname(docs), "examples")) return relativeUrl(p.url, `/docs/${id}/examples/${suffix}`);
      if (absolute.startsWith(docs + path.sep) && fs.existsSync(absolute)) {
        return relativeUrl(p.url, `/docs/${id}/${path.relative(docs, absolute).split(path.sep).join("/")}`);
      }
      return null;
    };
    const rendered = render(fs.readFileSync(p.source, "utf8"), resolve);
    return { ...p, title: rendered.title || path.basename(p.source, ".md"), rendered };
  });
  cache.set(id, pages);
  return pages;
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
