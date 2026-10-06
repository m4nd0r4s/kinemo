//! Display list -> pixels.

use kurbo::{BezPath, PathEl};
use tiny_skia as sk;

use super::{Cap, DisplayList, DotCloud, DrawItem, Glow, Image, Join, Stroke};

fn to_sk_path(p: &BezPath) -> Option<sk::Path> {
    let mut b = sk::PathBuilder::new();
    for el in p.elements() {
        match *el {
            PathEl::MoveTo(p) => b.move_to(p.x as f32, p.y as f32),
            PathEl::LineTo(p) => b.line_to(p.x as f32, p.y as f32),
            PathEl::QuadTo(a, p) => b.quad_to(a.x as f32, a.y as f32, p.x as f32, p.y as f32),
            PathEl::CurveTo(a, c, p) => b.cubic_to(
                a.x as f32, a.y as f32, c.x as f32, c.y as f32, p.x as f32, p.y as f32,
            ),
            PathEl::ClosePath => b.close(),
        }
    }
    b.finish()
}

fn to_sk_color(c: [f64; 4], opacity: f64) -> sk::Color {
    let f = |v: f64| v.clamp(0.0, 1.0) as f32;
    sk::Color::from_rgba(f(c[0]), f(c[1]), f(c[2]), f(c[3] * opacity.clamp(0.0, 1.0)))
        .unwrap_or(sk::Color::TRANSPARENT)
}

fn paint_for(color: [f64; 4], opacity: f64, antialias: bool) -> sk::Paint<'static> {
    let mut paint = sk::Paint::default();
    paint.set_color(to_sk_color(color, opacity));
    paint.anti_alias = antialias;
    paint
}

fn to_sk_stroke(s: &Stroke) -> sk::Stroke {
    let mut st = sk::Stroke {
        width: s.width.max(0.0) as f32,
        line_cap: match s.cap {
            Cap::Butt => sk::LineCap::Butt,
            Cap::Round => sk::LineCap::Round,
            Cap::Square => sk::LineCap::Square,
        },
        line_join: match s.join {
            Join::Miter => sk::LineJoin::Miter,
            Join::Round => sk::LineJoin::Round,
            Join::Bevel => sk::LineJoin::Bevel,
        },
        ..Default::default()
    };
    if let Some(dash) = &s.dash {
        let mut arr: Vec<f32> = dash.iter().map(|d| d.max(0.0) as f32).collect();
        // tiny-skia requires an even number of entries (SVG semantics: repeat odd lists).
        if arr.len() % 2 == 1 {
            arr.extend_from_within(..);
        }
        st.dash = sk::StrokeDash::new(arr, 0.0);
    }
    st
}

/// Largest dot (pixels) stamped from a local coverage buffer; larger ones are rare and fall
/// back to the path.
const MAX_STAMP_RADIUS: f32 = 12.0;
const STAMP_SPAN: usize = (2.0 * MAX_STAMP_RADIUS) as usize + 4;

/// Coverage (0–255) of one disk on the pixels around it, `(pixel index, coverage)`: a
/// one-pixel ramp at the edge, scaled so a dot smaller than a pixel covers its area.
fn disk_coverage(center: [f32; 2], radius: f32, width: i32, height: i32, antialias: bool, out: &mut Vec<(u32, u8)>) {
    let [cx, cy] = center;
    let radius = radius.clamp(0.0, MAX_STAMP_RADIUS);
    if radius <= 0.0 {
        return;
    }
    let x0 = ((cx - radius - 1.0).floor() as i32).max(0);
    let y0 = ((cy - radius - 1.0).floor() as i32).max(0);
    let x1 = ((cx + radius + 1.0).ceil() as i32).min(width - 1);
    let y1 = ((cy + radius + 1.0).ceil() as i32).min(height - 1);
    if x0 > x1 || y0 > y1 {
        return;
    }
    let mut total = 0.0f32;
    let mut ramp = [0.0f32; STAMP_SPAN * STAMP_SPAN];
    let span = (x1 - x0 + 1) as usize;
    for (row, y) in (y0..=y1).enumerate() {
        let dy = y as f32 + 0.5 - cy;
        for (column, x) in (x0..=x1).enumerate() {
            let dx = x as f32 + 0.5 - cx;
            let distance = (dx * dx + dy * dy).sqrt();
            let coverage = if antialias { (radius + 0.5 - distance).clamp(0.0, 1.0) } else if distance <= radius { 1.0 } else { 0.0 };
            ramp[row * span + column] = coverage;
            total += coverage;
        }
    }
    // The ramp overestimates the area of sub-pixel dots (from a pixel up it matches).
    let area = std::f32::consts::PI * radius * radius;
    let scale = if antialias && radius < 1.0 && total > area { area / total } else { 1.0 };
    for (row, y) in (y0..=y1).enumerate() {
        for (column, x) in (x0..=x1).enumerate() {
            let value = (ramp[row * span + column] * scale * 255.0).round() as u8;
            if value > 0 {
                out.push(((y * width + x) as u32, value));
            }
        }
    }
}

/// Source-over of a premultiplied color scaled by `coverage` onto one premultiplied pixel.
fn blend(pixel: &mut [u8; 4], source: [f32; 4], coverage: u8) {
    let k = coverage as f32 / 255.0;
    let inverse = 1.0 - source[3] * k;
    for channel in 0..4 {
        let value = source[channel] * k * 255.0 + pixel[channel] as f32 * inverse;
        pixel[channel] = value.round().clamp(0.0, 255.0) as u8;
    }
}

/// Fills the union of the disks of `dots` with `color`: coverages are merged by maximum per
/// pixel, so overlapping dots of one color do not darken each other, then blended once.
fn fill_dots(pm: &mut sk::Pixmap, dots: &DotCloud, color: [f64; 4], opacity: f64, antialias: bool) {
    let (width, height) = (pm.width() as i32, pm.height() as i32);
    let alpha = (color[3] * opacity.clamp(0.0, 1.0)).clamp(0.0, 1.0) as f32;
    let source = [color[0] as f32 * alpha, color[1] as f32 * alpha, color[2] as f32 * alpha, alpha];
    let mut covered: Vec<(u32, u8)> = Vec::with_capacity(dots.centers.len() * 16);
    for (&center, &radius) in dots.centers.iter().zip(&dots.radii) {
        disk_coverage(center, radius, width, height, antialias, &mut covered);
    }
    if covered.is_empty() {
        return;
    }
    let pixels = pm.data_mut().as_chunks_mut::<4>().0;
    // Dense clouds merge in a buffer over their bounding box; sparse ones sort their entries.
    let (first, last) = covered.iter().fold((u32::MAX, 0), |(lo, hi), &(index, _)| (lo.min(index), hi.max(index)));
    let span = (last - first + 1) as usize;
    if covered.len() * 16 >= span {
        let mut merged = vec![0u8; span];
        for (index, coverage) in covered {
            let cell = &mut merged[(index - first) as usize];
            *cell = (*cell).max(coverage);
        }
        for (offset, coverage) in merged.into_iter().enumerate() {
            if coverage > 0 {
                blend(&mut pixels[first as usize + offset], source, coverage);
            }
        }
        return;
    }
    covered.sort_unstable_by_key(|&(index, _)| index);
    let mut entries = covered.into_iter().peekable();
    while let Some((index, mut coverage)) = entries.next() {
        while let Some(&(next, more)) = entries.peek() {
            if next != index {
                break;
            }
            coverage = coverage.max(more);
            entries.next();
        }
        blend(&mut pixels[index as usize], source, coverage);
    }
}

/// Multiplies the blurred coverage of a glow (a blurred thin stroke is faint).
const GLOW_GAIN: f32 = 3.0;

/// Box-blurs a coverage plane in place, `passes` times along each axis (three passes look
/// close to a gaussian of the same radius).
fn blur(plane: &mut [f32], width: usize, height: usize, radius: usize, passes: usize) {
    if radius == 0 {
        return;
    }
    let mut line = vec![0.0f32; width.max(height)];
    let window = (2 * radius + 1) as f32;
    for _ in 0..passes {
        for axis in 0..2 {
            let (count, length, stride, step) = if axis == 0 { (height, width, width, 1) } else { (width, height, 1, width) };
            for index in 0..count {
                let base = index * stride;
                let value = |i: isize| -> f32 {
                    if i < 0 || i >= length as isize { 0.0 } else { plane[base + i as usize * step] }
                };
                let mut sum: f32 = (-(radius as isize)..=radius as isize).map(value).sum();
                for (i, out) in line.iter_mut().enumerate().take(length) {
                    *out = sum / window;
                    sum += value(i as isize + radius as isize + 1) - value(i as isize - radius as isize);
                }
                for (i, &v) in line.iter().enumerate().take(length) {
                    plane[base + i * step] = v;
                }
            }
        }
    }
}

/// Paints the soft halo of an item under it: its shape (fill and stroke) rasterized into a
/// coverage plane around it, blurred, then blended in the glow's color.
fn draw_glow(pm: &mut sk::Pixmap, item: &DrawItem, glow: &Glow, antialias: bool) {
    let Some(path) = to_sk_path(&item.path) else { return };
    let stroke_half = item.stroke.as_ref().map_or(0.0, |s| s.width / 2.0);
    let reach = stroke_half + glow.radius * 3.0;
    let bounds = kurbo::Shape::bounding_box(&item.path).inflate(reach, reach);
    let (frame_w, frame_h) = (pm.width() as f64, pm.height() as f64);
    let (x0, y0) = (bounds.x0.max(0.0).floor(), bounds.y0.max(0.0).floor());
    let (x1, y1) = (bounds.x1.min(frame_w).ceil(), bounds.y1.min(frame_h).ceil());
    if x1 <= x0 || y1 <= y0 {
        return;
    }
    let (width, height) = ((x1 - x0) as u32, (y1 - y0) as u32);
    let Some(mut shape) = sk::Pixmap::new(width, height) else { return };
    let white = paint_for([1.0, 1.0, 1.0, 1.0], 1.0, antialias);
    let shift = sk::Transform::from_translate(-x0 as f32, -y0 as f32);
    let rule = if item.fill_rule_even_odd { sk::FillRule::EvenOdd } else { sk::FillRule::Winding };
    if item.fill.is_some() || item.stroke.is_none() {
        shape.fill_path(&path, &white, rule, shift, None);
    }
    if let Some(stroke) = &item.stroke {
        shape.stroke_path(&path, &white, &to_sk_stroke(stroke), shift, None);
    }
    let mut plane: Vec<f32> = shape.pixels().iter().map(|p| p.alpha() as f32 / 255.0).collect();
    blur(&mut plane, width as usize, height as usize, (glow.radius / 2.0).round().max(1.0) as usize, 3);
    let alpha = (glow.color[3] * item.opacity).clamp(0.0, 1.0) as f32;
    let source = [glow.color[0] as f32 * alpha, glow.color[1] as f32 * alpha, glow.color[2] as f32 * alpha, alpha];
    let stride = pm.width() as usize;
    let pixels = pm.data_mut().as_chunks_mut::<4>().0;
    for row in 0..height as usize {
        for column in 0..width as usize {
            // Blurring spreads a thin shape thin: a gain brings the halo up near the shape.
            let coverage = (plane[row * width as usize + column] * GLOW_GAIN).min(1.0);
            let coverage = (coverage * 255.0).round() as u8;
            if coverage > 0 {
                blend(&mut pixels[(y0 as usize + row) * stride + x0 as usize + column], source, coverage);
            }
        }
    }
}

fn draw_item(pm: &mut sk::Pixmap, item: &DrawItem, antialias: bool) {
    if item.opacity <= 0.0 {
        return;
    }
    if let Some(glow) = &item.glow {
        draw_glow(pm, item, glow, antialias);
    }
    let Some(path) = to_sk_path(&item.path) else { return };
    let mask = match &item.clip {
        Some(clip) => {
            let mut m = sk::Mask::new(pm.width(), pm.height()).expect("mask size");
            if let Some(cp) = to_sk_path(clip) {
                m.fill_path(&cp, sk::FillRule::Winding, antialias, sk::Transform::identity());
            }
            Some(m)
        }
        None => None,
    };
    let rule = if item.fill_rule_even_odd { sk::FillRule::EvenOdd } else { sk::FillRule::Winding };
    let id = sk::Transform::identity();
    if let Some(fill) = &item.fill {
        let paint = paint_for(fill.color, item.opacity, antialias);
        match &item.dots {
            Some(dots) if mask.is_none() => fill_dots(pm, dots, fill.color, item.opacity, antialias),
            _ => pm.fill_path(&path, &paint, rule, id, mask.as_ref()),
        }
    }
    if let Some(stroke) = &item.stroke {
        if stroke.width > 0.0 {
            let paint = paint_for(stroke.color, item.opacity, antialias);
            pm.stroke_path(&path, &paint, &to_sk_stroke(stroke), id, mask.as_ref());
        }
    }
    if let Some(image) = &item.image {
        super::bitmap::draw_image(pm, &path, image, item.opacity, antialias, mask.as_ref());
    }
}

/// Rasterize the display list into a straight-alpha RGBA8 image.
/// Items are drawn in order with source-over blending; output is deterministic.
pub fn rasterize(dl: &DisplayList, antialias: bool) -> Image {
    let Some(mut pm) = sk::Pixmap::new(dl.width, dl.height) else {
        return Image { width: dl.width, height: dl.height, rgba: Vec::new() };
    };
    pm.fill(to_sk_color(dl.background, 1.0));
    for item in &dl.items {
        draw_item(&mut pm, item, antialias);
    }
    let opaque = dl.background[3] >= 1.0;
    let mut rgba = pm.take();
    // Over an opaque background every pixel stays opaque (source-over), and premultiplied
    // equals straight alpha: the buffer is already the image. Otherwise demultiply in place,
    // skipping the opaque and empty pixels.
    if !opaque {
        for pixel in rgba.as_chunks_mut::<4>().0 {
            let alpha = pixel[3];
            if alpha == 0 || alpha == 255 {
                continue;
            }
            if let Some(c) = sk::PremultipliedColorU8::from_rgba(pixel[0], pixel[1], pixel[2], alpha) {
                let c = c.demultiply();
                *pixel = [c.red(), c.green(), c.blue(), c.alpha()];
            }
        }
    }
    Image { width: dl.width, height: dl.height, rgba }
}
