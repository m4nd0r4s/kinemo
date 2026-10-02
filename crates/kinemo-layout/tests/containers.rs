//! Containers: `Row`, `Column`, `Grid`, `Stack`, alignment and reorder transitions.

mod common;

use common::*;
use kinemo_ir::{Ease, ObjectId, Value};

fn squares(b: &mut SceneBuilder, n: usize) -> Vec<ObjectId> {
    (0..n).map(|_| b.rect(1.0, 1.0)).collect()
}

#[test]
fn row_spaces_children_with_default_gap() {
    let mut b = SceneBuilder::new();
    let items = squares(&mut b, 3);
    let row = b.parent_of("row", &items);
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_v2(l.translation(items[0], 0.0), [-1.25, 0.0]);
        assert_v2(l.translation(items[1], 0.0), [0.0, 0.0]);
        assert_v2(l.translation(items[2], 0.0), [1.25, 0.0]);
        assert_rect(l.local_bbox(row, 0.0), [-1.75, -0.5, 1.75, 0.5]);
    });
}

#[test]
fn column_stacks_downwards_with_gap() {
    let mut b = SceneBuilder::new();
    let items = squares(&mut b, 3);
    let column = b.parent_of("column", &items);
    b.prop_f(column, "gap", 0.5);
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_v2(l.translation(items[0], 0.0), [0.0, 1.5]);
        assert_v2(l.translation(items[1], 0.0), [0.0, 0.0]);
        assert_v2(l.translation(items[2], 0.0), [0.0, -1.5]);
    });
}

#[test]
fn column_left_alignment_lines_up_left_edges() {
    let mut b = SceneBuilder::new();
    let wide = b.rect(3.0, 1.0);
    let narrow = b.rect(1.0, 1.0);
    let column = b.parent_of("column", &[wide, narrow]);
    b.prop(column, "align", Value::Str("left".into()));
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_near(l.world_bbox(wide, 0.0).x0, l.world_bbox(narrow, 0.0).x0);
    });
}

#[test]
fn grid_fills_rows_left_to_right() {
    let mut b = SceneBuilder::new();
    let items = squares(&mut b, 4);
    let grid = b.parent_of("grid", &items);
    b.prop_f(grid, "cols", 2.0);
    b.prop_f(grid, "gap", 0.0);
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_v2(l.translation(items[0], 0.0), [-0.5, 0.5]);
        assert_v2(l.translation(items[1], 0.0), [0.5, 0.5]);
        assert_v2(l.translation(items[2], 0.0), [-0.5, -0.5]);
        assert_v2(l.translation(items[3], 0.0), [0.5, -0.5]);
    });
}

#[test]
fn stack_overlaps_children_centered_or_aligned() {
    let mut b = SceneBuilder::new();
    let back = b.rect(2.0, 2.0);
    let icon = b.rect(1.0, 1.0);
    b.parent_of("stack", &[back, icon]);
    let back2 = b.rect(2.0, 2.0);
    let icon2 = b.rect(1.0, 1.0);
    let corner = b.parent_of("stack", &[back2, icon2]);
    b.prop(corner, "align", Value::Str("top-left".into()));
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_v2(l.translation(back, 0.0), [0.0, 0.0]);
        assert_v2(l.translation(icon, 0.0), [0.0, 0.0]);
        assert_v2(l.translation(icon2, 0.0), [-0.5, 0.5]);
    });
}

#[test]
fn row_bottom_alignment_of_different_heights() {
    let mut b = SceneBuilder::new();
    let short = b.rect(1.0, 1.0);
    let tall = b.rect(1.0, 3.0);
    let medium = b.rect(1.0, 2.0);
    let row = b.parent_of("row", &[short, tall, medium]);
    b.prop(row, "align", Value::Str("bottom".into()));
    let scene = b.build();
    with_layout(&scene, |l| {
        let bottoms: Vec<f64> = [short, tall, medium].iter().map(|&o| l.world_bbox(o, 0.0).y0).collect();
        assert_near(bottoms[0], -1.5);
        assert_near(bottoms[1], -1.5);
        assert_near(bottoms[2], -1.5);
    });
}

#[test]
fn placed_row_moves_its_children() {
    let mut b = SceneBuilder::new();
    let items = squares(&mut b, 2);
    let row = b.parent_of("row", &items);
    b.prop_f(row, "gap", 0.0);
    b.place(row, at("bottom-left"));
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_rect(l.world_bbox(row, 0.0), [-7.5, -4.0, -5.5, -3.0]);
        assert_rect(l.world_bbox(items[0], 0.0), [-7.5, -4.0, -6.5, -3.0]);
    });
}

#[test]
fn row_reorder_blends_positions_continuously() {
    let mut b = SceneBuilder::new();
    let items = squares(&mut b, 3);
    let row = b.object("row");
    let children = b.children(row, &items);
    b.entry(children, anim(1.0, 2.0, object_list(&[items[2], items[1], items[0]]), Ease::Linear));
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_v2(l.translation(items[0], 0.5), [-1.25, 0.0]);
        assert_v2(l.translation(items[0], 1.5), [0.0, 0.0]);
        assert_v2(l.translation(items[2], 1.5), [0.0, 0.0]);
        assert_v2(l.translation(items[1], 1.5), [0.0, 0.0]);
        assert_v2(l.translation(items[0], 2.0), [1.25, 0.0]);
        assert_v2(l.translation(items[2], 2.5), [-1.25, 0.0]);
        for &item in &items {
            let step = max_step(0.5, 2.5, 400, |t| l.translation(item, t));
            assert!(step < 0.05, "child {item} jumps by {step} during reorder");
        }
    });
}

#[test]
fn row_insert_keeps_existing_children_continuous() {
    let mut b = SceneBuilder::new();
    let items = squares(&mut b, 3);
    let row = b.object("row");
    let children = b.children(row, &items[..2]);
    // The third square joins the row (its parent link exists from the start).
    b.set_parent(items[2], row);
    b.entry(children, anim(1.0, 2.0, object_list(&items), Ease::Linear));
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_v2(l.translation(items[0], 0.5), [-0.625, 0.0]);
        assert_v2(l.translation(items[0], 2.0), [-1.25, 0.0]);
        let step = max_step(0.5, 2.5, 400, |t| l.translation(items[0], t));
        assert!(step < 0.05, "existing child jumps by {step} during insert");
    });
}
