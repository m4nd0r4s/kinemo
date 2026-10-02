//! PNG frame cache keyed by (timeline segment hash, frame index), bounded by total bytes.
//!
//! Keying by segment content means an edit only invalidates the frames it can change.

use std::collections::HashMap;
use std::sync::Arc;

/// Identifies one rendered frame by the content of its timeline segment.
#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq)]
pub struct FrameKey {
    pub segment_hash: u64,
    pub frame_index: u64,
}

/// Frame index of instant `t` at `fps`, rounded to the nearest frame and clamped to
/// `[0, frame_count - 1]`.
pub fn frame_index_for_time(t: f64, fps: f64, frame_count: u64) -> u64 {
    let last = frame_count.saturating_sub(1);
    if !t.is_finite() || t <= 0.0 || fps <= 0.0 {
        return 0;
    }
    ((t * fps).round() as u64).min(last)
}

struct CachedFrame {
    png: Arc<Vec<u8>>,
    last_used: u64,
}

/// Least-recently-used cache of encoded frames.
pub struct FrameCache {
    byte_budget: usize,
    bytes_used: usize,
    clock: u64,
    frames: HashMap<FrameKey, CachedFrame>,
}

impl FrameCache {
    pub fn new(byte_budget: usize) -> Self {
        FrameCache { byte_budget, bytes_used: 0, clock: 0, frames: HashMap::new() }
    }

    pub fn get(&mut self, key: FrameKey) -> Option<Arc<Vec<u8>>> {
        self.clock += 1;
        let clock = self.clock;
        self.frames.get_mut(&key).map(|f| {
            f.last_used = clock;
            f.png.clone()
        })
    }

    pub fn insert(&mut self, key: FrameKey, png: Arc<Vec<u8>>) {
        self.clock += 1;
        self.bytes_used += png.len();
        if let Some(old) = self.frames.insert(key, CachedFrame { png, last_used: self.clock }) {
            self.bytes_used -= old.png.len();
        }
        self.evict_to_budget(key);
    }

    /// Drops every frame whose segment no longer exists in the current scene.
    pub fn retain_segments(&mut self, live: &std::collections::HashSet<u64>) {
        self.frames.retain(|k, _| live.contains(&k.segment_hash));
        self.bytes_used = self.frames.values().map(|f| f.png.len()).sum();
    }

    pub fn len(&self) -> usize {
        self.frames.len()
    }

    pub fn is_empty(&self) -> bool {
        self.frames.is_empty()
    }

    pub fn bytes_used(&self) -> usize {
        self.bytes_used
    }

    /// Evicts least-recently-used frames until within budget, never evicting `keep`.
    fn evict_to_budget(&mut self, keep: FrameKey) {
        while self.bytes_used > self.byte_budget && self.frames.len() > 1 {
            let oldest = self
                .frames
                .iter()
                .filter(|(k, _)| **k != keep)
                .min_by_key(|(_, f)| f.last_used)
                .map(|(k, _)| *k);
            match oldest.and_then(|k| self.frames.remove(&k)) {
                Some(f) => self.bytes_used -= f.png.len(),
                None => break,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn key(v: u64, i: u64) -> FrameKey {
        FrameKey { segment_hash: v, frame_index: i }
    }

    fn png(n: usize) -> Arc<Vec<u8>> {
        Arc::new(vec![0u8; n])
    }

    #[test]
    fn time_rounds_to_nearest_frame_and_clamps() {
        assert_eq!(frame_index_for_time(0.0, 30.0, 90), 0);
        assert_eq!(frame_index_for_time(0.49 / 30.0, 30.0, 90), 0);
        assert_eq!(frame_index_for_time(0.51 / 30.0, 30.0, 90), 1);
        assert_eq!(frame_index_for_time(1.0, 30.0, 90), 30);
        assert_eq!(frame_index_for_time(100.0, 30.0, 90), 89);
        assert_eq!(frame_index_for_time(-1.0, 30.0, 90), 0);
        assert_eq!(frame_index_for_time(f64::NAN, 30.0, 90), 0);
    }

    #[test]
    fn nearby_times_share_a_cached_frame() {
        let mut cache = FrameCache::new(1 << 20);
        let i = frame_index_for_time(1.0, 30.0, 90);
        cache.insert(key(1, i), png(10));
        let j = frame_index_for_time(1.0 + 0.2 / 30.0, 30.0, 90);
        assert!(cache.get(key(1, j)).is_some());
    }

    #[test]
    fn hit_returns_same_bytes_and_other_version_misses() {
        let mut cache = FrameCache::new(1 << 20);
        let data = png(10);
        cache.insert(key(1, 5), data.clone());
        assert!(Arc::ptr_eq(&cache.get(key(1, 5)).unwrap(), &data));
        assert!(cache.get(key(2, 5)).is_none());
        assert!(cache.get(key(1, 6)).is_none());
    }

    #[test]
    fn evicts_least_recently_used_over_budget() {
        let mut cache = FrameCache::new(30);
        cache.insert(key(1, 0), png(10));
        cache.insert(key(1, 1), png(10));
        cache.insert(key(1, 2), png(10));
        cache.get(key(1, 0)); // frame 1 becomes the oldest
        cache.insert(key(1, 3), png(10));
        assert!(cache.get(key(1, 1)).is_none());
        assert!(cache.get(key(1, 0)).is_some());
        assert!(cache.get(key(1, 3)).is_some());
        assert_eq!(cache.bytes_used(), 30);
    }

    #[test]
    fn oversized_frame_is_kept_alone() {
        let mut cache = FrameCache::new(5);
        cache.insert(key(1, 0), png(3));
        cache.insert(key(1, 1), png(50));
        assert_eq!(cache.len(), 1);
        assert!(cache.get(key(1, 1)).is_some());
    }

    #[test]
    fn replacing_a_frame_keeps_byte_count_exact() {
        let mut cache = FrameCache::new(100);
        cache.insert(key(1, 0), png(10));
        cache.insert(key(1, 0), png(20));
        assert_eq!(cache.bytes_used(), 20);
        assert_eq!(cache.len(), 1);
    }

    #[test]
    fn retain_segments_drops_stale_frames() {
        let mut cache = FrameCache::new(1000);
        cache.insert(key(1, 0), png(10));
        cache.insert(key(2, 0), png(10));
        cache.retain_segments(&[2].into_iter().collect());
        assert_eq!(cache.len(), 1);
        assert_eq!(cache.bytes_used(), 10);
        assert!(cache.get(key(2, 0)).is_some());
    }
}
