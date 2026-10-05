"""Capture the screenshots of the `kinemo dev` preview used on the website.

    .venv/bin/python website/capture.py

Starts `kinemo dev` on an example and photographs it with headless Chrome, opening the page
on a given state through the URL (`#t=2.6&select=dot`). The PNGs land in
website/static/img/. The website workflow runs it on every deploy, so the site shows the
current editor; the committed PNGs are the fallback for a local build without Chrome.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import struct
import sys
import time
import zlib
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent
ROOT = WEBSITE.parent
OUT = WEBSITE / "static" / "img"

#: Screenshot name → page state.
SHOTS = {
    "editor-inspector": "t=2.6&select=dot",
    "editor-bar": "t=2.6&bar=2",
    # The Code tab following the playhead, with a breakpoint on the zoom.
    "editor-code": "t=2.6&pane=code&bp=19",
}
WINDOW = (1600, 1000)
SCALE = 2

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
)


#: Screenshots taken of a page before it is ready are retried this many times.
ATTEMPTS = 5


def png_pixels(path: Path) -> tuple[int, int, list[bytes]]:
    """Width, height and the RGB(A) rows of a PNG written by Chrome (8-bit, no interlace)."""
    data = path.read_bytes()
    width, height, depth, color = struct.unpack(">IIBB", data[16:26])
    channels = {2: 3, 6: 4}[color]
    assert depth == 8, "capture.py reads 8-bit PNGs"
    chunks, pos = [], 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        if kind == b"IDAT":
            chunks.append(data[pos + 8 : pos + 8 + length])
        pos += 12 + length
    raw = zlib.decompress(b"".join(chunks))
    stride = width * channels
    rows: list[bytes] = []
    prev = bytearray(stride)
    for y in range(height):
        kind, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1 : (y + 1) * (stride + 1)])
        for i in range(stride):
            left = line[i - channels] if i >= channels else 0
            up = prev[i]
            corner = prev[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif kind == 4:
                p = left + up - corner
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
                line[i] = (line[i] + (left if pa <= pb and pa <= pc else up if pb <= pc else corner)) & 0xFF
        rows.append(bytes(line))
        prev = line
    return width, height, rows


def frame_drawn(path: Path) -> bool:
    """Whether the frame has arrived: before the scene, the frame area is pure black."""
    width, height, rows = png_pixels(path)
    channels = len(rows[0]) // width
    # The middle of the stage (between the outliner and the side panel), above the timeline.
    x0, y0 = int(width * 0.40), int(height * 0.40)
    for y in range(y0, y0 + 20, 4):
        for x in range(x0, x0 + 20, 4):
            if any(rows[y][x * channels : x * channels + 3]):
                return True
    return False


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
        encoding="utf-8",
    )
    try:
        wait_until_built(server)
        OUT.mkdir(parents=True, exist_ok=True)
        for name, state in SHOTS.items():
            target = OUT / f"{name}.png"
            # The page fills in once its WebSocket delivers the scene, which headless Chrome's
            # virtual time does not wait for: retry until the frame is drawn.
            for _ in range(ATTEMPTS):
                subprocess.run(
                    [
                        browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        # CI containers have no user namespace for Chrome's sandbox.
                        *(["--no-sandbox"] if os.environ.get("CI") else []),
                        f"--window-size={WINDOW[0]},{WINDOW[1]}", f"--force-device-scale-factor={SCALE}",
                        "--virtual-time-budget=6000", f"--screenshot={target}", f"http://127.0.0.1:{port}/#{state}",
                    ],
                    check=True, capture_output=True,
                )
                if frame_drawn(target):
                    break
            else:
                raise SystemExit(f"capture.py: {name} still shows the page before the scene arrived")
            print(f"wrote {target.relative_to(ROOT)}")
    finally:
        server.terminate()
        server.wait(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
