//! Display list -> pixels.

use kurbo::{BezPath, PathEl};
use tiny_skia as sk;

use super::{Cap, DisplayList, DotCloud, DrawItem, Image, Join, Stroke};

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

fn draw_item(pm: &mut sk::Pixmap, item: &DrawItem, antialias: bool) {
    if item.opacity <= 0.0 {
        return;
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
    let mut rgba = Vec::with_capacity(pm.data().len());
    for px in pm.pixels() {
        let c = px.demultiply();
        rgba.extend_from_slice(&[c.red(), c.green(), c.blue(), c.alpha()]);
    }
    Image { width: dl.width, height: dl.height, rgba }
}
