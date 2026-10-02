//! `stream_lines`: integral curves of a field, integrated with RK4 in the layout.
//!
//! Seeds are the `seeds` list (`Vec2`s) or, when it is empty, `seed_count` points of
//! a Halton sequence (bases 2 and 3) over the region — deterministic, evenly spread.
//! Each line follows the field's *direction* at unit speed (arc-length steps of
//! `step`, at most `steps` of them), so lines have comparable lengths whatever the
//! field magnitude; it stops when it leaves the region or the field vanishes. The
//! line color mixes `color_low` → `color_high` by its mean magnitude relative to the
//! strongest line (or uses `color` when given).

use kinemo_eval::{color, PointContext, PointSource};
use kinemo_ir::{ObjectId, Value};
use kurbo::{Point, Rect};

use super::color_or;
use super::vector_field::{DEFAULT_HIGH, DEFAULT_LOW};
use crate::Layout;

/// Integrated vertices are capped per line to bound the work per frame.
const MAX_STEPS: usize = 2000;

/// One integrated line, in local coordinates.
#[derive(Clone, Debug, PartialEq)]
pub struct StreamLine {
    /// Vertices from the seed onwards (at least the seed itself).
    pub points: Vec<[f64; 2]>,
    /// Mean field magnitude along the line relative to the strongest line, in `[0, 1]`.
    pub magnitude: f64,
    pub color: [f64; 4],
}

impl StreamLine {
    /// Arc length up to each vertex (`lengths[0] == 0`).
    pub fn cumulative_lengths(&self) -> Vec<f64> {
        let mut acc = 0.0;
        let mut out = Vec::with_capacity(self.points.len());
        for (i, p) in self.points.iter().enumerate() {
            if i > 0 {
                let q = self.points[i - 1];
                acc += (p[0] - q[0]).hypot(p[1] - q[1]);
            }
            out.push(acc);
        }
        out
    }
}

/// Halton radical inverse of `i` in `base`.
fn halton(mut i: usize, base: usize) -> f64 {
    let (mut f, mut r) = (1.0, 0.0);
    while i > 0 {
        f /= base as f64;
        r += f * (i % base) as f64;
        i /= base;
    }
    r
}

/// `n` deterministic seeds spread over `region`.
pub(crate) fn halton_seeds(region: Rect, n: usize) -> Vec<[f64; 2]> {
    (1..=n).map(|i| [region.x0 + halton(i, 2) * region.width(), region.y0 + halton(i, 3) * region.height()]).collect()
}

/// A field evaluator bound to one line (its seed index gives `p.index`).
struct Field<'l, 'a> {
    layout: &'l Layout<'a>,
    source: &'l PointSource<'a>,
    index: usize,
    count: usize,
}

impl Field<'_, '_> {
    fn at(&self, p: [f64; 2]) -> [f64; 2] {
        let ctx = PointContext::new(p[0], p[1], self.index, self.count);
        let v = self.layout.ev.eval_point_source(self.source, self.layout, &ctx).as_v2();
        if v[0].is_finite() && v[1].is_finite() {
            v
        } else {
            [0.0, 0.0]
        }
    }

    /// Unit direction of the field at `p` (zero where the field vanishes).
    fn dir(&self, p: [f64; 2]) -> [f64; 2] {
        unit(self.at(p))
    }

    /// One RK4 step of length `h` along the field direction; `k1` is the direction at `p`.
    fn rk4(&self, p: [f64; 2], k1: [f64; 2], h: f64) -> [f64; 2] {
        let add = |a: [f64; 2], k: [f64; 2], s: f64| [a[0] + k[0] * s, a[1] + k[1] * s];
        let k2 = self.dir(add(p, k1, h / 2.0));
        let k3 = self.dir(add(p, k2, h / 2.0));
        let k4 = self.dir(add(p, k3, h));
        [
            p[0] + h / 6.0 * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0]),
            p[1] + h / 6.0 * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1]),
        ]
    }

    /// Integrates from `seed` (4 field evaluations per step); returns the vertices and
    /// the mean magnitude along them.
    fn integrate(&self, seed: [f64; 2], h: f64, steps: usize, region: Rect) -> (Vec<[f64; 2]>, f64) {
        let mut pts = vec![seed];
        let mut v = self.at(seed);
        let mut total = v[0].hypot(v[1]);
        let mut p = seed;
        for _ in 0..steps {
            if v[0].hypot(v[1]) <= 1e-12 {
                break;
            }
            let q = self.rk4(p, unit(v), h);
            if !region.contains(Point::new(q[0], q[1])) {
                break;
            }
            v = self.at(q);
            total += v[0].hypot(v[1]);
            pts.push(q);
            p = q;
        }
        let mean = total / pts.len() as f64;
        (pts, mean)
    }
}

fn unit(v: [f64; 2]) -> [f64; 2] {
    let m = v[0].hypot(v[1]);
    if m > 1e-12 {
        [v[0] / m, v[1] / m]
    } else {
        [0.0, 0.0]
    }
}

impl<'a> Layout<'a> {
    /// Seeds of a `stream_lines` leaf at `t`.
    pub(crate) fn stream_seeds(&self, o: ObjectId, t: f64) -> Vec<[f64; 2]> {
        let listed: Vec<[f64; 2]> = self.prop(o, "seeds", t).map(|v| v.as_list().iter().map(Value::as_v2).collect()).unwrap_or_default();
        if !listed.is_empty() {
            return listed;
        }
        let n = self.prop_f(o, "seed_count", t, 200.0).round().clamp(0.0, 20_000.0) as usize;
        halton_seeds(self.mass_region(o, t), n)
    }

    /// Every integrated line of a `stream_lines` leaf at `t` (deterministic).
    pub fn stream_lines(&self, o: ObjectId, t: f64) -> Vec<StreamLine> {
        let region = self.mass_region(o, t);
        let seeds = self.stream_seeds(o, t);
        let h = self.prop_f(o, "step", t, 0.05).max(1e-4);
        let steps = (self.prop_f(o, "steps", t, 60.0).round().max(0.0) as usize).min(MAX_STEPS);
        let source = self.point_source(o, "field", t);
        let count = seeds.len();
        let raw: Vec<(Vec<[f64; 2]>, f64)> = seeds
            .iter()
            .enumerate()
            .map(|(index, &seed)| Field { layout: self, source: &source, index, count }.integrate(seed, h, steps, region))
            .collect();
        let max = raw.iter().map(|(_, m)| *m).fold(0.0, f64::max);
        let low = self.prop_color(o, "color_low", t).unwrap_or(DEFAULT_LOW);
        let high = self.prop_color(o, "color_high", t).unwrap_or(DEFAULT_HIGH);
        let contexts: Vec<PointContext> = seeds.iter().enumerate().map(|(i, s)| PointContext::new(s[0], s[1], i, count)).collect();
        let own = self.per_point(o, "color", t, &contexts);
        raw.into_iter()
            .zip(own)
            .map(|((points, mean), own)| {
                let magnitude = if max > 0.0 { mean / max } else { 0.0 };
                StreamLine { points, magnitude, color: color_or(&own, color::mix(low, high, magnitude)) }
            })
            .collect()
    }
}
