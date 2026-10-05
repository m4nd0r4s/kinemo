//! Time-independent facts about a scene's timelines, shared by every evaluator of the same
//! scene: each frame of a render and each sample of the lints sort a signal's entries and
//! snapshot an animation's start value once, instead of once per frame.

use kinemo_ir::{Scene, Signal, SignalId, Value};
use std::sync::{Arc, OnceLock};

/// The start values of one signal's animations, by sorted entry position.
type StartValues = Box<[OnceLock<Value>]>;

/// Sorted entry orders and animation start values, filled lazily, by signal.
///
/// Thread-safe: rayon workers rendering different frames share one index. The scene it was
/// made for must not change while it is in use.
#[derive(Debug)]
pub struct TimelineIndex {
    orders: Box<[OnceLock<Arc<[usize]>>]>,
    starts: Box<[OnceLock<StartValues>]>,
}

impl TimelineIndex {
    pub fn new(scene: &Scene) -> Self {
        let signals = scene.signals.len();
        TimelineIndex { orders: (0..signals).map(|_| OnceLock::new()).collect(), starts: (0..signals).map(|_| OnceLock::new()).collect() }
    }

    /// Whether this index was made for a scene with these many signals.
    pub(crate) fn fits(&self, scene: &Scene) -> bool {
        self.orders.len() == scene.signals.len()
    }

    /// Stable start-time order of a signal's entries.
    pub(crate) fn order(&self, signal: &Signal, id: SignalId) -> Arc<[usize]> {
        self.orders[id as usize].get_or_init(|| Self::sorted(signal)).clone()
    }

    /// Entry indices of a signal sorted by start time (stable).
    pub(crate) fn sorted(signal: &Signal) -> Arc<[usize]> {
        let mut indices: Vec<usize> = (0..signal.timeline.len()).collect();
        indices.sort_by(|&a, &b| signal.timeline[a].start().total_cmp(&signal.timeline[b].start()));
        indices.into()
    }

    /// The cell holding the start value of the anim at sorted position `position`. Read with
    /// `get` and fill with `set` (not `get_or_init`): computing a start value may evaluate other
    /// signals, and a dependency cycle must not re-enter the same cell's initializer.
    pub(crate) fn start(&self, signal: &Signal, id: SignalId, position: usize) -> &OnceLock<Value> {
        let cells = self.starts[id as usize].get_or_init(|| (0..signal.timeline.len()).map(|_| OnceLock::new()).collect());
        &cells[position]
    }
}
