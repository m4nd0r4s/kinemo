//! `stroke_width` is given in pixels at 1080p and scales with the output height.

mod common;

use common::*;
use kinemo_render::{display_list, render_frame, FrameSize, RenderOptions};

fn horizontal_line_scene(width_at_1080p: f64) -> kinemo_ir::Scene {
    let mut b = SceneBuilder::new();
    let l = b.line([-6.0, 0.0], [6.0, 0.0]);
    b.stroke(l, RED, width_at_1080p);
    b.build()
}

fn stroke_width_at(scene: &kinemo_ir::Scene, size: FrameSize) -> f64 {
    let dl = display_list(scene, 0.0, size, false);
    assert_eq!(dl.items.len(), 1);
    dl.items[0].stroke.as_ref().unwrap().width
}

#[test]
fn stroke_width_is_unchanged_at_1080p() {
    let w = stroke_width_at(&horizontal_line_scene(4.0), FrameSize { width: 1920, height: 1080 });
    assert_near(w, 4.0, 1e-12);
}

#[test]
fn stroke_width_halves_at_540p() {
    let w = stroke_width_at(&horizontal_line_scene(4.0), FrameSize { width: 960, height: 540 });
    assert_near(w, 2.0, 1e-12);
}

#[test]
fn stroke_width_doubles_at_2160p() {
    let w = stroke_width_at(&horizontal_line_scene(4.0), FrameSize { width: 3840, height: 2160 });
    assert_near(w, 8.0, 1e-12);
}

#[test]
fn open_line_has_stroke_but_no_fill() {
    let mut b = SceneBuilder::new();
    let l = b.line([-6.0, 0.0], [6.0, 0.0]);
    b.stroke(l, RED, 4.0);
    b.fill(l, BLUE);
    let dl = small_display_list(&b.build(), 0.0);
    assert_eq!(dl.items.len(), 1);
    assert!(dl.items[0].fill.is_none());
}

/// Rows covered by the line's stroke in the column at the image center.
fn painted_rows(scene: &kinemo_ir::Scene, width: u32, height: u32) -> Vec<u32> {
    let opts = RenderOptions { width, height, fps: 30.0, antialias: false, transparent: false };
    let img = render_frame(scene, 0.0, &opts);
    (0..height).filter(|&y| pixel(&img, width / 2, y)[0] > 0).collect()
}

#[test]
fn rendered_stroke_thickness_follows_output_height() {
    // 108 px at 1080p → 9 px at 90 px high, 18 px at 180 px high.
    let scene = horizontal_line_scene(108.0);
    let small = painted_rows(&scene, 160, 90);
    let large = painted_rows(&scene, 320, 180);
    assert_eq!(small.len(), 9, "rows: {small:?}");
    assert_eq!(large.len(), 18, "rows: {large:?}");
}

#[test]
fn rendered_stroke_is_centered_on_the_line() {
    let rows = painted_rows(&horizontal_line_scene(108.0), 160, 90);
    let mid = (rows[0] + rows[rows.len() - 1]) as f64 / 2.0;
    assert_near(mid, 45.0, 0.5);
}
