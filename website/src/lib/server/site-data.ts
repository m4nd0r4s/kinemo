import fs from "node:fs";
import path from "node:path";
import type { SiteData } from "$lib/site-data";

/** Written by `npm run export`; KINEMO_SITE_DATA points elsewhere (the test suite). */
const FILE = process.env.KINEMO_SITE_DATA ?? path.join(process.cwd(), "src", "lib", "generated", "site-data.json");

/** The exported data; the build stops with instructions when it has not been exported yet. */
export function siteData(): SiteData {
  if (!fs.existsSync(FILE)) {
    throw new Error("src/lib/generated/site-data.json is missing: run `npm run export` (website/export.py) before building the site.");
  }
  return JSON.parse(fs.readFileSync(FILE, "utf8")) as SiteData;
}

/** Example names that have a rendered video in static/media/. */
export function renderedExamples(): Set<string> {
  const media = path.join(process.cwd(), "static", "media");
  if (!fs.existsSync(media)) return new Set();
  return new Set(fs.readdirSync(media).filter((f) => f.endsWith(".mp4")).map((f) => f.replace(/\.mp4$/, "")));
}
