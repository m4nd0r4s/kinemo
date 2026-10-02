import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [sveltekit()],
  // The docs are read from the repository at build time (../docs).
  server: { fs: { allow: [".."] } },
});
