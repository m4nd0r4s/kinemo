import { error } from "@sveltejs/kit";
import { docPages, navigation, neighbours } from "$lib/server/docs";
import { renderedExamples } from "$lib/server/site-data";
import type { EntryGenerator, PageServerLoad } from "./$types";

/** Every Markdown file in docs/ is a page. */
export const entries: EntryGenerator = async () => (await docPages()).map((page) => ({ slug: page.slug }));

export const load: PageServerLoad = async ({ params }) => {
  const pages = await docPages();
  // Pages are folders (trailing slash on), so the parameter may end with "/".
  const slug = params.slug.replace(/\/$/, "");
  const page = pages.find((p) => p.slug === slug);
  if (!page) error(404, `No documentation page at docs/${slug}`);
  const [previous, next] = neighbours(pages, page);
  const exampleName = page.section === "Examples" ? page.slug.replace(/^examples\/?/, "") : "";
  return {
    url: page.url,
    title: page.title,
    section: page.section,
    html: page.rendered.html,
    toc: page.rendered.headings.filter((h) => h.level === 2 || h.level === 3),
    nav: navigation(pages),
    previous: previous && { url: previous.url, title: previous.title },
    next: next && { url: next.url, title: next.title },
    video: exampleName && renderedExamples().has(exampleName) ? exampleName : null,
  };
};
