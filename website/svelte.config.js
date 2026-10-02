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
    prerender: {
      handleHttpError: ({ path, message }) => {
        // A build without rendered videos (the test suite, `export.py --no-videos`) declares
        // it with KINEMO_SITE_NO_MEDIA; any other missing file fails the build.
        if (process.env.KINEMO_SITE_NO_MEDIA && path.startsWith("/media/")) return;
        throw new Error(message);
      },
      handleMissingId: "fail",
      entries: ["*"],
    },
  },
};

export default config;
