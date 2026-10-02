"""Props the scene wrote carry its span in the IR; defaults carry none, so the `dev`
inspector labels them "default" instead of pointing at a line."""

from __future__ import annotations

import json

import kinemo as k


def prop_spans(s: k.Scene, node: k.Node) -> dict[str, str]:
    ir = json.loads(s.builder.to_json())
    return {
        signal["owner"][1]: signal["span"]["file"]
        for signal in ir["signals"]
        if signal["owner"] and signal["owner"][0] == node._id  # pyright: ignore[reportPrivateUsage]
    }


def test_written_props_keep_the_span_and_defaults_have_none() -> None:
    found: dict[str, dict[str, str]] = {}

    @k.scene
    def scene(s: k.Scene) -> None:
        dot = k.Dot(color=k.RED)
        big = k.Dot(r=0.08)
        label = k.Text("hi")
        s.add(dot, big, label)
        found["dot"] = prop_spans(s, dot)
        found["big"] = prop_spans(s, big)
        found["label"] = prop_spans(s, label)

    scene.build()
    dot, big, label = found["dot"], found["big"], found["label"]
    assert dot["fill"] == dot["stroke"] == __file__
    assert dot["r"] == "" and dot["rotate"] == ""
    assert big["r"] == __file__  # written, even though it equals the default
    assert any(file == __file__ for file in label.values())
