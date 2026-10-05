//! Memo caches and the recursion guard.
//!
//! Every accessor copies data out and releases its `RefCell` borrow before
//! returning, so evaluation (and resolver callbacks that re-enter the
//! evaluator) never runs while a borrow is held.

use super::Evaluated;
use kinemo_ir::{SignalId, Value};
use std::cell::RefCell;
use rustc_hash::{FxHashMap, FxHashSet};
use std::hash::Hash;
use std::sync::Arc;

/// Time key: the exact bit pattern of the query time.
pub(crate) type TimeKey = u64;

pub(crate) fn time_key(t: f64) -> TimeKey {
    // Normalize -0.0 to 0.0 so both hit the same entry.
    (t + 0.0).to_bits()
}

/// A `RefCell<HashMap>` whose accessors never leak a borrow.
#[derive(Debug)]
pub(crate) struct Cache<K, V>(RefCell<FxHashMap<K, V>>);

impl<K, V> Default for Cache<K, V> {
    fn default() -> Self {
        Cache(RefCell::new(FxHashMap::default()))
    }
}

impl<K: Eq + Hash, V: Clone> Cache<K, V> {
    pub(crate) fn get(&self, k: &K) -> Option<V> {
        self.0.borrow().get(k).cloned()
    }

    pub(crate) fn insert(&self, k: K, v: V) {
        self.0.borrow_mut().insert(k, v);
    }

    pub(crate) fn clear(&self) {
        self.0.borrow_mut().clear();
    }

    pub(crate) fn len(&self) -> usize {
        self.0.borrow().len()
    }
}

/// Identifies one evaluation of a signal's timeline: the signal, how many
/// (sorted) entries are considered, and the query time.
pub(crate) type FrameKey = (SignalId, usize, TimeKey);

#[derive(Debug, Default)]
pub(crate) struct Memo {
    /// Final collapsed values by `(signal, t)`.
    pub(crate) value: Cache<(SignalId, TimeKey), Value>,
    /// Raw evaluations by `(signal, t)`.
    pub(crate) raw: Cache<(SignalId, TimeKey), Evaluated>,
    /// Start values of `Anim` entries by `(signal, sorted position)`, for an evaluator without
    /// a shared [`super::TimelineIndex`]; time-independent.
    pub(crate) from: Cache<(SignalId, usize), Value>,
    /// Stable start-time order of each signal's timeline (same).
    pub(crate) order: Cache<SignalId, Arc<[usize]>>,
    /// Timeline evaluations currently on the stack (cycle detection).
    active: RefCell<FxHashSet<FrameKey>>,
}

impl Memo {
    /// Marks `key` as being evaluated. Returns `None` if it already is (a cycle).
    pub(crate) fn enter(&self, key: FrameKey) -> Option<ActiveGuard<'_>> {
        let inserted = self.active.borrow_mut().insert(key);
        // Build the guard only on success: a dropped guard removes `key`.
        inserted.then(|| ActiveGuard { memo: self, key })
    }

    /// Drops the per-time results, keeping the maps' capacity for the next instant.
    pub(crate) fn clear(&self) {
        self.value.clear();
        self.raw.clear();
    }
}

/// Removes its frame from the active set when dropped.
pub(crate) struct ActiveGuard<'m> {
    memo: &'m Memo,
    key: FrameKey,
}

impl Drop for ActiveGuard<'_> {
    fn drop(&mut self) {
        self.memo.active.borrow_mut().remove(&self.key);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn guard_detects_reentry_and_releases() {
        let m = Memo::default();
        let g = m.enter((1, 2, time_key(0.5))).expect("first entry");
        assert!(m.enter((1, 2, time_key(0.5))).is_none());
        assert!(m.enter((1, 1, time_key(0.5))).is_some());
        drop(g);
        assert!(m.enter((1, 2, time_key(0.5))).is_some());
    }

    #[test]
    fn negative_zero_shares_key() {
        assert_eq!(time_key(-0.0), time_key(0.0));
    }
}
