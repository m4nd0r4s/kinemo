//! `.place(...)`: frame anchors, relative sides, inside, clamp, blending and cycles.

mod common;

use common::*;
use kinemo_ir::{Ease, Side};
use kinemo_layout::LayoutIssueKind;

#[test]
fn at_center_ignores_default_margin() {
    let mut b = SceneBuilder::new();
    let r = b.rect(2.0, 1.0);
    b.place(r, at("center"));
    let scene = b.build();
    with_layout(&scene, |l| assert_v2(l.translation(r, 0.0), [0.0, 0.0]));
}

#[test]
fn at_top_uses_default_margin_of_half_unit() {
    let mut b = SceneBuilder::new();
    let r = b.rect(2.0, 1.0);
    b.place(r, at("top"));
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_v2(l.translation(r, 0.0), [0.0, 3.5]);
        assert_rect(l.world_bbox(r, 0.0), [-1.0, 3.0, 1.0, 4.0]);
    });
}

#[test]
fn at_top_left_touches_both_margins() {
    let mut b = SceneBuilder::new();
    let r = b.rect(2.0, 1.0);
    b.place(r, at("top-left"));
    let scene = b.build();
    with_layout(&scene, |l| assert_rect(l.world_bbox(r, 0.0), [-7.5, 3.0, -5.5, 4.0]));
}

#[test]
fn explicit_margin_overrides_default() {
    let mut b = SceneBuilder::new();
    let r = b.rect(2.0, 1.0);
    b.place(r, at("bottom-right").margin(0.0));
    let scene = b.build();
    with_layout(&scene, |l| assert_rect(l.world_bbox(r, 0.0), [6.0, -4.5, 8.0, -3.5]));
}

#[test]
fn below_with_gap_is_centered_on_target() {
    let mut b = SceneBuilder::new();
    let target = b.rect(2.0, 1.0);
    b.prop_f(target, "x", 2.0);
    let r = b.rect(1.0, 1.0);
    b.place(r, side(Side::Below, target).gap(0.5));
    let scene = b.build();
    with_layout(&scene, |l| assert_v2(l.translation(r, 0.0), [2.0, -1.5]));
}

#[test]
fn above_with_left_alignment() {
    let mut b = SceneBuilder::new();
    let target = b.rect(2.0, 1.0);
    let r = b.rect(1.0, 1.0);
    b.place(r, side(Side::Above, target).gap(0.5).align("left"));
    let scene = b.build();
    with_layout(&scene, |l| assert_rect(l.world_bbox(r, 0.0), [-1.0, 1.0, 0.0, 2.0]));
}

#[test]
fn right_of_uses_default_gap() {
    let mut b = SceneBuilder::new();
    let target = b.rect(2.0, 1.0);
    let r = b.rect(1.0, 1.0);
    b.place(r, side(Side::RightOf, target));
    let scene = b.build();
    with_layout(&scene, |l| assert_v2(l.translation(r, 0.0), [1.75, 0.0]));
}

#[test]
fn left_of_with_top_alignment() {
    let mut b = SceneBuilder::new();
    let target = b.rect(2.0, 1.0);
    let r = b.rect(1.0, 0.4);
    b.place(r, side(Side::LeftOf, target).gap(0.3).align("top"));
    let scene = b.build();
    with_layout(&scene, |l| assert_rect(l.world_bbox(r, 0.0), [-2.3, 0.1, -1.3, 0.5]));
}

#[test]
fn inside_bottom_uses_gap_as_padding() {
    let mut b = SceneBuilder::new();
    let frame = b.rect(4.0, 2.0);
    b.prop_f(frame, "x", 1.0);
    b.prop_f(frame, "y", 1.0);
    let r = b.rect(1.0, 1.0);
    b.place(r, side(Side::Inside, frame).gap(0.2).align("bottom"));
    let scene = b.build();
    with_layout(&scene, |l| assert_rect(l.world_bbox(r, 0.0), [0.5, 0.2, 1.5, 1.2]));
}

#[test]
fn placement_follows_a_moving_target() {
    let mut b = SceneBuilder::new();
    let target = b.rect(1.0, 1.0);
    let x = b.prop_f(target, "x", 0.0);
    b.entry(x, anim(0.0, 1.0, kinemo_ir::Value::Float(4.0), Ease::Linear));
    let r = b.rect(1.0, 1.0);
    b.place(r, side(Side::Above, target).gap(0.0));
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_v2(l.translation(r, 0.5), [2.0, 1.0]);
        assert_v2(l.translation(r, 1.0), [4.0, 1.0]);
    });
}

#[test]
fn clamp_keeps_object_in_safe_area() {
    let mut b = SceneBuilder::new();
    let far = b.rect(2.0, 2.0);
    b.place(far, at_point(10.0, 0.0).clamped());
    let edge = b.rect(2.0, 2.0);
    b.place(edge, at("right").margin(0.0).clamped());
    let inside = b.rect(2.0, 2.0);
    b.place(inside, at_point(1.0, 1.0).clamped());
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_v2(l.translation(far, 0.0), [6.5, 0.0]);
        assert_v2(l.translation(edge, 0.0), [6.5, 0.0]);
        assert_v2(l.translation(inside, 0.0), [1.0, 1.0]);
    });
}

#[test]
fn placement_change_blends_with_ease() {
    let mut b = SceneBuilder::new();
    let r = b.rect(2.0, 1.0);
    b.place(r, at("center"));
    b.place_entry(r, 1.0, 1.0, Ease::Linear, Some(at("right").margin(0.0)));
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_v2(l.translation(r, 0.99999), [0.0, 0.0]);
        assert_v2(l.translation(r, 1.5), [3.5, 0.0]);
        assert_v2(l.translation(r, 2.0), [7.0, 0.0]);
        let step = max_step(0.5, 2.5, 400, |t| l.translation(r, t));
        assert!(step < 0.1, "placement blend jumps by {step}");
    });
}

#[test]
fn placement_blend_from_free_position() {
    let mut b = SceneBuilder::new();
    let r = b.rect(1.0, 1.0);
    b.prop_f(r, "x", -4.0);
    b.place_entry(r, 1.0, 2.0, Ease::Smooth, Some(at("center")));
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_v2(l.translation(r, 0.5), [-4.0, 0.0]);
        assert_v2(l.translation(r, 3.0), [0.0, 0.0]);
        let step = max_step(0.0, 3.5, 700, |t| l.translation(r, t));
        assert!(step < 0.05, "blend from free position jumps by {step}");
    });
}

#[test]
fn interrupted_placement_blend_is_continuous() {
    // A new placement starting while the previous blend is still running must start
    // from where the object currently is, not from the previous placement's target.
    let mut b = SceneBuilder::new();
    let r = b.rect(2.0, 1.0);
    b.place(r, at("left").margin(0.0));
    b.place_entry(r, 1.0, 4.0, Ease::Linear, Some(at("right").margin(0.0)));
    b.place_entry(r, 2.0, 1.0, Ease::Linear, Some(at("top").margin(0.0)));
    let scene = b.build();
    with_layout(&scene, |l| {
        let before = l.translation(r, 2.0 - 1e-9);
        let after = l.translation(r, 2.0);
        assert_v2(after, before);
        assert_v2(l.translation(r, 3.0), [0.0, 4.0]);
        let step = max_step(0.0, 3.5, 700, |t| l.translation(r, t));
        assert!(step < 0.1, "interrupted blend jumps by {step}");
    });
}

#[test]
fn placement_released_to_free_blends_back() {
    let mut b = SceneBuilder::new();
    let r = b.rect(1.0, 1.0);
    b.prop_f(r, "x", 2.0);
    b.place(r, at("center"));
    b.place_entry(r, 1.0, 1.0, Ease::Linear, None);
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_v2(l.translation(r, 0.5), [0.0, 0.0]);
        assert_v2(l.translation(r, 1.5), [1.0, 0.0]);
        assert_v2(l.translation(r, 2.5), [2.0, 0.0]);
    });
}

#[test]
fn mutual_below_is_reported_as_cycle_without_hanging() {
    let mut b = SceneBuilder::new();
    let a = b.rect(1.0, 1.0);
    let c = b.rect(1.0, 1.0);
    b.place(a, side(Side::Below, c));
    b.place(c, side(Side::Below, a));
    let scene = b.build();
    with_layout(&scene, |l| {
        let pa = l.translation(a, 0.0);
        let pc = l.translation(c, 0.0);
        assert!(pa.iter().chain(pc.iter()).all(|v| v.is_finite()));
        let issues = l.issues();
        assert_eq!(issues.len(), 1, "{issues:?}");
        assert_eq!(issues[0].kind, LayoutIssueKind::Cycle);
        assert_eq!(issues[0].objects, vec![a, c]);
    });
}

#[test]
fn acyclic_chain_reports_no_issue() {
    let mut b = SceneBuilder::new();
    let a = b.rect(1.0, 1.0);
    let c = b.rect(1.0, 1.0);
    let d = b.rect(1.0, 1.0);
    b.place(c, side(Side::Below, a).gap(0.0));
    b.place(d, side(Side::Below, c).gap(0.0));
    let scene = b.build();
    with_layout(&scene, |l| {
        assert_v2(l.translation(d, 0.0), [0.0, -2.0]);
        assert!(l.issues().is_empty());
    });
}
