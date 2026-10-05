//! W1003: contrast below 4.5:1 between a text's fill and what is behind it: the scene
//! background, with the fills of the shapes drawn before the text under its center (a speech
//! bubble, a card, a panel) composited over it.
//!
//! The text color is first blended over that backdrop with its effective alpha
//! (`fill` alpha × `fill_opacity` × accumulated opacity), the way the rasterizer
//! composites it (straight alpha, sRGB space). Contrast is the WCAG 2 ratio of relative
//! luminances. Only texts at rest are judged, so fades in and out never count; texts
//! with a nearly-zero alpha are W1005's business.

use kinemo_layout::Layout;

use super::{FirstOccurrences, LintCode, LintContext, LintDetails, LintFinding, VisualLint};
use crate::sampling::{object_label, FrameSample};

#[derive(Default)]
pub(crate) struct ContrastLint {
    found: FirstOccurrences,
}

/// WCAG 2 relative luminance of an sRGB color (components in 0..=1).
pub(crate) fn relative_luminance(rgb: [f64; 3]) -> f64 {
    let linear = |c: f64| {
        let c = c.clamp(0.0, 1.0);
        if c <= 0.04045 {
            c / 12.92
        } else {
            ((c + 0.055) / 1.055).powf(2.4)
        }
    };
    0.2126 * linear(rgb[0]) + 0.7152 * linear(rgb[1]) + 0.0722 * linear(rgb[2])
}

/// WCAG contrast ratio, from 1 (same luminance) to 21 (black on white).
pub(crate) fn contrast_ratio(a: [f64; 3], b: [f64; 3]) -> f64 {
    let (la, lb) = (relative_luminance(a), relative_luminance(b));
    (la.max(lb) + 0.05) / (la.min(lb) + 0.05)
}

/// `foreground` with `alpha` composited over an opaque `background`.
pub(crate) fn blend_over(foreground: [f64; 3], alpha: f64, background: [f64; 3]) -> [f64; 3] {
    let a = alpha.clamp(0.0, 1.0);
    [0, 1, 2].map(|i| foreground[i] * a + background[i] * (1.0 - a))
}

/// What is behind the text at `index`: the scene background, with the fill of every shape
/// drawn before it (tree order) whose box contains the text's center composited over it.
fn backdrop(sample: &FrameSample, layout: &Layout, index: usize, scene_background: [f64; 3], visible_opacity: f64) -> [f64; 3] {
    let text = &sample.leaves[index];
    let center = text.world_bbox.center();
    let mut color = scene_background;
    for leaf in &sample.leaves[..index] {
        if leaf.is_text || !leaf.revealed || !leaf.is_visible(visible_opacity) || !leaf.world_bbox.contains(center) {
            continue;
        }
        let Some(fill) = layout.prop_color(leaf.id, "fill", sample.t) else { continue };
        let alpha = fill[3] * layout.prop_f(leaf.id, "fill_opacity", sample.t, 1.0) * leaf.opacity;
        if alpha > visible_opacity {
            color = blend_over([fill[0], fill[1], fill[2]], alpha, color);
        }
    }
    color
}

impl VisualLint for ContrastLint {
    fn observe(&mut self, context: &LintContext, sample: &FrameSample, layout: &Layout) {
        let options = context.options;
        let bg = context.scene.config.background;
        let scene_background = [bg[0], bg[1], bg[2]];
        for (index, leaf) in sample.leaves.iter().enumerate() {
            if !leaf.is_text || !leaf.at_rest || leaf.fading || !leaf.is_visible(options.visible_opacity) {
                continue;
            }
            if self.found.contains(&[leaf.id]) {
                continue;
            }
            let Some(fill) = layout.prop_color(leaf.id, "fill", sample.t) else { continue };
            let fill_opacity = layout.prop_f(leaf.id, "fill_opacity", sample.t, 1.0);
            let alpha = fill[3] * fill_opacity * leaf.opacity;
            if alpha <= options.visible_opacity {
                continue;
            }
            let background = backdrop(sample, layout, index, scene_background, options.visible_opacity);
            let shown = blend_over([fill[0], fill[1], fill[2]], alpha, background);
            let ratio = contrast_ratio(shown, background);
            if ratio >= options.minimum_contrast {
                continue;
            }
            let message = format!(
                "contrast {:.1}:1 between {} and the background (minimum {:.1}:1)",
                ratio,
                object_label(context.scene, leaf.id),
                options.minimum_contrast
            );
            self.found.record(LintFinding::new(
                LintCode::LowContrast,
                vec![leaf.id],
                sample.t,
                message,
                LintDetails::Contrast { ratio, text_color: shown, background },
            ));
        }
    }

    fn finish(self: Box<Self>, _context: &LintContext) -> Vec<LintFinding> {
        self.found.into_findings()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn black_on_white_is_21() {
        assert!((contrast_ratio([0.0; 3], [1.0; 3]) - 21.0).abs() < 1e-9);
    }

    #[test]
    fn half_alpha_white_over_black_is_mid_gray() {
        let c = blend_over([1.0; 3], 0.5, [0.0; 3]);
        assert_eq!(c, [0.5; 3]);
    }
}
