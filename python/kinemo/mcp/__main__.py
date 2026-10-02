"""`python -m kinemo.mcp`: the MCP server over stdio (same as `kinemo mcp`)."""

import sys

from .server import serve

sys.exit(serve())
