"""`kinemo dev`: browser preview with hot reload, a draggable timeline and source edits.

The scene is built in Python once per save; frames and picking are served by the Rust
preview server (`kinemo._core.PreviewServer`), so scrubbing never touches Python. Edits
made in the page come back through the server and rewrite the source (`dev_session`).
"""

from __future__ import annotations

import argparse
import json
import os
import time
import webbrowser

from .dev_session import Session

#: Seconds between checks of the watched files' modification times and of edits from the page.
POLL_INTERVAL = 0.05

__all__ = ["Session", "run", "watch"]


def mtimes(files: set[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for f in files:
        try:
            out[f] = os.stat(f).st_mtime
        except OSError:
            out[f] = -1.0
    return out


def watch(session: Session) -> None:
    seen = mtimes(session.watched)
    while True:
        time.sleep(POLL_INTERVAL)
        edits = [json.loads(e) for e in session.server.take_edits()]
        if edits:
            session.process_edits(edits)
        now = mtimes(session.watched)
        if now != seen:
            changed = sorted(os.path.basename(f) for f in now if now[f] != seen.get(f))
            print(f"kinemo dev: {', '.join(changed)} changed; rebuilding", flush=True)
            session.rebuild()
            seen = mtimes(session.watched)


def run(args: argparse.Namespace) -> int:
    if not os.path.exists(args.file):
        print(f"kinemo: file not found: {args.file}")
        return 1
    from .._core import PreviewServer  # imported late: other commands work without it

    server = PreviewServer(args.port)
    try:
        url = server.start()
    except RuntimeError as e:
        print(f"kinemo dev: {e}")
        return 1
    session = Session(args.file, args.scene, args.params, server, debug=tuple(f for f in (args.debug or "").split(",") if f))
    session.rebuild()
    print(f"kinemo dev: preview at {url}  (Ctrl+C to quit)", flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        watch(session)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0
