//! W1002: text over text — two visible texts at rest whose boxes overlap by more than
//! 10 % of the smaller box's area.

use kurbo::Rect;


use super::{FirstOccurrences, LintCode, LintContext, LintDetails, LintFinding, VisualLint};
use crate::sampling::{object_label, FrameSample};

#[derive(Default)]
pub(crate) struct TextOverlapLint {
    found: FirstOccurrences,
}

/// Area of `a ∩ b` divided by the area of the smaller box (0 for degenerate boxes).
pub(crate) fn overlap_fraction(a: Rect, b: Rect) -> f64 {
    let smaller = a.area().min(b.area());
    if smaller <= 0.0 {
        return 0.0;
    }
    let i = a.intersect(b);
    (i.width().max(0.0) * i.height().max(0.0)) / smaller
}

impl VisualLint for TextOverlapLint {
    fn observe(&mut self, context: &LintContext, sample: &FrameSample) {
        let options = context.options;
        let texts: Vec<_> = sample
            .leaves
            .iter()
            .filter(|l| l.is_text && l.at_rest && l.is_visible(options.visible_opacity))
            .collect();
        for (i, a) in texts.iter().enumerate() {
            for b in &texts[i + 1..] {
                if a.text_owner == b.text_owner {
                    continue;
                }
                let mut pair = vec![a.id, b.id];
                pair.sort_unstable();
                if self.found.contains(&pair) {
                    continue;
                }
                let fraction = overlap_fraction(a.world_bbox, b.world_bbox);
                if fraction <= options.text_overlap_fraction {
                    continue;
                }
                let message = format!(
                    "text over text: {} and {} ({:.0}% of the smaller)",
                    object_label(context.scene, pair[0]),
                    object_label(context.scene, pair[1]),
                    fraction * 100.0
                );
                self.found.record(LintFinding::new(
                    LintCode::TextOverText,
                    pair,
                    sample.t,
                    message,
                    LintDetails::TextOverlap { overlap_fraction: fraction },
                ));
            }
        }
    }

    fn finish(self: Box<Self>, _context: &LintContext) -> Vec<LintFinding> {
        self.found.into_findings()
    }
}
