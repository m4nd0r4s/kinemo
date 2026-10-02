//! Trails (`k.trace(dot.position, length=2)`): the recent path of a moving point.
//!
//! The render stays pure: a trail samples its `point` signal at earlier instants of the
//! timeline instead of remembering anything.

use kurbo::{BezPath, Point};

use kinemo_ir::ObjectId;

use crate::Layout;

const MAX_SAMPLES: usize = 240;

impl<'a> Layout<'a> {
    /// Polyline through `point` over the last `length` seconds (since the trail entered).
    pub(crate) fn trail_path(&self, o: ObjectId, t: f64) -> BezPath {
        let length = self.prop_f(o, "length", t, 2.0).max(0.0);
        let since = t - self.age(o, t);
        let start = (t - length).max(since);
        let span = t - start;
        let samples = ((span * 60.0).ceil() as usize).clamp(1, MAX_SAMPLES);
        let mut path = BezPath::new();
        for i in 0..=samples {
            let ti = start + span * i as f64 / samples as f64;
            let [x, y] = self.prop_v2(o, "point", ti, [0.0, 0.0]);
            let p = Point::new(x, y);
            if i == 0 {
                path.move_to(p);
            } else {
                path.line_to(p);
            }
        }
        path
    }
}
