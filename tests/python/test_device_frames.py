"""Device frames: content fits the screen and the parts are named."""

from __future__ import annotations

import kinemo as k
from conftest import build


def test_content_is_scaled_down_to_fit_the_screen() -> None:
    seen: dict[str, float] = {}

    @build
    def scene(s: k.Scene) -> None:
        wide = k.Rect(w=20, h=1)
        phone = k.Phone(wide, w=2.0, h=4.0)
        s.add(phone)
        seen["content_width"] = float(phone.content.width.now)
        seen["screen_width"] = float(phone.screen.width.now)

    assert seen["content_width"] <= seen["screen_width"]


def test_frames_build_with_and_without_content() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        window = k.BrowserWindow(url="kinemo.dev")
        laptop = k.Laptop(k.Text("hi"))
        s.add(window, laptop)
        seen["url"] = window.url.text.now
        seen["base_below"] = float(laptop.base.y.now) < float(laptop.screen.y.now)

    assert seen["url"] == "kinemo.dev" and seen["base_below"] is True
