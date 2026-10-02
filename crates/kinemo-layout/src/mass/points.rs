//! `points`: dots at `xy` (a list of `Vec2`) with per-point `radius` and `color`.

use kinemo_eval::PointContext;
use kinemo_ir::ObjectId;

use super::color_or;
use crate::Layout;

const DEFAULT_RADIUS: f64 = 0.02;
const DEFAULT_COLOR: [f64; 4] = [1.0, 1.0, 1.0, 1.0];

/// Every dot of a `points` leaf at one time, in local coordinates. All vectors have
/// the same length (one entry per point, in `xy` order).
#[derive(Clone, Debug, Default, PartialEq)]
pub struct PointBatch {
    pub centers: Vec<[f64; 2]>,
    pub radii: Vec<f64>,
    pub colors: Vec<[f64; 4]>,
}

impl PointBatch {
    pub fn len(&self) -> usize {
        self.centers.len()
    }

    pub fn is_empty(&self) -> bool {
        self.centers.is_empty()
    }
}

impl<'a> Layout<'a> {
    /// Point contexts of a `points` leaf: one per `xy` entry.
    pub(crate) fn point_contexts(&self, o: ObjectId, t: f64) -> Vec<PointContext> {
        let xy = self.prop(o, "xy", t).unwrap_or(kinemo_ir::Value::None);
        let list = xy.as_list();
        let n = list.len();
        list.iter()
            .enumerate()
            .map(|(i, v)| {
                let [x, y] = v.as_v2();
                PointContext::new(x, y, i, n)
            })
            .collect()
    }

    /// Centers, radii and colors of every dot of a `points` leaf at `t`.
    pub fn point_batch(&self, o: ObjectId, t: f64) -> PointBatch {
        let contexts = self.point_contexts(o, t);
        let radii = self
            .per_point(o, "radius", t, &contexts)
            .iter()
            .map(|v| match v {
                kinemo_ir::Value::None => DEFAULT_RADIUS,
                v => v.as_f64().max(0.0),
            })
            .collect();
        let colors = self.per_point(o, "color", t, &contexts).iter().map(|v| color_or(v, DEFAULT_COLOR)).collect();
        PointBatch { centers: contexts.iter().map(|p| [p.x, p.y]).collect(), radii, colors }
    }
}
