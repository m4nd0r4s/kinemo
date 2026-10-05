import { error, json } from "@sveltejs/kit";
import { docPages, docsVersion, docsVersions, searchIndex } from "$lib/server/docs";
import type { EntryGenerator, RequestHandler } from "./$types";

/** Written once at build time, like the pages. */
export const prerender = true;

export const entries: EntryGenerator = () => docsVersions().map((version) => ({ version: version.id }));

/** The search index of one version, loaded by the search dialog on first use. */
export const GET: RequestHandler = async ({ params }) => {
  if (!docsVersion(params.version)) error(404, `No docs version ${params.version}`);
  return json(searchIndex(await docPages(params.version)));
};
