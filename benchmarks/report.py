"""Benchmark tables for the terminal and for a CI job summary."""

from __future__ import annotations

from .stages import SceneTimings

COLUMNS = (
    ("scene", "scene"),
    ("duration", "length s"),
    ("build", "build s"),
    ("lint_layout", "layout lint s"),
    ("lint_visual", "visual lint s"),
    ("lint_other", "other lints s"),
    ("frame_draft_ms", "draft frame ms"),
    ("frame_final_ms", "final frame ms"),
    ("render_only_fps", "render fps"),
    ("video_fps", "video fps"),
)


def _cell(value: object) -> str:
    if value is None:
        return "–"
    if isinstance(value, float):
        return f"{value:.0f}" if value >= 100 else f"{value:.2f}" if value < 10 else f"{value:.1f}"
    return str(value)


def _rows(results: list[SceneTimings]) -> list[list[str]]:
    return [[_cell(getattr(result, key)) for key, _ in COLUMNS] for result in results]


def text_table(results: list[SceneTimings]) -> str:
    header = [title for _, title in COLUMNS]
    rows = _rows(results)
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header))]
    lines = ["  ".join(cell.ljust(widths[i]) if i == 0 else cell.rjust(widths[i]) for i, cell in enumerate(row)) for row in [header, *rows]]
    return "\n".join(lines)


def markdown_table(results: list[SceneTimings]) -> str:
    header = [title for _, title in COLUMNS]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in _rows(results)]
    return "### Benchmarks\n\n" + "\n".join(lines) + "\n"
