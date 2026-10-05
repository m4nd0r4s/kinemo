# kinemo website

A landing page and the full documentation, built with SvelteKit (Svelte 5, prerendered to
static files) from the repository. Nothing on the site is written twice:

- the docs pages are the Markdown in [`docs/`](../docs), read at build time with the same
  anchors (`src/lib/server/docs.ts`);
- every video is rendered by kinemo from [`examples/`](../examples);
- every terminal block is a real `kinemo check` run (on `examples/` and `snippets/`);
- the diff in "Edit the code from the preview" is made by the preview's own editing engine;
- the timings are measured against the budgets of `tests/python/test_performance.py`.

The last four need kinemo itself, so they come from a Python export step that writes
`src/lib/generated/site-data.json` and `static/media/`. The Svelte build reads them.

## Build

Needs kinemo built in the repository's `.venv` (`maturin develop`), `ffmpeg` and Node.

```bash
cd website
npm install
npm run export    # videos, check runs, timings → src/lib/generated/, static/media/
npm run build     # the static site → build/
npm run preview   # serves build/
```

`npm run dev` serves the site with hot reload while editing components or styles.

The first export renders the example videos (about half a minute); they are cached in
`website/.cache/` by source, so later exports take a few seconds. `export.py --no-videos`
skips renders that are not cached, and `--no-timings` skips the measurements.

The build fails when a page links to an `#anchor` that does not exist.
`tests/python/test_website.py` builds the site and checks every relative link as well.
`npm run check` type-checks the TypeScript and Svelte code.

The output in `build/` is static files with relative links: it works from any web server or
folder.

## Documentation versions

The docs are published per version under `/docs/<version>/`: `latest` (the newest release,
the default), the newest release of each minor version (`0.11`, `0.10`, ...) and `dev` (this
checkout, unreleased). `npm run export` extracts each release's `docs/` from its git tag into
`.versions/` (only tags reachable from the current commit), so the build needs the tags:
CI checks out with `fetch-depth: 0`. Addresses from before versions (`/docs/guide/...`)
redirect to `latest`.

## Screenshots of the preview

`static/img/editor-*.png` are captures of `kinemo dev`, taken with headless Chrome by
`capture.py`. The website workflow takes them again on every deploy, so the published site
always shows the current editor. To see them locally after a change to the preview UI:

```bash
../.venv/bin/python capture.py
```

## Layout

```
website/
  export.py, siteexport/   the Python export (media, check runs, edit, timings, link check)
  capture.py               screenshots of the preview
  snippets/                small scenes whose `kinemo check` output the landing page shows
  src/
    routes/                the landing page, docs/[...slug], search.json, llms.txt
    lib/server/            build-time code: docs discovery, Markdown, highlighting (Shiki)
    lib/components/        the header, search, landing sections, docs navigation
    lib/styles/            CSS: tokens and base, code, landing, docs
  static/img/              the favicon and the preview screenshots
```
