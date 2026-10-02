"""`kinemo mcp`: MCP server (stdio) exposing check, inspect, snap, docs and explain to agents.

Only the standard library is used. `python -m kinemo.mcp` or `kinemo mcp` starts it."""

from .server import McpServer, serve
from .tools import TOOLS, call_tool

__all__ = ["McpServer", "TOOLS", "call_tool", "serve"]
