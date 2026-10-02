//! Function plots: polylines in data coordinates mapped into an axes box.
//!
//! A `plot` carries its data points (one list per continuous segment) plus the axes
//! mapping (`x_range`, `y_range`, `size`), usually bound to the axes' own signals so
//! that zooming the axes re-maps every curve. `clip` limits the data x interval drawn,
//! which is how `ax.plot(f, until=signal)` grows a curve.

use kurbo::{BezPath, Point};

use kinemo_ir::{ObjectId, Value};

use crate::Layout;

/// Data → local coordinates of an axes box centered on the origin.
#[derive(Clone, Copy, Debug)]
pub(crate) struct AxesMap {
    x: [f64; 2],
    y: [f64; 2],
    size: [f64; 2],
}

impl AxesMap {
    pub(crate) fn apply(&self, x: f64, y: f64) -> Point {
        let fx = (x - self.x[0]) / (self.x[1] - self.x[0]);
        let fy = (y - self.y[0]) / (self.y[1] - self.y[0]);
        Point::new(fx * self.size[0] - self.size[0] / 2.0, fy * self.size[1] - self.size[1] / 2.0)
    }
}

fn segments(v: Option<Value>) -> Vec<Vec<[f64; 2]>> {
    v.map(|v| {
        v.as_list()
            .iter()
            .map(|seg| seg.as_list().iter().map(|p| p.as_v2()).collect())
            .collect()
    })
    .unwrap_or_default()
}

/// Points of one segment restricted to `clip` in data x, interpolating at the cut.
fn clipped(seg: &[[f64; 2]], clip: [f64; 2]) -> Vec<[f64; 2]> {
    let mut out = Vec::with_capacity(seg.len());
    for w in seg.windows(2) {
        let (a, b) = (w[0], w[1]);
        let lerp = |x: f64| {
            let t = if b[0] == a[0] { 0.0 } else { (x - a[0]) / (b[0] - a[0]) };
            [x, a[1] + (b[1] - a[1]) * t]
        };
        let (lo, hi) = (a[0].min(b[0]), a[0].max(b[0]));
        if hi < clip[0] || lo > clip[1] {
            continue;
        }
        let start = if a[0] < clip[0] { lerp(clip[0]) } else if a[0] > clip[1] { lerp(clip[1]) } else { a };
        let end = if b[0] > clip[1] { lerp(clip[1]) } else if b[0] < clip[0] { lerp(clip[0]) } else { b };
        if out.last() != Some(&start) {
            out.push(start);
        }
        out.push(end);
    }
    if seg.len() == 1 && seg[0][0] >= clip[0] && seg[0][0] <= clip[1] {
        out.push(seg[0]);
    }
    out
}

/// Runs of a polyline inside the data y interval `[lo, hi]`, cut exactly at the border:
/// a curve leaving the axes stops at its edge instead of drawing over the scene.
fn inside_y(points: &[[f64; 2]], lo: f64, hi: f64) -> Vec<Vec<[f64; 2]>> {
    let inside = |p: &[f64; 2]| p[1] >= lo && p[1] <= hi;
    let cross = |a: [f64; 2], b: [f64; 2], y: f64| {
        let t = (y - a[1]) / (b[1] - a[1]);
        [a[0] + (b[0] - a[0]) * t, y]
    };
    let border = |a: [f64; 2], b: [f64; 2]| {
        let target = if (a[1] > hi) != (b[1] > hi) { hi } else { lo };
        cross(a, b, target)
    };
    let mut runs: Vec<Vec<[f64; 2]>> = Vec::new();
    let mut current: Vec<[f64; 2]> = Vec::new();
    for (i, &p) in points.iter().enumerate() {
        let prev = i.checked_sub(1).map(|j| points[j]);
        match (prev, inside(&p)) {
            (None, true) => current.push(p),
            (None, false) => {}
            (Some(a), true) => {
                if !inside(&a) {
                    current.push(border(a, p));
                }
                current.push(p);
            }
            (Some(a), false) => {
                if inside(&a) {
                    current.push(border(a, p));
                    runs.push(std::mem::take(&mut current));
                } else if (a[1] < lo && p[1] > hi) || (a[1] > hi && p[1] < lo) {
                    // Jumps across the whole range in one step: draw the crossing chord.
                    runs.push(vec![cross(a, p, if a[1] < lo { lo } else { hi }), cross(a, p, if a[1] < lo { hi } else { lo })]);
                }
            }
        }
    }
    if current.len() > 1 {
        runs.push(current);
    }
    runs.into_iter().filter(|r| r.len() > 1).collect()
}

impl<'a> Layout<'a> {
    pub(crate) fn axes_map(&self, o: ObjectId, t: f64) -> AxesMap {
        AxesMap {
            x: self.prop_v2(o, "x_range", t, [0.0, 1.0]),
            y: self.prop_v2(o, "y_range", t, [0.0, 1.0]),
            size: self.prop_v2(o, "size", t, [1.0, 1.0]),
        }
    }

    /// Drawn data-x interval: the requested clip, never beyond the visible x range.
    fn clip(&self, o: ObjectId, t: f64) -> [f64; 2] {
        let [lo, hi] = self.prop_v2(o, "clip", t, [f64::NEG_INFINITY, f64::INFINITY]);
        let [x0, x1] = self.prop_v2(o, "x_range", t, [f64::NEG_INFINITY, f64::INFINITY]);
        [lo.max(x0.min(x1)), hi.min(x0.max(x1))]
    }

    /// Open polyline(s) of a `plot` in local coordinates.
    pub(crate) fn plot_path(&self, o: ObjectId, t: f64) -> BezPath {
        let map = self.axes_map(o, t);
        let clip = self.clip(o, t);
        let [y0, y1] = self.prop_v2(o, "y_range", t, [f64::NEG_INFINITY, f64::INFINITY]);
        let mut path = BezPath::new();
        for seg in segments(self.prop(o, "points", t)) {
            for run in inside_y(&clipped(&seg, clip), y0.min(y1), y0.max(y1)) {
                for (i, [x, y]) in run.into_iter().enumerate() {
                    let p = map.apply(x, y);
                    if i == 0 {
                        path.move_to(p);
                    } else {
                        path.line_to(p);
                    }
                }
            }
        }
        path
    }

    /// Closed region between `points` (top) and `base` (bottom, same x samples) of a
    /// `plot_area`; a missing base means the x axis (y = 0).
    pub(crate) fn plot_area_path(&self, o: ObjectId, t: f64) -> BezPath {
        let map = self.axes_map(o, t);
        let clip = self.clip(o, t);
        let tops = segments(self.prop(o, "points", t));
        let bases = segments(self.prop(o, "base", t));
        let mut path = BezPath::new();
        for (i, top) in tops.iter().enumerate() {
            let top = clipped(top, clip);
            if top.len() < 2 {
                continue;
            }
            let base: Vec<[f64; 2]> = match bases.get(i) {
                Some(b) => clipped(b, clip),
                None => top.iter().map(|p| [p[0], 0.0]).collect(),
            };
            for (j, [x, y]) in top.iter().enumerate() {
                let p = map.apply(*x, *y);
                if j == 0 {
                    path.move_to(p);
                } else {
                    path.line_to(p);
                }
            }
            for [x, y] in base.iter().rev() {
                path.line_to(map.apply(*x, *y));
            }
            path.close_path();
        }
        path
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clip_interpolates_the_cut() {
        let seg = [[0.0, 0.0], [2.0, 2.0], [4.0, 0.0]];
        let out = clipped(&seg, [f64::NEG_INFINITY, 1.0]);
        assert_eq!(out, vec![[0.0, 0.0], [1.0, 1.0]]);
    }

    #[test]
    fn clip_keeps_everything_inside() {
        let seg = [[0.0, 0.0], [1.0, 1.0]];
        assert_eq!(clipped(&seg, [-10.0, 10.0]), seg.to_vec());
    }

    #[test]
    fn curves_stop_at_the_y_range() {
        let runs = inside_y(&[[0.0, 0.0], [1.0, 2.0], [2.0, 0.0]], -1.0, 1.0);
        assert_eq!(runs, vec![vec![[0.0, 0.0], [0.5, 1.0]], vec![[1.5, 1.0], [2.0, 0.0]]]);
    }

    #[test]
    fn axes_map_corners() {
        let m = AxesMap { x: [0.0, 10.0], y: [0.0, 5.0], size: [8.0, 4.0] };
        assert_eq!(m.apply(0.0, 0.0), Point::new(-4.0, -2.0));
        assert_eq!(m.apply(10.0, 5.0), Point::new(4.0, 2.0));
    }
}
