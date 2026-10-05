//! The scene evaluator: answers "what is signal `id` at time `t`?" and
//! evaluates expression graphs, memoizing per `(signal, t)`.

mod expr;
mod index;
mod memo;
pub(crate) mod ops;
mod point;
mod timeline;

use crate::interp;
use kinemo_ir::{Lerp, ObjectId, Scene, SignalId, Value};
use memo::{time_key, Memo};
pub use index::TimelineIndex;
pub use point::{PointContext, PointSource};
use std::sync::Arc;

/// The raw state of a signal at a time.
#[derive(Clone, Debug, PartialEq)]
pub enum Evaluated {
    /// A settled value (no transition in progress).
    Value(Value),
    /// A `Replace` animation in progress; `alpha` is the *eased* progress
    /// (may leave `[0, 1]` for overshooting easings). Additive offsets are
    /// already applied to both ends.
    Transition { from: Value, to: Value, alpha: f64 },
}

impl Evaluated {
    /// Collapses to a single value using `lerp`.
    ///
    /// Step modes and non-interpolable values keep `from` (or `to` for
    /// `StepStart`) for the whole transition, regardless of overshoot.
    pub fn collapse(self, lerp: Lerp) -> Value {
        match self {
            Evaluated::Value(v) => v,
            Evaluated::Transition { from, to, alpha } => match lerp {
                Lerp::StepStart => to,
                _ if !interp::is_continuous(&from, &to, lerp) => from,
                _ => interp::lerp_value(&from, &to, alpha, lerp),
            },
        }
    }
}

/// Answers layout-derived reads (`Expr::Derived`) and object ages for the
/// evaluator. Implementations may call back into the [`Evaluator`].
pub trait Resolver {
    fn derived(&self, ev: &Evaluator, obj: ObjectId, prop: &str, world: bool, t: f64) -> Value;
    fn age(&self, ev: &Evaluator, obj: ObjectId, t: f64) -> f64;
    /// Maps a point in `obj`'s local coordinates to world coordinates.
    fn to_world(&self, _ev: &Evaluator, _obj: ObjectId, point: [f64; 2], _t: f64) -> [f64; 2] {
        point
    }
}

/// A resolver with no layout: derived reads are `Value::None`, ages are 0.
#[derive(Clone, Copy, Debug, Default)]
pub struct NoResolver;

impl Resolver for NoResolver {
    fn derived(&self, _: &Evaluator, _: ObjectId, _: &str, _: bool, _: f64) -> Value {
        Value::None
    }
    fn age(&self, _: &Evaluator, _: ObjectId, _: f64) -> f64 {
        0.0
    }
}

/// Evaluates signals and expressions of one scene, with memoization.
///
/// Results computed while a dependency cycle was being cut (see
/// [`Evaluator::signal`]) are memoized like any other; cycles are build
/// errors, so this only affects already-invalid scenes.
#[derive(Debug)]
pub struct Evaluator<'a> {
    scene: &'a Scene,
    memo: Memo,
    /// Shared time-independent work; `None` keeps it in `memo` (a one-off evaluator).
    index: Option<Arc<TimelineIndex>>,
}

impl<'a> Evaluator<'a> {
    pub fn new(scene: &'a Scene) -> Self {
        Evaluator { scene, memo: Memo::default(), index: None }
    }

    /// An evaluator sharing the time-independent work of `index` (made for this scene) with
    /// other evaluators: one per frame or per thread, one index per render.
    pub fn with_index(scene: &'a Scene, index: Arc<TimelineIndex>) -> Self {
        debug_assert!(index.fits(scene), "timeline index made for another scene");
        Evaluator { scene, memo: Memo::default(), index: Some(index) }
    }

    pub fn scene(&self) -> &'a Scene {
        self.scene
    }

    /// Final value of signal `id` at `t`: an in-progress transition is
    /// collapsed with the signal's [`Lerp`] mode at the eased progress.
    ///
    /// Unknown ids and dependency cycles yield `Value::None`.
    pub fn signal(&self, id: SignalId, t: f64, r: &dyn Resolver) -> Value {
        let key = (id, time_key(t));
        if let Some(v) = self.memo.value.get(&key) {
            return v;
        }
        let Some(sig) = self.scene.signals.get(id as usize) else {
            return Value::None;
        };
        let v = self.signal_raw(id, t, r).collapse(sig.lerp);
        self.memo.value.insert(key, v.clone());
        v
    }

    /// Raw state of signal `id` at `t`, for consumers that blend themselves
    /// (`Lerp::Layout`, morphs).
    pub fn signal_raw(&self, id: SignalId, t: f64, r: &dyn Resolver) -> Evaluated {
        let key = (id, time_key(t));
        if let Some(v) = self.memo.raw.get(&key) {
            return v;
        }
        let Some(ev) = self.eval_timeline(id, t, r) else {
            // Unknown signal or cycle: do not memoize a cut cycle at its root.
            return Evaluated::Value(Value::None);
        };
        self.memo.raw.insert(key, ev.clone());
        ev
    }

    /// Drops the memoized per-time results, keeping their capacity (the time-independent work
    /// stays), so one evaluator can serve many instants.
    pub fn clear(&self) {
        self.memo.clear();
    }

    /// Number of memoized signal values (for tests and diagnostics).
    pub fn cached_values(&self) -> usize {
        self.memo.value.len()
    }
}
