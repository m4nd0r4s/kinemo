import fs from "node:fs";
import path from "node:path";
import { docsVersion } from "$lib/server/docs";

/** Written once at build time, like the pages. */
export const prerender = true;

/** The compact API reference for language models, of the latest release (its docs/llms.txt). */
export function GET() {
  return new Response(fs.readFileSync(path.join(docsVersion("latest")!.root, "llms.txt"), "utf8"), { headers: { "content-type": "text/plain; charset=utf-8" } });
}
