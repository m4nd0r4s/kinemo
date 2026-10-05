//! `points`: every dot as a small polygon (or a Bézier circle when large), merged per
//! color. `k.draw` reveals dots in index order.

use std::f64::consts::TAU;

use kurbo::{BezPath, Circle, Point, Shape};

use super::{Buckets, MassContext};
use crate::raster::DrawItem;

/// Above this radius in pixels dots are drawn as Bézier circles.
const BEZIER_RADIUS_PX: f64 = 12.0;

/// Unit polygons by vertex count, built once per frame.
struct UnitPolygons(Vec<Vec<(f64, f64)>>);

impl UnitPolygons {
    fn new() -> Self {
        UnitPolygons(vec![Vec::new(); 33])
    }

    /// Vertices of a regular polygon fine enough for a circle of `radius_px` pixels.
    fn get(&mut self, radius_px: f64) -> &[(f64, f64)] {
        let n = ((TAU * radius_px / 2.0).ceil() as usize).clamp(6, 32);
        let slot = &mut self.0[n];
        if slot.is_empty() {
            *slot = (0..n).map(|i| (TAU * i as f64 / n as f64).sin_cos()).map(|(s, c)| (c, s)).collect();
        }
        slot
    }
}

pub(super) fn draw(cx: &MassContext) -> Vec<DrawItem> {
    let batch = cx.layout.point_batch(cx.leaf, cx.t);
    let shown = (cx.progress * batch.len() as f64).ceil() as usize;
    // Pixels per local unit (geometric mean of the axes, exact for similarity transforms).
    let px_per_unit = cx.to_px.determinant().abs().sqrt();
    let mut buckets = Buckets::default();
    let mut polygons = UnitPolygons::new();
    for i in 0..shown.min(batch.len()) {
        let (c, r) = (batch.centers[i], batch.radii[i]);
        let color = cx.tinted(batch.colors[i]);
        if r <= 0.0 || color[3] <= 0.0 {
            continue;
        }
        let radius_px = r * px_per_unit;
        if radius_px > BEZIER_RADIUS_PX {
            let circle = cx.to_px * Circle::new(Point::new(c[0], c[1]), r).to_path(0.1);
            buckets.path(0, color).extend(circle.elements().iter().copied());
            continue;
        }
        let path = buckets.disk(0, color, cx.to_px * Point::new(c[0], c[1]), radius_px);
        push_polygon(path, cx, c, r, polygons.get(radius_px));
    }
    buckets.into_fills()
}

fn push_polygon(path: &mut BezPath, cx: &MassContext, c: [f64; 2], r: f64, unit: &[(f64, f64)]) {
    for (k, (ux, uy)) in unit.iter().enumerate() {
        let p = cx.to_px * Point::new(c[0] + r * ux, c[1] + r * uy);
        if k == 0 {
            path.move_to(p);
        } else {
            path.line_to(p);
        }
    }
    path.close_path();
}
