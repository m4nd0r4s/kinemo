"""JSON-RPC 2.0 over the MCP stdio transport: one JSON message per line, UTF-8, no embedded newlines."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import IO, Any, Iterator, Union

JSONRPC_VERSION = "2.0"

# Standard JSON-RPC error codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

RequestId = Union[str, int]


class RpcError(Exception):
    """Raised by a method handler to answer with a JSON-RPC error object."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def json(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            error["data"] = self.data
        return error


@dataclass
class Message:
    """An incoming request (has `id`) or notification (no `id`)."""

    method: str
    params: dict[str, Any]
    id: RequestId | None = None
    is_notification: bool = False


@dataclass
class InvalidMessage:
    """A line that could not be turned into a `Message`; `id` is known when the JSON parsed."""

    error: RpcError
    id: RequestId | None = None


Incoming = Union[Message, InvalidMessage]


def parse_line(line: str) -> list[Incoming]:
    """Decode one transport line. A JSON array (legacy batch) yields one entry per element;
    responses sent by the client (no `method`) are dropped since this server issues no requests."""
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as e:
        return [InvalidMessage(RpcError(PARSE_ERROR, f"parse error: {e.msg}"))]
    items = payload if isinstance(payload, list) else [payload]
    return [m for m in (_decode(item) for item in items) if m is not None]


def _decode(item: Any) -> Incoming | None:
    if not isinstance(item, dict) or item.get("jsonrpc") != JSONRPC_VERSION:
        request_id = item.get("id") if isinstance(item, dict) else None
        return InvalidMessage(RpcError(INVALID_REQUEST, "invalid request: expected a JSON-RPC 2.0 object"), request_id)
    if "method" not in item:
        return None  # a response to us; we never send requests
    method = item["method"]
    params = item.get("params", {})
    if not isinstance(method, str) or not isinstance(params, (dict, type(None))):
        return InvalidMessage(RpcError(INVALID_REQUEST, "invalid request: bad method or params"), item.get("id"))
    if "id" not in item:
        return Message(method, params or {}, None, is_notification=True)
    return Message(method, params or {}, item["id"])


class StdioTransport:
    """Reads newline-delimited messages from `reader` and writes them to `writer`.

    Both are binary streams (e.g. `sys.stdin.buffer`, `io.BytesIO`). Writes are serialized
    with a lock so responses never interleave."""

    def __init__(self, reader: IO[bytes], writer: IO[bytes]) -> None:
        self.reader = reader
        self.writer = writer
        self._lock = threading.Lock()

    def lines(self) -> Iterator[str]:
        """Each non-empty line until EOF."""
        while True:
            raw = self.reader.readline()
            if not raw:
                return
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                yield line

    def send(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            self.writer.write(data.encode("utf-8"))
            self.writer.flush()

    def respond(self, request_id: RequestId | None, result: Any) -> None:
        self.send({"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result})

    def respond_error(self, request_id: RequestId | None, error: RpcError) -> None:
        self.send({"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": error.json()})

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        message: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": method}
        if params is not None:
            message["params"] = params
        self.send(message)
