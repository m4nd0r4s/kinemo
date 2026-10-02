import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

/** Every page is prerendered to static HTML with relative links, so `build/` works from
 * any web server or folder. */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    // KINEMO_SITE_OUT builds elsewhere (the test suite builds into a temporary folder).
    adapter: adapter({ pages: process.env.KINEMO_SITE_OUT ?? "build", assets: process.env.KINEMO_SITE_OUT ?? "build", strict: true }),
    paths: { relative: true },
    prerender: { handleHttpError: "fail", handleMissingId: "fail", entries: ["*"] },
  },
};

export default config;
