"""`kinemo mcp`: JSON-RPC framing, lifecycle and the five tools (always --strict)."""

from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from kinemo.mcp.server import LATEST_PROTOCOL_VERSION, serve

ROOT = Path(__file__).resolve().parents[2]
HELLO = str(ROOT / "examples" / "hello.py")
BUBBLE_SORT = str(ROOT / "examples" / "bubble_sort.py")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

ERROR_SCENE = '''import kinemo as k


@k.scene
def bad(s: k.Scene):
    title = k.Text("oi").place(at="center")
    s.add(title)
    s.play(title.to(x=3))
'''

WARNING_SCENE = '''import kinemo as k


@k.scene
def warn(s: k.Scene):
    far = k.Text("longe")
    far.set(x=9.5, y=0)
    s.play(k.write(far))
'''

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 0,
    "method": "initialize",
    "params": {"protocolVersion": LATEST_PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "pytest", "version": "1"}},
}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def session(*messages: dict[str, Any] | str, initialize: bool = True) -> list[dict[str, Any]]:
    """Run the server over in-memory streams and return every response, in order."""
    prelude: list[dict[str, Any] | str] = [INITIALIZE, INITIALIZED] if initialize else []
    lines = [m if isinstance(m, str) else json.dumps(m) for m in [*prelude, *messages]]
    reader = io.BytesIO(("\n".join(lines) + "\n").encode("utf-8"))
    writer = io.BytesIO()
    assert serve(reader, writer, log=io.StringIO()) == 0
    responses = [json.loads(line) for line in writer.getvalue().decode("utf-8").splitlines()]
    return responses[1:] if initialize else responses


def call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    (response,) = session({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
    assert response["id"] == 1 and "result" in response, response
    return response["result"]


def payload_of(result: dict[str, Any]) -> dict[str, Any]:
    text = result["content"][0]
    assert text["type"] == "text"
    payload = json.loads(text["text"])
    assert payload == result["structuredContent"]
    return payload


@pytest.fixture
def scene_file(tmp_path: Path):  # type: ignore[no-untyped-def]
    def write(source: str, name: str = "scene.py") -> str:
        path = tmp_path / name
        path.write_text(source, encoding="utf-8")
        return str(path)

    return write


# --- lifecycle -----------------------------------------------------------------------------


def test_initialize_answers_capabilities_and_supported_version() -> None:
    (response,) = session(INITIALIZE, initialize=False)
    result = response["result"]
    assert response["id"] == 0
    assert result["protocolVersion"] == "2025-06-18"
    assert result["capabilities"] == {"tools": {"listChanged": False}}
    assert result["serverInfo"]["name"] == "kinemo"


def test_initialize_echoes_an_older_supported_version_and_offers_latest_for_unknown() -> None:
    older = {**INITIALIZE, "params": {**INITIALIZE["params"], "protocolVersion": "2024-11-05"}}
    unknown = {**INITIALIZE, "id": 9, "params": {**INITIALIZE["params"], "protocolVersion": "1999-01-01"}}
    first, second = session(older, unknown, initialize=False)
    assert first["result"]["protocolVersion"] == "2024-11-05"
    assert second["result"]["protocolVersion"] == LATEST_PROTOCOL_VERSION


def test_notifications_get_no_response_and_ping_returns_empty_result() -> None:
    responses = session({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 3}}, {"jsonrpc": "2.0", "id": "p", "method": "ping"})
    assert responses == [{"jsonrpc": "2.0", "id": "p", "result": {}}]


def test_shutdown_stops_the_loop() -> None:
    responses = session({"jsonrpc": "2.0", "id": 1, "method": "shutdown"}, {"jsonrpc": "2.0", "id": 2, "method": "ping"})
    assert responses == [{"jsonrpc": "2.0", "id": 1, "result": {}}]


def test_protocol_errors() -> None:
    parse, unknown, bad_tool = session(
        "{not json",
        {"jsonrpc": "2.0", "id": 1, "method": "resources/list"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "render", "arguments": {}}},
    )
    assert parse["error"]["code"] == -32700 and parse["id"] is None
    assert unknown["error"]["code"] == -32601
    assert bad_tool["error"]["code"] == -32602


def test_tools_list_exposes_the_five_tools_with_schemas() -> None:
    (response,) = session({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = {t["name"]: t for t in response["result"]["tools"]}
    assert set(tools) == {"check", "inspect", "snap", "docs", "explain"}
    for tool in tools.values():
        assert tool["inputSchema"]["type"] == "object" and tool["description"]
    assert tools["inspect"]["inputSchema"]["required"] == ["file", "at"]


# --- tools ---------------------------------------------------------------------------------


@pytest.mark.parametrize("path,scene", [(HELLO, "hello"), (BUBBLE_SORT, "bubble_sort")])
def test_check_reports_timeline_of_examples(path: str, scene: str) -> None:
    result = call("check", {"file": path})
    payload = payload_of(result)
    assert result["isError"] is False
    assert payload["ok"] is True and payload["strict"] is True
    (entry,) = payload["scenes"]
    assert entry["name"] == scene and entry["duration"] > 0 and entry["timeline"]


def test_check_error_file_returns_diagnostics_with_fixes(scene_file) -> None:  # type: ignore[no-untyped-def]
    result = call("check", {"file": scene_file(ERROR_SCENE)})
    payload = payload_of(result)
    assert result["isError"] is True and payload["ok"] is False
    (diagnostic,) = payload["scenes"][0]["diagnostics"]
    assert diagnostic["code"] == "K0401" and diagnostic["level"] == "error"
    assert diagnostic["spans"][0]["line"] == 8 and diagnostic["fixes"]


def test_check_is_strict_so_warnings_fail(scene_file) -> None:  # type: ignore[no-untyped-def]
    result = call("check", {"file": scene_file(WARNING_SCENE)})
    payload = payload_of(result)
    assert result["isError"] is True and payload["ok"] is False
    assert payload["scenes"][0]["ok"] is False  # builds fine; fails only because of --strict
    assert [d["code"] for d in payload["scenes"][0]["diagnostics"]] == ["W1001"]


def test_check_file_that_fails_to_load(scene_file) -> None:  # type: ignore[no-untyped-def]
    result = call("check", {"file": scene_file("import kinemo as k\nraise ValueError('boom')\n")})
    payload = payload_of(result)
    assert result["isError"] is True
    assert payload["diagnostics"][0]["code"] == "K0001" and "boom" in payload["diagnostics"][0]["message"]


def test_check_bad_arguments_are_tool_errors() -> None:
    missing = call("check", {"file": "/nonexistent/scene.py"})
    unknown_scene = call("check", {"file": HELLO, "scene": "nope"})
    assert missing["isError"] and "file not found" in payload_of(missing)["error"]
    assert unknown_scene["isError"] and "nope" in payload_of(unknown_scene)["error"]


def test_inspect_matches_cli_json_and_labels_objects() -> None:
    result = call("inspect", {"file": HELLO, "at": "end"})
    payload = payload_of(result)
    assert result["isError"] is False
    (scene,) = payload["scenes"]
    cli = subprocess.run(
        [sys.executable, "-m", "kinemo.cli", "inspect", HELLO, "--at", "end", "--json"],
        capture_output=True, text=True, check=True, cwd=ROOT,
        encoding="utf-8",
    )
    expected = json.loads(cli.stdout)
    assert {k: scene[k] for k in expected} == expected
    (title,) = [o for o in scene["objects"] if o["label"] == "title"]
    assert title["position"] == [0.0, 0.0]


def test_inspect_bubble_sort_at_a_number() -> None:
    payload = payload_of(call("inspect", {"file": BUBBLE_SORT, "at": 2}))
    labels = {o["label"] for o in payload["scenes"][0]["objects"]}
    assert "row" in labels and payload["scenes"][0]["t"] == 2.0


def test_inspect_error_file(scene_file) -> None:  # type: ignore[no-untyped-def]
    result = call("inspect", {"file": scene_file(ERROR_SCENE), "at": 0})
    assert result["isError"] is True
    assert payload_of(result)["scenes"][0]["diagnostics"][0]["code"] == "K0401"


@pytest.mark.parametrize("path", [HELLO, BUBBLE_SORT])
def test_snap_returns_png_images(path: str) -> None:
    result = call("snap", {"file": path, "at": "0,end"})
    payload = payload_of(result)
    images = [c for c in result["content"] if c["type"] == "image"]
    assert result["isError"] is False and len(images) == 2
    assert [f["at"] for f in payload["scenes"][0]["frames"]] == ["0", "end"]
    for image in images:
        assert image["mimeType"] == "image/png"
        assert base64.b64decode(image["data"]).startswith(PNG_SIGNATURE)


def test_snap_accepts_a_list_of_instants() -> None:
    result = call("snap", {"file": HELLO, "at": [1, "end"]})
    assert len([c for c in result["content"] if c["type"] == "image"]) == 2


def test_docs_known_and_unknown_symbol() -> None:
    known = call("docs", {"symbol": "k.Text"})
    assert known["isError"] is False and payload_of(known)["text"]
    unknown = call("docs", {"symbol": "k.definitely_not_a_symbol"})
    assert unknown["isError"] is True and "suggestions" in payload_of(unknown)


def test_explain_known_and_unknown_code() -> None:
    known = call("explain", {"code": "k0401"})
    payload = payload_of(known)
    assert known["isError"] is False and payload["code"] == "K0401" and "K0401" in payload["text"]
    assert call("explain", {"code": "K9999"})["isError"] is True


def test_scene_prints_do_not_corrupt_the_stream(scene_file) -> None:  # type: ignore[no-untyped-def]
    noisy = "print('hello from the scene')\n" + WARNING_SCENE
    result = call("check", {"file": scene_file(noisy)})
    assert payload_of(result)["scenes"][0]["name"] == "warn"


# --- real process --------------------------------------------------------------------------


def test_python_dash_m_kinemo_mcp_over_stdio() -> None:
    messages = [
        INITIALIZE,
        INITIALIZED,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "snap", "arguments": {"file": HELLO, "at": "end"}}},
    ]
    stdin = "".join(json.dumps(m) + "\n" for m in messages)
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    process = subprocess.run(
        [sys.executable, "-m", "kinemo.mcp"], input=stdin, capture_output=True, text=True, timeout=120, cwd=ROOT, env=env
    , encoding="utf-8")
    assert process.returncode == 0, process.stderr
    responses = [json.loads(line) for line in process.stdout.splitlines()]
    assert [r["id"] for r in responses] == [0, 1, 2]
    image = responses[2]["result"]["content"][1]
    assert base64.b64decode(image["data"]).startswith(PNG_SIGNATURE)
