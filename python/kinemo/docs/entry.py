"""`DocEntry`: one documented symbol. One entry = one small dataclass instance."""

from __future__ import annotations

from dataclasses import dataclass

#: Areas in the order they appear in `kinemo docs` listings and in `llms.txt`.
AREAS = (
    "Scene",
    "Object state",
    "Verbs",
    "Composition",
    "Objects",
    "Text",
    "Layout",
    "Charts",
    "Reactive",
    "Native blocks",
    "Stateful systems",
    "Events",
    "Components",
    "Parameters",
    "Output",
    "Theme and colors",
)


@dataclass(frozen=True)
class DocEntry:
    """A documented public symbol.

    `symbol` is the canonical name: `k.draw` for module functions and classes,
    `Scene.play` / `Axes.plot` / `Node.to` for methods (shown as `s.play`, `ax.plot`,
    `obj.to`). `example` is a complete scene of at most 15 lines that passes
    `kinemo check --strict`; it shows exactly one form per concept.
    """

    symbol: str
    area: str
    summary: str
    example: str
    related: tuple[str, ...] = ()
    #: Other names that answer with this entry (`k.cos` → `k.sin`).
    aliases: tuple[str, ...] = ()
    #: Signature shown instead of the one extracted with `inspect` (overloads, namespaces).
    signature: str = ""
    #: Files from `kinemo/docs/assets/` the example reads (copied next to it when checked).
    assets: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.area not in AREAS:
            raise ValueError(f"{self.symbol}: unknown area {self.area!r}")
        object.__setattr__(self, "example", self.example.strip("\n") + "\n")
