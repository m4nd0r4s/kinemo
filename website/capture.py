"""Capture the screenshots of the `kinemo dev` preview used on the website.

    .venv/bin/python website/capture.py

Starts `kinemo dev` on an example and photographs it with headless Chrome, opening the page
on a given state through the URL (`#t=2.6&select=dot`). The PNGs land in
website/static/img/ and are committed, since the capture needs a local Chrome.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent
ROOT = WEBSITE.parent
OUT = WEBSITE / "static" / "img"

#: Screenshot name → page state.
SHOTS = {
    "editor-inspector": "t=2.6&select=dot",
    "editor-bar": "t=2.6&bar=2",
}
WINDOW = (1600, 1000)
SCALE = 2

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
)


def chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        found = candidate if os.path.exists(candidate) else shutil.which(candidate)
        if found:
            return found
    raise SystemExit("capture.py needs Google Chrome or Chromium")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def wait_until_built(server: subprocess.Popen[str], timeout: float = 30.0) -> None:
    """`kinemo dev` prints its URL after the first build is published."""
    deadline = time.monotonic() + timeout
    assert server.stdout is not None
    while time.monotonic() < deadline:
        line = server.stdout.readline()
        if "preview at" in line:
            return
        if not line and server.poll() is not None:
            break
    raise SystemExit("kinemo dev did not publish a scene")


def main() -> int:
    browser = chrome()
    port = free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "kinemo.cli", "dev", "examples/derivative.py", "--no-open", "--port", str(port)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        wait_until_built(server)
        OUT.mkdir(parents=True, exist_ok=True)
        for name, state in SHOTS.items():
            target = OUT / f"{name}.png"
            subprocess.run(
                [
                    browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--window-size={WINDOW[0]},{WINDOW[1]}", f"--force-device-scale-factor={SCALE}",
                    "--virtual-time-budget=6000", f"--screenshot={target}", f"http://127.0.0.1:{port}/#{state}",
                ],
                check=True, capture_output=True,
            )
            print(f"wrote {target.relative_to(ROOT)}")
    finally:
        server.terminate()
        server.wait(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
