import { json } from "@sveltejs/kit";
import { docPages, searchIndex } from "$lib/server/docs";

/** Written once at build time, like the pages. */
export const prerender = true;

/** The search index, one entry per docs section, loaded by the search dialog on first use. */
export async function GET() {
  return json(searchIndex(await docPages()));
}
