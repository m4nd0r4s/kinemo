"""Render: PNG frames and determinism (same source → same bytes)."""

from __future__ import annotations

import random

import kinemo as k
from conftest import build, ir

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def demo(s: k.Scene) -> None:
    c = k.Circle(r=0.5 + random.random())
    s.play(k.draw(c))
    s.play(c.to(x=2, color=k.RED))
    title = k.Text("Hello, kinemo").place(above=c)
    s.play(k.write(title))
    row = k.Row(*[k.Bar(v) for v in (3, 1, 2)]).place(at="bottom")
    s.play(k.stagger([k.grow(b, from_="bottom") for b in row], lag=0.1))
    s.play(row.swap(0, 2))


def test_frame_png_returns_png_bytes() -> None:
    scene = build(demo, size="720p")
    png = scene.builder.frame_png(1.5)
    assert isinstance(png, bytes)
    assert png.startswith(PNG_SIGNATURE)
    assert len(png) > 100


def test_frames_change_over_time() -> None:
    scene = build(demo, size="720p")
    assert scene.builder.frame_png(0.0) != scene.builder.frame_png(1.5)


def test_frame_rgba_has_the_draft_size() -> None:
    scene = build(demo, size="720p")
    width, height, pixels = scene.builder.frame_rgba(0.5)
    assert len(pixels) == width * height * 4
    assert width / height == 1280 / 720


def test_render_is_a_pure_function_of_t() -> None:
    scene = build(demo, size="720p")
    late = scene.builder.frame_png(3.0)
    early = scene.builder.frame_png(0.5)
    assert scene.builder.frame_png(3.0) == late
    assert scene.builder.frame_png(0.5) == early


def test_same_build_twice_gives_identical_ir_and_pixels() -> None:
    first = build(demo, size="720p")
    second = build(demo, size="720p")
    assert first.builder.to_json() == second.builder.to_json()
    for t in (0.0, 0.7, 2.5, 4.2):
        assert first.builder.frame_png(t) == second.builder.frame_png(t)


def test_random_is_seeded_per_scene() -> None:
    seen = []

    def body(s: k.Scene) -> None:
        seen.append(random.random())

    build(body)
    build(body)
    build(body, seed=1)
    assert seen[0] == seen[1]
    assert seen[0] != seen[2]


def test_numpy_random_is_seeded_per_scene() -> None:
    import numpy as np

    seen = []

    def body(s: k.Scene) -> None:
        seen.append(float(np.random.random()))

    build(body)
    build(body)
    assert seen[0] == seen[1]


def test_build_restores_the_global_random_state() -> None:
    random.seed(1234)
    expected = random.random()
    random.seed(1234)
    build(demo)
    assert random.random() == expected


def test_scene_config_is_in_the_ir() -> None:
    scene = build(demo, size="720p", fps=30, seed=3, tail=1.0)
    config = ir(scene)["config"]
    assert (config["width"], config["height"], config["fps"], config["seed"], config["tail"]) == (1280, 720, 30.0, 3, 1.0)
    assert (config["frame_w"], config["frame_h"]) == (16.0, 9.0)
    assert ir(scene)["ir_version"] == k.IR_VERSION


def test_build_accepts_size_presets_as_overrides() -> None:
    scene = k.scene(demo).build(size="720p")
    assert (scene.config.size, ir(scene)["config"]["width"]) == ((1280, 720), 1280)
