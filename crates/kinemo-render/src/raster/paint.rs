//! Display list -> pixels.

use kurbo::{BezPath, PathEl};
use tiny_skia as sk;

use super::{Cap, DisplayList, DrawItem, Image, Join, Stroke};

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
        pm.fill_path(&path, &paint, rule, id, mask.as_ref());
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
