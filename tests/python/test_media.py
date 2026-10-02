"""Media objects: `k.Image` (raster files), `k.SVG` (imported illustrations with parts
addressable by id) and `k.Brace` (follows its target's box)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import kinemo as k
from conftest import build, raises_code, snapshot_of

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
RED_BLUE_PNG = str(FIXTURES / "red_blue.png")  # 4×2 px: left half red, right half blue
MACHINE_SVG = str(FIXTURES / "machine.svg")  # 200×100 viewBox, ids motor/housing/shaft/belt


def pixel_at(scene: Any, t: float, x: float, y: float) -> tuple[int, int, int, int]:
    """RGBA of the frame at scene point (x, y) (units, y-up)."""
    width, height, pixels = scene.builder.frame_rgba(t, "final")
    frame_h = 9.0  # short side of a landscape frame, in units
    frame_w = frame_h * width / height
    px = int((x + frame_w / 2) * width / frame_w)
    py = int((frame_h / 2 - y) * height / frame_h)
    i = (py * width + px) * 4
    return tuple(pixels[i : i + 4])  # type: ignore[return-value]


# ---- k.Image ------------------------------------------------------------------------------

def test_image_keeps_aspect_and_draws_its_pixels() -> None:
    @build
    def scene(s: k.Scene) -> None:
        photo = k.Image(RED_BLUE_PNG, height=2)
        s.add(photo)
        assert photo.pixel_size == (4, 2)
        assert abs(photo.width.now - 4.0) < 1e-6 and abs(photo.height.now - 2.0) < 1e-6

    red = pixel_at(scene, 0.0, -1.0, 0.0)
    blue = pixel_at(scene, 0.0, 1.0, 0.0)
    assert red[0] > 240 and red[2] < 15, red
    assert blue[2] > 240 and blue[0] < 15, blue
    background = pixel_at(scene, 0.0, -3.0, 0.0)
    assert background[:3] != red[:3]


def test_image_default_size_rotation_and_determinism() -> None:
    def body(s: k.Scene) -> None:
        photo = k.Image(RED_BLUE_PNG, rotate=180)
        s.add(photo)
        assert abs(photo.height.now - 3.0) < 1e-6
        s.play(k.fade_out(photo))

    first, second = build(body), build(body)
    assert first.builder.frame_png(0.3) == second.builder.frame_png(0.3)
    # Upside down: the red half is now on the right.
    assert pixel_at(first, 0.0, 2.0, 0.0)[0] > 240


def test_image_width_only_and_relative_path_next_to_the_scene_file() -> None:
    @build
    def scene(s: k.Scene) -> None:
        photo = k.Image("../fixtures/red_blue.png", width=1)
        s.add(photo)
        assert abs(photo.height.now - 0.5) < 1e-6

    assert snapshot_of(scene, 0.0, "photo")


def test_image_missing_file_is_a_diagnostic() -> None:
    with raises_code("K0105"):
        build(lambda s: s.add(k.Image("does_not_exist.png")))


def test_image_morphs_as_its_rectangle_and_exports_as_data_uri() -> None:
    @build
    def scene(s: k.Scene) -> None:
        photo = k.Image(RED_BLUE_PNG, height=2)
        s.add(photo)
        s.play(k.morph(photo, k.Circle(r=1, fill=k.GREEN, fill_opacity=1)))

    mid = scene.builder.frame_png(0.5)
    assert mid != scene.builder.frame_png(0.0)
    svg = scene.builder.frame_svg(0.0, False)
    assert "<image" in svg and "data:image/png;base64," in svg


# ---- k.SVG --------------------------------------------------------------------------------

def test_svg_parts_are_paths_and_groups_addressable_by_id() -> None:
    @build
    def scene(s: k.Scene) -> None:
        machine = k.SVG(MACHINE_SVG, height=2)
        s.add(machine)
        assert machine.ids == ["motor", "housing", "shaft", "belt"]
        motor = machine["#motor"]
        assert isinstance(motor, k.Group) and machine["motor"] is motor
        assert isinstance(machine["#shaft"], k.Path) and machine["#shaft"] in motor.children
        assert abs(machine.height.now - 2.0) < 1e-6 and abs(machine.width.now - 4.0) < 1e-6
        # The housing spans x 0..80 of 200 → -2..-0.4 units; the y axis flips.
        housing = machine["#housing"]
        assert abs(housing.left.now + 2.0) < 1e-4 and abs(housing.right.now + 0.4) < 1e-4
        assert abs(motor.opacity.now - 0.8) < 1e-6
        assert machine["#belt"].fill_opacity.now == 0.0 and machine["#belt"].stroke_width.now > 0
        s.play(machine["#shaft"].to(fill=k.RED))

    housing = pixel_at(scene, 0.0, -1.8, 0.8)
    assert housing[2] > housing[0], housing  # blue (#4C9BE8 at 80% over the background)
    shaft = pixel_at(scene, 1.0, -1.2, 0.0)
    assert shaft[0] > shaft[2], shaft  # recolored red


def test_svg_unknown_id_suggests_the_closest() -> None:
    def body(s: k.Scene) -> None:
        machine = k.SVG(MACHINE_SVG)
        machine["#motr"]

    with raises_code("K0105") as info:
        build(body)
    assert "motor" in info.value.diagnostic.render()


def test_svg_inline_markup() -> None:
    @build
    def scene(s: k.Scene) -> None:
        dot = k.SVG('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle id="c" cx="5" cy="5" r="5" fill="#ff0000"/></svg>', height=1)
        s.add(dot)
        assert dot.ids == ["c"]

    assert pixel_at(scene, 0.0, 0.0, 0.0)[0] > 240


# ---- k.Brace ------------------------------------------------------------------------------

def test_brace_follows_a_moving_target() -> None:
    @build
    def scene(s: k.Scene) -> None:
        box = k.Rect(2, 1)
        brace = k.Brace(box, "down", label="n", gap=0.1)
        s.add(box, brace)
        assert abs(brace.shape.top.now - (-0.6)) < 1e-6
        assert abs(brace.shape.width.now - 2.0) < 1e-6
        assert brace.label.top.now < brace.shape.bottom.now
        s.play(box.to(x=3, w=4))
        assert abs(brace.shape.left.now - 1.0) < 1e-6 and abs(brace.shape.right.now - 5.0) < 1e-6
        assert abs(brace.label.center.now[0] - 3.0) < 1e-6

    assert snapshot_of(scene, 1.0, "box")


def test_brace_sides() -> None:
    @build
    def scene(s: k.Scene) -> None:
        box = k.Square(2)
        right = k.Brace(box, "right", gap=0.2)
        up = k.Brace(box, "up")
        s.add(box, right, up)
        assert abs(right.shape.left.now - 1.2) < 1e-6 and abs(right.shape.height.now - 2.0) < 1e-6
        assert abs(up.shape.bottom.now - 1.1) < 1e-6
        assert up.label is None


def test_brace_rejects_unknown_direction() -> None:
    with raises_code("K0105"):
        build(lambda s: s.add(k.Brace(k.Circle(), "sideways")))
