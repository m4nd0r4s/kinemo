import { siteData } from "$lib/server/site-data";

/** The kinemo version the site documents, shown in the footer. */
export function load() {
  return { version: siteData().version };
}
