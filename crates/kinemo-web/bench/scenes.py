"""Frame-time benchmark of the WASM player, to run on a phone.

    cargo build -p kinemo-web --target wasm32-unknown-unknown --release
    wasm-bindgen target/wasm32-unknown-unknown/release/kinemo_web.wasm --target web --out-dir crates/kinemo-web/bench/pkg
    python crates/kinemo-web/bench/scenes.py examples/*.py
    python -m http.server -d crates/kinemo-web/bench 8000   # then open http://<this machine>:8000 on the phone

Writes each scene's IR and baked layouts to `bench/scenes/`; the page renders up to 240 frames
of the chosen scene and reports layout and raster times, memory and load time.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from kinemo.cli.loader import build, find_scenes, load_module

out = Path(__file__).parent / "scenes"
out.mkdir(exist_ok=True)
names: list[str] = []
for path in sys.argv[1:]:
    scenes = find_scenes(load_module(path))
    for definition in scenes:
        scene = build(definition).scene
        if scene is None:
            print(f"{path}: does not build, skipped")
            continue
        name = Path(path).stem if len(scenes) == 1 else f"{Path(path).stem}-{definition.name}"
        (out / f"{name}.ir.json").write_text(scene.builder.to_json())
        (out / f"{name}.baked.json").write_text(scene.builder.baked_layouts(30.0))
        names.append(name)
(out / "index.json").write_text(json.dumps(names))
print(f"{len(names)} scenes in {out}")
