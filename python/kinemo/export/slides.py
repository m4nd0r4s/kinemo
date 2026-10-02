"""`kinemo render --format slides`: one video per section and an HTML player that waits
for a key at every `s.mark(slide=True)`."""

from __future__ import annotations

import html
import json
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..scene.scene import Scene

PLAYER = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  html, body {{ margin: 0; height: 100%; background: #000; overflow: hidden; }}
  video {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; }}
  #hud {{ position: fixed; right: 16px; bottom: 12px; color: #9aa0aa; font: 13px system-ui, sans-serif; opacity: .7; }}
</style>
</head>
<body>
<video id="v" playsinline muted></video>
<div id="hud"></div>
<script>
const sections = {sections};
const v = document.getElementById("v"), hud = document.getElementById("hud");
let i = 0;
function show(k, autoplay) {{
  i = Math.max(0, Math.min(sections.length - 1, k));
  v.src = sections[i].file;
  hud.textContent = `${{i + 1}} / ${{sections.length}}` + (sections[i].name ? ` · ${{sections[i].name}}` : "");
  if (autoplay) v.play();
}}
document.addEventListener("keydown", (e) => {{
  if (["ArrowRight", " ", "PageDown", "Enter"].includes(e.key)) {{
    if (!v.ended && !v.paused) {{ v.currentTime = v.duration; return; }}
    if (i < sections.length - 1) show(i + 1, true);
  }} else if (["ArrowLeft", "PageUp"].includes(e.key)) {{
    show(i - 1, true);
  }} else if (e.key === "f") {{
    document.documentElement.requestFullscreen?.();
  }}
}});
document.addEventListener("click", () => document.dispatchEvent(new KeyboardEvent("keydown", {{ key: "ArrowRight" }})));
show(0, true);
</script>
</body>
</html>
"""


def sections(s: "Scene") -> list[tuple[float, float, str | None]]:
    """(start, end, name) of every section between slide breaks."""
    breaks = sorted((t, name) for name, t, slide, _ in s._marks if slide)
    starts = [(0.0, None)] + [(t, name) for t, name in breaks if 0.0 < t < s.duration]
    out = []
    for k, (t, name) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else s.duration
        if end - t > 1e-6:
            out.append((t, end, name))
    return out


def export(s: "Scene", out_dir: str, quality: str = "final") -> str:
    """Render the sections and write `index.html`. Returns the HTML path."""
    folder = os.path.join(out_dir, f"{s.config.name}_slides")
    os.makedirs(folder, exist_ok=True)
    entries = []
    for k, (start, end, name) in enumerate(sections(s)):
        file = f"section_{k + 1:02d}.mp4"
        s.builder.render_section(os.path.join(folder, file), start, end, "mp4", quality)
        entries.append({"file": file, "name": name, "start": start, "end": end})
    page = PLAYER.format(title=html.escape(s.config.name), sections=json.dumps(entries))
    path = os.path.join(folder, "index.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return path
