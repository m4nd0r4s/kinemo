//! Geometry conversion: glyph outlines (ttf-parser) and typst shapes to kurbo paths.

use kurbo::{Affine, BezPath, Cap, Join, Point, Shape, Stroke, StrokeOpts};
use typst::layout::Abs;
use typst::visualize::{Curve, CurveItem, FixedStroke, Geometry, LineCap, LineJoin};

/// Flattening tolerance for strokes, in typst pt.
const STROKE_TOLERANCE_PT: f64 = 0.001;

struct OutlineBuilder {
    path: BezPath,
}

impl ttf_parser::OutlineBuilder for OutlineBuilder {
    fn move_to(&mut self, x: f32, y: f32) {
        self.path.move_to((x as f64, y as f64));
    }
    fn line_to(&mut self, x: f32, y: f32) {
        self.path.line_to((x as f64, y as f64));
    }
    fn quad_to(&mut self, x1: f32, y1: f32, x: f32, y: f32) {
        self.path.quad_to((x1 as f64, y1 as f64), (x as f64, y as f64));
    }
    fn curve_to(&mut self, x1: f32, y1: f32, x2: f32, y2: f32, x: f32, y: f32) {
        self.path.curve_to((x1 as f64, y1 as f64), (x2 as f64, y2 as f64), (x as f64, y as f64));
    }
    fn close(&mut self) {
        self.path.close_path();
    }
}

/// Outline of glyph `id` in font units (y-up), or `None` if it has no outline.
pub(crate) fn glyph_outline(face: &ttf_parser::Face<'_>, id: u16) -> Option<BezPath> {
    let mut builder = OutlineBuilder { path: BezPath::new() };
    face.outline_glyph(ttf_parser::GlyphId(id), &mut builder)?;
    Some(builder.path)
}

fn point(p: typst::layout::Point) -> Point {
    Point::new(p.x.to_pt(), p.y.to_pt())
}

fn curve_path(curve: &Curve) -> BezPath {
    let mut path = BezPath::new();
    for item in &curve.0 {
        match item {
            CurveItem::Move(p) => path.move_to(point(*p)),
            CurveItem::Line(p) => path.line_to(point(*p)),
            CurveItem::Cubic(a, b, c) => path.curve_to(point(*a), point(*b), point(*c)),
            CurveItem::Close => path.close_path(),
        }
    }
    path
}

/// Shape geometry as a path in its local frame (pt, y-down).
pub(crate) fn geometry_path(geometry: &Geometry) -> BezPath {
    match geometry {
        Geometry::Line(to) => {
            let mut path = BezPath::new();
            path.move_to((0.0, 0.0));
            path.line_to(point(*to));
            path
        }
        Geometry::Rect(size) => kurbo::Rect::new(0.0, 0.0, size.x.to_pt(), size.y.to_pt()).to_path(0.1),
        Geometry::Curve(curve) => curve_path(curve),
    }
}

/// The filled outline of `path` stroked with `stroke`, then transformed by `transform`.
pub(crate) fn stroke_outline(path: &BezPath, stroke: &FixedStroke, transform: Affine) -> BezPath {
    let cap = match stroke.cap {
        LineCap::Butt => Cap::Butt,
        LineCap::Round => Cap::Round,
        LineCap::Square => Cap::Square,
    };
    let join = match stroke.join {
        LineJoin::Miter => Join::Miter,
        LineJoin::Round => Join::Round,
        LineJoin::Bevel => Join::Bevel,
    };
    let style = Stroke::new(stroke.thickness.to_pt())
        .with_caps(cap)
        .with_join(join)
        .with_miter_limit(stroke.miter_limit.get());
    let mut outline = kurbo::stroke(path.iter(), &style, &StrokeOpts::default(), STROKE_TOLERANCE_PT);
    outline.apply_affine(transform);
    outline
}

/// typst point offset helper: `abs` in pt.
pub(crate) fn pt(abs: Abs) -> f64 {
    abs.to_pt()
}
