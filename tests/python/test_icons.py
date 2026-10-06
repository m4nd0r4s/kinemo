"""`k.Icon`: every built-in icon builds, sizes to `size`, recolors, and unknown names suggest."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build


def test_every_icon_builds_within_its_square() -> None:
    seen: dict[str, float] = {}

    @build
    def scene(s: k.Scene) -> None:
        for name in k.ICON_NAMES:
            icon = k.Icon(name, size=2.0)
            s.add(icon)
            seen[name] = max(float(icon.width.now), float(icon.height.now))

    assert len(seen) >= 30
    assert all(0.1 < extent <= 2.0 for extent in seen.values())


def test_stroke_recolors_every_part() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        icon = k.Icon("cpu", color=k.BLUE)
        s.add(icon)
        s.play(icon.to(stroke=k.RED))
        seen["colors"] = {str(part.stroke.now) for part in icon.children}  # type: ignore[attr-defined]

    assert seen["colors"] == {str(k.RED)}


def test_unknown_icon_suggests_names() -> None:
    with pytest.raises(k.KinemoError, match="unknown icon"):

        @build
        def scene(s: k.Scene) -> None:
            k.Icon("chek")
