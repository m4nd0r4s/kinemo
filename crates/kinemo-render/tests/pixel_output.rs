//! Rasterized frames: units → pixels mapping (y up → y down), background, transparency.
//! The test frame is 16 x 9 units at 160 x 90 px, so 10 px per unit, origin at (80, 45).

mod common;

use common::*;

/// 2 x 2 red square centered at (-4, 2) units: pixel center (40, 25), spans x 30..50, y 15..35.
fn red_square_scene() -> kinemo_ir::Scene {
    let mut b = SceneBuilder::new();
    b.background(BLUE);
    let r = b.filled_rect(2.0, 2.0, RED);
    b.at(r, -4.0, 2.0);
    b.build()
}

#[test]
fn image_has_requested_size() {
    let img = render_small(&red_square_scene(), 0.0, false);
    assert_eq!((img.width, img.height), (SMALL_WIDTH, SMALL_HEIGHT));
    assert_eq!(img.rgba.len(), (SMALL_WIDTH * SMALL_HEIGHT * 4) as usize);
}

#[test]
fn filled_rect_lands_on_expected_pixels() {
    let img = render_small(&red_square_scene(), 0.0, false);
    for (x, y) in [(40, 25), (30, 15), (49, 34), (31, 33)] {
        assert_eq!(pixel(&img, x, y), to_rgba8(RED), "pixel ({x}, {y})");
    }
}

#[test]
fn filled_rect_does_not_spill_outside_its_box() {
    let img = render_small(&red_square_scene(), 0.0, false);
    for (x, y) in [(29, 25), (50, 25), (40, 14), (40, 35)] {
        assert_eq!(pixel(&img, x, y), to_rgba8(BLUE), "pixel ({x}, {y})");
    }
}

#[test]
fn positive_y_is_drawn_in_the_upper_half() {
    let img = render_small(&red_square_scene(), 0.0, false);
    // The vertical mirror of the square (y = -2 units → row 65) must stay background.
    assert_eq!(pixel(&img, 40, 65), to_rgba8(BLUE));
}

#[test]
fn background_fills_everything_else() {
    let img = render_small(&red_square_scene(), 0.0, false);
    for (x, y) in [(0, 0), (159, 0), (0, 89), (159, 89), (80, 45)] {
        assert_eq!(pixel(&img, x, y), to_rgba8(BLUE), "pixel ({x}, {y})");
    }
}

#[test]
fn transparent_option_gives_zero_alpha_background() {
    let img = render_small(&red_square_scene(), 0.0, true);
    assert_eq!(pixel(&img, 0, 0)[3], 0);
    assert_eq!(pixel(&img, 120, 70)[3], 0);
    assert_eq!(pixel(&img, 40, 25), to_rgba8(RED));
}

#[test]
fn opaque_render_has_opaque_background() {
    let img = render_small(&red_square_scene(), 0.0, false);
    assert_eq!(pixel(&img, 0, 0)[3], 255);
}

#[test]
fn half_opacity_blends_with_background() {
    let mut b = SceneBuilder::new();
    b.background(BLACK);
    let r = b.filled_rect(2.0, 2.0, RED);
    b.prop_f(r, "opacity", 0.5);
    let img = render_small(&b.build(), 0.0, false);
    let p = pixel(&img, 80, 45);
    assert!((p[0] as i32 - 128).abs() <= 1, "got {p:?}");
    assert_eq!(p[3], 255);
}

#[test]
fn absent_leaf_leaves_background_untouched() {
    let mut scene = red_square_scene();
    scene.objects[0].presence = vec![(5.0, true)];
    let img = render_small(&scene, 0.0, false);
    assert_eq!(pixel(&img, 40, 25), to_rgba8(BLUE));
}
