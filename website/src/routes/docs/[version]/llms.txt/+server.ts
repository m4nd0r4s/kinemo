import fs from "node:fs";
import path from "node:path";
import { error } from "@sveltejs/kit";
import { docsVersion, docsVersions } from "$lib/server/docs";
import type { EntryGenerator, RequestHandler } from "./$types";

/** Written once at build time, like the pages. */
export const prerender = true;

export const entries: EntryGenerator = () => docsVersions().map((version) => ({ version: version.id }));

/** The compact API reference for language models of each version (its docs/llms.txt). */
export const GET: RequestHandler = ({ params }) => {
  const version = docsVersion(params.version);
  const file = version && path.join(version.root, "llms.txt");
  if (!file || !fs.existsSync(file)) error(404, `No llms.txt for ${params.version}`);
  return new Response(fs.readFileSync(file, "utf8"), { headers: { "content-type": "text/plain; charset=utf-8" } });
};
