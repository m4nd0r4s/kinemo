"""Entry point of the `kinemo` command."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable

from . import check, dev, docs_cmd, inspect, mcp_cmd, new, render, snap, upgrade_cmd


def _params(items: list[str] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items or []:
        key, _, raw = item.partition("=")
        value: Any = raw
        for conv in (int, float):
            try:
                value = conv(raw)
                break
            except ValueError:
                continue
        out[key] = value
    return out


def _explain(args: argparse.Namespace) -> int:
    from ..diagnostics import explain

    print(explain(args.code))
    return 0


def _scene_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("file")
    p.add_argument("--scene", help="scene name (default: all)")
    p.add_argument("--param", action="append", dest="param_items", metavar="NAME=VALUE")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="kinemo", description="Explanatory animations in Python.")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new", help="create a project")
    p.add_argument("name")
    p.set_defaults(run=new.run)

    p = sub.add_parser("dev", help="browser preview with hot reload and a scrubbable timeline")
    _scene_args(p)
    p.add_argument("--port", type=int, default=7878)
    p.add_argument("--no-open", action="store_true", help="do not open the browser")
    p.add_argument("--debug", default="", help="overlays: layout,safe (comma-separated)")
    p.set_defaults(run=dev.run)

    p = sub.add_parser("check", help="build + resolve without rendering: errors, lints, timeline")
    _scene_args(p)
    p.add_argument("--json", action="store_true")
    p.add_argument("--strict", action="store_true", help="treat warnings as errors")
    p.add_argument("--fix", action="store_true", help="apply safe fixes")
    p.set_defaults(run=check.run)

    p = sub.add_parser("inspect", help="scene graph at time t")
    _scene_args(p)
    p.add_argument("--at", default="0")
    p.add_argument("--json", action="store_true")
    p.add_argument("--all", action="store_true", help="include objects not in the scene")
    p.set_defaults(run=inspect.run)

    p = sub.add_parser("snap", help="PNGs of the requested times")
    _scene_args(p)
    p.add_argument("--at", default="0,end")
    p.add_argument("--out", default="out")
    p.add_argument("--quality", choices=["draft", "final"], default="draft")
    p.set_defaults(run=snap.run)

    p = sub.add_parser("render", help="final output")
    _scene_args(p)
    p.add_argument("--format", default="mp4", choices=["mp4", "webm", "mov", "gif", "png", "svg", "slides"])
    p.add_argument("--quality", choices=["draft", "final"], default="final")
    p.add_argument("--out", default="out")
    p.add_argument("--at", help="time (png/svg): seconds, a mark name or 'end'")
    p.add_argument("--frames", action="store_true", help="png: the whole sequence")
    p.add_argument("--transparent", action="store_true")
    p.set_defaults(run=render.run)

    p = sub.add_parser("mcp", help="MCP server (stdio) with check, inspect, snap, docs and explain")
    mcp_cmd.add_arguments(p)
    p.set_defaults(run=mcp_cmd.run)

    p = sub.add_parser("docs", help="short offline docs with a canonical example")
    docs_cmd.add_arguments(p)
    p.set_defaults(run=docs_cmd.run)

    p = sub.add_parser("upgrade", help="codemods between versions")
    upgrade_cmd.add_arguments(p)
    p.set_defaults(run=upgrade_cmd.run)

    p = sub.add_parser("explain", help="long explanation of an error or lint")
    p.add_argument("code")
    p.set_defaults(run=_explain)
    return ap


def _utf8_output() -> None:
    """kinemo prints "—", "×" and "→". On Windows, output to a pipe (CI, an editor, a
    subprocess) defaults to the ANSI code page, which cannot encode them; use UTF-8."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    _utf8_output()
    args = parser().parse_args(argv)
    args.params = _params(getattr(args, "param_items", None))
    run: Callable[[argparse.Namespace], int] = args.run
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
