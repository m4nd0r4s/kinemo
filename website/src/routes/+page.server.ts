import { getHighlighter, highlightBlock, highlightLines } from "$lib/server/highlight";
import { siteData } from "$lib/server/site-data";

const INSTALL = {
  pip: "pip install kinemo",
  source: "uv venv .venv\nuv pip install --python .venv/bin/python maturin\nsource .venv/bin/activate\nmaturin develop --release",
  start: "kinemo new hello\ncd hello",
  run: "kinemo dev scene.py      # live preview\nkinemo check scene.py    # errors and timeline, no rendering\nkinemo render scene.py   # MP4; also webm, mov, gif, png, slides",
};

export async function load() {
  const site = siteData();
  const highlighter = await getHighlighter();
  return {
    site,
    heroLines: highlightLines(highlighter, site.hero.source),
    install: Object.fromEntries(Object.entries(INSTALL).map(([key, code]) => [key, highlightBlock(highlighter, code, "bash")])) as Record<keyof typeof INSTALL, string>,
  };
}
