//! `_draw` traces the outline then fills; `_write` reveals text glyphs in order.

mod common;

use common::*;
use kinemo_render::raster::DisplayList;

/// 2 x 1 unit rect = 20 x 10 px, perimeter 60 px.
const RECT_PERIMETER_PX: f64 = 60.0;

fn stroked_rect_scene(draw: f64) -> kinemo_ir::Scene {
    let mut b = SceneBuilder::new();
    let r = b.filled_rect(2.0, 1.0, RED);
    b.stroke(r, BLUE, 4.0);
    b.prop_f(r, "_draw", draw);
    b.build()
}

fn stroke_items(dl: &DisplayList) -> Vec<&kinemo_render::raster::DrawItem> {
    dl.items.iter().filter(|i| i.stroke.is_some()).collect()
}

#[test]
fn draw_zero_draws_nothing() {
    assert!(small_display_list(&stroked_rect_scene(0.0), 0.0).items.is_empty());
}

#[test]
fn draw_complete_is_one_item_with_full_outline() {
    let dl = small_display_list(&stroked_rect_scene(1.0), 0.0);
    assert_eq!(dl.items.len(), 1);
    let item = &dl.items[0];
    assert_eq!(item.fill.as_ref().unwrap().color, RED);
    assert!(item.stroke.is_some());
    assert_near(item_length(item), RECT_PERIMETER_PX, 1e-6);
}

#[test]
fn partial_draw_trims_the_outline_stroke() {
    // outline fraction = 0.35 / 0.7 = 0.5.
    let dl = small_display_list(&stroked_rect_scene(0.35), 0.0);
    let strokes = stroke_items(&dl);
    assert_eq!(strokes.len(), 1);
    assert!(strokes[0].fill.is_none(), "the traced outline is a separate stroke-only item");
    assert_near(item_length(strokes[0]), RECT_PERIMETER_PX * 0.5, 1e-3);
}

#[test]
fn partial_draw_fill_is_transparent_before_halfway() {
    let dl = small_display_list(&stroked_rect_scene(0.35), 0.0);
    let fills: Vec<_> = dl.items.iter().filter_map(|i| i.fill.as_ref()).collect();
    assert!(fills.iter().all(|f| f.color[3] == 0.0), "fill alpha should be 0, got {fills:?}");
}

#[test]
fn partial_draw_fill_is_partial_after_halfway() {
    // fill fraction = (0.75 - 0.5) / 0.5 = 0.5; outline already complete.
    let dl = small_display_list(&stroked_rect_scene(0.75), 0.0);
    let fill_item = dl.items.iter().find(|i| i.fill.is_some()).expect("fill item");
    assert!(fill_item.stroke.is_none());
    assert_near(fill_item.fill.as_ref().unwrap().color[3], 0.5, 1e-12);
    assert_near(item_length(stroke_items(&dl)[0]), RECT_PERIMETER_PX, 1e-6);
}

#[test]
fn partial_draw_without_stroke_traces_with_fill_color() {
    let mut b = SceneBuilder::new();
    let r = b.filled_rect(2.0, 1.0, RED);
    b.prop_f(r, "_draw", 0.35);
    let dl = small_display_list(&b.build(), 0.0);
    let strokes = stroke_items(&dl);
    assert_eq!(strokes.len(), 1);
    let s = strokes[0].stroke.as_ref().unwrap();
    assert_eq!(&s.color[..3], &RED[..3]);
    assert_near(s.width, 2.0 * SMALL_HEIGHT as f64 / 1080.0, 1e-12);
    assert_near(item_length(strokes[0]), RECT_PERIMETER_PX * 0.5, 1e-3);
}

fn text_scene(text: &str, write: f64) -> kinemo_ir::Scene {
    let mut b = SceneBuilder::new();
    let t = b.text(text, RED);
    b.prop_f(t, "_write", write);
    b.build()
}

/// Items that are fully revealed glyphs (fill at full alpha, no reveal stroke).
fn complete_glyphs(dl: &DisplayList) -> Vec<&kinemo_render::raster::DrawItem> {
    dl.items.iter().filter(|i| i.stroke.is_none() && i.fill.as_ref().is_some_and(|f| f.color[3] == 1.0)).collect()
}

#[test]
fn write_complete_draws_every_glyph_fully() {
    let dl = small_display_list(&text_scene("ABCDEFGHIJ", 1.0), 0.0);
    assert_eq!(dl.items.len(), 10);
    assert_eq!(complete_glyphs(&dl).len(), 10);
}

#[test]
fn write_zero_draws_nothing() {
    assert!(small_display_list(&text_scene("ABCDEFGHIJ", 0.0), 0.0).items.is_empty());
}

#[test]
fn write_reveals_more_glyphs_as_it_progresses() {
    let counts: Vec<usize> = [0.1, 0.3, 0.6, 0.9]
        .iter()
        .map(|&w| complete_glyphs(&small_display_list(&text_scene("ABCDEFGHIJ", w), 0.0)).len())
        .collect();
    assert!(counts.windows(2).all(|p| p[0] <= p[1]), "counts not monotonic: {counts:?}");
    assert!(counts[0] < 10 && counts[3] > counts[0], "counts: {counts:?}");
}

#[test]
fn write_reveals_glyphs_left_to_right() {
    let partial = small_display_list(&text_scene("ABCDEFGHIJ", 0.4), 0.0);
    let full = small_display_list(&text_scene("ABCDEFGHIJ", 1.0), 0.0);
    let right_edge = |dl: &DisplayList| dl.items.iter().map(|i| path_bbox(&i.path).x1).fold(f64::MIN, f64::max);
    let left_edge = |dl: &DisplayList| dl.items.iter().map(|i| path_bbox(&i.path).x0).fold(f64::MAX, f64::min);
    assert!(!partial.items.is_empty());
    assert!(right_edge(&partial) < right_edge(&full) - 1.0, "last glyphs should not be drawn yet");
    assert_near(left_edge(&partial), left_edge(&full), 1e-6);
    let first_complete = complete_glyphs(&partial);
    assert!(!first_complete.is_empty(), "the first glyph should be complete at w=0.4");
    assert_near(path_bbox(&first_complete[0].path).x0, left_edge(&full), 1e-6);
}
