//! Display list → Vello scene, mirroring the tiny-skia rasterizer's semantics:
//! fill before stroke, `opacity` multiplies the fill and stroke alpha separately (no group
//! compositing, exactly like the CPU path), the clip is a nonzero-filled clip layer, strokes
//! are expanded to outlines by tiny-skia (see `stroke_outline`) and filled.

use kinemo_render::raster::{DisplayList, DrawItem};
use vello::kurbo as vk;
use vello::peniko;

use crate::stroke_outline::stroke_outline;

/// Curves are flattened on the CPU to this tolerance (pixels) before encoding. Vello's
/// GPU flattener uses a fixed 0.25 px tolerance with chords inside the curve, which
/// visibly erodes curved edges (up to ~0.25 coverage on circle rims) compared with the
/// tiny-skia reference; pre-flattened polylines are encoded exactly.
pub(crate) const CURVE_FLATTENING_TOLERANCE: f64 = 0.05;

/// kurbo 0.11 (kinemo) → kurbo 0.13 (Vello), curves flattened to line segments.
pub(crate) fn convert_path(path: &kurbo::BezPath) -> vk::BezPath {
    let point = |p: kurbo::Point| vk::Point::new(p.x, p.y);
    let mut out = vk::BezPath::new();
    kurbo::flatten(path, CURVE_FLATTENING_TOLERANCE, |element| match element {
        kurbo::PathEl::MoveTo(p) => out.move_to(point(p)),
        kurbo::PathEl::LineTo(p) => out.line_to(point(p)),
        kurbo::PathEl::QuadTo(a, p) => out.quad_to(point(a), point(p)),
        kurbo::PathEl::CurveTo(a, b, p) => out.curve_to(point(a), point(b), point(p)),
        kurbo::PathEl::ClosePath => out.close_path(),
    });
    out
}

/// sRGB straight-alpha color with `opacity` folded into alpha.
pub(crate) fn convert_color(color: [f64; 4], opacity: f64) -> peniko::Color {
    let channel = |v: f64| v.clamp(0.0, 1.0) as f32;
    peniko::Color::new([
        channel(color[0]),
        channel(color[1]),
        channel(color[2]),
        channel(color[3] * opacity.clamp(0.0, 1.0)),
    ])
}

fn encode_item(scene: &mut vello::Scene, item: &DrawItem) {
    if item.opacity <= 0.0 || item.path.elements().is_empty() {
        return;
    }
    let path = convert_path(&item.path);
    let identity = vk::Affine::IDENTITY;
    let clipped = item.clip.as_ref().map(|clip| {
        scene.push_clip_layer(peniko::Fill::NonZero, identity, &convert_path(clip));
    });
    if let Some(fill) = &item.fill {
        let rule = if item.fill_rule_even_odd { peniko::Fill::EvenOdd } else { peniko::Fill::NonZero };
        scene.fill(rule, identity, convert_color(fill.color, item.opacity), None, &path);
    }
    if let Some(stroke) = &item.stroke {
        if let Some(outline) = stroke_outline(&item.path, stroke) {
            let color = convert_color(stroke.color, item.opacity);
            scene.fill(peniko::Fill::NonZero, identity, color, None, &convert_path(&outline));
        }
    }
    if let Some(image) = &item.image {
        encode_image(scene, image, item.opacity);
    }
    if clipped.is_some() {
        scene.pop_layer();
    }
}

/// Premultiplied pixels of a shared bitmap, borrowed by a Vello blob without copying.
struct BitmapPixels(std::sync::Arc<kinemo_render::raster::Bitmap>);

impl AsRef<[u8]> for BitmapPixels {
    fn as_ref(&self) -> &[u8] {
        &self.0.premultiplied_rgba
    }
}

/// Bilinear image draw, mirroring the CPU path (`transform`: image pixels → output pixels).
fn encode_image(scene: &mut vello::Scene, image: &kinemo_render::raster::ImagePaint, opacity: f64) {
    let bitmap = &image.bitmap;
    let data = peniko::ImageData {
        data: peniko::Blob::new(std::sync::Arc::new(BitmapPixels(bitmap.clone()))),
        format: peniko::ImageFormat::Rgba8,
        alpha_type: peniko::ImageAlphaType::AlphaPremultiplied,
        width: bitmap.width,
        height: bitmap.height,
    };
    let brush = peniko::ImageBrush::new(data).with_quality(peniko::ImageQuality::Medium).with_alpha(opacity.clamp(0.0, 1.0) as f32);
    scene.draw_image(&brush, vk::Affine::new(image.transform.as_coeffs()));
}

/// Encodes all items; the background is passed separately as Vello's base color.
pub(crate) fn encode_display_list(display_list: &DisplayList) -> vello::Scene {
    let mut scene = vello::Scene::new();
    for item in &display_list.items {
        encode_item(&mut scene, item);
    }
    scene
}
