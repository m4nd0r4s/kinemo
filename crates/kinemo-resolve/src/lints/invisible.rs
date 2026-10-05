//! W1005: an object that is in the scene but cannot be seen for more than 3 s, is never
//! removed and is not seen again (a leftover: forgotten `fade_out`, moved off-frame,
//! `opacity=0`). An object that waits invisible and then shows (a label fading in when a
//! curve reaches it) is not a leftover.
//!
//! Invisible means: hidden (`visible=False` up the tree), accumulated opacity at or
//! below 0.01 (or nothing drawn yet), or a world box entirely outside the frame.
//! The stretch is measured between the first and the last consecutive invisible samples.

use std::collections::HashMap;

use kurbo::Rect;

use kinemo_ir::{ObjectId, Scene};
use kinemo_layout::frame_rect;

use super::{InvisibilityReason, LintCode, LintContext, LintDetails, LintFinding, VisualLint};
use crate::sampling::{object_label, FrameSample, LeafSample};

#[derive(Clone, Copy)]
struct InvisibleRun {
    start: f64,
    last: f64,
    reason: InvisibilityReason,
}

#[derive(Default)]
pub(crate) struct InvisibleObjectLint {
    open_runs: HashMap<ObjectId, InvisibleRun>,
    findings: Vec<LintFinding>,
}

fn outside(b: Rect, frame: Rect) -> bool {
    b.x1 <= frame.x0 || b.x0 >= frame.x1 || b.y1 <= frame.y0 || b.y0 >= frame.y1
}

fn invisibility(leaf: &LeafSample, frame: Rect, invisible_opacity: f64) -> Option<InvisibilityReason> {
    if !leaf.shown {
        Some(InvisibilityReason::Hidden)
    } else if !leaf.revealed || leaf.opacity <= invisible_opacity {
        Some(InvisibilityReason::Transparent)
    } else if outside(leaf.world_bbox, frame) {
        Some(InvisibilityReason::OutsideFrame)
    } else {
        None
    }
}

fn never_removed(scene: &Scene, o: ObjectId) -> bool {
    scene.object(o).presence.iter().all(|(_, present)| *present)
}

fn reason_name(reason: InvisibilityReason) -> &'static str {
    match reason {
        InvisibilityReason::Transparent => "opacity 0",
        InvisibilityReason::OutsideFrame => "outside the frame",
        InvisibilityReason::Hidden => "visible=False",
    }
}

impl InvisibleObjectLint {
    fn close(&mut self, context: &LintContext, o: ObjectId, run: InvisibleRun) {
        let duration = run.last - run.start;
        if duration <= context.options.invisible_seconds || !never_removed(context.scene, o) {
            return;
        }
        if self.findings.iter().any(|f| f.objects == [o]) {
            return;
        }
        let message = format!(
            "{} stays invisible for {:.1} s ({}) and is never removed",
            object_label(context.scene, o),
            duration,
            reason_name(run.reason)
        );
        self.findings.push(LintFinding::new(
            LintCode::InvisibleObject,
            vec![o],
            run.start,
            message,
            LintDetails::Invisible { duration, reason: run.reason },
        ));
    }
}

impl VisualLint for InvisibleObjectLint {
    fn observe(&mut self, context: &LintContext, sample: &FrameSample) {
        let frame = frame_rect(&context.scene.config);
        let mut still_invisible: HashMap<ObjectId, InvisibilityReason> = HashMap::new();
        for leaf in &sample.leaves {
            if let Some(reason) = invisibility(leaf, frame, context.options.invisible_opacity) {
                still_invisible.insert(leaf.id, reason);
            }
        }
        let ended: Vec<(ObjectId, InvisibleRun)> = self
            .open_runs
            .iter()
            .filter(|(o, _)| !still_invisible.contains_key(o))
            .map(|(o, r)| (*o, *r))
            .collect();
        // Seen again: it was waiting, not forgotten.
        for (o, _) in ended {
            self.open_runs.remove(&o);
        }
        for (o, reason) in still_invisible {
            self.open_runs
                .entry(o)
                .and_modify(|run| run.last = sample.t)
                .or_insert(InvisibleRun { start: sample.t, last: sample.t, reason });
        }
    }

    fn finish(mut self: Box<Self>, context: &LintContext) -> Vec<LintFinding> {
        let mut open: Vec<(ObjectId, InvisibleRun)> = self.open_runs.drain().collect();
        open.sort_by_key(|(o, _)| *o);
        for (o, run) in open {
            self.close(context, o, run);
        }
        self.findings
    }
}
