//! Expression evaluation.

use super::ops;
use super::point::PointContext;
use super::{Evaluator, Resolver};
use crate::{format, interp, noise};
use kinemo_ir::{Expr, Table, Value};

impl<'a> Evaluator<'a> {
    /// Evaluates `e` at time `t`. Point attributes (`Expr::Point`) read 0 here; use
    /// [`Evaluator::expr_at_point`] for per-point functions.
    pub fn expr(&self, e: &Expr, t: f64, r: &dyn Resolver) -> Value {
        self.eval_in(e, t, r, None)
    }

    /// Evaluates `e` at `t`, with `point` (if any) answering `Expr::Point` reads.
    pub(super) fn eval_in(&self, e: &Expr, t: f64, r: &dyn Resolver, point: Option<&PointContext>) -> Value {
        let ev = |x: &Expr| self.eval_in(x, t, r, point);
        match e {
            Expr::Const { v } => v.clone(),
            Expr::Sig { id } => self.signal(*id, t, r),
            Expr::Time => Value::Float(t),
            Expr::Age { obj } => Value::Float(r.age(self, *obj, t)),
            Expr::Derived { obj, prop, world } => r.derived(self, *obj, prop, *world, t),
            Expr::ToWorld { obj, p } => {
                let local = ev(p).as_v2();
                Value::Vec2(r.to_world(self, *obj, local, t))
            }
            Expr::Un { f, a } => ops::unary(*f, &ev(a)),
            Expr::Bin { f, a, b } => ops::binary(*f, &ev(a), &ev(b)),
            Expr::Where { c, a, b } => {
                if ev(c).as_bool() {
                    ev(a)
                } else {
                    ev(b)
                }
            }
            Expr::Clamp { a, lo, hi } => ops::clamp(&ev(a), &ev(lo), &ev(hi)),
            Expr::Mix { a, b, t: k } => interp::mix_value(&ev(a), &ev(b), ev(k).as_f64()),
            Expr::Vec2 { x, y } => Value::Vec2([ev(x).as_f64(), ev(y).as_f64()]),
            Expr::Format { spec, a } => Value::Str(format::format_value(spec, &ev(a))),
            Expr::Concat { parts } => Value::Str(parts.iter().map(|p| format::display(&ev(p))).collect()),
            Expr::Interp { x, xs, ys } => Value::Float(piecewise(ev(x).as_f64(), xs, ys)),
            Expr::Spline { x, xs, ys, m } => Value::Float(spline(ev(x).as_f64(), xs, ys, m)),
            Expr::Table { table } => match self.scene.tables.get(*table as usize) {
                Some(tab) => Value::Float(sample_table(tab, t)),
                None => Value::None,
            },
            Expr::Noise { a, seed } => Value::Float(noise::noise1(ev(a).as_f64(), *seed)),
            Expr::Point { attr } => point.map_or(Value::Float(0.0), |p| p.attr(attr)),
        }
    }
}

/// Natural cubic spline with precomputed second derivatives `m`; clamped outside the range.
fn spline(x: f64, xs: &[f64], ys: &[f64], m: &[f64]) -> f64 {
    let n = xs.len();
    if n == 0 || ys.len() != n || m.len() != n {
        return 0.0;
    }
    if n == 1 || x <= xs[0] {
        return ys[0];
    }
    if x >= xs[n - 1] {
        return ys[n - 1];
    }
    let i = xs.partition_point(|&v| v <= x).clamp(1, n - 1);
    let (x0, x1) = (xs[i - 1], xs[i]);
    let h = x1 - x0;
    if h <= 0.0 {
        return ys[i];
    }
    let (a, b) = ((x1 - x) / h, (x - x0) / h);
    a * ys[i - 1] + b * ys[i] + ((a * a * a - a) * m[i - 1] + (b * b * b - b) * m[i]) * h * h / 6.0
}

/// Piecewise-linear interpolation through `(xs[i], ys[i])` (xs ascending),
/// clamped to the end values outside the range. Empty tables give 0.
pub(crate) fn piecewise(x: f64, xs: &[f64], ys: &[f64]) -> f64 {
    let n = xs.len().min(ys.len());
    if n == 0 {
        return 0.0;
    }
    if x.is_nan() || x <= xs[0] {
        return ys[0];
    }
    if x >= xs[n - 1] {
        return ys[n - 1];
    }
    // First index with xs[i] > x; 1 <= i <= n - 1 here.
    let i = xs[..n].partition_point(|&v| v <= x);
    let (x0, x1, y0, y1) = (xs[i - 1], xs[i], ys[i - 1], ys[i]);
    if x1 <= x0 {
        return y1;
    }
    interp::lerp_f(y0, y1, (x - x0) / (x1 - x0))
}

/// Samples a uniform-grid table (`t0 + i·dt`) at time `t`, linearly, clamped.
pub(crate) fn sample_table(tab: &Table, t: f64) -> f64 {
    let n = tab.values.len();
    if n == 0 {
        return 0.0;
    }
    if n == 1 || tab.dt.is_nan() || tab.dt <= 0.0 {
        return tab.values[0];
    }
    let pos = ((t - tab.t0) / tab.dt).clamp(0.0, (n - 1) as f64);
    if pos.is_nan() {
        return tab.values[0];
    }
    let i = (pos.floor() as usize).min(n - 2);
    interp::lerp_f(tab.values[i], tab.values[i + 1], pos - i as f64)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn piecewise_interp() {
        let xs = [0.0, 1.0, 3.0];
        let ys = [0.0, 10.0, 30.0];
        assert_eq!(piecewise(-1.0, &xs, &ys), 0.0);
        assert_eq!(piecewise(0.5, &xs, &ys), 5.0);
        assert_eq!(piecewise(1.0, &xs, &ys), 10.0);
        assert_eq!(piecewise(2.0, &xs, &ys), 20.0);
        assert_eq!(piecewise(9.0, &xs, &ys), 30.0);
        assert_eq!(piecewise(1.0, &[], &[]), 0.0);
        assert_eq!(piecewise(5.0, &[2.0], &[7.0]), 7.0);
    }

    #[test]
    fn table_sampling() {
        let tab = Table { t0: 1.0, dt: 0.5, values: vec![0.0, 1.0, 4.0] };
        assert_eq!(sample_table(&tab, 0.0), 0.0);
        assert_eq!(sample_table(&tab, 1.25), 0.5);
        assert_eq!(sample_table(&tab, 1.5), 1.0);
        assert_eq!(sample_table(&tab, 1.75), 2.5);
        assert_eq!(sample_table(&tab, 2.0), 4.0);
        assert_eq!(sample_table(&tab, 10.0), 4.0);
        assert_eq!(sample_table(&Table { t0: 0.0, dt: 1.0, values: vec![] }, 1.0), 0.0);
        assert_eq!(sample_table(&Table { t0: 0.0, dt: 0.0, values: vec![3.0, 4.0] }, 1.0), 3.0);
    }
}
