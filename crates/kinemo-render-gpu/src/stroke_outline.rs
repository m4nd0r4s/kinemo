//! Stroke expansion on the CPU with tiny-skia's stroker and dasher.
//!
//! Vello's GPU stroker flattens round joins/caps and offset curves with a fixed 0.25 px
//! tolerance (chords inside the arc), which makes round caps visibly smaller than the
//! tiny-skia reference, and kurbo's dasher merges the dash wrapping through `ClosePath`,
//! which tiny-skia does not. Expanding strokes here gives outlines identical to the CPU
//! path; the GPU then only fills them (nonzero), so the remaining differences are
//! anti-aliasing coverage alone. Expansion runs in parallel per frame in a batch.

use kinemo_render::raster::{Cap, Join, Stroke};
use kurbo::{BezPath, PathEl};
use tiny_skia as sk;

fn to_tiny_skia_path(path: &BezPath) -> Option<sk::Path> {
    let mut builder = sk::PathBuilder::new();
    for element in path.elements() {
        match *element {
            PathEl::MoveTo(p) => builder.move_to(p.x as f32, p.y as f32),
            PathEl::LineTo(p) => builder.line_to(p.x as f32, p.y as f32),
            PathEl::QuadTo(a, p) => builder.quad_to(a.x as f32, a.y as f32, p.x as f32, p.y as f32),
            PathEl::CurveTo(a, b, p) => {
                builder.cubic_to(a.x as f32, a.y as f32, b.x as f32, b.y as f32, p.x as f32, p.y as f32)
            }
            PathEl::ClosePath => builder.close(),
        }
    }
    builder.finish()
}

fn from_tiny_skia_path(path: &sk::Path) -> BezPath {
    let point = |p: sk::Point| kurbo::Point::new(p.x as f64, p.y as f64);
    let mut out = BezPath::new();
    for segment in path.segments() {
        match segment {
            sk::PathSegment::MoveTo(p) => out.move_to(point(p)),
            sk::PathSegment::LineTo(p) => out.line_to(point(p)),
            sk::PathSegment::QuadTo(a, p) => out.quad_to(point(a), point(p)),
            sk::PathSegment::CubicTo(a, b, p) => out.curve_to(point(a), point(b), point(p)),
            sk::PathSegment::Close => out.close_path(),
        }
    }
    out
}

/// Same stroke parameters as the CPU rasterizer (`kinemo_render::raster::paint`).
fn to_tiny_skia_stroke(stroke: &Stroke) -> sk::Stroke {
    let mut style = sk::Stroke {
        width: stroke.width.max(0.0) as f32,
        line_cap: match stroke.cap {
            Cap::Butt => sk::LineCap::Butt,
            Cap::Round => sk::LineCap::Round,
            Cap::Square => sk::LineCap::Square,
        },
        line_join: match stroke.join {
            Join::Miter => sk::LineJoin::Miter,
            Join::Round => sk::LineJoin::Round,
            Join::Bevel => sk::LineJoin::Bevel,
        },
        ..Default::default()
    };
    if let Some(dash) = &stroke.dash {
        let mut pattern: Vec<f32> = dash.iter().map(|d| d.max(0.0) as f32).collect();
        if pattern.len() % 2 == 1 {
            pattern.extend_from_within(..);
        }
        style.dash = sk::StrokeDash::new(pattern, 0.0);
    }
    style
}

/// Fill outline (nonzero) of `path` stroked with `stroke`, or `None` when tiny-skia would
/// draw nothing (zero width, invalid dash pattern, empty path).
pub(crate) fn stroke_outline(path: &BezPath, stroke: &Stroke) -> Option<BezPath> {
    if stroke.width <= 0.0 {
        return None;
    }
    let style = to_tiny_skia_stroke(stroke);
    if stroke.dash.is_some() && style.dash.is_none() {
        return None;
    }
    let mut source = to_tiny_skia_path(path)?;
    if let Some(dash) = &style.dash {
        source = source.dash(dash, 1.0)?;
    }
    source.stroke(&style, 1.0).map(|outline| from_tiny_skia_path(&outline))
}
