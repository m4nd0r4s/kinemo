//! Transforms, group boxes, derived props and render-only effects.

mod common;

use common::*;
use kinemo_eval::Evaluator;
use kinemo_ir::{BinOp, Expr, Lerp, Side, Src, Value};
use kinemo_layout::Layout;

#[test]
fn scale_about_center_by_default() {
    let mut b = SceneBuilder::new();
    let r = b.rect(2.0, 1.0);
    b.prop_f(r, "scale", 2.0);
    let scene = b.build();
    with_layout(&scene, |l| assert_rect(l.parent_box(r, 0.0), [-2.0, -1.0, 2.0, 1.0]));
}

#[test]
fn scale_about_bottom_left_anchor() {
    let mut b = SceneBuilder::new();
    let r = b.rect(2.0, 1.0);
    b.prop_f(r, "scale", 2.0);
    b.prop(r, "anchor", Value::Vec2([-1.0, -1.0]));
    let scene = b.build();
    with_layout(&scene, |l| assert_rect(l.parent_box(r, 0.0), [-1.0, -0.5, 3.0, 1.5]));
}

#[test]
fn rotate_about_center_and_about_anchor() {
    let mut b = SceneBuilder::new();
    let centered = b.rect(2.0, 1.0);
    b.prop_f(centered, "rotate", 90.0);
    let pivoted = b.rect(2.0, 1.0);
    b.prop_f(pivoted, "rotate", 90.0);
    b.prop(pivoted, "anchor", Value::Vec2([-1.0, -1.0]));
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_rect(l.parent_box(centered, 0.0), [-0.5, -1.0, 0.5, 1.0]);
        assert_rect(l.parent_box(pivoted, 0.0), [-2.0, -0.5, -1.0, 1.5]);
    });
}

#[test]
fn group_bbox_includes_transformed_children() {
    let mut b = SceneBuilder::new();
    let scaled = b.rect(2.0, 1.0);
    b.prop_f(scaled, "scale", 2.0);
    b.prop_f(scaled, "x", 3.0);
    let rotated = b.rect(2.0, 1.0);
    b.prop_f(rotated, "rotate", 90.0);
    b.prop_f(rotated, "x", -3.0);
    let group = b.parent_of("group", &[scaled, rotated]);
    let scene = b.build();
    with_layout(&scene, |l| assert_rect(l.local_bbox(group, 0.0), [-3.5, -1.0, 5.0, 1.0]));
}

#[test]
fn empty_children_do_not_stretch_a_group_box() {
    let mut b = SceneBuilder::new();
    let square = b.rect(1.0, 1.0);
    b.prop_f(square, "x", 3.0);
    let empty = b.parent_of("group", &[]);
    let group = b.parent_of("group", &[square, empty]);
    let scene = b.build();
    with_layout(&scene, |l| assert_rect(l.local_bbox(group, 0.0), [2.5, -0.5, 3.5, 0.5]));
}

#[test]
fn world_bbox_of_nested_groups_composes_transforms() {
    let mut b = SceneBuilder::new();
    let leaf = b.rect(1.0, 1.0);
    b.prop_f(leaf, "x", 0.5);
    let inner = b.parent_of("group", &[leaf]);
    b.prop_f(inner, "x", 2.0);
    let outer = b.parent_of("group", &[inner]);
    b.prop_f(outer, "x", 1.0);
    b.prop_f(outer, "y", 1.0);
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_rect(l.world_bbox(leaf, 0.0), [3.0, 0.5, 4.0, 1.5]);
        assert_rect(l.world_bbox(inner, 0.0), [3.0, 0.5, 4.0, 1.5]);
        assert_rect(l.world_bbox(outer, 0.0), [3.0, 0.5, 4.0, 1.5]);
    });

    // Scaling the outer group (pivot at its bbox center) scales everything inside.
    let mut b = SceneBuilder::new();
    let leaf = b.rect(1.0, 1.0);
    b.prop_f(leaf, "x", 0.5);
    let inner = b.parent_of("group", &[leaf]);
    b.prop_f(inner, "x", 2.0);
    let outer = b.parent_of("group", &[inner]);
    b.prop_f(outer, "x", 1.0);
    b.prop_f(outer, "y", 1.0);
    b.prop_f(outer, "scale", 2.0);
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_rect(l.world_bbox(leaf, 0.0), [2.5, 0.0, 4.5, 2.0]);
        assert_rect(l.world_bbox(outer, 0.0), [2.5, 0.0, 4.5, 2.0]);
    });
}

#[test]
fn scaling_a_group_preserves_internal_relations() {
    let mut b = SceneBuilder::new();
    let base = b.rect(2.0, 1.0);
    let label = b.rect(1.0, 0.5);
    b.place(label, side(Side::Above, base).gap(0.0));
    let group = b.parent_of("group", &[base, label]);
    b.prop_f(group, "scale", 3.0);
    let scene = b.build();
    with_layout(&scene, |l| {
        let (wb, wl) = (l.world_bbox(base, 0.0), l.world_bbox(label, 0.0));
        assert_near(wl.y0, wb.y1);
        assert_near(wl.width(), 3.0);
    });
}

#[test]
fn derived_props_through_evaluator_with_layout_resolver() {
    let mut b = SceneBuilder::new();
    let r = b.rect(2.0, 1.0);
    b.place(r, at("top-left"));
    let scene = b.build();
    let ev = Evaluator::new(&scene);
    let layout = Layout::new(&ev);
    let read = |prop: &str| ev.expr(&derived(r, prop), 0.0, &layout);
    assert_eq!(read("left"), Value::Float(-7.5));
    assert_eq!(read("top"), Value::Float(4.0));
    assert_eq!(read("width"), Value::Float(2.0));
    assert_eq!(read("height"), Value::Float(1.0));
    assert_eq!(read("center"), Value::Vec2([-6.5, 3.5]));
    assert_eq!(read("x"), Value::Float(-6.5));
}

#[test]
fn prop_bound_to_derived_value_follows_layout() {
    // follower.x = leader.right + 1 (reactive binding), leader moves.
    let mut b = SceneBuilder::new();
    let leader = b.rect(2.0, 1.0);
    let leader_x = b.prop_f(leader, "x", 0.0);
    b.entry(leader_x, anim(0.0, 1.0, Value::Float(2.0), kinemo_ir::Ease::Linear));
    let follower = b.rect(1.0, 1.0);
    let follower_x = b.prop_f(follower, "x", 0.0);
    let bound = Expr::Bin {
        f: BinOp::Add,
        a: Box::new(derived(leader, "right")),
        b: Box::new(constant(Value::Float(1.0))),
    };
    b.entry(follower_x, set(0.0, Src::Expr { e: bound }));
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_near(l.translation(follower, 0.0)[0], 2.0);
        assert_near(l.translation(follower, 0.5)[0], 3.0);
        assert_near(l.translation(follower, 1.0)[0], 4.0);
    });
}

#[test]
fn derived_world_reads_compose_parents() {
    let mut b = SceneBuilder::new();
    let leaf = b.rect(1.0, 1.0);
    b.prop_f(leaf, "x", 1.0);
    let group = b.parent_of("group", &[leaf]);
    b.prop_f(group, "x", 2.0);
    let scene = b.build();
    let ev = Evaluator::new(&scene);
    let layout = Layout::new(&ev);
    let world = Expr::Derived { obj: leaf, prop: "left".into(), world: true };
    assert_eq!(ev.expr(&derived(leaf, "left"), 0.0, &layout), Value::Float(0.5));
    assert_eq!(ev.expr(&world, 0.0, &layout), Value::Float(2.5));
}

#[test]
fn render_effects_do_not_move_layout_dependents() {
    let build = |with_effects: bool| {
        let mut b = SceneBuilder::new();
        let a = b.rect(2.0, 2.0);
        if with_effects {
            b.prop_f(a, "_grow", 0.25);
            b.prop(a, "_shift", Value::Vec2([3.0, -1.0]));
        }
        let dependent = b.rect(1.0, 1.0);
        b.place(dependent, side(Side::RightOf, a).gap(0.5));
        let free = b.signal(Value::Float(0.0), Lerp::Linear);
        b.entry(free, set(0.0, Src::Expr { e: derived(a, "width") }));
        (b.build(), a, dependent, free)
    };
    let (plain, ..) = build(false);
    let (effects, a, dependent, free) = build(true);
    let expected = with_layout(&plain, |l| l.translation(dependent, 0.0));
    let ev = Evaluator::new(&effects);
    let l = Layout::new(&ev);
    assert_v2(l.translation(dependent, 0.0), expected);
    assert_rect(l.world_bbox(a, 0.0), [-1.0, -1.0, 1.0, 1.0]);
    assert_eq!(ev.signal(free, 0.0, &l), Value::Float(2.0));
    // ...but the render transform does carry them: shrunk to a quarter, then shifted.
    let corner = l.render_affine(a, 0.0) * kurbo::Point::new(1.0, 1.0);
    assert_v2([corner.x, corner.y], [3.25, -0.75]);
}
