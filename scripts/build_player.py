"""Build the lesson player's WebAssembly into `python/kinemo/export/player/pkg/`, where
`kinemo render --format lesson` copies it from (and the wheels ship it).

    python scripts/build_player.py

Needs the `wasm32-unknown-unknown` Rust target and `wasm-bindgen` at the version
`crates/kinemo-web` pins (`cargo install wasm-bindgen-cli --version <it>`).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "python" / "kinemo" / "export" / "player" / "pkg"


def pinned_bindgen() -> str:
    manifest = (ROOT / "crates" / "kinemo-web" / "Cargo.toml").read_text(encoding="utf-8")
    match = re.search(r'wasm-bindgen = "=([0-9.]+)"', manifest)
    assert match, "crates/kinemo-web pins wasm-bindgen with ="
    return match.group(1)


def main() -> int:
    version = pinned_bindgen()
    bindgen = shutil.which("wasm-bindgen")
    found = subprocess.run([bindgen, "--version"], capture_output=True, text=True, encoding="utf-8").stdout.split()[-1] if bindgen else None
    if found != version:
        print(f"wasm-bindgen {version} is needed (found {found}): cargo install wasm-bindgen-cli --version {version}")
        return 1
    subprocess.run(["cargo", "build", "-p", "kinemo-web", "--target", "wasm32-unknown-unknown", "--profile", "player"], cwd=ROOT, check=True)
    wasm = ROOT / "target" / "wasm32-unknown-unknown" / "player" / "kinemo_web.wasm"
    if OUT.exists():
        shutil.rmtree(OUT)
    subprocess.run([bindgen, str(wasm), "--target", "web", "--no-typescript", "--out-dir", str(OUT)], check=True)
    size = (OUT / "kinemo_web_bg.wasm").stat().st_size
    print(f"player: {OUT.relative_to(ROOT)} ({size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
