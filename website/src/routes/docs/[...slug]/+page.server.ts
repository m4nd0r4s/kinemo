import { error } from "@sveltejs/kit";
import { docPages, docsVersion, docsVersions, navigation, neighbours, relativeUrl } from "$lib/server/docs";
import { renderedExamples } from "$lib/server/site-data";
import type { EntryGenerator, PageServerLoad } from "./$types";

/** Every Markdown file of every version is a page (`latest/guide/timeline`); the addresses
 * from before versions (`guide/timeline`, and `/docs/` itself) redirect to `latest`. */
export const entries: EntryGenerator = async () => {
  const out: { slug: string }[] = [];
  for (const version of docsVersions()) {
    for (const page of await docPages(version.id)) out.push({ slug: page.slug ? `${version.id}/${page.slug}` : version.id });
  }
  for (const page of await docPages("latest")) out.push({ slug: page.slug });
  return out;
};

export const load: PageServerLoad = async ({ params }) => {
  // Pages are folders (trailing slash on), so the parameter may end with "/".
  const parts = params.slug.replace(/\/$/, "").split("/").filter(Boolean);
  const version = parts.length ? docsVersion(parts[0]) : undefined;
  if (!version) {
    const from = parts.length ? `/docs/${parts.join("/")}/` : "/docs/";
    const to = parts.length ? `/docs/latest/${parts.join("/")}/` : "/docs/latest/";
    return { redirect: relativeUrl(from, to) };
  }
  const slug = parts.slice(1).join("/");
  const pages = await docPages(version.id);
  const page = pages.find((p) => p.slug === slug);
  if (!page) error(404, `No documentation page at docs/${version.id}/${slug}`);
  const [previous, next] = neighbours(pages, page);
  const exampleName = page.section === "Examples" ? page.slug.replace(/^examples\/?/, "") : "";
  // The same page in every other version, or that version's overview when it has no such page.
  const versions = [];
  for (const other of docsVersions()) {
    const there = (await docPages(other.id)).find((p) => p.slug === slug);
    versions.push({ id: other.id, label: other.label, url: there ? there.url : `/docs/${other.id}/` });
  }
  return {
    redirect: null,
    url: page.url,
    title: page.title,
    section: page.section,
    html: page.rendered.html,
    toc: page.rendered.headings.filter((h) => h.level === 2 || h.level === 3),
    nav: navigation(pages),
    previous: previous && { url: previous.url, title: previous.title },
    next: next && { url: next.url, title: next.title },
    video: exampleName && renderedExamples().has(exampleName) ? exampleName : null,
    version: { id: version.id, label: version.label },
    versions,
  };
};
