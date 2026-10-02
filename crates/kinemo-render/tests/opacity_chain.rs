//! Opacity inheritance: `opacity` and `_fade` multiply down the tree.

mod common;

use common::*;

fn only_item_opacity(scene: &kinemo_ir::Scene) -> f64 {
    let dl = small_display_list(scene, 0.0);
    assert_eq!(dl.items.len(), 1);
    dl.items[0].opacity
}

#[test]
fn leaf_opacity_is_item_opacity() {
    let mut b = SceneBuilder::new();
    let r = b.filled_rect(1.0, 1.0, RED);
    b.prop_f(r, "opacity", 0.5);
    assert_near(only_item_opacity(&b.build()), 0.5, 1e-12);
}

#[test]
fn parent_opacity_multiplies_child_opacity() {
    let mut b = SceneBuilder::new();
    let r = b.filled_rect(1.0, 1.0, RED);
    b.prop_f(r, "opacity", 0.5);
    let g = b.group(&[r]);
    b.prop_f(g, "opacity", 0.5);
    assert_near(only_item_opacity(&b.build()), 0.25, 1e-12);
}

#[test]
fn parent_fade_affects_children() {
    let mut b = SceneBuilder::new();
    let r = b.filled_rect(1.0, 1.0, RED);
    let g = b.group(&[r]);
    b.prop_f(g, "_fade", 0.4);
    assert_near(only_item_opacity(&b.build()), 0.4, 1e-12);
}

#[test]
fn grandparent_opacity_and_fade_combine_with_leaf() {
    let mut b = SceneBuilder::new();
    let r = b.filled_rect(1.0, 1.0, RED);
    b.prop_f(r, "_fade", 0.5);
    let g = b.group(&[r]);
    let top = b.group(&[g]);
    b.prop_f(top, "opacity", 0.8);
    b.prop_f(top, "_fade", 0.5);
    assert_near(only_item_opacity(&b.build()), 0.2, 1e-12);
}

#[test]
fn fully_faded_parent_removes_child_items() {
    let mut b = SceneBuilder::new();
    let r = b.filled_rect(1.0, 1.0, RED);
    let g = b.group(&[r]);
    b.prop_f(g, "_fade", 0.0);
    assert!(small_display_list(&b.build(), 0.0).items.is_empty());
}

#[test]
fn opacity_does_not_alter_fill_color_alpha() {
    let mut b = SceneBuilder::new();
    let r = b.filled_rect(1.0, 1.0, RED);
    b.prop_f(r, "opacity", 0.5);
    let dl = small_display_list(&b.build(), 0.0);
    assert_eq!(dl.items[0].fill.as_ref().unwrap().color, RED);
}
