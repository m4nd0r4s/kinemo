//! Pixel picking and object snapshots used by `kinemo inspect` and the `kinemo dev` preview.
//!
//! The test frame is 16 x 9 units at 160 x 90 px: the scene origin is pixel (80, 45) and
//! one unit is 10 px.

mod common;

use common::*;
use kinemo_ir::{Entry, Span, Src, Value};
use kinemo_render::inspect::{pick_object, scene_snapshot_json};

const CENTER: (f64, f64) = (80.0, 45.0);

fn pick(scene: &kinemo_ir::Scene, t: f64, x: f64, y: f64) -> Option<u32> {
    pick_object(scene, t, small_size(), x, y)
}

#[test]
fn picks_the_shape_under_the_pixel_and_nothing_on_background() {
    let mut b = SceneBuilder::new();
    let square = b.filled_rect(2.0, 2.0, RED);
    let scene = b.build();
    assert_eq!(pick(&scene, 0.0, CENTER.0, CENTER.1), Some(square));
    assert_eq!(pick(&scene, 0.0, 5.0, 5.0), None);
}

#[test]
fn topmost_in_draw_order_wins() {
    let mut b = SceneBuilder::new();
    let below = b.filled_rect(4.0, 4.0, RED);
    let above = b.filled_rect(2.0, 2.0, BLUE);
    let scene = b.build();
    assert_eq!(pick(&scene, 0.0, CENTER.0, CENTER.1), Some(above));
    // Inside the big square but outside the small one.
    assert_eq!(pick(&scene, 0.0, CENTER.0 + 15.0, CENTER.1), Some(below));
}

#[test]
fn z_order_overrides_tree_order() {
    let mut b = SceneBuilder::new();
    let raised = b.filled_rect(2.0, 2.0, RED);
    b.prop_f(raised, "z", 1.0);
    b.filled_rect(2.0, 2.0, BLUE);
    let scene = b.build();
    assert_eq!(pick(&scene, 0.0, CENTER.0, CENTER.1), Some(raised));
}

#[test]
fn absent_objects_are_not_picked() {
    let mut b = SceneBuilder::new();
    let below = b.filled_rect(2.0, 2.0, RED);
    let later = b.filled_rect(2.0, 2.0, BLUE);
    b.presence(later, vec![(1.0, true)]);
    let scene = b.build();
    assert_eq!(pick(&scene, 0.5, CENTER.0, CENTER.1), Some(below));
    assert_eq!(pick(&scene, 1.5, CENTER.0, CENTER.1), Some(later));
}

#[test]
fn fully_transparent_objects_are_skipped() {
    let mut b = SceneBuilder::new();
    let below = b.filled_rect(2.0, 2.0, RED);
    let ghost = b.filled_rect(2.0, 2.0, BLUE);
    b.prop_f(ghost, "opacity", 0.0);
    let scene = b.build();
    assert_eq!(pick(&scene, 0.0, CENTER.0, CENTER.1), Some(below));
}

#[test]
fn thin_strokes_are_picked_with_tolerance() {
    let mut b = SceneBuilder::new();
    let line = b.line([-3.0, 0.0], [3.0, 0.0]);
    b.stroke(line, GREEN, 2.0);
    let scene = b.build();
    assert_eq!(pick(&scene, 0.0, CENTER.0 + 10.0, CENTER.1 + 2.0), Some(line));
    assert_eq!(pick(&scene, 0.0, CENTER.0 + 10.0, CENTER.1 + 20.0), None);
}

#[test]
fn group_children_are_picked_as_leaves() {
    let mut b = SceneBuilder::new();
    let left = b.filled_rect(2.0, 2.0, RED);
    b.at(left, -3.0, 0.0);
    let right = b.filled_rect(2.0, 2.0, BLUE);
    b.at(right, 3.0, 0.0);
    b.group(&[left, right]);
    let scene = b.build();
    assert_eq!(pick(&scene, 0.0, CENTER.0 - 30.0, CENTER.1), Some(left));
    assert_eq!(pick(&scene, 0.0, CENTER.0 + 30.0, CENTER.1), Some(right));
    assert_eq!(pick(&scene, 0.0, CENTER.0, CENTER.1), None);
}

#[test]
fn snapshot_reports_values_and_their_sources() {
    let mut b = SceneBuilder::new();
    let square = b.filled_rect(2.0, 2.0, RED);
    let scene = {
        let mut scene = b.build();
        let width_signal = scene.objects[square as usize].props["w"];
        let span = Span { file: "/tmp/scene.py".into(), line: 12, col: 0, ..Default::default() };
        scene.signals[width_signal as usize].span = Span { file: "/tmp/scene.py".into(), line: 3, col: 0, ..Default::default() };
        scene.signals[width_signal as usize].timeline.push(Entry::Anim {
            t0: 1.0,
            t1: 2.0,
            to: Src::Val { v: Value::Float(4.0) },
            from: None,
            ease: Default::default(),
            blend: Default::default(),
            span,
        });
        scene
    };
    let before = &scene_snapshot_json(&scene, 0.5)[square as usize];
    assert_eq!(before["prop_sources"]["w"]["kind"], "initial");
    assert_eq!(before["prop_sources"]["w"]["span"]["line"], 3);
    assert_eq!(before["prop_sources"]["h"]["kind"], "default");
    assert_eq!(before["props"]["w"]["Float"], 2.0);

    let during = &scene_snapshot_json(&scene, 1.5)[square as usize];
    assert_eq!(during["prop_sources"]["w"]["kind"], "animation");
    assert_eq!(during["prop_sources"]["w"]["running"], true);
    assert_eq!(during["prop_sources"]["w"]["span"]["line"], 12);

    let after = &scene_snapshot_json(&scene, 3.0)[square as usize];
    assert_eq!(after["prop_sources"]["w"]["running"], false);
    assert_eq!(after["props"]["w"]["Float"], 4.0);
    assert_eq!(after["position_source"]["kind"], "free");
}
