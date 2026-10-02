//! Mass objects: many marks in one leaf, with per-point props evaluated natively.
//!
//! * `points` — dots at `xy` with per-point `radius` and `color` ([`PointBatch`]).
//! * `vector_field` — arrows of a field `f(p)` sampled on a grid ([`FieldArrow`]).
//! * `stream_lines` — RK4 integral curves of a field from seeds ([`StreamLine`]).
//!
//! A per-point prop is either a uniform value, a list with one value per point, or a
//! per-point expression (`Expr::Point` reads, traced from a Python lambda over `p`),
//! evaluated with [`kinemo_eval::PointContext`] once per point.

mod points;
mod stream_lines;
mod vector_field;

use kurbo::{BezPath, Circle, Point, Rect, Shape};

use kinemo_eval::{PointContext, PointSource};
use kinemo_ir::{ObjectId, Value};

use crate::geometry::{PartRole, ShapePart};
use crate::Layout;

pub use points::PointBatch;
pub use stream_lines::StreamLine;
pub use vector_field::FieldArrow;

/// Kinds handled by this module.
pub fn is_mass_kind(kind: &str) -> bool {
    matches!(kind, "points" | "vector_field" | "stream_lines")
}

/// Default field/seed region: the frame's safe area (inset 0.5 u) shrunk a bit more.
const REGION_INSET: f64 = 1.0;

impl<'a> Layout<'a> {
    /// Values of a per-point prop for every point in `points` (see the module docs).
    pub(crate) fn per_point(&self, o: ObjectId, prop: &str, t: f64, points: &[PointContext]) -> Vec<Value> {
        let Some(id) = self.scene().prop(o, prop) else {
            return vec![Value::None; points.len()];
        };
        if self.ev.signal_uses_point(id) {
            let source = self.ev.point_source(id, t, self);
            return points.iter().map(|p| self.ev.eval_point_source(&source, self, p)).collect();
        }
        match self.ev.signal(id, t, self) {
            Value::List(list) if !list.is_empty() => (0..points.len()).map(|i| list[i % list.len()].clone()).collect(),
            v => vec![v; points.len()],
        }
    }

    /// How a per-point prop is evaluated at `t` (resolved once, evaluated per point with
    /// [`kinemo_eval::Evaluator::eval_point_source`]).
    pub(crate) fn point_source(&self, o: ObjectId, prop: &str, t: f64) -> PointSource<'a> {
        match self.scene().prop(o, prop) {
            Some(id) => self.ev.point_source(id, t, self),
            None => PointSource::Value(Value::None),
        }
    }

    /// The `x_range` × `y_range` region of a field (defaults: the frame inset by 1 u).
    pub(crate) fn mass_region(&self, o: ObjectId, t: f64) -> Rect {
        let cfg = &self.scene().config;
        let (hw, hh) = (cfg.frame_w / 2.0 - REGION_INSET, cfg.frame_h / 2.0 - REGION_INSET);
        let [x0, x1] = self.prop_v2(o, "x_range", t, [-hw, hw]);
        let [y0, y1] = self.prop_v2(o, "y_range", t, [-hh, hh]);
        Rect::new(x0.min(x1), y0.min(y1), x0.max(x1), y0.max(y1))
    }

    /// Generic parts of a mass leaf (all marks merged), for consumers that are not the
    /// mass renderer (morphs, picking).
    pub(crate) fn mass_parts(&self, o: ObjectId, t: f64) -> Vec<ShapePart> {
        match self.scene().object(o).kind.as_str() {
            "points" => {
                let batch = self.point_batch(o, t);
                let mut path = BezPath::new();
                for (c, r) in batch.centers.iter().zip(&batch.radii) {
                    path.extend(Circle::new(Point::new(c[0], c[1]), r.max(0.0)).path_elements(1e-2));
                }
                vec![ShapePart::plain(path, PartRole::Shape)]
            }
            "vector_field" => {
                let mut path = BezPath::new();
                for a in self.field_arrows(o, t) {
                    path.move_to(Point::new(a.start[0], a.start[1]));
                    path.line_to(Point::new(a.end[0], a.end[1]));
                }
                vec![ShapePart::plain(path, PartRole::Open)]
            }
            "stream_lines" => {
                let mut path = BezPath::new();
                for line in self.stream_lines(o, t) {
                    for (i, p) in line.points.iter().enumerate() {
                        let p = Point::new(p[0], p[1]);
                        if i == 0 {
                            path.move_to(p);
                        } else {
                            path.line_to(p);
                        }
                    }
                }
                vec![ShapePart::plain(path, PartRole::Open)]
            }
            _ => vec![],
        }
    }

    /// Local bounding box of a mass leaf, without building paths.
    pub(crate) fn mass_bbox(&self, o: ObjectId, t: f64) -> Rect {
        let boxes: Vec<Rect> = match self.scene().object(o).kind.as_str() {
            "points" => {
                let b = self.point_batch(o, t);
                b.centers
                    .iter()
                    .zip(&b.radii)
                    .map(|(c, r)| Rect::new(c[0] - r, c[1] - r, c[0] + r, c[1] + r))
                    .collect()
            }
            "vector_field" => self
                .field_arrows(o, t)
                .iter()
                .map(|a| Rect::from_points(Point::new(a.start[0], a.start[1]), Point::new(a.end[0], a.end[1])))
                .collect(),
            "stream_lines" => self
                .stream_lines(o, t)
                .iter()
                .flat_map(|l| l.points.iter().map(|p| Rect::from_points(Point::new(p[0], p[1]), Point::new(p[0], p[1]))))
                .collect(),
            _ => vec![],
        };
        boxes.into_iter().reduce(|a, b| a.union(b)).unwrap_or(Rect::ZERO)
    }
}

/// `Value` → color, falling back to `default` for non-colors.
pub(crate) fn color_or(v: &Value, default: [f64; 4]) -> [f64; 4] {
    match v {
        Value::Color(c) => *c,
        _ => default,
    }
}

#[cfg(test)]
mod tests;
