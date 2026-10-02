//! Draw order: accumulated `z` first, tree order as the tie-breaker.

mod common;

use common::*;

#[test]
fn roots_draw_in_insertion_order_when_z_is_equal() {
    let mut b = SceneBuilder::new();
    b.filled_rect(1.0, 1.0, RED);
    b.filled_rect(1.0, 1.0, BLUE);
    let scene = b.build();
    assert_eq!(fill_colors(&small_display_list(&scene, 0.0)), vec![Some(RED), Some(BLUE)]);
}

#[test]
fn higher_z_draws_later_regardless_of_tree_order() {
    let mut b = SceneBuilder::new();
    let first = b.filled_rect(1.0, 1.0, RED);
    b.prop_f(first, "z", 1.0);
    b.filled_rect(1.0, 1.0, BLUE);
    let scene = b.build();
    assert_eq!(fill_colors(&small_display_list(&scene, 0.0)), vec![Some(BLUE), Some(RED)]);
}

#[test]
fn negative_z_draws_before_default_z() {
    let mut b = SceneBuilder::new();
    b.filled_rect(1.0, 1.0, RED);
    let second = b.filled_rect(1.0, 1.0, BLUE);
    b.prop_f(second, "z", -1.0);
    let scene = b.build();
    assert_eq!(fill_colors(&small_display_list(&scene, 0.0)), vec![Some(BLUE), Some(RED)]);
}

#[test]
fn group_children_draw_in_children_list_order() {
    let mut b = SceneBuilder::new();
    let a = b.filled_rect(1.0, 1.0, RED);
    let c = b.filled_rect(1.0, 1.0, BLUE);
    b.group(&[c, a]);
    let scene = b.build();
    assert_eq!(fill_colors(&small_display_list(&scene, 0.0)), vec![Some(BLUE), Some(RED)]);
}

#[test]
fn ancestor_z_is_added_to_child_z() {
    let mut b = SceneBuilder::new();
    let child = b.filled_rect(1.0, 1.0, RED);
    let g = b.group(&[child]);
    b.prop_f(g, "z", 2.0);
    let sibling = b.filled_rect(1.0, 1.0, BLUE);
    b.prop_f(sibling, "z", 1.5);
    let scene = b.build();
    // child: 2 + 0 = 2 > 1.5, so it is drawn on top even though it comes first in the tree.
    assert_eq!(fill_colors(&small_display_list(&scene, 0.0)), vec![Some(BLUE), Some(RED)]);
}

#[test]
fn negative_group_z_pulls_child_below_root_sibling() {
    let mut b = SceneBuilder::new();
    let sibling = b.filled_rect(1.0, 1.0, BLUE);
    b.prop_f(sibling, "z", 0.5);
    let child = b.filled_rect(1.0, 1.0, RED);
    b.prop_f(child, "z", 1.0);
    let g = b.group(&[child]);
    b.prop_f(g, "z", -1.0);
    let scene = b.build();
    // child: -1 + 1 = 0 < 0.5.
    assert_eq!(fill_colors(&small_display_list(&scene, 0.0)), vec![Some(RED), Some(BLUE)]);
}

#[test]
fn equal_accumulated_z_falls_back_to_tree_order_across_groups() {
    let mut b = SceneBuilder::new();
    let a = b.filled_rect(1.0, 1.0, RED);
    b.prop_f(a, "z", 1.0);
    b.group(&[a]);
    let c = b.filled_rect(1.0, 1.0, BLUE);
    let h = b.group(&[c]);
    b.prop_f(h, "z", 1.0);
    let scene = b.build();
    assert_eq!(fill_colors(&small_display_list(&scene, 0.0)), vec![Some(RED), Some(BLUE)]);
}
