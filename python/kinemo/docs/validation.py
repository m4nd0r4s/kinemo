"""Check canonical examples the way `kinemo check --strict` does: load the source as a
scene file, build every scene and collect all diagnostics (errors and lints)."""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field

from ..diagnostics import Diagnostic
from .entry import DocEntry

MAX_EXAMPLE_LINES = 15
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


@dataclass
class ExampleReport:
    entry: DocEntry
    scenes: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.diagnostics and not self.problems

    def render(self) -> str:
        lines = [f"{self.entry.symbol}: {'ok' if self.ok else 'FAILED'}"]
        lines += [f"  {p}" for p in self.problems]
        lines += ["  " + line for d in self.diagnostics for line in d.render().splitlines()]
        return "\n".join(lines)


def module_slug(symbol: str) -> str:
    return "doc_" + re.sub(r"\W+", "_", symbol).strip("_")


def check_example(entry: DocEntry, directory: str | None = None) -> ExampleReport:
    """Build every scene of `entry.example`; any diagnostic makes the example fail."""
    from ..cli.loader import LoadError, build, find_scenes, load_module

    report = ExampleReport(entry)
    lines = entry.example.rstrip("\n").splitlines()
    if len(lines) > MAX_EXAMPLE_LINES:
        report.problems.append(f"{len(lines)} lines (maximum {MAX_EXAMPLE_LINES})")
    with tempfile.TemporaryDirectory(dir=directory) as tmp:
        path = os.path.join(tmp, module_slug(entry.symbol) + ".py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(entry.example)
        for asset in entry.assets:
            shutil.copy(os.path.join(ASSETS_DIR, asset), os.path.join(tmp, asset))
        try:
            module = load_module(path)
        except LoadError as e:
            report.diagnostics.append(e.diagnostic)
            return report
        try:
            scenes = find_scenes(module)
            if not scenes:
                report.problems.append("no scene (@k.scene) in the example")
            for definition in scenes:
                report.scenes.append(definition.name)
                report.diagnostics.extend(build(definition).diagnostics)
        finally:
            sys.modules.pop(module.__name__, None)
    return report
