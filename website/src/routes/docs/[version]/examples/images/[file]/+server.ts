import fs from "node:fs";
import path from "node:path";
import { error } from "@sveltejs/kit";
import { docAssets, docsVersion, docsVersions } from "$lib/server/docs";
import type { EntryGenerator, RequestHandler } from "./$types";

/** Written once at build time, like the pages. */
export const prerender = true;

/** The example frames each version's docs embed (docs/examples/images/), at the same path. */
export const entries: EntryGenerator = () =>
  docsVersions().flatMap((version) => {
    const folder = docAssets(version);
    return fs.existsSync(folder) ? fs.readdirSync(folder).filter((f) => f.endsWith(".png")).map((file) => ({ version: version.id, file })) : [];
  });

export const GET: RequestHandler = ({ params }) => {
  const version = docsVersion(params.version);
  const file = version && path.join(docAssets(version), path.basename(params.file));
  if (!file || !fs.existsSync(file)) error(404, `No image ${params.file}`);
  return new Response(fs.readFileSync(file), { headers: { "content-type": "image/png" } });
};
