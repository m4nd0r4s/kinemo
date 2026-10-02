"""`kinemo mcp`: MCP server over stdio exposing check, inspect, snap, docs and explain (always --strict)."""

from __future__ import annotations

import argparse


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """`kinemo mcp` takes no arguments: the client launches it and talks over stdin/stdout."""
    parser.description = (
        "MCP server (stdio) with the check, inspect, snap, docs and explain tools, always with --strict."
    )


def run(args: argparse.Namespace) -> int:
    from ..mcp.server import serve

    return serve()
