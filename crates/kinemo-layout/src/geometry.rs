//! Local geometry of leaf nodes (shapes and text), before any transform.
//!
//! Shapes are centered on their local origin unless their definition says otherwise
//! (lines and paths use the coordinates they were given).

use kurbo::{BezPath, Circle, Ellipse, Point, Rect, RoundedRect, Shape, Vec2};

use kinemo_ir::ObjectId;
use kinemo_text::{Align, TextOptions};

use crate::Layout;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PartRole {
    /// Painted with both fill and stroke styles (closed shapes).
    Shape,
    /// Stroke only (open paths: lines, arcs).
    Open,
    /// Text glyph: filled with the fill color, stroked only when stroke width > 0.
    Glyph,
}

/// One drawable piece of a leaf, in local coordinates (y-up, scene units).
#[derive(Clone, Debug)]
pub struct ShapePart {
    pub path: BezPath,
    pub role: PartRole,
    /// Index among the glyphs of the text/math/code source (for `write`); 0 otherwise.
    pub index: usize,
    /// Number of glyphs in the source (the `write` order spans the whole source).
    pub count: usize,
    /// Matching key for morphs (the character, token or TeX of a glyph).
    pub key: Option<String>,
    /// Own color (syntax highlighting); `None` uses the leaf's fill.
    pub color: Option<[f64; 4]>,
}

impl ShapePart {
    pub(crate) fn plain(path: BezPath, role: PartRole) -> Self {
        ShapePart { path, role, index: 0, count: 1, key: None, color: None }
    }
}

const TOL: f64 = 1e-3;

impl<'a> Layout<'a> {
    /// Drawable parts of a leaf node at `t`. Groups and containers have none.
    pub fn parts(&self, o: ObjectId, t: f64) -> Vec<ShapePart> {
        let kind = self.scene().object(o).kind.as_str();
        let shape = |p: BezPath| vec![ShapePart::plain(p, PartRole::Shape)];
        let open = |p: BezPath| vec![ShapePart::plain(p, PartRole::Open)];
        match kind {
            "circle" | "dot" => {
                let r = self.prop_f(o, "r", t, if kind == "dot" { 0.08 } else { 1.0 });
                shape(Circle::new(Point::ZERO, r.max(0.0)).to_path(TOL))
            }
            "ellipse" => {
                let w = self.prop_f(o, "w", t, 2.0);
                let h = self.prop_f(o, "h", t, 1.0);
                shape(Ellipse::new(Point::ZERO, Vec2::new(w / 2.0, h / 2.0), 0.0).to_path(TOL))
            }
            "rect" => {
                let w = self.prop_f(o, "w", t, 2.0).max(0.0);
                let h = self.prop_f(o, "h", t, 1.0).max(0.0);
                let r = self.prop_f(o, "radius", t, 0.0).clamp(0.0, w.min(h) / 2.0);
                let rect = Rect::new(-w / 2.0, -h / 2.0, w / 2.0, h / 2.0);
                if r > 0.0 {
                    shape(RoundedRect::from_rect(rect, r).to_path(TOL))
                } else {
                    shape(rect.to_path(TOL))
                }
            }
            "polygon" => shape(polyline(&self.prop_points(o, "points", t), true)),
            "regular_polygon" => {
                let sides = self.prop_f(o, "sides", t, 5.0).round().max(3.0) as usize;
                let r = self.prop_f(o, "r", t, 1.0);
                let pts: Vec<Point> = (0..sides)
                    .map(|i| {
                        let a = std::f64::consts::FRAC_PI_2 + std::f64::consts::TAU * i as f64 / sides as f64;
                        Point::new(r * a.cos(), r * a.sin())
                    })
                    .collect();
                shape(polyline(&pts, true))
            }
            "polyline" => open(polyline(&self.prop_points(o, "points", t), false)),
            "line" => {
                let [ax, ay] = self.prop_v2(o, "start", t, [-1.0, 0.0]);
                let [bx, by] = self.prop_v2(o, "end", t, [1.0, 0.0]);
                open(polyline(&[Point::new(ax, ay), Point::new(bx, by)], false))
            }
            "arrow" => self.arrow_parts(o, t),
            "arc" => {
                let r = self.prop_f(o, "r", t, 1.0);
                let start = self.prop_f(o, "start_angle", t, 0.0).to_radians();
                let sweep = self.prop_f(o, "angle", t, 90.0).to_radians();
                let arc = kurbo::Arc::new(Point::ZERO, Vec2::new(r, r), start, sweep, 0.0);
                open(arc.into_path(TOL))
            }
            "sector" => {
                let outer = self.prop_f(o, "r", t, 1.0).max(0.0);
                let inner = self.prop_f(o, "inner", t, 0.0).clamp(0.0, outer);
                let start = self.prop_f(o, "start_angle", t, 0.0).to_radians();
                let sweep = self.prop_f(o, "angle", t, 90.0).to_radians();
                if sweep.abs() < 1e-9 || outer <= 0.0 {
                    return vec![];
                }
                shape(sector_path(outer, inner, start, sweep))
            }
            "path" => {
                let d = self.prop_str(o, "d", t).unwrap_or_default();
                let closed = self.prop_bool(o, "closed", t, false);
                let p = BezPath::from_svg(&d).unwrap_or_default();
                if closed {
                    shape(p)
                } else {
                    open(p)
                }
            }
            "image" => {
                // Drawn by the renderer as a bitmap; for layout, morphs and picking it is
                // its rectangle.
                let w = self.prop_f(o, "w", t, 1.0).max(0.0);
                let h = self.prop_f(o, "h", t, 1.0).max(0.0);
                shape(Rect::new(-w / 2.0, -h / 2.0, w / 2.0, h / 2.0).to_path(TOL))
            }
            "brace" => self.brace_parts(o, t),
            "text" => self.source_parts(o, t, None),
            "glyphs" => self.glyph_run_parts(o, t),
            "plot" => open(self.plot_path(o, t)),
            "plot_area" => shape(self.plot_area_path(o, t)),
            "trail" => open(self.trail_path(o, t)),
            k if crate::mass::is_mass_kind(k) => self.mass_parts(o, t),
            _ => vec![],
        }
    }

    fn arrow_parts(&self, o: ObjectId, t: f64) -> Vec<ShapePart> {
        let [ax, ay] = self.prop_v2(o, "start", t, [-1.0, 0.0]);
        let [bx, by] = self.prop_v2(o, "end", t, [1.0, 0.0]);
        let tip = self.prop_f(o, "tip", t, 0.25);
        let (a, b) = (Point::new(ax, ay), Point::new(bx, by));
        let d = b - a;
        let len = d.hypot();
        if len < 1e-9 {
            return vec![];
        }
        let dir = d / len;
        let normal = Vec2::new(-dir.y, dir.x);
        let tip = tip.min(len * 0.5);
        let base = b - dir * tip;
        let shaft = polyline(&[a, base], false);
        let head = polyline(&[b, base + normal * (tip * 0.5), base - normal * (tip * 0.5)], true);
        vec![ShapePart::plain(shaft, PartRole::Open), ShapePart { index: 1, ..ShapePart::plain(head, PartRole::Shape) }]
    }

    pub(crate) fn text_options(&self, o: ObjectId, t: f64) -> TextOptions {
        let width = self.prop_f(o, "wrap", t, 0.0);
        TextOptions {
            size: self.prop_f(o, "size", t, 0.5),
            width: (width > 0.0).then_some(width),
            align: match self.prop_str(o, "align", t).as_deref() {
                Some("center") => Align::Center,
                Some("right") => Align::Right,
                _ => Align::Left,
            },
            mono: self.prop_bool(o, "mono", t, false),
            ..TextOptions::default()
        }
    }

    /// Bounding box of a leaf in local coordinates (logical box for text).
    pub(crate) fn leaf_bbox(&self, o: ObjectId, t: f64) -> Rect {
        match self.scene().object(o).kind.as_str() {
            "text" => return self.source_box(o, t),
            "glyphs" => return self.glyph_run_box(o, t),
            k if crate::mass::is_mass_kind(k) => return self.mass_bbox(o, t),
            _ => {}
        }
        self.parts(o, t)
            .iter()
            .map(|p| p.path.bounding_box())
            .reduce(|a, b| a.union(b))
            .unwrap_or(Rect::ZERO)
    }
}

fn polyline(pts: &[Point], closed: bool) -> BezPath {
    let mut p = BezPath::new();
    for (i, pt) in pts.iter().enumerate() {
        if i == 0 {
            p.move_to(*pt);
        } else {
            p.line_to(*pt);
        }
    }
    if closed && pts.len() > 2 {
        p.close_path();
    }
    p
}

/// A pie slice (`inner` 0) or a ring slice: the outer arc, then the inner one back, closed.
fn sector_path(outer: f64, inner: f64, start: f64, sweep: f64) -> BezPath {
    let mut path = BezPath::new();
    let point = |r: f64, a: f64| Point::new(r * a.cos(), r * a.sin());
    path.move_to(point(outer, start));
    path.extend(kurbo::Arc::new(Point::ZERO, Vec2::new(outer, outer), start, sweep, 0.0).append_iter(TOL));
    if inner > 0.0 {
        path.line_to(point(inner, start + sweep));
        path.extend(kurbo::Arc::new(Point::ZERO, Vec2::new(inner, inner), start + sweep, -sweep, 0.0).append_iter(TOL));
    } else {
        path.line_to(Point::ZERO);
    }
    path.close_path();
    path
}
