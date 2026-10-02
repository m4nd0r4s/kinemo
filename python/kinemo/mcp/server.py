"""The kinemo MCP server: lifecycle (initialize/initialized, ping, shutdown) and tools/list, tools/call."""

from __future__ import annotations

import contextlib
import os
import sys
import traceback
from typing import IO, Any, Callable

from .protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    InvalidMessage,
    Message,
    RpcError,
    StdioTransport,
    parse_line,
)
from .tools import TOOLS, call_tool, error_result

SERVER_NAME = "kinemo"
#: Newest first; the first one is what we answer when the client asks for one we don't know.
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
LATEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]
INSTRUCTIONS = (
    "kinemo: explanatory animations in Python. Agent loop: call `docs` for the symbols you will use, "
    "write the scene, call `check` and apply the fixes until ok, `inspect` at the end of each play "
    "to confirm positions, optionally `snap` to look at frames. Every tool runs with --strict: "
    "warnings are errors. `explain` gives the long explanation of a diagnostic code."
)


def negotiate_protocol_version(requested: Any) -> str:
    """Echo the client's version when supported, else offer the latest we speak."""
    return requested if requested in SUPPORTED_PROTOCOL_VERSIONS else LATEST_PROTOCOL_VERSION


class McpServer:
    """Serves MCP requests from `transport` until EOF or `shutdown`.

    Anything the scene code prints while a tool runs goes to `log` (stderr by default),
    never to the protocol stream."""

    def __init__(self, transport: StdioTransport, log: IO[str] | None = None) -> None:
        self.transport = transport
        self.log = log if log is not None else sys.stderr
        self.initialized = False
        self.protocol_version = LATEST_PROTOCOL_VERSION
        self.client_info: dict[str, Any] = {}
        self.running = True
        self.handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "initialize": self.handle_initialize,
            "ping": lambda params: {},
            "tools/list": self.handle_tools_list,
            "tools/call": self.handle_tools_call,
            "shutdown": self.handle_shutdown,
        }

    # --- loop ----------------------------------------------------------------------------

    def serve(self) -> None:
        for line in self.transport.lines():
            for incoming in parse_line(line):
                self.dispatch(incoming)
            if not self.running:
                break

    def dispatch(self, incoming: Message | InvalidMessage) -> None:
        if isinstance(incoming, InvalidMessage):
            self.transport.respond_error(incoming.id, incoming.error)
            return
        if incoming.is_notification:
            self.handle_notification(incoming)
            return
        handler = self.handlers.get(incoming.method)
        if handler is None:
            self.transport.respond_error(incoming.id, RpcError(METHOD_NOT_FOUND, f"method not found: {incoming.method}"))
            return
        try:
            result = handler(incoming.params)
        except RpcError as e:
            self.transport.respond_error(incoming.id, e)
            return
        except Exception as e:  # noqa: BLE001 - never let one request kill the server
            traceback.print_exc(file=self.log)
            self.transport.respond_error(incoming.id, RpcError(INTERNAL_ERROR, f"{type(e).__name__}: {e}"))
            return
        self.transport.respond(incoming.id, result)

    def handle_notification(self, message: Message) -> None:
        if message.method == "notifications/initialized":
            self.initialized = True
        elif message.method == "exit":
            self.running = False
        # notifications/cancelled and anything else: requests run synchronously, nothing to do.

    # --- methods -------------------------------------------------------------------------

    def handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        from .. import __version__

        self.protocol_version = negotiate_protocol_version(params.get("protocolVersion"))
        self.client_info = params.get("clientInfo") or {}
        return {
            "protocolVersion": self.protocol_version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "title": "kinemo", "version": __version__},
            "instructions": INSTRUCTIONS,
        }

    def handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"tools": [tool.definition() for tool in TOOLS.values()]}

    def handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in TOOLS:
            raise RpcError(INVALID_PARAMS, f"unknown tool: {name}", {"tools": list(TOOLS)})
        if not isinstance(arguments, dict):
            raise RpcError(INVALID_PARAMS, "'arguments' must be an object")
        with contextlib.redirect_stdout(self.log):
            try:
                return call_tool(name, arguments)
            except Exception as e:  # noqa: BLE001 - a crash in a tool is a tool error, not a protocol one
                traceback.print_exc(file=self.log)
                return error_result(f"{type(e).__name__}: {e}")

    def handle_shutdown(self, params: dict[str, Any]) -> dict[str, Any]:
        self.running = False
        return {}


def serve(reader: IO[bytes] | None = None, writer: IO[bytes] | None = None, log: IO[str] | None = None) -> int:
    """Run the server over stdio (or the given binary streams) until EOF or `shutdown`.

    On real stdio the protocol keeps a private copy of fd 1 and fd 1 itself is pointed at
    stderr, so nothing printed by scene code or native libraries can corrupt the stream."""
    if writer is None:
        writer = _protocol_stdout()
    transport = StdioTransport(reader or sys.stdin.buffer, writer)
    McpServer(transport, log).serve()
    return 0


def _protocol_stdout() -> IO[bytes]:
    sys.stdout.flush()
    protocol_fd = os.dup(sys.stdout.fileno())
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    return os.fdopen(protocol_fd, "wb", buffering=0)
