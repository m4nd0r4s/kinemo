import fs from "node:fs";
import path from "node:path";
import { DOCS } from "$lib/server/docs";

/** Written once at build time, like the pages. */
export const prerender = true;

/** The compact API reference for language models, generated from the code (docs/llms.txt). */
export function GET() {
  return new Response(fs.readFileSync(path.join(DOCS, "llms.txt"), "utf8"), { headers: { "content-type": "text/plain; charset=utf-8" } });
}
