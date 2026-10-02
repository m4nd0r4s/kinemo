"""The MCP tools: `check`, `inspect`, `snap`, `docs` and `explain`, always with `--strict` semantics.

Each tool returns an MCP `CallToolResult`: the payload as JSON text content (and as
`structuredContent`), PNG frames as image content for `snap`, and `isError: true` when a
diagnostic fails under `--strict` (errors and warnings) or the request can't be served."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any, Callable

from ..cli.check import load_error_report, scene_report
from ..cli.inspect import inspect_payload
from ..cli.loader import BuildResult, LoadError, build, find_scenes, load_module, select
from ..cli.output import exit_code
from ..cli.snap import snap_png
from ..diagnostics import CATALOG, Diagnostic, explain
from .documentation import SymbolNotFound, lookup_documentation

STRICT = True
SCENE_FILE_PROPERTIES: dict[str, Any] = {
    "file": {"type": "string", "description": "Path of the scene file (.py), absolute or relative to the server's cwd."},
    "scene": {"type": "string", "description": "Scene name (@k.scene function). Default: every scene in the file."},
    "params": {"type": "object", "description": "Values for the scene's params=, like --param NAME=VALUE.", "additionalProperties": True},
}
INSTANT_DESCRIPTION = "Instant: seconds, a mark name or 'end'."


class ToolInputError(Exception):
    """Bad arguments: reported as a tool error result so the model can correct itself."""


@dataclass
class Tool:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]

    def definition(self) -> dict[str, Any]:
        return {"name": self.name, "title": self.title, "description": self.description, "inputSchema": self.input_schema}


# --- results -----------------------------------------------------------------------------


def tool_result(payload: dict[str, Any], is_error: bool, images: list[bytes] | None = None) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}]
    for png in images or []:
        content.append({"type": "image", "data": base64.b64encode(png).decode("ascii"), "mimeType": "image/png"})
    return {"content": content, "structuredContent": payload, "isError": is_error}


def error_result(message: str, **extra: Any) -> dict[str, Any]:
    return tool_result({"ok": False, "error": message, **extra}, True)


def strict_failing(diagnostics: list[Diagnostic]) -> bool:
    return exit_code(diagnostics, STRICT) != 0


# --- scene loading -----------------------------------------------------------------------


@dataclass
class LoadedScenes:
    file: str
    results: list[BuildResult]

    @property
    def diagnostics(self) -> list[Diagnostic]:
        return [d for r in self.results for d in r.diagnostics]


class SceneFileFailed(Exception):
    """The file did not load (syntax error, exception at import): carries the check payload."""

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(payload)
        self.payload = payload


def load_and_build(arguments: dict[str, Any]) -> LoadedScenes:
    file = _required_string(arguments, "file")
    scene_name = arguments.get("scene")
    params = arguments.get("params") or {}
    if not isinstance(params, dict):
        raise ToolInputError("'params' must be an object")
    if not os.path.exists(file):
        raise ToolInputError(f"file not found: {os.path.abspath(file)}")
    try:
        module = load_module(file)
    except LoadError as e:
        raise SceneFileFailed({"ok": False, "strict": STRICT, **load_error_report(file, e.diagnostic)}) from e
    try:
        definitions = select(find_scenes(module), scene_name)
    except SystemExit as e:  # select() reports an unknown scene this way for the CLI
        raise ToolInputError(str(e.code).removeprefix("kinemo: ")) from e
    if not definitions:
        raise ToolInputError(f"no scenes (@k.scene) in {file}")
    return LoadedScenes(file, [build(d, params) for d in definitions])


def _required_string(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and key == "at":
        return str(value)
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"'{key}' is required (string)")
    return value


def _instants(arguments: dict[str, Any]) -> list[str]:
    value = arguments.get("at")
    if isinstance(value, list):
        instants = [str(v) for v in value]
    else:
        instants = [part for part in _required_string(arguments, "at").split(",")]
    instants = [i.strip() for i in instants if str(i).strip()]
    if not instants:
        raise ToolInputError("'at' needs at least one instant")
    return instants


def _failed_scene_entry(result: BuildResult) -> dict[str, Any]:
    return {"scene": result.definition.name, "ok": False, "diagnostics": [d.json() for d in result.diagnostics]}


# --- tools -------------------------------------------------------------------------------


def check_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    loaded = load_and_build(arguments)
    failing = strict_failing(loaded.diagnostics) or any(r.scene is None for r in loaded.results)
    payload = {"file": loaded.file, "ok": not failing, "strict": STRICT, "scenes": [scene_report(r, STRICT) for r in loaded.results]}
    return tool_result(payload, failing)


def inspect_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    at = _required_string(arguments, "at")
    include_absent = bool(arguments.get("all", False))
    loaded = load_and_build(arguments)
    scenes: list[dict[str, Any]] = []
    for result in loaded.results:
        if result.scene is None:
            scenes.append(_failed_scene_entry(result))
            continue
        entry = inspect_payload(result, at, include_absent)
        entry["ok"] = not strict_failing(result.diagnostics)
        entry["diagnostics"] = [d.json() for d in result.diagnostics]
        scenes.append(entry)
    failing = not all(s["ok"] for s in scenes)
    return tool_result({"file": loaded.file, "ok": not failing, "strict": STRICT, "scenes": scenes}, failing)


def snap_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    instants = _instants(arguments)
    quality = arguments.get("quality", "draft")
    if quality not in ("draft", "final"):
        raise ToolInputError("'quality' must be 'draft' or 'final'")
    loaded = load_and_build(arguments)
    scenes: list[dict[str, Any]] = []
    images: list[bytes] = []
    for result in loaded.results:
        if result.scene is None:
            scenes.append(_failed_scene_entry(result))
            continue
        frames = []
        for at in instants:
            t, png = snap_png(result, at, quality)
            frames.append({"at": at, "t": t, "image": len(images)})
            images.append(png)
        scenes.append(
            {
                "scene": result.definition.name,
                "ok": not strict_failing(result.diagnostics),
                "frames": frames,
                "diagnostics": [d.json() for d in result.diagnostics],
            }
        )
    failing = not all(s["ok"] for s in scenes)
    payload = {"file": loaded.file, "ok": not failing, "strict": STRICT, "quality": quality, "scenes": scenes}
    return tool_result(payload, failing, images)


def docs_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    symbol = _required_string(arguments, "symbol")
    try:
        found = lookup_documentation(symbol)
    except SymbolNotFound as e:
        return error_result(str(e), symbol=symbol, suggestions=e.suggestions)
    return tool_result({"ok": True, **found}, False)


def explain_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    code = _required_string(arguments, "code").strip().upper()
    if code not in CATALOG:
        return error_result(f"{code}: unknown code", code=code)
    entry = CATALOG[code]
    return tool_result({"ok": True, "code": code, "title": entry.title, "text": explain(code)}, False)


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in [
        Tool(
            "check",
            "Check a scene",
            "Build and resolve a kinemo scene without rendering (kinemo check --json --strict): "
            "errors, lints with fixes, timeline. Warnings count as errors. Apply the fixes and call again.",
            {"type": "object", "properties": SCENE_FILE_PROPERTIES, "required": ["file"]},
            check_tool,
        ),
        Tool(
            "inspect",
            "Inspect the scene graph",
            "Scene graph at instant t (kinemo inspect --json): position, bbox, props of every object, "
            "the source of each value and its line. Use at the end of each play to confirm positions.",
            {
                "type": "object",
                "properties": {
                    **SCENE_FILE_PROPERTIES,
                    "at": {"type": ["string", "number"], "description": INSTANT_DESCRIPTION},
                    "all": {"type": "boolean", "description": "Include objects not in the scene at t."},
                },
                "required": ["file", "at"],
            },
            inspect_tool,
        ),
        Tool(
            "snap",
            "Snapshot frames",
            "PNG frames of the requested instants (kinemo snap), returned as images.",
            {
                "type": "object",
                "properties": {
                    **SCENE_FILE_PROPERTIES,
                    "at": {
                        "type": ["string", "number", "array"],
                        "items": {"type": ["string", "number"]},
                        "description": INSTANT_DESCRIPTION + " Several: '0,2.5,end' or a list.",
                    },
                    "quality": {"type": "string", "enum": ["draft", "final"], "default": "draft"},
                },
                "required": ["file", "at"],
            },
            snap_tool,
        ),
        Tool(
            "docs",
            "Symbol docs",
            "Short offline docs for a kinemo symbol with its canonical example (kinemo docs k.morph).",
            {
                "type": "object",
                "properties": {"symbol": {"type": "string", "description": "e.g. 'k.morph', 'k.Text', 'Scene.play'."}},
                "required": ["symbol"],
            },
            docs_tool,
        ),
        Tool(
            "explain",
            "Explain a diagnostic",
            "Long explanation of an error or lint code, with an example and the fix (kinemo explain K0401).",
            {
                "type": "object",
                "properties": {"code": {"type": "string", "description": "Diagnostic code, e.g. 'K0401' or 'W1001'."}},
                "required": ["code"],
            },
            explain_tool,
        ),
    ]
}


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Run tool `name`; bad input and scene files that fail to load become `isError` results."""
    tool = TOOLS[name]
    try:
        return tool.handler(arguments)
    except ToolInputError as e:
        return error_result(str(e))
    except SceneFileFailed as e:
        return tool_result(e.payload, True)
