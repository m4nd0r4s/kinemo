import fs from "node:fs";
import path from "node:path";
import { error } from "@sveltejs/kit";
import { DOC_ASSETS } from "$lib/server/docs";
import type { EntryGenerator, RequestHandler } from "./$types";

/** Written once at build time, like the pages. */
export const prerender = true;

/** The example frames the docs embed (docs/examples/images/), served at the same path. */
export const entries: EntryGenerator = () => fs.readdirSync(DOC_ASSETS).filter((f) => f.endsWith(".png")).map((file) => ({ file }));

export const GET: RequestHandler = ({ params }) => {
  const file = path.join(DOC_ASSETS, path.basename(params.file));
  if (!fs.existsSync(file)) error(404, `No image ${params.file}`);
  return new Response(fs.readFileSync(file), { headers: { "content-type": "image/png" } });
};
