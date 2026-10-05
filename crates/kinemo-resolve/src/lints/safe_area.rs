//! W1001: a visible object at rest extends past the safe area (frame inset 0.5 u). Objects
//! entirely outside the frame (offstage) and objects with `bleed=True` are left alone.

use kurbo::Rect;

use kinemo_ir::{ObjectId, Scene};
use kinemo_layout::frame_rect;

use super::{FirstOccurrences, FrameEdge, LintCode, LintContext, LintDetails, LintFinding, SuggestedFix, VisualLint};
use crate::sampling::{ancestry, object_label, FrameSample};

#[derive(Default)]
pub(crate) struct SafeAreaLint {
    found: FirstOccurrences,
}

/// The frame shrunk by `margin` on every side.
pub(crate) fn safe_area(scene: &Scene, margin: f64) -> Rect {
    let f = frame_rect(&scene.config);
    Rect::new(f.x0 + margin, f.y0 + margin, f.x1 - margin, f.y1 - margin)
}

/// Edge with the largest overshoot of `b` past `area`, and that overshoot.
pub(crate) fn largest_overshoot(b: Rect, area: Rect) -> (FrameEdge, f64) {
    [
        (FrameEdge::Top, b.y1 - area.y1),
        (FrameEdge::Bottom, area.y0 - b.y0),
        (FrameEdge::Left, area.x0 - b.x0),
        (FrameEdge::Right, b.x1 - area.x1),
    ]
    .into_iter()
    .fold((FrameEdge::Top, f64::NEG_INFINITY), |best, cur| if cur.1 > best.1 { cur } else { best })
}

fn edge_name(edge: FrameEdge) -> &'static str {
    match edge {
        FrameEdge::Top => "top",
        FrameEdge::Bottom => "bottom",
        FrameEdge::Left => "left",
        FrameEdge::Right => "right",
    }
}

/// Whether `b` lies entirely outside `frame` (nothing of it is on screen).
fn offstage(b: Rect, frame: Rect) -> bool {
    b.x1 <= frame.x0 || b.x0 >= frame.x1 || b.y1 <= frame.y0 || b.y0 >= frame.y1
}

/// Whether `o` follows a constraint (`place`) at `t`.
fn has_active_placement(scene: &Scene, o: ObjectId, t: f64) -> bool {
    scene.object(o).place.iter().rev().find(|e| e.t <= t).is_some_and(|e| e.p.is_some())
}

/// The object whose placement decides where `leaf` is: the nearest placed object in the
/// chain gets `clamp=True`; with none, the root of the chain should be placed.
fn suggested_fix(scene: &Scene, leaf: ObjectId, t: f64) -> SuggestedFix {
    let mut root = leaf;
    for o in ancestry(scene, leaf) {
        if has_active_placement(scene, o, t) {
            return SuggestedFix::ClampPlacement { target: o };
        }
        root = o;
    }
    SuggestedFix::PlaceWithClamp { target: root }
}

impl VisualLint for SafeAreaLint {
    fn observe(&mut self, context: &LintContext, sample: &FrameSample) {
        let area = safe_area(context.scene, context.options.safe_margin);
        let frame = frame_rect(&context.scene.config);
        for leaf in &sample.leaves {
            if !leaf.at_rest || !leaf.is_visible(context.options.visible_opacity) || self.found.contains(&[leaf.id]) {
                continue;
            }
            // Entirely outside the frame: offstage (waiting to slide in), not clipped.
            // `bleed=True` up the tree: cropped by the edge on purpose.
            if offstage(leaf.world_bbox, frame) || leaf.bleeds {
                continue;
            }
            let (edge, overshoot) = largest_overshoot(leaf.world_bbox, area);
            if overshoot <= context.options.safe_area_tolerance {
                continue;
            }
            let message = format!(
                "{} leaves the safe area ({}, {:.1} u)",
                object_label(context.scene, leaf.id),
                edge_name(edge),
                overshoot
            );
            let mut finding = LintFinding::new(
                LintCode::OutsideSafeArea,
                vec![leaf.id],
                sample.t,
                message,
                LintDetails::SafeArea { edge, overshoot },
            );
            finding.fix = Some(suggested_fix(context.scene, leaf.id, sample.t));
            self.found.record(finding);
        }
    }

    fn finish(self: Box<Self>, _context: &LintContext) -> Vec<LintFinding> {
        self.found.into_findings()
    }
}
