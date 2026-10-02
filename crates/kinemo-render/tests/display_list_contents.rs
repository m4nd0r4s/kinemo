//! Which leaves contribute draw items at a given time.

mod common;

use common::*;
use kinemo_ir::Value;

#[test]
fn leaf_draws_only_while_present() {
    let mut b = SceneBuilder::new();
    let r = b.filled_rect(2.0, 2.0, RED);
    b.presence(r, vec![(1.0, true), (3.0, false)]);
    let scene = b.build();
    assert_eq!(small_display_list(&scene, 0.5).items.len(), 0);
    assert_eq!(small_display_list(&scene, 1.0).items.len(), 1);
    assert_eq!(small_display_list(&scene, 2.9).items.len(), 1);
    assert_eq!(small_display_list(&scene, 3.0).items.len(), 0);
}

#[test]
fn leaf_reappears_after_second_entry() {
    let mut b = SceneBuilder::new();
    let r = b.filled_rect(2.0, 2.0, RED);
    b.presence(r, vec![(0.0, true), (1.0, false), (2.0, true)]);
    let scene = b.build();
    assert_eq!(small_display_list(&scene, 1.5).items.len(), 0);
    assert_eq!(small_display_list(&scene, 2.5).items.len(), 1);
}

#[test]
fn group_draws_nothing_itself_only_its_leaves() {
    let mut b = SceneBuilder::new();
    let a = b.filled_rect(1.0, 1.0, RED);
    let c = b.filled_rect(1.0, 1.0, BLUE);
    let g = b.group(&[a, c]);
    b.fill(g, GREEN);
    let scene = b.build();
    assert_eq!(fill_colors(&small_display_list(&scene, 0.0)), vec![Some(RED), Some(BLUE)]);
}

#[test]
fn empty_group_draws_nothing() {
    let mut b = SceneBuilder::new();
    let g = b.group(&[]);
    b.fill(g, GREEN);
    let scene = b.build();
    assert!(small_display_list(&scene, 0.0).items.is_empty());
}

#[test]
fn absent_child_of_group_is_skipped() {
    let mut b = SceneBuilder::new();
    let a = b.filled_rect(1.0, 1.0, RED);
    let c = b.filled_rect(1.0, 1.0, BLUE);
    b.presence(c, vec![(2.0, true)]);
    b.group(&[a, c]);
    let scene = b.build();
    assert_eq!(fill_colors(&small_display_list(&scene, 1.0)), vec![Some(RED)]);
    assert_eq!(fill_colors(&small_display_list(&scene, 2.0)), vec![Some(RED), Some(BLUE)]);
}

#[test]
fn invisible_group_hides_its_children() {
    let mut b = SceneBuilder::new();
    let a = b.filled_rect(1.0, 1.0, RED);
    let g = b.group(&[a]);
    b.prop(g, "visible", Value::Bool(false));
    let scene = b.build();
    assert!(small_display_list(&scene, 0.0).items.is_empty());
}

#[test]
fn leaf_without_fill_or_stroke_draws_nothing() {
    let mut b = SceneBuilder::new();
    b.rect(2.0, 2.0);
    let scene = b.build();
    assert!(small_display_list(&scene, 0.0).items.is_empty());
}

#[test]
fn fill_with_zero_fill_opacity_draws_nothing() {
    let mut b = SceneBuilder::new();
    let r = b.filled_rect(2.0, 2.0, RED);
    b.prop_f(r, "fill_opacity", 0.0);
    let scene = b.build();
    assert!(small_display_list(&scene, 0.0).items.is_empty());
}
