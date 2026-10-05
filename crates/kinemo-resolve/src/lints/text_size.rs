//! W1004: text smaller than 18 px at the output resolution.
//!
//! Measured as the **em size** (the `size` prop, i.e. font size in scene units) times
//! the object's vertical world scale times pixels per unit (`width / frame_w`). The cap
//! height of the default font is about 0.7 em, so an 18 px em has ~13 px capitals.
//! Only texts at rest are judged (a `scale` or `size` animation in progress is skipped).


use super::{FirstOccurrences, LintCode, LintContext, LintDetails, LintFinding, VisualLint};
use crate::sampling::{object_label, FrameSample};

/// Default `size` of a text when the IR does not declare one.

#[derive(Default)]
pub(crate) struct TextSizeLint {
    found: FirstOccurrences,
}

impl VisualLint for TextSizeLint {
    fn observe(&mut self, context: &LintContext, sample: &FrameSample) {
        let scene = context.scene;
        let options = context.options;
        let pixels_per_unit = scene.config.width as f64 / scene.config.frame_w;
        for leaf in &sample.leaves {
            if !leaf.is_text || !leaf.at_rest || leaf.fading || !leaf.is_visible(options.visible_opacity) {
                continue;
            }
            if self.found.contains(&[leaf.id]) {
                continue;
            }
            let Some(metrics) = leaf.text else { continue };
            if metrics.blank {
                continue;
            }
            let pixels = metrics.em * metrics.vertical_scale * pixels_per_unit;
            if pixels <= 0.0 || pixels >= options.minimum_text_pixels {
                continue;
            }
            let message = format!(
                "{} is {:.0} px at the output resolution (minimum {:.0} px)",
                object_label(scene, leaf.id),
                pixels,
                options.minimum_text_pixels
            );
            self.found.record(LintFinding::new(
                LintCode::SmallText,
                vec![leaf.id],
                sample.t,
                message,
                LintDetails::TextSize { pixels },
            ));
        }
    }

    fn finish(self: Box<Self>, _context: &LintContext) -> Vec<LintFinding> {
        self.found.into_findings()
    }
}
