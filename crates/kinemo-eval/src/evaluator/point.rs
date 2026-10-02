//! Per-point evaluation for mass objects (`k.Points`, `k.VectorField`, `k.StreamLines`).
//!
//! A per-point function is traced in Python with a symbolic point `p` and stored as an
//! ordinary expression containing `Expr::Point { attr }` reads. The layout evaluates it
//! once per point with a [`PointContext`]; everything else in the expression (signals,
//! `k.time`, layout reads) is evaluated as usual and memoized per time, so only the
//! point-dependent arithmetic runs per point.

use super::{Evaluator, Resolver};
use crate::{ease, interp};
use kinemo_ir::{Blend, Entry, Expr, Lerp, Signal, SignalId, Src, Value};

/// The point a per-point expression is evaluated at.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct PointContext {
    pub x: f64,
    pub y: f64,
    pub index: usize,
    pub count: usize,
}

impl PointContext {
    pub fn new(x: f64, y: f64, index: usize, count: usize) -> Self {
        PointContext { x, y, index, count }
    }

    /// Normalized position of the point in its set: `index / (count - 1)` (0 for one point).
    pub fn param(&self) -> f64 {
        if self.count > 1 {
            self.index as f64 / (self.count - 1) as f64
        } else {
            0.0
        }
    }

    /// Value of the attribute `attr` (`x`, `y`, `index`, `count`, `t`, `xy`); unknown ones are 0.
    pub fn attr(&self, attr: &str) -> Value {
        match attr {
            "x" => Value::Float(self.x),
            "y" => Value::Float(self.y),
            "index" => Value::Float(self.index as f64),
            "count" => Value::Float(self.count as f64),
            "t" => Value::Float(self.param()),
            "xy" | "position" => Value::Vec2([self.x, self.y]),
            _ => Value::Float(0.0),
        }
    }
}

fn src_uses_point(src: &Src) -> bool {
    matches!(src, Src::Expr { e } if e.uses_point())
}

/// Whether any entry of `sig` is a per-point expression.
pub(crate) fn signal_has_point_source(sig: &Signal) -> bool {
    sig.timeline.iter().any(|e| match e {
        Entry::Set { src, .. } => src_uses_point(src),
        Entry::Anim { to, from, .. } => src_uses_point(to) || from.as_ref().is_some_and(src_uses_point),
    })
}

/// How a signal produces its value at one time, for every point: resolved once per
/// time from the timeline (which does not depend on the point), then evaluated per point
/// with [`Evaluator::eval_point_source`].
#[derive(Clone, Debug, PartialEq)]
pub enum PointSource<'s> {
    /// The same value for every point.
    Value(Value),
    /// A per-point expression evaluated at time `t`.
    Expr { e: &'s Expr, t: f64 },
    /// A replace animation in progress between two sources (`alpha` already eased).
    Blend { from: Box<PointSource<'s>>, to: Box<PointSource<'s>>, alpha: f64, lerp: Lerp },
}

impl<'a> Evaluator<'a> {
    /// Evaluates `e` at `t` for one point of a mass object.
    pub fn expr_at_point(&self, e: &Expr, t: f64, r: &dyn Resolver, point: &PointContext) -> Value {
        self.eval_in(e, t, r, Some(point))
    }

    /// Whether signal `id` is driven (at any time) by a per-point expression.
    pub fn signal_uses_point(&self, id: SignalId) -> bool {
        self.scene.signals.get(id as usize).is_some_and(signal_has_point_source)
    }

    /// Value of signal `id` at `t` for one point (see [`Evaluator::point_source`]).
    pub fn signal_at_point(&self, id: SignalId, t: f64, r: &dyn Resolver, point: &PointContext) -> Value {
        self.eval_point_source(&self.point_source(id, t, r), r, point)
    }

    /// Resolves how signal `id` gives its value at `t` for any point.
    ///
    /// Signals without per-point sources give their ordinary (memoized) value. For
    /// per-point signals the timeline is walked like [`Evaluator::signal`] does — sets,
    /// replace animations with easing and the signal's lerp mode — keeping each
    /// source as an expression to evaluate per point. Additive animations are not
    /// applied per point.
    pub fn point_source(&self, id: SignalId, t: f64, r: &dyn Resolver) -> PointSource<'a> {
        let Some(sig) = self.scene.signals.get(id as usize) else {
            return PointSource::Value(Value::None);
        };
        if !signal_has_point_source(sig) {
            return PointSource::Value(self.signal(id, t, r));
        }
        let order = self.order(sig, id);
        self.walk_point_source(sig, &order, order.len(), t)
    }

    /// Value of `source` at `point`.
    pub fn eval_point_source(&self, source: &PointSource, r: &dyn Resolver, point: &PointContext) -> Value {
        match source {
            PointSource::Value(v) => v.clone(),
            PointSource::Expr { e, t } => self.eval_in(e, *t, r, Some(point)),
            PointSource::Blend { from, to, alpha, lerp } => {
                let (from, to) = (self.eval_point_source(from, r, point), self.eval_point_source(to, r, point));
                match lerp {
                    Lerp::StepStart => to,
                    lerp if !interp::is_continuous(&from, &to, *lerp) => from,
                    lerp => interp::lerp_value(&from, &to, *alpha, *lerp),
                }
            }
        }
    }

    /// Source of `sig` at `t` from its first `n` sorted entries.
    fn walk_point_source(&self, sig: &'a Signal, order: &[usize], n: usize, t: f64) -> PointSource<'a> {
        let mut base: Option<&'a Src> = None;
        let mut running: Option<usize> = None;
        for (pos, &idx) in order[..n].iter().enumerate() {
            let entry = &sig.timeline[idx];
            if entry.start() > t {
                break;
            }
            match entry {
                Entry::Set { src, .. } => (base, running) = (Some(src), None),
                Entry::Anim { blend: Blend::Add, .. } => {}
                Entry::Anim { t1, to, .. } => {
                    if t >= *t1 {
                        (base, running) = (Some(to), None);
                    } else {
                        running = Some(pos);
                    }
                }
            }
        }
        let Some(pos) = running else {
            return match base {
                Some(src) => source_at(src, t),
                None => PointSource::Value(sig.initial.clone()),
            };
        };
        let Entry::Anim { t0, t1, to, from, ease: e, .. } = &sig.timeline[order[pos]] else {
            unreachable!("running always points at an Anim entry")
        };
        let from = match from {
            Some(src) => source_at(src, *t0),
            None => self.walk_point_source(sig, order, pos, *t0),
        };
        PointSource::Blend {
            from: Box::new(from),
            to: Box::new(source_at(to, t)),
            alpha: ease::apply(e, (t - t0) / (t1 - t0)),
            lerp: sig.lerp,
        }
    }
}

fn source_at(src: &Src, t: f64) -> PointSource<'_> {
    match src {
        Src::Val { v } => PointSource::Value(v.clone()),
        Src::Expr { e } => PointSource::Expr { e, t },
    }
}
