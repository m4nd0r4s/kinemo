//! `k.Image` leaves → one draw item that paints the decoded bitmap over its rectangle.

use kurbo::{Affine, Rect, Shape};

use kinemo_ir::ObjectId;
use kinemo_layout::Layout;

use super::style::{chain_min, PaintedPart, Reveal};
use super::FrameSize;
use crate::media::load_bitmap;
use crate::raster::{DrawItem, ImagePaint};

/// The image of `leaf` as one painted part. `draw`/`write` progress fades it in.
pub(super) fn painted_image(layout: &Layout, leaf: ObjectId, t: f64, size: FrameSize, reveal: Reveal, opacity: f64) -> Vec<PaintedPart> {
    let Some(src) = layout.prop_str(leaf, "src", t) else { return vec![] };
    let Ok(bitmap) = load_bitmap(std::path::Path::new(&src)) else { return vec![] };
    let w = layout.prop_f(leaf, "w", t, 1.0).max(0.0);
    let h = layout.prop_f(leaf, "h", t, 1.0).max(0.0);
    let progress = match reveal {
        Reveal::Full => 1.0,
        Reveal::Animated => chain_min(layout, leaf, "_draw", t).min(chain_min(layout, leaf, "_write", t)),
    };
    let opacity = opacity * progress.clamp(0.0, 1.0);
    if w <= 0.0 || h <= 0.0 || (opacity <= 0.0 && reveal == Reveal::Animated) {
        return vec![];
    }
    let to_px = size.pixel_affine(layout.scene()) * layout.render_affine(leaf, t);
    // Image pixels (y-down, origin top-left) → local units (y-up, centered).
    let image_to_local = Affine::new([w / bitmap.width as f64, 0.0, 0.0, -h / bitmap.height as f64, -w / 2.0, h / 2.0]);
    let outline = to_px * Rect::new(-w / 2.0, -h / 2.0, w / 2.0, h / 2.0).to_path(1e-3);
    let item = DrawItem {
        path: outline,
        fill: None,
        stroke: None,
        opacity,
        clip: None,
        fill_rule_even_odd: false,
        image: Some(ImagePaint { bitmap, transform: to_px * image_to_local }),
        dots: None, glow: None,
    };
    vec![PaintedPart { item, key: None, index: 0 }]
}
