"""`inspect(scene, t)`: the scene graph at an instant, as `kinemo inspect --json` returns it."""

from __future__ import annotations

from typing import Any, Union

from ..cli.inspect import inspect_payload
from .building import BuiltScene, SceneLike, build

Instant = Union[float, int, str]


class InspectReport(dict):  # type: ignore[type-arg]
    """The `kinemo inspect --json` payload — `{"scene", "t", "objects": [...]}` — plus lookups.

    It *is* that dict (compare it, dump it with `json.dumps`), and adds:

    - `report.object("title")`: the object with that label (variable name, `row[2]`, `text#0`);
    - `report["title"]`: same as `.object`, for any key that isn't one of the payload's own;
    - `report.labels`: every label present at that instant."""

    @property
    def objects(self) -> list[dict[str, Any]]:
        return self["objects"]  # type: ignore[no-any-return]

    @property
    def t(self) -> float:
        return self["t"]  # type: ignore[no-any-return]

    @property
    def labels(self) -> list[str]:
        return [o["label"] for o in self.objects if o.get("label")]

    def object(self, label: str) -> dict[str, Any]:
        """The object labelled `label`; `KeyError` listing the available labels otherwise."""
        matches = [o for o in self.objects if o.get("label") == label]
        if not matches:
            available = ", ".join(self.labels) or "none"
            raise KeyError(f"no object labelled {label!r} at t = {self.t:.2f} s (available: {available})")
        return matches[0]

    def __getitem__(self, key: str) -> Any:
        if key in self.keys():
            return super().__getitem__(key)
        return self.object(key)

    def __contains__(self, key: object) -> bool:
        return dict.__contains__(self, key) or any(o.get("label") == key for o in self.objects)


def inspect(scene_def_or_built: SceneLike, t: Instant, *, include_absent: bool = False) -> InspectReport:
    """The scene graph at `t` (seconds, a mark name or `"end"`), as `kinemo inspect --json`.

    Builds the scene first when given a `@k.scene` (raising `SceneBuildError` on errors);
    pass a `BuiltScene` from `build()` to inspect many instants without rebuilding.
    `include_absent=True` also lists objects not in the scene at `t` (`--all`)."""
    built: BuiltScene = build(scene_def_or_built)
    return InspectReport(inspect_payload(built.result, str(t), include_absent))
