//! Timeline semantics: how a signal's `initial` value and its `Set` / `Anim`
//! entries combine into the value at a time.
//!
//! Entries are considered in stable start-time order; for a query at `t`,
//! every entry with `start <= t` is applied in turn, so later starts win.
//!
//! * `Set { t, src }` makes `src` the base (a constant, or an expression
//!   re-evaluated at each query time — a reactive binding).
//! * `Anim` with `Replace` blends from its start value (explicit `from` at
//!   `t0`, or a snapshot of the signal at `t0` built from the *earlier*
//!   entries only) to `to` (evaluated live at `t`). From `t1` on, `to`
//!   becomes the base. Zero-length anims act like a `Set` at `t0`.
//! * `Anim` with `Add` contributes `to · ease(alpha)` (full `to` after `t1`)
//!   on top of the base; numbers and vectors only. A `Set`/`Replace` that
//!   starts after an additive anim has finished absorbs it (the snapshot
//!   already contains it); additive anims still running keep adding.

use super::memo::time_key;
use super::ops;
use super::{Evaluated, Evaluator, Resolver, TimelineIndex};
use crate::ease;
use kinemo_ir::{Blend, Entry, Signal, SignalId, Src, Value};
use std::sync::Arc;

/// What currently provides the base value while walking the timeline.
#[derive(Clone, Copy)]
enum Base<'s> {
    Initial,
    Src(&'s Src),
    /// A `Replace` anim in progress, by sorted position.
    Anim(usize),
}

impl<'a> Evaluator<'a> {
    /// Evaluates signal `id` at `t` considering all its entries. Returns
    /// `None` for unknown signals and when this exact evaluation is already
    /// on the stack (a cycle).
    pub(super) fn eval_timeline(&self, id: SignalId, t: f64, r: &dyn Resolver) -> Option<Evaluated> {
        self.walk(id, None, t, r)
    }

    /// Walks the first `prefix` sorted entries (`None` = all) at `t`.
    ///
    /// With a prefix (start-value snapshots), additive anims still running
    /// at `t` are left out: they keep contributing on top of the anim being
    /// started, so including them here would count them twice.
    fn walk(&self, id: SignalId, prefix: Option<usize>, t: f64, r: &dyn Resolver) -> Option<Evaluated> {
        let sig = self.scene.signals.get(id as usize)?;
        let order = self.order(sig, id);
        let n = prefix.unwrap_or(order.len()).min(order.len());
        let _guard = self.memo.enter((id, n, time_key(t)))?;

        let mut base = Base::Initial;
        let mut adds: Vec<usize> = Vec::new();
        for (pos, &idx) in order[..n].iter().enumerate() {
            let entry = &sig.timeline[idx];
            let start = entry.start();
            if start > t {
                break;
            }
            match entry {
                Entry::Set { src, .. } => {
                    base = Base::Src(src);
                    self.absorb_adds(sig, &order, &mut adds, start);
                }
                Entry::Anim { blend: Blend::Add, .. } => adds.push(pos),
                Entry::Anim { t1, to, .. } => {
                    base = if t >= *t1 { Base::Src(to) } else { Base::Anim(pos) };
                    self.absorb_adds(sig, &order, &mut adds, start);
                }
            }
        }

        let main = match base {
            Base::Initial => Evaluated::Value(sig.initial.clone()),
            Base::Src(src) => Evaluated::Value(self.src(src, t, r)),
            Base::Anim(pos) => {
                let Entry::Anim { t0, t1, to, ease: e, .. } = &sig.timeline[order[pos]] else {
                    unreachable!("Base::Anim always points at an Anim entry")
                };
                let from = self.anim_from(id, sig, pos, r);
                let to = self.src(to, t, r);
                let alpha = ease::apply(e, (t - t0) / (t1 - t0));
                Evaluated::Transition { from, to, alpha }
            }
        };

        if prefix.is_some() {
            adds.retain(|&pos| sig.timeline[order[pos]].end() <= t);
        }
        let offsets: Vec<Value> = adds.iter().map(|&pos| self.add_offset(&sig.timeline[order[pos]], t, r)).collect();
        Some(offsets.iter().fold(main, |acc, off| match acc {
            Evaluated::Value(v) => Evaluated::Value(ops::add_offset(&v, off)),
            Evaluated::Transition { from, to, alpha } => {
                Evaluated::Transition { from: ops::add_offset(&from, off), to: ops::add_offset(&to, off), alpha }
            }
        }))
    }

    /// Drops additive anims that finished by `at` (absorbed by a new base).
    fn absorb_adds(&self, sig: &Signal, order: &[usize], adds: &mut Vec<usize>, at: f64) {
        adds.retain(|&pos| sig.timeline[order[pos]].end() > at);
    }

    /// Current offset contributed by an additive anim (called for `start <= t`).
    fn add_offset(&self, entry: &Entry, t: f64, r: &dyn Resolver) -> Value {
        let Entry::Anim { t0, t1, to, ease: e, .. } = entry else {
            return Value::None;
        };
        let delta = self.src(to, t, r);
        if t >= *t1 {
            delta
        } else {
            ops::scale(&delta, ease::apply(e, (t - t0) / (t1 - t0)))
        }
    }

    /// Start value of the anim at sorted position `pos`: explicit `from` at
    /// `t0`, or the snapshot of the earlier entries at `t0` (memoized).
    fn anim_from(&self, id: SignalId, sig: &Signal, pos: usize, r: &dyn Resolver) -> Value {
        let cell = self.index.as_ref().map(|index| index.start(sig, id, pos));
        let cached = match cell {
            Some(cell) => cell.get().cloned(),
            None => self.memo.from.get(&(id, pos)),
        };
        if let Some(v) = cached {
            return v;
        }
        let order = self.order(sig, id);
        let Entry::Anim { t0, from, .. } = &sig.timeline[order[pos]] else {
            return Value::None;
        };
        let v = match from {
            Some(src) => self.src(src, *t0, r),
            None => match self.walk(id, Some(pos), *t0, r) {
                Some(ev) => ev.collapse(sig.lerp),
                None => return Value::None,
            },
        };
        match cell {
            // A cycle may have filled the cell meanwhile; the first value wins either way.
            Some(cell) => {
                let _ = cell.set(v.clone());
            }
            None => self.memo.from.insert((id, pos), v.clone()),
        }
        v
    }

    pub(super) fn src(&self, src: &Src, t: f64, r: &dyn Resolver) -> Value {
        match src {
            Src::Val { v } => v.clone(),
            Src::Expr { e } => self.expr(e, t, r),
        }
    }

    /// Stable start-time order of a signal's entries (shared by the index).
    pub(super) fn order(&self, sig: &Signal, id: SignalId) -> Arc<[usize]> {
        if let Some(index) = &self.index {
            return index.order(sig, id);
        }
        if let Some(order) = self.memo.order.get(&id) {
            return order;
        }
        let order = TimelineIndex::sorted(sig);
        self.memo.order.insert(id, order.clone());
        order
    }
}
