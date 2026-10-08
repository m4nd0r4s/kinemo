//! W1001: a visible object at rest extends past the safe area (frame inset 0.5 u). Objects
//! entirely outside the frame (offstage) and objects with `bleed=True` are left alone.
//!
//! A moving object is judged by the frame itself, and only when it was seen inside the safe
//! area before the frame cut it and comes to rest inside it again: a path that dips out of
//! the frame on the way (a swap arc) is reported, an entrance or an exit through the edge is
//! not.

use std::collections::HashMap;

use kurbo::Rect;

use kinemo_ir::{Entry, ObjectId, Scene};
use kinemo_layout::frame_rect;

use super::{FirstOccurrences, FrameEdge, LintCode, LintContext, LintDetails, LintFinding, SuggestedFix, VisualLint};
use crate::sampling::{ancestry, object_label, FrameSample, LeafSample};

#[derive(Default)]
pub(crate) struct SafeAreaLint {
    found: FirstOccurrences,
    /// Per object: whether it was last seen entirely inside the safe area (moving or not)
    /// rather than offstage, so a cut while it moves is not an entrance.
    seen_inside: HashMap<ObjectId, bool>,
    /// Per object in motion: where it first left the frame, and by how much at most.
    cut_mid_motion: HashMap<ObjectId, Crossing>,
}

/// An object cut by the frame edge while it moves.
struct Crossing {
    t: f64,
    edge: FrameEdge,
    overshoot: f64,
    reorder: bool,
}

/// Whether a container above `leaf` is reordering its children at `t` (`row.swap`).
fn reordering(scene: &Scene, leaf: ObjectId, t: f64) -> bool {
    ancestry(scene, leaf).skip(1).any(|o| {
        scene.object(o).children.is_some_and(|signal| {
            scene.signal(signal).timeline.iter().any(|entry| matches!(entry, Entry::Anim { t0, t1, .. } if *t0 <= t && t <= *t1))
        })
    })
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

impl SafeAreaLint {
    /// A moving object seen inside the safe area before: note where the frame edge cuts it.
    fn observe_motion(&mut self, context: &LintContext, leaf: &LeafSample, frame: Rect, t: f64, inside: bool) {
        let (id, bbox) = (leaf.id, leaf.world_bbox);
        if inside {
            self.seen_inside.insert(id, true);
            return;
        }
        if offstage(bbox, frame) {
            // Gone entirely: an exit through the edge (or not yet entered), not a cut.
            self.seen_inside.insert(id, false);
            self.cut_mid_motion.remove(&id);
            return;
        }
        if !self.seen_inside.get(&id).copied().unwrap_or(false) {
            return;
        }
        let (edge, overshoot) = largest_overshoot(bbox, frame);
        if overshoot <= context.options.safe_area_tolerance {
            return;
        }
        let crossing = self.cut_mid_motion.entry(id).or_insert_with(|| Crossing { t, edge, overshoot, reorder: reordering(context.scene, id, t) });
        if overshoot > crossing.overshoot {
            crossing.edge = edge;
            crossing.overshoot = overshoot;
        }
    }

    fn report_motion(&mut self, context: &LintContext, id: ObjectId, crossing: Crossing) {
        let message = format!(
            "{} is cut by the frame edge while it moves ({}, {:.1} u)",
            object_label(context.scene, id),
            edge_name(crossing.edge),
            crossing.overshoot
        );
        let details = LintDetails::SafeArea { edge: crossing.edge, overshoot: crossing.overshoot, moving: true, reorder: crossing.reorder };
        self.found.record(LintFinding::new(LintCode::OutsideSafeArea, vec![id], crossing.t, message, details));
    }
}

impl VisualLint for SafeAreaLint {
    fn observe(&mut self, context: &LintContext, sample: &FrameSample) {
        let area = safe_area(context.scene, context.options.safe_margin);
        let frame = frame_rect(&context.scene.config);
        let tolerance = context.options.safe_area_tolerance;
        for leaf in &sample.leaves {
            if !leaf.is_visible(context.options.visible_opacity) || leaf.bleeds || self.found.contains(&[leaf.id]) {
                continue;
            }
            let (edge, overshoot) = largest_overshoot(leaf.world_bbox, area);
            let inside = !offstage(leaf.world_bbox, frame) && overshoot <= tolerance;
            if !leaf.at_rest {
                self.observe_motion(context, leaf, frame, sample.t, inside);
                continue;
            }
            self.seen_inside.insert(leaf.id, inside);
            if let Some(crossing) = self.cut_mid_motion.remove(&leaf.id) {
                if inside {
                    self.report_motion(context, leaf.id, crossing);
                    continue;
                }
            }
            // Entirely outside the frame: offstage (waiting to slide in), not clipped.
            // `bleed=True` up the tree: cropped by the edge on purpose.
            if offstage(leaf.world_bbox, frame) || overshoot <= tolerance {
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
                LintDetails::SafeArea { edge, overshoot, moving: false, reorder: false },
            );
            finding.fix = Some(suggested_fix(context.scene, leaf.id, sample.t));
            self.found.record(finding);
        }
    }

    fn finish(self: Box<Self>, _context: &LintContext) -> Vec<LintFinding> {
        self.found.into_findings()
    }
}
