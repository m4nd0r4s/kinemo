//! Visual lints (W10xx) on IR scenes built directly in Rust.

mod common;

use common::{at_anchor, codes, only, SceneBuilder};
use kinemo_ir::{Expr, Value};
use kinemo_resolve::lints::{FrameEdge, InvisibilityReason};
use kinemo_resolve::{run_visual_lints, LintDetails, LintOptions, SuggestedFix};

#[test]
fn clean_scene_has_no_findings() {
    let mut b = SceneBuilder::new(2.0);
    b.text("title", "Hello", 0.5, 0.0, 2.0);
    b.rect("box", 2.0, 1.0, 0.0, -1.0);
    assert!(b.lints().is_empty(), "{:?}", b.lints());
}

// ---- W1001 ------------------------------------------------------------------------

#[test]
fn object_past_the_safe_area_is_reported_with_edge_and_overshoot() {
    let mut b = SceneBuilder::new(2.0);
    let r = b.rect("box", 1.0, 1.0, 7.8, 0.0);
    let findings = b.lints();
    let w = only(&findings, "W1001");
    assert_eq!(w.len(), 1, "deduplicated per object: {findings:?}");
    assert_eq!(w[0].objects, vec![r]);
    assert_eq!(w[0].t, 0.0);
    match &w[0].details {
        LintDetails::SafeArea { edge, overshoot, .. } => {
            assert_eq!(*edge, FrameEdge::Right);
            assert!((overshoot - 0.8).abs() < 1e-6);
        }
        other => panic!("unexpected details {other:?}"),
    }
    assert_eq!(w[0].fix, Some(SuggestedFix::PlaceWithClamp { target: r }));
    assert!(w[0].message.contains("box leaves the safe area (right, 0.8 u)"), "{}", w[0].message);
}

#[test]
fn placed_object_gets_a_clamp_fix() {
    let mut b = SceneBuilder::new(1.0);
    let r = b.rect("badge", 1.0, 1.0, 0.0, 0.0);
    b.place(r, at_anchor("top"));
    let findings = b.lints();
    let w = only(&findings, "W1001");
    assert_eq!(w.len(), 1);
    assert_eq!(w[0].fix, Some(SuggestedFix::ClampPlacement { target: r }));
    assert!(matches!(w[0].details, LintDetails::SafeArea { edge: FrameEdge::Top, .. }));
}

#[test]
fn entrance_from_off_frame_is_not_a_safe_area_problem() {
    let mut b = SceneBuilder::new(2.0);
    let r = b.rect("box", 1.0, 1.0, 20.0, 0.0);
    b.animate(r, "x", 0.0, 1.0, Value::Float(0.0));
    assert!(only(&b.lints(), "W1001").is_empty());
}

#[test]
fn bound_motion_counts_and_reports_the_first_instant() {
    // x follows k.time: the object drifts right and leaves the safe area at t ≈ 7.
    let mut b = SceneBuilder::new(7.5);
    let r = b.rect("dot", 1.0, 1.0, 0.0, 0.0);
    b.bind(r, "x", 0.0, Expr::Time);
    let findings = b.lints();
    let w = only(&findings, "W1001");
    assert_eq!(w.len(), 1);
    assert_eq!(w[0].t, 7.1);
}

// ---- W1002 ------------------------------------------------------------------------

#[test]
fn overlapping_texts_are_reported_once_per_pair() {
    let mut b = SceneBuilder::new(1.0);
    let a = b.text("a", "Hello", 0.5, 0.0, 0.0);
    let c = b.text("c", "World", 0.5, 0.2, 0.0);
    b.text("far", "Far", 0.5, 0.0, -3.0);
    let findings = b.lints();
    let w = only(&findings, "W1002");
    assert_eq!(w.len(), 1, "{findings:?}");
    assert_eq!(w[0].objects, vec![a, c]);
    match w[0].details {
        LintDetails::TextOverlap { overlap_fraction } => assert!(overlap_fraction > 0.5),
        _ => panic!(),
    }
}

#[test]
fn faded_text_does_not_overlap() {
    let mut b = SceneBuilder::new(1.0);
    b.text("a", "Hello", 0.5, 0.0, 0.0);
    let c = b.text("c", "World", 0.5, 0.2, 0.0);
    b.prop(c, "opacity", Value::Float(0.02));
    assert!(only(&b.lints(), "W1002").is_empty());
}

#[test]
fn texts_slightly_touching_are_fine() {
    let mut b = SceneBuilder::new(1.0);
    b.text("a", "Hello", 0.5, 0.0, 0.0);
    // Line boxes are 1.25 em tall: 0.6 u apart leaves a ~4% overlap.
    b.text("c", "Hello", 0.5, 0.0, 0.6);
    assert!(only(&b.lints(), "W1002").is_empty());
}

// ---- W1003 ------------------------------------------------------------------------

#[test]
fn dark_text_on_dark_background_has_low_contrast() {
    let mut b = SceneBuilder::new(1.0);
    let t = b.text("hint", "psst", 0.5, 0.0, 0.0);
    b.prop(t, "fill", Value::Color([0.2, 0.2, 0.22, 1.0]));
    let findings = b.lints();
    let w = only(&findings, "W1003");
    assert_eq!(w.len(), 1);
    match w[0].details {
        LintDetails::Contrast { ratio, .. } => assert!(ratio < 4.5 && ratio > 1.0),
        _ => panic!(),
    }
}

#[test]
fn translucent_white_text_blends_into_the_background() {
    let mut b = SceneBuilder::new(1.0);
    let t = b.text("ghost", "boo", 0.5, 0.0, 0.0);
    b.prop(t, "fill_opacity", Value::Float(0.15));
    assert_eq!(only(&b.lints(), "W1003").len(), 1);
}

#[test]
fn fading_text_is_judged_only_at_rest() {
    let mut b = SceneBuilder::new(2.0);
    let t = b.text("title", "Hello", 0.5, 0.0, 0.0);
    b.prop(t, "_fade", Value::Float(0.0));
    b.animate(t, "_fade", 0.0, 1.0, Value::Float(1.0));
    assert!(b.lints().is_empty(), "{:?}", b.lints());
}

// ---- W1004 ------------------------------------------------------------------------

#[test]
fn small_text_is_measured_in_output_pixels() {
    let mut b = SceneBuilder::new(1.0);
    let t = b.text("tiny", "fine print", 0.1, 0.0, 0.0);
    let findings = b.lints();
    let w = only(&findings, "W1004");
    assert_eq!(w.len(), 1);
    assert_eq!(w[0].objects, vec![t]);
    match w[0].details {
        LintDetails::TextSize { pixels } => assert!((pixels - 12.0).abs() < 1e-6),
        _ => panic!(),
    }
}

#[test]
fn scale_counts_toward_text_size() {
    let mut b = SceneBuilder::new(1.0);
    let t = b.text("shrunk", "abc", 0.5, 0.0, 0.0);
    b.prop(t, "scale", Value::Float(0.2));
    assert_eq!(only(&b.lints(), "W1004").len(), 1);
    let mut ok = SceneBuilder::new(1.0);
    ok.text("normal", "abc", 0.5, 0.0, 0.0);
    assert!(only(&ok.lints(), "W1004").is_empty());
}

// ---- W1005 ------------------------------------------------------------------------

#[test]
fn transparent_object_kept_in_the_scene_is_reported() {
    let mut b = SceneBuilder::new(5.0);
    let r = b.rect("leftover", 1.0, 1.0, 0.0, 0.0);
    b.animate(r, "opacity", 0.5, 1.0, Value::Float(0.0));
    let findings = b.lints();
    let w = only(&findings, "W1005");
    assert_eq!(w.len(), 1, "{findings:?}");
    assert_eq!(w[0].objects, vec![r]);
    assert!((w[0].t - 1.0).abs() < 1e-6);
    assert!(matches!(w[0].details, LintDetails::Invisible { reason: InvisibilityReason::Transparent, .. }));
}

#[test]
fn removed_object_is_not_a_leftover() {
    let mut b = SceneBuilder::new(6.0);
    let r = b.rect("gone", 1.0, 1.0, 0.0, 0.0);
    b.prop(r, "opacity", Value::Float(0.0));
    b.presence(r, vec![(0.0, true), (5.0, false)]);
    assert!(only(&b.lints(), "W1005").is_empty());
}

#[test]
fn short_invisibility_is_fine() {
    let mut b = SceneBuilder::new(2.5);
    let r = b.rect("blink", 1.0, 1.0, 0.0, 0.0);
    b.prop(r, "opacity", Value::Float(0.0));
    assert!(only(&b.lints(), "W1005").is_empty());
}

#[test]
fn object_parked_off_frame_is_invisible() {
    let mut b = SceneBuilder::new(4.0);
    b.rect("parked", 1.0, 1.0, 30.0, 0.0);
    let findings = b.lints();
    let w = only(&findings, "W1005");
    assert_eq!(w.len(), 1);
    assert!(matches!(w[0].details, LintDetails::Invisible { reason: InvisibilityReason::OutsideFrame, .. }));
}

// ---- W1006 ------------------------------------------------------------------------

fn burst(count: usize, duration: f64) -> SceneBuilder {
    let mut b = SceneBuilder::new(3.0);
    for i in 0..count {
        let r = b.rect(&format!("r{i}"), 0.2, 0.2, -6.0 + i as f64 * 0.5, 0.0);
        // Two props in the same interval are one animation of the object.
        b.animate(r, "y", 1.0, 1.0 + duration, Value::Float(1.0));
        b.animate(r, "x", 1.0, 1.0 + duration, Value::Float(0.0));
    }
    b
}

#[test]
fn many_short_simultaneous_animations_are_noise() {
    let b = burst(13, 0.2);
    let findings = b.lints();
    let w = only(&findings, "W1006");
    assert_eq!(w.len(), 1);
    assert_eq!(w[0].objects.len(), 13);
    assert_eq!(w[0].t, 1.0);
    assert!(matches!(w[0].details, LintDetails::Noise { simultaneous: 13 }));
}

#[test]
fn twelve_short_animations_or_long_ones_are_fine() {
    assert!(only(&burst(12, 0.2).lints(), "W1006").is_empty());
    assert!(only(&burst(13, 0.5).lints(), "W1006").is_empty());
}

// ---- W1007 ------------------------------------------------------------------------

#[test]
fn long_stillness_is_reported_at_its_start() {
    let mut b = SceneBuilder::new(12.0);
    let r = b.rect("box", 1.0, 1.0, 0.0, 0.0);
    b.animate(r, "x", 0.0, 1.0, Value::Float(1.0));
    let findings = b.lints();
    let w = only(&findings, "W1007");
    assert_eq!(w.len(), 1, "{findings:?}");
    assert_eq!(w[0].t, 1.0);
    match w[0].details {
        LintDetails::Static { duration } => assert!((duration - 11.0).abs() < 1e-6),
        _ => panic!(),
    }
}

#[test]
fn time_driven_binding_is_a_visual_change() {
    let mut b = SceneBuilder::new(12.0);
    let r = b.rect("spinner", 1.0, 1.0, 0.0, 0.0);
    b.bind(r, "rotate", 0.0, Expr::Time);
    assert!(only(&b.lints(), "W1007").is_empty());
}

#[test]
fn constant_binding_is_not_a_change() {
    let mut b = SceneBuilder::new(12.0);
    let r = b.rect("box", 1.0, 1.0, 0.0, 0.0);
    b.bind(r, "rotate", 0.0, Expr::Const { v: Value::Float(10.0) });
    assert_eq!(only(&b.lints(), "W1007").len(), 1);
}

// ---- driver -----------------------------------------------------------------------

#[test]
fn findings_are_sorted_by_time_and_serialize_with_stable_codes() {
    let mut b = SceneBuilder::new(1.0);
    b.rect("box", 1.0, 1.0, 7.8, 0.0);
    b.text("tiny", "x", 0.1, 0.0, 0.0);
    let findings = run_visual_lints(&b.scene, &LintOptions::with_step(0.25));
    assert_eq!(codes(&findings), vec!["W1001", "W1004"]);
    let json = serde_json::to_value(&findings).unwrap();
    assert_eq!(json[0]["code"], "W1001");
    assert_eq!(json[0]["details"]["kind"], "safe_area");
    assert_eq!(json[0]["details"]["edge"], "right");
    assert_eq!(json[0]["fix"]["kind"], "place_with_clamp");
    assert_eq!(json[1]["details"]["kind"], "text_size");
}

#[test]
fn sample_times_include_every_boundary() {
    let mut b = SceneBuilder::new(1.0);
    let r = b.rect("box", 1.0, 1.0, 0.0, 0.0);
    b.animate(r, "x", 0.333, 0.777, Value::Float(1.0));
    let times = kinemo_resolve::sampling::sample_times(&b.scene, 0.25);
    for t in [0.0, 0.25, 0.333, 0.5, 0.75, 0.777, 1.0] {
        assert!(times.iter().any(|s| (s - t).abs() < 1e-9), "missing {t} in {times:?}");
    }
}
