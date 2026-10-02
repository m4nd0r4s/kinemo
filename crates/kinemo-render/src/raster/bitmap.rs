//! Raster images in the CPU rasterizer: the item's outline filled with a bilinear image
//! pattern, so rotated or scaled images keep anti-aliased edges.

use tiny_skia as sk;

use super::ImagePaint;

fn to_sk_transform(a: kurbo::Affine) -> sk::Transform {
    let [sx, ky, kx, sy, tx, ty] = a.as_coeffs();
    sk::Transform::from_row(sx as f32, ky as f32, kx as f32, sy as f32, tx as f32, ty as f32)
}

/// Paints `image` inside `outline` (pixel coordinates) with `opacity`.
pub(super) fn draw_image(pm: &mut sk::Pixmap, outline: &sk::Path, image: &ImagePaint, opacity: f64, antialias: bool, mask: Option<&sk::Mask>) {
    let bitmap = &image.bitmap;
    let Some(source) = sk::PixmapRef::from_bytes(&bitmap.premultiplied_rgba, bitmap.width, bitmap.height) else { return };
    let shader = sk::Pattern::new(
        source,
        sk::SpreadMode::Pad,
        sk::FilterQuality::Bilinear,
        opacity.clamp(0.0, 1.0) as f32,
        to_sk_transform(image.transform),
    );
    let paint = sk::Paint { shader, anti_alias: antialias, ..sk::Paint::default() };
    pm.fill_path(outline, &paint, sk::FillRule::Winding, sk::Transform::identity(), mask);
}
